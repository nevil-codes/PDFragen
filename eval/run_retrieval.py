"""RQ1: is retrieval worse for English questions over German documents?

For every embedder in the config, indexes the benchmark documents, then
retrieves for each question in German, in English, and (optionally) in English
machine-translated to German by the local LLM. Scores the rank of the gold
page and, where a ``gold_evidence`` span is annotated, of the gold chunk.

Runs without Ollama unless the translation baseline is enabled:

    python eval/run_retrieval.py --config eval/configs/retrieval.yaml
    python eval/run_retrieval.py --config eval/configs/retrieval.yaml --translate
"""

from __future__ import annotations

import argparse
import dataclasses
import gc
import re
import sys
import tempfile
import time
from pathlib import Path

from langchain_core.documents import Document

from pdfragen.config import Config, get_config
from pdfragen.evaluation.benchmark import BenchmarkItem, load_benchmark, normalize_text
from pdfragen.evaluation.metrics import (
    bootstrap_ci,
    dedupe_ranked,
    first_hit_rank,
    hit_at_k,
    paired_bootstrap_diff,
    reciprocal_rank,
)
from pdfragen.evaluation.runs import (
    expand_globs,
    fmt_ci,
    load_config,
    make_run_dir,
    markdown_table,
    resolve,
    write_csv,
    write_run_header,
)
from pdfragen.evaluation.translate import build_translator, translate_to_german
from pdfragen.ingestion import chunk_documents, load_pdf
from pdfragen.rag import check_ollama, retrieve
from pdfragen.vectorstore import add_chunks, get_vectorstore

TRANSLATED = "en_translated"


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def load_corpus(items: list[BenchmarkItem], docs_dir: Path, cfg: Config) -> dict[str, list[Document]]:
    """Chunk every benchmark document once; chunking is embedder-independent."""
    corpus = {}
    for doc_file in sorted({item.doc_file for item in items}):
        chunks = chunk_documents(load_pdf(docs_dir / doc_file), cfg)
        for chunk in chunks:
            chunk.metadata["doc_file"] = doc_file
        corpus[doc_file] = chunks
    return corpus


def evidence_in(chunk: Document, item: BenchmarkItem) -> bool:
    return chunk.metadata["doc_file"] == item.doc_file and normalize_text(
        item.gold_evidence
    ) in normalize_text(chunk.page_content)


def translate_questions(items: list[BenchmarkItem], tcfg: dict, base_url: str) -> dict[str, str]:
    """Translate every English question once (shared across embedders)."""
    probe = check_ollama(dataclasses.replace(get_config(), llm_model=tcfg["model"]))
    if probe:
        sys.exit(f"Translation baseline needs Ollama: {probe}")
    llm = build_translator(tcfg["model"], base_url, tcfg.get("temperature", 0.0), tcfg.get("seed", 42))
    translations = {}
    for i, item in enumerate(items, 1):
        translations[item.id] = translate_to_german(item.question_en, llm)
        print(f"  translate [{i}/{len(items)}] {item.question_en!r} -> {translations[item.id]!r}")
    return translations


def score_query(
    item: BenchmarkItem, results: list[Document], evidence_coverable: bool
) -> dict:
    """Ranks of the gold page and gold chunk within one retrieved list."""
    pages = dedupe_ranked([(d.metadata["doc_file"], d.metadata["page"]) for d in results])
    gold_key = (item.doc_file, item.gold_page - 1)
    page_rank = first_hit_rank([key == gold_key for key in pages])
    chunk_rank = (
        first_hit_rank([evidence_in(d, item) for d in results]) if evidence_coverable else None
    )
    return {
        "page_rank": page_rank,
        "chunk_rank": chunk_rank,
        "top_pages": " ".join(f"{doc.split('.')[0]}:p{page + 1}" for doc, page in pages[:5]),
    }


def run_embedder(
    embedder: str,
    base_cfg: Config,
    corpus: dict[str, list[Document]],
    items: list[BenchmarkItem],
    queries: dict[str, dict[str, str]],
    coverable: dict[str, bool],
    exp: dict,
) -> list[dict]:
    rows = []
    with tempfile.TemporaryDirectory(prefix="pdfragen-eval-") as tmp:
        cfg = dataclasses.replace(base_cfg, embedding_model=embedder, chroma_dir=tmp)
        # One index over all documents ("pooled"), or one per document.
        if exp["corpus"] == "pooled":
            groups = {None: [c for chunks in corpus.values() for c in chunks]}
        else:
            groups = {doc: chunks for doc, chunks in corpus.items()}

        stores = {}
        embeddings = None
        t0 = time.perf_counter()
        for key, chunks in groups.items():
            gcfg = dataclasses.replace(cfg, collection_name=f"eval-{_slug(str(key))}")
            store = get_vectorstore(gcfg, embeddings)
            embeddings = store.embeddings  # load the model once per embedder
            add_chunks(chunks, gcfg, store)
            stores[key] = (store, len(chunks))
        index_s = time.perf_counter() - t0
        print(f"  indexed {sum(n for _, n in stores.values())} chunks in {index_s:.1f}s")

        for item in items:
            store, n_chunks = stores[None if exp["corpus"] == "pooled" else item.doc_file]
            depth = min(exp["top_n"], n_chunks)
            qcfg = dataclasses.replace(cfg, top_k=depth)
            for condition, query in queries[item.id].items():
                results = retrieve(query, qcfg, store)
                rows.append(
                    {
                        "embedder": embedder,
                        "condition": condition,
                        "id": item.id,
                        "doc_file": item.doc_file,
                        "gold_page": item.gold_page,
                        "query": query,
                        **score_query(item, results, coverable[item.id]),
                    }
                )
        del stores, embeddings
    _free_memory()
    return rows


def _free_memory() -> None:
    gc.collect()
    try:
        import torch

        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def summarize(rows: list[dict], exp: dict) -> list[dict]:
    """Aggregate per (embedder, condition, level) with bootstrap CIs."""
    boot = exp.get("bootstrap", {})
    summary = []
    for embedder in exp["embedders"]:
        for condition in exp["conditions"]:
            for level in ("page", "chunk"):
                ranks = [
                    r[f"{level}_rank"]
                    for r in rows
                    if r["embedder"] == embedder
                    and r["condition"] == condition
                    and (level == "page" or r["evidence_coverable"])
                ]
                if not ranks:
                    continue
                out = {"embedder": embedder, "condition": condition, "level": level, "n": len(ranks)}
                for k in exp["ks"]:
                    vals = [hit_at_k(r, k) for r in ranks]
                    mean = sum(vals) / len(vals)
                    out[f"R@{k}"] = round(mean, 4)
                    out[f"R@{k}_lo"], out[f"R@{k}_hi"] = bootstrap_ci(vals, **boot)
                vals = [reciprocal_rank(r) for r in ranks]
                out["MRR"] = round(sum(vals) / len(vals), 4)
                out["MRR_lo"], out["MRR_hi"] = bootstrap_ci(vals, **boot)
                summary.append(out)
    return summary


def paired_deltas(rows: list[dict], exp: dict) -> list[dict]:
    """Paired MRR differences between conditions, per embedder and level."""
    boot = exp.get("bootstrap", {})
    pairs = [("en", "de")]
    if TRANSLATED in exp["conditions"]:
        pairs += [(TRANSLATED, "en"), (TRANSLATED, "de")]
    out = []
    for embedder in exp["embedders"]:
        for level in ("page", "chunk"):
            by_cond: dict[str, dict[str, float]] = {}
            for r in rows:
                if r["embedder"] != embedder or (level == "chunk" and not r["evidence_coverable"]):
                    continue
                by_cond.setdefault(r["condition"], {})[r["id"]] = reciprocal_rank(r[f"{level}_rank"])
            for a, b in pairs:
                if a not in by_cond or b not in by_cond:
                    continue
                ids = sorted(by_cond[a].keys() & by_cond[b].keys())
                mean, low, high = paired_bootstrap_diff(
                    [by_cond[a][i] for i in ids], [by_cond[b][i] for i in ids], **boot
                )
                out.append(
                    {
                        "embedder": embedder,
                        "level": level,
                        "comparison": f"MRR({a}) - MRR({b})",
                        "n": len(ids),
                        "delta": fmt_ci(mean, low, high),
                    }
                )
    return out


def write_summary_md(path: Path, summary: list[dict], deltas: list[dict], exp: dict, context: dict) -> None:
    ks = exp["ks"]
    display = [
        {
            "embedder": s["embedder"],
            "query": s["condition"],
            "n": s["n"],
            **{f"R@{k}": fmt_ci(s[f"R@{k}"], s[f"R@{k}_lo"], s[f"R@{k}_hi"]) for k in ks},
            "MRR": fmt_ci(s["MRR"], s["MRR_lo"], s["MRR_hi"]),
        }
        for s in summary
    ]
    lines = [
        f"# Retrieval results: {exp['name']}\n",
        f"- Corpus: **{exp['corpus']}**, chunk size {exp['chunk_size']} "
        f"(overlap {exp['chunk_overlap']}), retrieval depth {exp['top_n']}",
        f"- Questions: {context['n_items']}; documents: {context['n_docs']}; "
        f"pages in largest index: {context['max_pages']}; chunks: {context['n_chunks']}",
        f"- Random-ranking page-level Recall@1 baseline: "
        f"~{1 / context['max_pages']:.2f}" + (" (per-document index)" if exp["corpus"] != "pooled" else ""),
        f"- Chunk-level scoring covers {context['n_coverable']}/{context['n_items']} questions "
        f"(those whose gold_evidence lies wholly inside one chunk).",
        "- Values: mean [95% bootstrap CI over questions].\n",
    ]
    for level in ("page", "chunk"):
        rows = [d for d, s in zip(display, summary) if s["level"] == level]
        lines += [f"## {level.capitalize()}-level\n", markdown_table(rows)]
    lines += ["## Paired differences (MRR)\n", markdown_table(deltas)]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="eval/configs/retrieval.yaml")
    parser.add_argument("--translate", action="store_true", help="enable the EN->DE translation baseline (needs Ollama)")
    parser.add_argument("--limit", type=int, help="only use the first N questions (smoke tests)")
    args = parser.parse_args(argv)

    exp = load_config(resolve(args.config))
    tcfg = exp.get("translate", {})
    if args.translate:
        tcfg["enabled"] = True
        exp["translate"] = tcfg
    conditions = list(exp.get("conditions", ["de", "en"]))
    if tcfg.get("enabled") and TRANSLATED not in conditions:
        conditions.append(TRANSLATED)
    exp["conditions"] = conditions

    items = load_benchmark(expand_globs(exp["benchmark"]))
    base_cfg = dataclasses.replace(
        get_config(), chunk_size=exp["chunk_size"], chunk_overlap=exp["chunk_overlap"]
    )
    # Index every benchmark document even under --limit, so the pooled corpus
    # keeps its distractors.
    corpus = load_corpus(items, resolve(exp["docs_dir"]), base_cfg)
    if args.limit:
        items = items[: args.limit]
    all_chunks = [c for chunks in corpus.values() for c in chunks]
    coverable = {
        item.id: bool(item.gold_evidence) and any(evidence_in(c, item) for c in all_chunks)
        for item in items
    }
    for item in items:
        if item.gold_evidence and not coverable[item.id]:
            print(f"warning: {item.id} gold_evidence spans a chunk boundary; excluded from chunk-level scores")

    run_dir = make_run_dir(exp["name"])
    print(f"Run directory: {run_dir}")

    queries = {item.id: {"de": item.question_de, "en": item.question_en} for item in items}
    if tcfg.get("enabled"):
        print(f"Translating {len(items)} questions with {tcfg['model']} ...")
        for item_id, text in translate_questions(items, tcfg, base_cfg.ollama_base_url).items():
            queries[item_id][TRANSLATED] = text
    for q in queries.values():
        for condition in list(q):
            if condition not in conditions:
                del q[condition]

    rows: list[dict] = []
    for embedder in exp["embedders"]:
        print(f"Embedder: {embedder}")
        for row in run_embedder(embedder, base_cfg, corpus, items, queries, coverable, exp):
            row["evidence_coverable"] = coverable[row["id"]]
            rows.append(row)

    pages_per_doc = {doc: len({c.metadata["page"] for c in chunks}) for doc, chunks in corpus.items()}
    context = {
        "n_items": len(items),
        "n_docs": len(corpus),
        "n_chunks": len(all_chunks),
        "n_coverable": sum(coverable.values()),
        "max_pages": sum(pages_per_doc.values()) if exp["corpus"] == "pooled" else max(pages_per_doc.values()),
    }
    summary = summarize(rows, exp)
    deltas = paired_deltas(rows, exp)

    write_run_header(run_dir, exp, {"context": context})
    write_csv(run_dir / "per_query.csv", rows)
    write_csv(run_dir / "summary.csv", summary)
    write_csv(run_dir / "paired_deltas.csv", deltas)
    write_summary_md(run_dir / "summary.md", summary, deltas, exp, context)
    print((run_dir / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
