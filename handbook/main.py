import logging
import time
import uuid
from contextlib import asynccontextmanager
from threading import BoundedSemaphore

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .config import ROOT, Settings
from .llm import GroqClient, ProviderError
from .retrieval import Retriever

logger = logging.getLogger("uvicorn.error")


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1200)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Enter a question with at least three characters.")
        return value


def create_app(settings=None, retriever=None, llm=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if app.state.retriever is None:
            try:
                app.state.retriever = Retriever(settings.data_dir)
            except Exception as exc:
                # Do not echo arbitrary filesystem/provider messages to visitors.
                logger.warning("Index startup failed: %s", type(exc).__name__)
        yield

    app = FastAPI(title="Product Handbook Assistant", version="0.1.0", lifespan=lifespan)
    app.state.retriever = retriever
    app.state.llm = llm or GroqClient(settings)
    app.state.gate = BoundedSemaphore(1)

    def ready_retriever():
        if app.state.retriever is None:
            raise HTTPException(
                503, "Index unavailable. Run python -m handbook index, then restart. Use doctor for details."
            )
        return app.state.retriever

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        retriever = ready_retriever()
        return {
            "status": "ready",
            "index_version": retriever.manifest["version"],
            "source": retriever.manifest["source"],
            "embedding_model": retriever.manifest["embedding_model"],
            "llm_model": settings.llm_model,
            "llm_configured": bool(settings.groq_api_key.get_secret_value()),
        }

    @app.post("/api/search")
    def search(request: Question):
        retriever = ready_retriever()
        start = time.perf_counter()
        hits = retriever.search(request.question, settings.top_k)
        return {
            "sources": hits,
            "retrieval_ms": round((time.perf_counter() - start) * 1000),
            "index_version": retriever.manifest["version"],
        }

    @app.post("/api/ask")
    def ask(request: Question):
        retriever = ready_retriever()
        if not app.state.gate.acquire(blocking=False):
            raise HTTPException(429, "An answer is already running. Please wait.")
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            hits = retriever.search(request.question, settings.top_k)
            retrieved = time.perf_counter()
            result, usage = app.state.llm.answer(request.question, hits)
            elapsed = round((time.perf_counter() - started) * 1000)
            logger.info(
                "rag request_id=%s status=%s elapsed_ms=%s index=%s",
                request_id,
                result.status,
                elapsed,
                retriever.manifest["version"],
            )
            return {
                **result.model_dump(),
                "sources": hits,
                "request_id": request_id,
                "index_version": retriever.manifest["version"],
                "model": settings.llm_model,
                "timings": {"retrieval_ms": round((retrieved - started) * 1000), "total_ms": elapsed},
                "usage": usage,
            }
        except ProviderError as exc:
            return JSONResponse(status_code=502, content={"detail": str(exc), "request_id": request_id})
        finally:
            app.state.gate.release()

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")

    @app.get("/")
    def home():
        return FileResponse(ROOT / "web/index.html")

    return app


app = create_app()
