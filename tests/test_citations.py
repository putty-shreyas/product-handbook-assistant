"""Citation contracts: generated source IDs are validated before rendering."""

import json
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from handbook.config import Settings
from handbook.llm import GroqClient, ProviderError, validate_answer
from handbook.main import create_app

HITS = [
    {"id": "p029-c01", "page": 29, "text": "A supported first instruction."},
    {"id": "p029-c02", "page": 29, "text": "A supported second instruction."},
]


def statement(text="A supported instruction.", citations=None):
    return {"text": text, "citations": ["p029-c01"] if citations is None else citations}


def answer(*statements):
    return {"status": "answered", "statements": list(statements)}


def test_python_renders_citations_without_model_inline_markers():
    result = validate_answer(answer(statement()), HITS)
    assert result.answer == "A supported instruction. [p029-c01]"
    assert result.citations == ["p029-c01"]


def test_multistep_sources_remain_attached_to_their_statements():
    result = validate_answer(answer(statement("First step."), statement("Second step.", ["p029-c02"])), HITS)
    assert result.answer == "First step. [p029-c01]\n\nSecond step. [p029-c02]"
    assert result.citations == ["p029-c01", "p029-c02"]


def test_duplicates_are_deduplicated_without_reordering():
    result = validate_answer(answer(statement(citations=["p029-c02", "p029-c01", "p029-c02"])), HITS)
    assert result.answer.endswith("[p029-c02] [p029-c01]")
    assert result.citations == ["p029-c02", "p029-c01"]


def test_redundant_valid_inline_marker_does_not_appear_twice():
    result = validate_answer(answer(statement("Instruction. [p029-c01]")), HITS)
    assert result.answer == "Instruction. [p029-c01]"


@pytest.mark.parametrize("citations", [[], ["p999-c01"], ["29"], [" p029-c01 "], ["[p029-c01]"]])
def test_missing_unknown_or_reformatted_source_ids_fail_closed(citations):
    with pytest.raises(ProviderError):
        validate_answer(answer(statement(citations=citations)), HITS)


def test_one_uncited_statement_invalidates_the_entire_answer():
    with pytest.raises(ProviderError, match="invalid_schema"):
        validate_answer(answer(statement(), statement("Unsupported second step.", [])), HITS)


@pytest.mark.parametrize("text", ["   ", "[p029-c01]"])
def test_empty_claim_is_rejected(text):
    with pytest.raises(ProviderError, match="empty_statement"):
        validate_answer(answer(statement(text)), HITS)


def test_no_statements_is_not_a_successful_answer():
    with pytest.raises(ProviderError, match="empty_answer"):
        validate_answer(answer(), HITS)


def test_refusal_cannot_carry_an_answer():
    with pytest.raises(ProviderError, match="refusal_contains_statements"):
        validate_answer({"status": "insufficient_evidence", "statements": [statement()]}, HITS)


def test_refusal_message_is_application_owned():
    result = validate_answer({"status": "insufficient_evidence", "statements": []}, HITS)
    assert result.answer == "I cannot answer that from the retrieved handbook passages."
    assert result.citations == []


def test_failure_logging_excludes_model_text(caplog):
    with pytest.raises(ProviderError):
        validate_answer(answer(statement("PRIVATE_MODEL_TEXT", ["p999-c01"])), HITS)
    assert "unknown_source" in caplog.text
    assert "PRIVATE_MODEL_TEXT" not in caplog.text


def test_new_response_contract_passes_through_real_client_and_api(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, groq_api_key="test-key-not-real")
    retriever = Mock()
    retriever.manifest = {"version": "fixture-index"}
    retriever.search.return_value = HITS
    completion = {
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer(statement()))}}],
        "usage": {"total_tokens": 200},
    }
    response = httpx.Response(
        200, json=completion, request=httpx.Request("POST", "https://api.groq.com/test")
    )
    with TestClient(create_app(settings, retriever, GroqClient(settings))) as client:
        with patch("handbook.llm.httpx.Client") as provider:
            post = provider.return_value.__enter__.return_value.post
            post.return_value = response
            result = client.post("/api/ask", json={"question": "How do I update firmware?"})
            assert result.status_code == 200
            assert result.json()["answer"].endswith("[p029-c01]")
            assert result.json()["citations"] == ["p029-c01"]
            assert result.json()["usage"] == {"total_tokens": 200}
            post.assert_called_once()
            request_json = post.call_args.kwargs["json"]
            user_message = json.loads(request_json["messages"][1]["content"])
            assert user_message["allowed_citation_ids"] == ["p029-c01", "p029-c02"]


def test_truncated_completion_is_rejected_before_parsing(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, groq_api_key="test-key-not-real")
    response = httpx.Response(
        200,
        json={"choices": [{"finish_reason": "length", "message": {"content": "{"}}]},
        request=httpx.Request("POST", "https://api.groq.com/test"),
    )
    with patch("handbook.llm.httpx.Client") as provider:
        provider.return_value.__enter__.return_value.post.return_value = response
        with pytest.raises(ProviderError, match="truncated_response"):
            GroqClient(settings).answer("question", HITS)
