# Product Handbook Assistant

A Python application that answers questions using the official Original Prusa MK4S / MK3.9S handbook. It combines local document retrieval with a hosted language model and links answers to the relevant PDF pages.

The application runs locally, either in Python or Docker. Answer generation uses the Groq API and requires an internet connection. Search runs locally after the manual and embedding model have been downloaded and cached.

## Features

- Official PDF download with a pinned SHA-256 checksum.
- Page-aware chunking and CPU-based embeddings.
- Cosine-similarity search over a NumPy vector index.
- Search-only mode without an LLM API key.
- Structured answers with validated citation IDs and source-page links.
- Request timings, token usage, health and readiness endpoints.
- Automated tests and a GitHub Actions workflow for Windows, Linux and container checks.

## Architecture

The indexing pipeline extracts text from the PDF, splits each page into overlapping chunks, and stores embeddings alongside the text and page metadata. For each question, the application retrieves relevant chunks and includes them in the language model's context. The model is not trained or fine-tuned on the handbook.

| Component | Implementation |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic, Uvicorn |
| PDF extraction | pypdf |
| Embeddings | BAAI/bge-small-en-v1.5 through FastEmbed/ONNX, 384 dimensions |
| Retrieval | Normalized vectors and NumPy dot products |
| Generation | Groq-hosted model, configured with `LLM_MODEL` |
| Interface | HTML, CSS and JavaScript |
| Packaging | Docker and Docker Compose |
| CI | GitHub Actions: Ruff, pytest and container health check |

For this corpus, an in-process vector matrix avoids a separate database service. A larger corpus or concurrent index updates would require revisiting that choice.

## Local setup

See [Windows setup](START_HERE_WINDOWS.md) for environment creation, configuration and indexing. A Groq API key belongs in a local `.env` file; `.env.example` contains the setting names.

After setup, with Docker Desktop running, `.env` configured and the index available in `data/`:

```powershell
docker compose up -d --build
```

Open http://127.0.0.1:8000. API documentation is available at http://127.0.0.1:8000/docs.

```powershell
docker compose logs --tail 50 handbook
docker compose down
```

Compose mounts the local `data/` directory. The image does not contain the manual, index or API key. The first container startup may need to download an embedding-model cache compatible with its environment.

## Documentation

- [Architecture and request flow](docs/ARCHITECTURE.md)
- [File layout](docs/FILE_MAP.md)
- [Example queries and troubleshooting scenarios](docs/DEMO.md)
- [Citation validation](docs/CITATION_FIX.md)
- [Validation scope and results](docs/VALIDATION.md)
- [Optional extensions](docs/STAGES.md)
- [Technical references](docs/REFERENCES.md)

## Source

Prusa Research, *Original Prusa MK4S / MK3.9S 3D Printing Handbook*, version 1.01, 26 September 2024.

- [Official PDF](https://www.prusa3d.com/downloads/manual/prusa3d_manual_mk4s_mk39s_101_en.pdf)
- [Product support](https://help.prusa3d.com/product/mk4s)
- Source metadata and checksum: `sources/prusa-mk4s.json`

The manual is downloaded from the publisher and is not included in the repository. Public availability does not grant redistribution rights. This project is independent of Prusa Research.

## Limitations

The application supports one English manual and independent questions. It extracts text without OCR or interpretation of diagrams. Citation validation checks that source IDs belong to the retrieved context; it does not prove factual support or completeness.

Automated tests mock external inference. The retrieval evaluation uses a small development set and does not establish production answer accuracy. Live answers require separate review.

Questions and retrieved passages are sent to Groq for answer generation. Application logs omit full questions, passages, API keys and model responses. Authentication and distributed rate limiting are not implemented; the supplied Compose configuration binds to localhost. Public hosting and cloud deployment are outside the current implementation.
