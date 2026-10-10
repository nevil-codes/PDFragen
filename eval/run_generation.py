"""RQ2: do local models answer in the context's language instead of the question's?

For every model x prompt variant x question language, answers each benchmark
question from the same retrieved German context and detects the answer's
language. Every answer is logged verbatim (per_query.csv / answers.jsonl) with
empty ``faithful``/``notes`` columns for later hand-checking.

Needs a running Ollama with the configured models pulled:

    python eval/run_generation.py --config eval/configs/generation.yaml
    python eval/run_generation.py --models llama3.1:8b --limit 3   # smoke test
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

from langchain_core.documents import Document
from langchain_ollama import ChatOllama

from pdfragen.config import get_config
from pdfragen.evaluation.benchmark import LANGUAGES, load_benchmark
from pdfragen.evaluation.language import detect_language
from pdfragen.evaluation.metrics import wilson_ci
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
from pdfragen.ingestion import chunk_documents, load_pdf
from pdfragen.rag import PROMPT_VARIANTS, check_ollama, generate, retrieve
from pdfragen.vectorstore import add_chunks, get_vectorstore

_FIELDS = [
    "model", "prompt_variant", "question_lang", "id", "doc_file", "gold_page",
    "question", "answer", "answer_lang", "lang_confidence", "de_share",
    "function_word_lang", "needs_review", "matches_question_lang",
    "retrieved_pages", "gold_page_retrieved", "latency_s", "reference_answer",
    "faithful", "notes",
]  # fmt: skip


def retrieve_contexts(items, exp: dict, cfg, tmp: str) -> dict[tuple[str, str], list[Document]]:
    """Retrieve once per (question, language); reused for every model/prompt.

    Mirrors the app: one index per document, the app's chunking and top-k.
    """
    rcfg = dataclasses.replace(
        cfg,
        embedding_model=exp["embedder"],
        chunk_size=exp["chunk_size"],
        chunk_overlap=exp["chunk_overlap"],
        top_k=exp["top_k"],
        chroma_dir=tmp,
    )
    stores, embeddings = {}, None
    for i, doc_file in enumerate(sorted({it.doc_file for it in items})):
        dcfg = dataclasses.replace(rcfg, collection_name=f"gen-{i}")
        store = get_vectorstore(dcfg, embeddings)
        embeddings = store.embeddings
        add_chunks(chunk_documents(load_pdf(resolve(exp["docs_dir"]) / doc_file), dcfg), dcfg, store)
        stores[doc_file] = store
    return {
        (item.id, lang): retrieve(item.question(lang), rcfg, stores[item.doc_file])
        for item in items
        for lang in exp["question_languages"]
    }


def summarize(rows: list[dict], exp: dict) -> list[dict]:
    """Answer-language rates per (model, prompt variant, question language)."""
    summary = []
    for model in exp["models"]:
        for variant in exp["prompt_variants"]:
            for lang in exp["question_languages"]:
                cell = [
                    r for r in rows
                    if r["model"] == model and r["prompt_variant"] == variant and r["question_lang"] == lang
                ]  # fmt: skip
                if not cell:
                    continue
                n = len(cell)
                match = sum(r["matches_question_lang"] for r in cell)
                german = sum(r["answer_lang"] == "de" for r in cell)
                summary.append(
                    {
                        "model": model,
                        "prompt_variant": variant,
                        "question_lang": lang,
                        "n": n,
                        "match_rate": round(match / n, 4),
                        "match_lo": round(wilson_ci(match, n)[0], 4),
                        "match_hi": round(wilson_ci(match, n)[1], 4),
                        "de_answer_rate": round(german / n, 4),
                        "de_lo": round(wilson_ci(german, n)[0], 4),
                        "de_hi": round(wilson_ci(german, n)[1], 4),
                        "mean_de_share": round(sum(r["de_share"] for r in cell) / n, 4),
                        "needs_review": sum(r["needs_review"] for r in cell),
                        "mean_latency_s": round(sum(r["latency_s"] for r in cell) / n, 2),
                    }
                )
    return summary


def write_summary_md(path: Path, summary: list[dict], exp: dict, n_items: int) -> None:
    def table(lang: str) -> str:
        return markdown_table(
            [
                {
                    "model": s["model"],
                    "prompt": s["prompt_variant"],
                    "n": s["n"],
                    "answers in question language": fmt_ci(s["match_rate"], s["match_lo"], s["match_hi"]),
                    "answers in German": fmt_ci(s["de_answer_rate"], s["de_lo"], s["de_hi"]),
                    "mean German share": f"{s['mean_de_share']:.2f}",
                    "needs review": s["needs_review"],
                    "latency (s)": s["mean_latency_s"],
                }
                for s in summary
                if s["question_lang"] == lang
            ]
        )

    lines = [
        f"# Answer-language results: {exp['name']}\n",
        f"- Questions: {n_items}; context: top-{exp['top_k']} chunks from {exp['embedder']} "
        f"(chunk size {exp['chunk_size']}, per-document index, same context for every model/prompt)",
        f"- Decoding: temperature {exp['temperature']}, seed {exp['seed']}, "
        f"num_ctx {exp['num_ctx']}, num_predict {exp['num_predict']}",
        "- Prompt variants: plain = no language instruction; once = language rule in "
        "the system prompt; repeated = rule in system prompt + reminder after the question (app default)",
        "- Rates: proportion [95% Wilson CI]. `needs review` = detectors disagree or low "
        "confidence; check those rows in per_query.csv by hand.\n",
    ]
    if "en" in exp["question_languages"]:
        lines += ["## English questions (German context) — main RQ2 condition\n", table("en")]
    if "de" in exp["question_languages"]:
        lines += ["## German questions — control\n", table("de")]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="eval/configs/generation.yaml")
    parser.add_argument("--models", nargs="+", help="override the config's model list")
    parser.add_argument("--limit", type=int, help="only use the first N questions (smoke tests)")
    parser.add_argument("--skip-missing", action="store_true", help="skip models not pulled in Ollama instead of aborting")
    args = parser.parse_args(argv)

    exp = load_config(resolve(args.config))
    if args.models:
        exp["models"] = args.models
    unknown = set(exp["prompt_variants"]) - PROMPT_VARIANTS.keys()
    if unknown or not set(exp["question_languages"]) <= set(LANGUAGES):
        sys.exit(f"Bad config: unknown prompt variants {unknown or ''} / languages {exp['question_languages']}")

    base_cfg = get_config()
    available = []
    for model in exp["models"]:
        problem = check_ollama(dataclasses.replace(base_cfg, llm_model=model))
        if problem and not args.skip_missing:
            sys.exit(problem)
        if problem:
            print(f"skipping {model}: {problem}")
        else:
            available.append(model)
    exp["models"] = available
    if not available:
        sys.exit("No models available.")

    items = load_benchmark(expand_globs(exp["benchmark"]))
    if args.limit:
        items = items[: args.limit]

    run_dir = make_run_dir(exp["name"])
    write_run_header(run_dir, exp)
    print(f"Run directory: {run_dir}")

    with tempfile.TemporaryDirectory(prefix="pdfragen-eval-") as tmp:
        contexts = retrieve_contexts(items, exp, base_cfg, tmp)

    total = len(exp["models"]) * len(exp["prompt_variants"]) * len(items) * len(exp["question_languages"])
    rows: list[dict] = []
    done = 0
    # Rows are appended and flushed as they come, so an interrupted run keeps
    # everything generated so far.
    with (
        open(run_dir / "per_query.csv", "w", encoding="utf-8", newline="") as csv_file,
        open(run_dir / "answers.jsonl", "w", encoding="utf-8") as jsonl_file,
    ):
        writer = csv.DictWriter(csv_file, fieldnames=_FIELDS)
        writer.writeheader()
        for model in exp["models"]:
            mcfg = dataclasses.replace(base_cfg, llm_model=model)
            llm = ChatOllama(
                model=model,
                base_url=base_cfg.ollama_base_url,
                temperature=exp["temperature"],
                seed=exp["seed"],
                num_ctx=exp["num_ctx"],
                num_predict=exp["num_predict"],
            )
            for variant in exp["prompt_variants"]:
                for item in items:
                    for lang in exp["question_languages"]:
                        chunks = contexts[(item.id, lang)]
                        t0 = time.perf_counter()
                        result = generate(item.question(lang), chunks, mcfg, llm=llm, prompt_variant=variant)
                        latency = time.perf_counter() - t0
                        detected = detect_language(result.text)
                        pages = [c.metadata.get("page", -1) + 1 for c in chunks]
                        row = {
                            "model": model,
                            "prompt_variant": variant,
                            "question_lang": lang,
                            "id": item.id,
                            "doc_file": item.doc_file,
                            "gold_page": item.gold_page,
                            "question": item.question(lang),
                            "answer": result.text,
                            "answer_lang": detected.label,
                            "lang_confidence": detected.confidence,
                            "de_share": detected.de_share,
                            "function_word_lang": detected.function_word_label,
                            "needs_review": detected.needs_review,
                            "matches_question_lang": detected.label == lang,
                            "retrieved_pages": " ".join(map(str, pages)),
                            "gold_page_retrieved": item.gold_page in pages,
                            "latency_s": round(latency, 2),
                            "reference_answer": item.reference_answer,
                            "faithful": "",
                            "notes": "",
                        }
                        rows.append(row)
                        writer.writerow(row)
                        csv_file.flush()
                        jsonl_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                        jsonl_file.flush()
                        done += 1
                        print(
                            f"[{done}/{total}] {model} {variant:8} {lang} {item.id}: "
                            f"{detected.label}{'?' if detected.needs_review else ''} ({latency:.1f}s)"
                        )

    summary = summarize(rows, exp)
    write_csv(run_dir / "summary.csv", summary)
    write_summary_md(run_dir / "summary.md", summary, exp, len(items))
    print((run_dir / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
