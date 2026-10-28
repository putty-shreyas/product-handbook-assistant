# Citation validation

## Response contract

The model returns a status and a list of statements. Each statement contains text and supporting source IDs. The application checks the schema and validates the IDs against the retrieved passages before rendering citations.

Illustrative response, not a handbook instruction:

```json
{"status":"answered","statements":[{"text":"A supported instruction.","citations":["p029-c01"]}]}
```

If the cited passage was retrieved, the rendered statement is:

```text
A supported instruction. [p029-c01]
```

The application derives the answer-level citation list from these statements. This avoids requiring the model to synchronize inline markers with a separate citation list. Duplicate source IDs are removed while preserving order.

An `insufficient_evidence` response must contain no statements. The application supplies the refusal message. Unknown IDs, empty answers, empty statements and truncated completions are rejected.

## Validation boundaries

The provider request uses JSON object mode. A schema is included in the prompt and validated locally; JSON mode alone does not enforce that schema. No additional model request is made to repair invalid output.

Citation membership does not establish that a source supports a statement, that warnings are preserved or that an answer is complete. Those properties require separate evaluation against the handbook.

## Diagnostics

| Code | Meaning |
|---|---|
| `invalid_schema` | Invalid shape, type, length or missing statement citations |
| `unknown_source` | Citation ID absent from the retrieved context |
| `unlisted_inline_source` | Statement text contains an ID absent from its citation array |
| `empty_answer` / `empty_statement` | No meaningful answer or statement text |
| `refusal_contains_statements` | Refusal accompanied by answer statements |
| `truncated_response` | Provider reported reaching the output-token limit |

Validation logs contain a fixed diagnostic code, not the key, prompt or raw model response. Keep the question and observed output in a separate local evaluation record when investigating failures.

## Relevant files

- `prompts/answer.txt`: grounding instructions and output requirements.
- `handbook/llm.py`: provider call, validation and citation rendering.
- `tests/test_citations.py`: response validation and mocked provider/API cases.
- `tests/test_pipeline.py`: ingestion, retrieval and API contracts.
