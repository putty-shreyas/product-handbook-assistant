# Example queries and failure scenarios

## Query walkthrough

1. Open the local application and inspect the linked Prusa handbook.
2. Search for **How do I update the printer firmware?** Review the retrieved evidence and open its PDF page. The firmware section is on physical page 29.
3. Use **Answer with sources** for the same question. Compare each statement against its cited passage, including any conditions or warnings.
4. Ask **The first layer is peeling off. What should I check?** The troubleshooting section on physical page 26 is relevant.
5. Ask **What was Prusa's revenue in 2025?** The handbook does not provide evidence for this question; the expected response is insufficient evidence.

Results depend on retrieval and model output. A passing example does not establish reliability across other questions or repeated requests.

## Design choices

| Choice | Reason and trade-off |
|---|---|
| Retrieval-augmented generation | Supplies product-specific evidence without retraining model weights; answers still require evaluation. |
| CPU embeddings and hosted generation | Keeps local memory requirements modest; generation depends on provider availability, quota and network access. |
| NumPy vector index | Supports exact ranking for a small corpus without an additional service; concurrent updates and large corpora need another storage design. |
| Source IDs with PDF pages | Makes evidence inspectable; source membership is not semantic verification. |
| Versioned index artifacts | Supports identification and local rollback; full reproducibility also requires pinned models, dependencies and image digests. |

## Answer evaluation

Record live checks in `reports/`: question, retrieved pages, answer, correctness, supported claims, omitted information, refusal outcome, latency and token usage. Include direct questions, troubleshooting, questions requiring several passages, unsupported questions and attempts to override the grounding instructions.

Use a separate set of questions after tuning retrieval or prompts. Report retrieval page hit rate separately from answer correctness, citation support and refusal behavior.

## Failure scenarios

- **Provider outage or quota limit:** search remains available if the local index and embedding model are loaded. Generation reports a provider error.
- **Invalid JSON or citations:** the application rejects the response and displays a diagnostic message.
- **Missing or corrupt index:** the web process can remain healthy while readiness fails. Rebuild or select a valid index and restart.
- **Incorrect answer:** first check whether the necessary evidence was retrieved. Missing evidence suggests a retrieval issue; misused available evidence suggests a generation issue. Both can occur together.
