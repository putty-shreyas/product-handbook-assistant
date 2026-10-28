"""Network-free contract tests. These do not measure live LLM answer quality."""

import json
from unittest.mock import Mock, patch

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from handbook.config import EMBEDDING_DIM, EMBEDDING_MODEL, SCHEMA_VERSION, Settings
from handbook.ingest import chunk_page, sha256
from handbook.llm import GroqClient, ModelAnswer, ProviderError, validate_answer
from handbook.main import create_app
from handbook.retrieval import Retriever

HIT = {
    "id": "p029-c01",
    "page": 29,
    "text": "Firmware instructions.",
    "score": 0.7,
    "url": "https://example.org/manual.pdf#page=29",
}


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, groq_api_key="")


@pytest.fixture
def index(tmp_path):
    folder = tmp_path / "indexes/0123456789abcdef"
    folder.mkdir(parents=True)
    chunks = [
        {**HIT, "id": f"p{page:03d}-c{i:02d}", "page": page} for i, page in enumerate([29, 29, 29, 30, 31], 1)
    ]
    (folder / "chunks.json").write_text(json.dumps(chunks))
    vectors = np.zeros((5, EMBEDDING_DIM), dtype=np.float32)
    vectors[:, 0] = [1, 0.99, 0.98, 0.9, 0.8]
    np.save(folder / "vectors.npy", vectors)
    manifest = {
        "schema": SCHEMA_VERSION,
        "embedding_model": EMBEDDING_MODEL,
        "dimension": EMBEDDING_DIM,
        "source": {"url": "https://example.org/manual.pdf"},
        "version": folder.name,
        "chunks_sha256": sha256(folder / "chunks.json"),
        "vectors_sha256": sha256(folder / "vectors.npy"),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    (folder.parent / "CURRENT").write_text(folder.name)
    embedder = Mock()
    embedder.query.return_value = np.eye(1, EMBEDDING_DIM, dtype=np.float32)[0]
    return tmp_path, folder, embedder


def test_chunks_preserve_page_and_limit_size():
    chunks = chunk_page("Firmware update procedure " * 100, page=29)
    assert len(chunks) > 1
    assert all(c["page"] == 29 and len(c["text"]) <= 1000 for c in chunks)
    assert len({c["id"] for c in chunks}) == len(chunks)
    assert chunks[-1]["text"].endswith("procedure")


def test_invalid_overlap_is_rejected():
    with pytest.raises(ValueError):
        chunk_page("test", 1, size=10, overlap=10)


def test_retrieval_rank_and_page_diversity(index):
    data, _, embedder = index
    hits = Retriever(data, embedder).search("firmware", top_k=3)
    assert [h["page"] for h in hits] == [29, 29, 30]
    assert hits[0]["url"].endswith("#page=29")


def test_corrupt_index_is_rejected(index):
    data, folder, embedder = index
    (folder / "chunks.json").write_text("[]")
    with pytest.raises(ValueError, match="integrity"):
        Retriever(data, embedder)


def test_embedding_mismatch_is_rejected(index):
    data, folder, embedder = index
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["embedding_model"] = "different-model"
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Incompatible"):
        Retriever(data, embedder)


@pytest.mark.parametrize(
    "citations,text",
    [([], "No citations"), (["p999-c01"], "Invented source"), (["p029-c01"], "Invented inline [p999-c01]")],
)
def test_missing_or_invented_citations_rejected(citations, text):
    with pytest.raises(ProviderError):
        validate_answer({"status": "answered", "statements": [{"text": text, "citations": citations}]}, [HIT])


def test_refusal_is_normalized():
    result = validate_answer({"status": "insufficient_evidence", "statements": []}, [HIT])
    assert result.citations == [] and "cannot answer" in result.answer


def test_missing_key_never_calls_provider(settings):
    with patch("handbook.llm.httpx.Client") as client:
        with pytest.raises(ProviderError, match="GROQ_API_KEY"):
            GroqClient(settings).answer("question", [HIT])
        client.assert_not_called()


def test_provider_error_does_not_expose_key(settings):
    settings = Settings(_env_file=None, data_dir=settings.data_dir, groq_api_key="not-a-real-key")
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.groq.com/test"))
    with patch("handbook.llm.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = response
        with pytest.raises(ProviderError) as error:
            GroqClient(settings).answer("question", [HIT])
    assert "401" in str(error.value) and "not-a-real-key" not in str(error.value)


def test_live_and_ready_have_different_meanings(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.post("/api/ask", json={"question": "hello"}).status_code == 503


@pytest.mark.parametrize("question", ["  ", "x" * 1201])
def test_invalid_question_is_rejected(settings, question):
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/search", json={"question": question}).status_code == 422


def test_answer_and_search_contract(settings):
    retriever = Mock()
    retriever.manifest = {"version": "test-index"}
    retriever.search.return_value = [HIT]
    llm = Mock()
    llm.answer.return_value = (
        ModelAnswer(
            status="answered", answer="See firmware instructions [p029-c01].", citations=["p029-c01"]
        ),
        {"total_tokens": 100},
    )
    with TestClient(create_app(settings, retriever, llm)) as client:
        response = client.post("/api/search", json={"question": "How do I update firmware?"})
        assert response.status_code == 200
        llm.answer.assert_not_called()
        response = client.post("/api/ask", json={"question": "How do I update firmware?"})
        assert response.status_code == 200
        assert response.json()["citations"] == ["p029-c01"]
        assert response.json()["usage"]["total_tokens"] == 100
        assert client.get("/").status_code == 200


def test_provider_failure_releases_concurrency_slot(settings):
    retriever = Mock()
    retriever.search.return_value = [HIT]
    llm = Mock()
    llm.answer.side_effect = ProviderError("Temporary provider failure")
    with TestClient(create_app(settings, retriever, llm)) as client:
        assert client.post("/api/ask", json={"question": "Firmware?"}).status_code == 502
        assert client.post("/api/ask", json={"question": "Firmware?"}).status_code == 502
