# PDFragen

Not a developer? Start with the User Guide → [docs/USER_GUIDE.md](docs/USER_GUIDE.md)

A RAG (Retrieval-Augmented Generation) chatbot for international students in
Germany. Upload a German-language document — a Studienbüro or Ausländerbehörde
letter, lecture notes, whatever — ask questions about it in English or German,
and get answers grounded in the document with citations back to the source
pages.

> **Fragen** is German for "questions" — PDFragen = "PDF questions".

## Architecture

Fully local RAG pipeline — no paid API required.

```mermaid
flowchart TD
    A[German PDF upload] --> B[Chunking]
    B --> C[Embeddings<br/>multilingual sentence-transformers]
    C --> D[(ChromaDB<br/>local vector store)]
    E[Student question<br/>EN or DE] --> F[Retrieval]
    D --> F
    F --> G[Ollama<br/>llama3.1:8b, local]
    G --> H[Streamlit UI<br/>answer + citations]
```

## Who this is for

An international student in Germany opens a letter from the Ausländerbehörde.
It is two pages of legal German, it mentions a deadline, and getting it wrong
means losing the right to stay. Machine translation gives a wooden rendering of
the whole page; it does not answer "so what do I actually need to bring, and
by when?"

PDFragen is built for that moment. Upload the letter, ask the question in
whichever language is easier, and get a direct answer with the source passage
and page number shown underneath — so the answer can be checked against the
document rather than trusted blindly.

The same thing works for lecture notes, exam regulations, and enrollment
paperwork. Two sample documents ship in [`examples/`](examples/) if you want to
try it without uploading anything of your own.

**Everything runs locally and free** — local LLM via Ollama, local embeddings,
local vector store. No API keys, no per-query cost, and no document ever leaves
the machine. For paperwork containing passport numbers and financial details,
that last point is the design constraint, not a nice-to-have.

## Design notes

A few decisions a reviewer might reasonably ask about:

- **Why a multilingual embedding model?** Questions arrive in English, but the
  documents are German. `paraphrase-multilingual-MiniLM-L12-v2` maps both into
  one space, so an English question retrieves the relevant German passage
  without a translation step in between.
- **Why cite pages rather than just answer?** The user usually has to act on
  the document (submit a form, hit a deadline). An unverifiable answer is not
  much use, so every answer carries the passages it came from.
- **Why the repeated language instruction in the prompt?** The excerpts are
  German, and an 8B model tends to answer in the language of the *context*
  rather than the *question*. Restating the rule after the question fixed this
  in practice — see `_PROMPT_TEMPLATE` in [`rag.py`](src/pdfragen/rag.py).
- **Why hash-based chunk ids?** Re-uploading the same document overwrites its
  chunks instead of duplicating them, which would otherwise skew retrieval
  toward whatever had been ingested twice.
- **Why keep styling in its own module?** [`theme.py`](src/pdfragen/theme.py)
  holds the palette, type scale and CSS so `app.py` reads as layout and state
  rather than a wall of style strings — and so a visual change never risks
  touching the pipeline.

## Stack

| Concern      | Choice                                              |
| ------------ | ---------------------------------------------------- |
| RAG pipeline | LangChain                                            |
| Vector store | ChromaDB (local, persisted)                          |
| Embeddings   | `paraphrase-multilingual-MiniLM-L12-v2` (local)      |
| Generation   | Ollama, `llama3.1:8b` (local, configurable)          |
| UI           | Streamlit                                            |
| Config       | python-dotenv                                        |

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install .   # installs the pdfragen package and its dependencies
cp .env.example .env   # defaults work for a local Ollama install

# Ollama must be running with the model pulled:
ollama pull llama3.1:8b
```

Requires Python 3.11+ and [Ollama](https://ollama.com) installed locally.

## Usage

Make sure Ollama is running (`ollama serve`), then launch the app:

```bash
streamlit run app.py
```

Drop a PDF on the landing screen, wait for indexing, and ask away.

Every answer is followed by citation pills — one per cited page, badged `p. 2`
for an English answer and `S. 2` for a German one — and an expander holding the
passages those pages were drawn from, so any claim can be checked against the
document. Each message carries an EN/DE chip showing the language it was
handled in. The sidebar's language control forces answers into English or
German; on *Auto* the answer matches the question.

Each uploaded document is indexed into its own collection, scoped to the
browser session — re-uploading the same file reuses the existing index instead
of re-embedding it.

### Try it with the sample documents

Two synthetic German documents are included, so reviewers can see the thing work
without supplying paperwork of their own:

| File | What it is | Questions worth asking |
| ---- | ---------- | ---------------------- |
| [`auslaenderbehoerde_verlaengerung.pdf`](examples/auslaenderbehoerde_verlaengerung.pdf) | A residence-permit extension letter | "What documents do I need to bring?" · "How many days a year may I work?" · "Wann ist die Frist?" |
| [`vorlesung_maschinelles_lernen.pdf`](examples/vorlesung_maschinelles_lernen.pdf) | Lecture notes on regularization | "What is the difference between L1 and L2?" · "When is the exercise sheet due?" |

Both are generated by [`examples/make_samples.py`](examples/make_samples.py) and
contain no real personal data.

### CLI

The pipeline stages are also runnable standalone, useful for inspecting
behaviour without the UI:

```bash
python -m pdfragen.ingestion path/to/dokument.pdf    # chunk stats
python -m pdfragen.vectorstore path/to/dokument.pdf  # chunk + embed + store
python -m pdfragen.rag "Wie lange habe ich Zeit?"    # retrieve + answer
```

## Evaluation

An evaluation harness for the research questions behind *Cross-Lingual RAG on
German Administrative Documents with Small Local Models*:

- **RQ1 (retrieval):** is retrieval worse for English questions than for
  German ones over German documents? It compares
  `paraphrase-multilingual-MiniLM-L12-v2`, `intfloat/multilingual-e5-base` and
  `BAAI/bge-m3`, plus a baseline that translates the English question to
  German with the local LLM first. Reports Recall@1/3/5 and MRR.
- **RQ2 (answer language):** how often do local Ollama models answer in the
  context's language (German) instead of the question's? It compares three prompt
  variants: `plain` (no language instruction), `once` (rule in the system
  prompt) and `repeated` (rule plus a reminder after the question, which is the app's default).

### Setup

```bash
pip install -e ".[eval,dev]"          # adds pyyaml + lingua-language-detector
ollama pull llama3.1:8b                # RQ2 and the translation baseline
ollama pull mistral-nemo:12b           # RQ2
```

Embedding models download from Hugging Face on first use (bge-m3 is about 2.3 GB).
Everything runs locally; the full grids fit comfortably in 24 GB of RAM.

### Run

```bash
# RQ1: no Ollama needed
python eval/run_retrieval.py --config eval/configs/retrieval.yaml
# RQ1 with the EN->DE translation baseline (needs Ollama)
python eval/run_retrieval.py --config eval/configs/retrieval.yaml --translate
# RQ1 under the app's own chunking / per-document index
python eval/run_retrieval.py --config eval/configs/retrieval_app_defaults.yaml

# RQ2: needs Ollama with the configured models pulled
python eval/run_generation.py --config eval/configs/generation.yaml
python eval/run_generation.py --models llama3.1:8b --limit 3   # quick smoke test
```

Each run writes to `eval/results/<timestamp>-<name>/`:

| File | Contents |
| --- | --- |
| `config.yaml` | the exact experiment config used |
| `meta.json` | git commit (and dirty flag), Python/package versions, platform, command |
| `per_query.csv` | one row per query (RQ1: gold page/chunk ranks; RQ2: full answer text, detected language, review flag, empty `faithful`/`notes` columns for hand-checking) |
| `summary.csv` / `summary.md` | aggregate table with 95% CIs (bootstrap for RQ1, Wilson for RQ2) |
| `paired_deltas.csv` | RQ1 only: paired MRR differences (EN − DE, translated − EN) |
| `answers.jsonl` | RQ2 only: same rows as `per_query.csv`, easier to read |

`eval/results/` is gitignored; `git add -f` the runs a paper table is built from.

### Benchmark format

`eval/benchmark/*.jsonl` has one question per line:

```json
{"id": "abh-02", "doc_file": "auslaenderbehoerde_verlaengerung.pdf", "gold_page": 1,
 "question_en": "What is the latest date by which I have to apply for the extension?",
 "question_de": "Bis wann muss ich die Verlängerung spätestens beantragen?",
 "reference_answer": "By 5 September 2026, i.e. eight weeks before the permit expires.",
 "gold_evidence": "bis zum 5. September 2026"}
```

`gold_page` is 1-indexed, as shown in a PDF viewer. `gold_evidence` is optional:
a verbatim German span from the gold page that enables **chunk-level**
scoring, where a hit is a retrieved chunk containing the span. `tests/test_benchmark.py`
checks every span against the real PDF text. The seed set has 26 questions over the
two sample PDFs.

### Methodological notes

- **The seed corpus is too small to separate embedders.** Each sample PDF has
  2 pages, so page-level Recall@3 saturates and random Recall@1 is 0.25 even
  on the pooled 4-page index. The main config therefore pools both documents
  and uses 300-character chunks, and chunk-level scores are the more informative
  numbers. Firm conclusions need more and longer real documents, added as
  further JSONL files and PDFs.
- **Detecting answer language is harder than it looks.** English answers quote German
  terms, and lingua treats a single umlaut as decisive. The detector drops
  quoted/parenthesised spans, transliterates umlauts, and cross-checks with an
  EN/DE function-word vote. Disagreements are flagged `needs_review`.
- **RQ2 holds context fixed.** Retrieval runs once per question and
  language, so every model and prompt variant answers from identical excerpts.
  Decoding is greedy (temperature 0, fixed seed).
- **Question authoring bias.** German questions were paraphrased to avoid
  copying document wording, but some lexical overlap remains and favours the DE
  condition. English questions sometimes share loanwords with the documents
  (e.g. *early stopping*).

## Project structure

```
PDFragen/
├── app.py               # Streamlit chat UI
├── src/pdfragen/        # library code
│   ├── config.py        # env-driven configuration
│   ├── ingestion.py     # PDF loading + German-aware chunking
│   ├── vectorstore.py   # embeddings + persistent ChromaDB
│   ├── rag.py           # retrieval + Ollama generation
│   ├── theme.py         # design tokens + injected CSS for the UI
│   └── evaluation/      # benchmark loading, metrics, language detection, run I/O
├── .streamlit/          # native Streamlit theming
├── eval/                # evaluation harness (see "Evaluation")
│   ├── benchmark/       # JSONL questions with gold pages / evidence
│   ├── configs/         # experiment grids (YAML)
│   ├── run_retrieval.py # RQ1
│   └── run_generation.py # RQ2
├── tests/               # unit tests
├── examples/            # sample + attack PDFs, their generators, security check scripts
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## Security

Uploaded PDFs are untrusted input. [SECURITY_ASSESSMENT.md](SECURITY_ASSESSMENT.md)
tests the app against the OWASP Top 10 for LLM Applications (2025) with
crafted German PDFs: indirect prompt injection via hidden text, HTML injection
through rendered passages and file names, data isolation between documents and
sessions, and upload path traversal. It reports observed success rates before
and after the fixes, the regression tests in `tests/test_security.py`, the
fixes' effect on answer language, and the risks that remain — prompt-injection
defences reduce the risk, they don't remove it.

## Limitations

Worth being explicit about, since they shape what this does and doesn't do:

- **Scanned PDFs are not supported.** Text is extracted, not OCR'd; an
  image-only PDF is rejected with a clear message rather than silently
  returning nothing.
- **Answer quality is bounded by an 8B local model.** The tradeoff is
  deliberate — privacy and zero cost over raw quality — but a larger model via
  `LLM_MODEL` noticeably improves multi-step questions.
- **No conversational memory.** Each question is retrieved and answered
  independently; follow-ups like "and what about the other one?" won't resolve.
- **One document at a time.** Uploading a new PDF replaces the indexed one
  rather than adding to it; questions can't span two documents.
- **It runs where Ollama runs.** That rules out zero-config hosts like
  Streamlit Community Cloud — the model is several GB and needs a local
  daemon. Demoing it means running it locally or recording it.
- **Chunking is character-based.** It respects paragraph and sentence
  boundaries, but a table split across a chunk boundary can still lose context.
- **This is not legal advice.** It helps read a document; it does not tell
  anyone what to do about it.

## License

MIT
