# Windows setup

Run commands in PowerShell from the project root. Use Python 3.12 (64-bit). Docker Desktop with Linux containers is required only for the container option.

## Project directory

Clone the repository, or extract its ZIP and open the extracted project folder in VS Code. The examples use this path:

```powershell
Set-Location "D:\Data_Science\product-handbook-assistant"
code .
```

Adjust the path to the local checkout. Install Microsoft's Python extension in VS Code.

## Python environment

Choose either Conda or a standard Python virtual environment. Do not create both in the same `.venv` directory. An existing working environment can be reused.

### Conda

For a standard Anaconda installation:

```powershell
$CondaExe = Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"
Test-Path $CondaExe
```

If the result is `False`, set `$CondaExe` to the actual Conda executable. This variable is specific to the terminal session; define it again in a new terminal.

Create the environment only if it does not already exist:

```powershell
& $CondaExe create --prefix .\.venv python=3.12 pip -y
```

Install dependencies and verify the interpreter:

```powershell
& $CondaExe run --prefix .\.venv --no-capture-output python -m pip install -r requirements-dev.txt
& $CondaExe run --prefix .\.venv python -c "import sys; print(sys.executable); print(sys.version)"
```

In VS Code, use **Python: Select Interpreter → Enter interpreter path** and select `.venv\python.exe` inside this project. The repository's default interpreter path follows this Conda layout.

### Standard Python virtual environment

With a Python 3.12 installation and the Windows launcher available:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Select `.venv\Scripts\python.exe` in VS Code. If `py` is unavailable, use the full path to an installed Python 3.12 executable to create the environment.

The remaining Python examples use Conda. For a standard virtual environment, replace `& $CondaExe run --prefix .\.venv --no-capture-output python` with `.\.venv\Scripts\python.exe`.

## Configuration and checks

Create `.env` without overwriting an existing file:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
& $CondaExe run --prefix .\.venv --no-capture-output python -m handbook doctor
& $CondaExe run --prefix .\.venv --no-capture-output python -m pytest -q
```

Search does not require a Groq API key. To enable answers, create a key at https://console.groq.com/keys and set `GROQ_API_KEY` in `.env`. Keep the configured `LLM_MODEL` unless selecting another compatible model available to the account. Account quotas and model availability are documented at https://console.groq.com/docs/models.

The backend reads `.env` through its settings class. VS Code terminal environment injection is not required for this application. Keep `.env` out of Git and do not include credentials in logs or screenshots.

## Download and index

```powershell
& $CondaExe run --prefix .\.venv --no-capture-output python -m handbook download
& $CondaExe run --prefix .\.venv --no-capture-output python -m handbook index
```

Initial downloads require internet access. The indexer verifies the manual, extracts text and creates embeddings on the CPU. It does not call the generation API.

| Location | Contents |
|---|---|
| `data/raw/` | Downloaded PDF |
| `data/cache/` | Embedding model cache |
| `data/indexes/<version>/` | Chunks, vectors and manifest |
| `data/indexes/CURRENT` | Selected index version |

Pages 1–5 are excluded from retrieval. Citations use physical PDF page numbers starting at 1. The extracted corpus contains text, not visual interpretations of figures.

```powershell
& $CondaExe run --prefix .\.venv --no-capture-output python -m handbook search "How do I update the printer firmware?"
& $CondaExe run --prefix .\.venv --no-capture-output python -m handbook evaluate
```

The firmware section is on physical PDF page 29. Evaluation writes `reports/retrieval.json`; the metric checks whether at least one expected page occurs among the retrieved passages. It does not score generated answers.

## Run with Python

```powershell
& $CondaExe run --prefix .\.venv --no-capture-output python -m uvicorn handbook.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Keep the terminal running; press **Ctrl+C** to stop. Restart after changing configuration or rebuilding the index.

## Run with Docker

Stop any Python server using port 8000. Start Docker Desktop and check the engine:

```powershell
docker info --format '{{.OSType}}'
```

Expected: `linux`. With `.env` and the generated index present:

```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail 50 handbook
Invoke-RestMethod "http://127.0.0.1:8000/ready"
```

Open the same local URL. The first container startup may download an embedding-model cache for Linux. Subsequent launches of an unchanged built image can use `docker compose up -d`.

```powershell
docker compose down
```

The downloaded files and index remain in the host's `data/` directory. Run one application instance at a time on a memory-constrained laptop.

After changing source or prompts, use `docker compose up -d --build`. After changing `.env`, use `docker compose up -d --force-recreate`. After rebuilding only the index, use `docker compose restart handbook` to reload it.

## CI

`.github/workflows/ci.yml` runs on pushes and pull requests. It checks lint and tests on Windows and Linux, then builds a Linux image and checks `/health`. The workflow does not require a Groq key or publish an image. It contains no cloud deployment job.

## Troubleshooting

| Symptom | Check |
|---|---|
| Invalid expression after `& $CondaExe` | Define `$CondaExe` in this terminal and verify it with `Test-Path`. |
| VS Code reports missing packages | Select the project's interpreter; Conda uses `.venv/python.exe`, standard venv uses `.venv/Scripts/python.exe`. |
| Docker Linux engine unavailable | Start Docker Desktop and wait for `docker info` to succeed. |
| `/ready` returns 503 | Run `handbook doctor`; check the index and restart after rebuilding. |
| Provider HTTP 401 | Check the private key and reload configuration. |
| Provider HTTP 429 | Check account limits and retry later. |
| Invalid response or citations | Retain the diagnostic code and inspect retrieved evidence; see `docs/CITATION_FIX.md`. |
| Download checksum mismatch | Inspect whether the upstream source changed before updating source metadata. |
| Port 8000 occupied | Stop the other Python server or container. |
| Model download or network failure | Check connectivity, proxy settings and certificates. |

`/ready` reports index availability and key presence. It does not verify key validity, provider connectivity or remaining quota.
