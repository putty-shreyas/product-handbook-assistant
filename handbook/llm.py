import json
import logging
import re
from typing import Literal
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .config import ROOT

logger = logging.getLogger("uvicorn.error")


class ProviderError(RuntimeError):
    pass


class ModelAnswer(BaseModel):
    """Validated answer returned by the API."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["answered", "insufficient_evidence"]
    answer: str = Field(min_length=1, max_length=10000)
    citations: list[str] = Field(max_length=8)


class CitedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=600)
    citations: list[str] = Field(min_length=1, max_length=8)


class GroundedResponse(BaseModel):
    """Provider response containing individually cited statements."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["answered", "insufficient_evidence"]
    statements: list[CitedStatement] = Field(max_length=12)


def reject_response(code):
    # Only a fixed diagnostic code is logged: no API key, prompt or raw model text.
    logger.warning("llm_validation_failed code=%s", code)
    raise ProviderError(f"Model response failed validation ({code}). No answer was displayed.")


def validate_answer(payload, hits):
    try:
        result = GroundedResponse.model_validate(payload)
    except ValidationError:
        reject_response("invalid_schema")
    available = {hit["id"] for hit in hits}
    if result.status == "insufficient_evidence":
        if result.statements:
            reject_response("refusal_contains_statements")
        return ModelAnswer(
            status="insufficient_evidence",
            answer="I cannot answer that from the retrieved handbook passages.",
            citations=[],
        )
    if not result.statements:
        reject_response("empty_answer")
    paragraphs = []
    all_citations = []
    for statement in result.statements:
        # Preserve source order while removing duplicate IDs.
        citations = list(dict.fromkeys(statement.citations))
        if not set(citations) <= available:
            reject_response("unknown_source")
        embedded_ids = set(re.findall(r"\bp\d+-c\d+\b", statement.text, flags=re.IGNORECASE))
        if not embedded_ids <= set(citations):
            reject_response("unlisted_inline_source")
        # Remove validated inline markers before rendering citations.
        text = re.sub(r"\[(p\d+-c\d+)\]", "", statement.text).strip()
        if not text:
            reject_response("empty_statement")
        markers = " ".join(f"[{source_id}]" for source_id in citations)
        paragraphs.append(f"{text} {markers}")
        for source_id in citations:
            if source_id not in all_citations:
                all_citations.append(source_id)
    # This verifies source membership, not whether sources entail each claim.
    return ModelAnswer(status="answered", answer="\n\n".join(paragraphs), citations=all_citations)


class GroqClient:
    def __init__(self, settings):
        self.settings = settings
        self.prompt = (ROOT / "prompts/answer.txt").read_text(encoding="utf-8")

    def answer(self, question, hits):
        key = self.settings.groq_api_key.get_secret_value()
        if not key:
            raise ProviderError(
                "GROQ_API_KEY is missing. Search works without it; add a key to .env and restart for answers."
            )
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": self.prompt
                    + "\nJSON schema:\n"
                    + json.dumps(GroundedResponse.model_json_schema()),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "allowed_citation_ids": [h["id"] for h in hits],
                            "passages": [{"id": h["id"], "page": h["page"], "text": h["text"]} for h in hits],
                        }
                    ),
                },
            ],
            "temperature": 0.1,
            "max_completion_tokens": 1600,
            "response_format": {"type": "json_object"},
        }
        if self.settings.llm_model.startswith("qwen/"):
            payload.update(reasoning_format="hidden", reasoning_effort="none")
        try:
            # No automatic retries: avoid duplicate paid requests on ambiguous failures.
            with httpx.Client(timeout=httpx.Timeout(60, connect=10)) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                reject_response("truncated_response")
            result = validate_answer(json.loads(choice["message"]["content"]), hits)
            return result, body.get("usage", {})
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hints = {
                401: "Check your API key.",
                429: "Rate or quota limit reached; wait before retrying.",
                400: "Check model availability and request settings.",
                404: "Check LLM_MODEL in .env.",
            }
            raise ProviderError(
                f"LLM service returned HTTP {code}. {hints.get(code, 'Try again later.')}"
            ) from None
        except httpx.RequestError:
            raise ProviderError("LLM service is unreachable or timed out. Check your connection.") from None
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            raise ProviderError("LLM returned an invalid response. No answer was displayed.") from None
