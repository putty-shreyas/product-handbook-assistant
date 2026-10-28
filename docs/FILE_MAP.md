# Where files belong

Paths below are relative to the repository root.

| Path relative to project root | Purpose | Commit to Git? |
|---|---|---|
| `handbook/` | Python application and CLI modules | Yes |
| `web/` | Browser interface | Yes |
| `prompts/answer.txt` | Model grounding and response instructions | Yes |
| `sources/prusa-mk4s.json` | Official URL, manual version and checksum | Yes |
| `eval/retrieval_cases.json` | Development questions and expected pages | Yes |
| `tests/` | Network-free automated tests | Yes |
| `docs/` | Architecture, demo, roadmap and validation notes | Yes |
| `.github/workflows/ci.yml` | GitHub Actions checks and container smoke test | Yes |
| `.vscode/` | Suggested interpreter and extensions | Yes |
| `.env.example` | Setting names and safe defaults | Yes |
| `.env` | Private API key and local settings | No |
| `.venv/` | Project Python interpreter and installed dependencies | No |
| `data/raw/` | Vendor PDF downloaded by the CLI | No |
| `data/cache/` | CPU embedding model cache | No |
| `data/indexes/` | Generated text/vector index versions and CURRENT pointer | No |
| `reports/` | Local evaluation output | No |
| `requirements.in`, `requirements-dev.in` | Human-maintained direct dependency choices | Yes |
| `requirements.txt`, `requirements-dev.txt` | Resolved dependency versions with platform markers | Yes |
| `Dockerfile`, `compose.yaml`, `.dockerignore` | Container build/run definitions | Yes |
| `pyproject.toml` | Test and lint configuration | Yes |

Credentials, the vendor manual, model weights, generated indexes and Python environments are excluded from version control. See `START_HERE_WINDOWS.md` for setup. Requirements locks were generated for Python 3.12 with uv; normal setup uses pip and does not require uv. If changing dependencies later, regenerate both locks and rerun checks.
