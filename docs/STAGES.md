# Scope and optional extensions

## Current implementation

The project runs locally in Python or Docker, with CPU-based retrieval and hosted generation through Groq. GitHub Actions performs lint, unit/API tests and a container health check. There is no public application endpoint, image publishing job or cloud deployment pipeline.

## Possible improvements

| Area | Extension | Verification |
|---|---|---|
| Answer quality | Reviewed evaluation set covering support, completeness and refusals | Compare results before changing prompts or models |
| Retrieval | Evaluate chunking, hybrid search or reranking | Measure retrieval and answer quality on separate test cases |
| Reproducibility | Pin model revisions and container digests | Rebuild from recorded inputs |
| Operations | Metrics, alerts and controlled concurrency | Load tests and simulated dependency failures |
| Access | Authentication and per-user request limits | Authorization and rate-limit tests |
| Delivery | Versioned image publishing and deployment | Smoke tests, quality gate and rollback rehearsal |

## Optional cloud deployment

A managed container service such as Azure Container Apps could host the API. This would require a container registry, persistent or downloadable index artifacts, runtime secret injection, access control and resource limits. The current local `./data` bind mount cannot be used unchanged in a remote environment.

A deployment workflow could authenticate through GitHub OIDC, publish a versioned image, deploy a revision, verify readiness and run application checks. Record the image digest and index version so a previous release can be restored. Terraform could define the infrastructure; it is not currently included.

Cloud deployment is optional and may incur charges. The local demo does not require an Azure subscription. Managed container hosting also does not demonstrate administration of a Kubernetes cluster.
