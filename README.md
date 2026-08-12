# PDFragen

A RAG (Retrieval-Augmented Generation) chatbot for international students in
Germany. Upload a German-language document — a Studienbüro or Ausländerbehörde
letter, lecture notes, whatever — ask questions about it in English or German,
and get answers grounded in the document with citations back to the source
pages.

> **Fragen** is German for "questions" — PDFragen = "PDF questions".

## Why

International students in Germany deal with a steady stream of official and
academic German they didn't sign up to parse: enrollment letters, visa/residence
paperwork, lecture slides. PDFragen lets you upload one of those documents and
just ask it what it means, in whichever language is easier for you — grounded
in the actual text, with page citations, not a generic translation.

Runs 100% locally and free: local LLM (Ollama), local embeddings, local vector
store. No API keys, no per-query cost.

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
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # defaults work for a local Ollama install

# Ollama must be running with the model pulled:
ollama pull llama3.1:8b
```

Requires Python 3.11+ and [Ollama](https://ollama.com) installed locally.

## Usage

_(Milestones land incrementally — see commit history.)_

- CLI ingestion / retrieval — _coming next_
- Streamlit app — _coming later_

## Project structure

```
PDFragen/
├── src/pdfragen/      # library code
│   └── config.py      # env-driven configuration
├── tests/             # unit tests
├── examples/          # sample PDF for reviewers to try
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## Architecture

_(Diagram added in the docs milestone.)_

## License

MIT
