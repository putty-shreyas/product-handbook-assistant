# Validation

## Automated checks

The test suite covers chunking, index integrity, retrieval behavior, request validation, provider failures and citation contracts. External model calls are mocked; tests require neither a Groq API key nor a model download.

GitHub Actions runs Ruff and pytest on Windows and Linux. A dependent job builds the Docker image and checks that `/health` responds without a corpus. This container check establishes process startup, not retrieval readiness or live answer quality.

## Recorded retrieval evaluation

`validation-retrieval.json` records a development evaluation against index `f2207ccf569f26a0`. All 10 questions retrieved at least one expected PDF page among the top five passages: `page_hit_rate@5 = 1.0`.

This result belongs to the recorded index and questions. It is not a measurement of every relevant passage, generated-answer accuracy or held-out generalization. A different index version should be evaluated separately.

The initial corpus check extracted the 66-page manual and produced 134 chunks from pages 6–66. CPU embeddings have 384 dimensions. The maximum observed chunk length under the downloaded embedding tokenizer was 304 tokens. These observations apply to this manual and configuration.

## Local integration observations

During local verification on Windows, the application downloaded and indexed the manual, returned source-page links and generated answers through Groq. The Docker service reported readiness with index `e23a4517bf83a97c`. Firmware and first-layer queries returned cited answers; unsupported revenue and full-product-catalog questions returned insufficient evidence.

These are manual smoke-test observations, not a scored answer-quality benchmark. Successful CI runs were also observed on GitHub. Live-answer quality has not been measured on a scored evaluation dataset.

## Repeatable checks

From the configured project environment:

```text
python -m ruff check .
python -m pytest -q
python -m handbook doctor
python -m handbook evaluate
```

The final two commands inspect or use local artifacts. Live generation must be checked separately with an API key. Record new retrieval output in `reports/retrieval.json` and retain reviewed answer cases separately.

Cloud deployment, load testing, adversarial robustness and production availability have not been established. Health, readiness, retrieval quality and answer quality are distinct checks.
