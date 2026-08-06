# PDFragen

A German-language RAG (Retrieval-Augmented Generation) chatbot. Upload a PDF,
ask questions about it in German, and get answers grounded in the document with
references to the source passages.

> **Fragen** is German for "questions" — PDFragen = "PDF questions".

## Why

Most RAG demos are English-only. PDFragen targets German documents end to end:
a multilingual embedding model, chunking tuned for German prose, and answers
generated in German with citations back to the source pages.

## Stack

| Concern      | Choice                                   |
| ------------ | ---------------------------------------- |
| RAG pipeline | LangChain                                |
| Vector store | ChromaDB (local, persisted)              |
| Embeddings   | `intfloat/multilingual-e5-base` (local)  |
| Generation   | OpenAI (`gpt-4o-mini`, configurable)     |
| UI           | Streamlit                                |
| Config       | python-dotenv                            |

**Why local embeddings?** No API key needed to index documents, works offline,
and multilingual-e5 is strong on German. The paid LLM is used only for the final
answer generation, where quality matters most.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OPENAI_API_KEY
```

Requires Python 3.11+.

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
