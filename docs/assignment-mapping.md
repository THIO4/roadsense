# Assignment 2 -> RoadSense mapping

Updated at every milestone. Status: planned / in progress / done.

| Assignment concept | RoadSense implementation | Status |
|---|---|---|
| Pipeline | GitHub Actions: lint + test -> build -> push -> deploy | planned |
| Continuous Integration | ruff + pytest on every push / PR | planned (tests exist locally) |
| Automated testing | 30 pytest tests: parser, HTTP client (MockTransport), repository, index, API (TestClient); 1 opt-in Cosmos integration test | done |
| Containerization | Multi-stage Dockerfile (non-root, .dockerignore), one image for API + collector; Compose for local dev (D16, D17) | done |
| Container registry | GHCR `ghcr.io/thio4/roadsense:<git-sha>`, public package (D20) | done |
| Continuous Deployment | `az containerapp update` from Actions on `main` | planned |
| Cloud client / SDK | `azure-cosmos` SDK in `db/cosmos.py` (collector + API); `az` CLI in `infra/` and pipeline | done (collector) |
| Cloud database | Azure Cosmos DB (NoSQL, free tier): `stations`, `observations` (D7), live in swedencentral | done |
| Environment variables | `pydantic-settings`, `.env.example`, Container Apps env | done (config.py) |
| Infrastructure as code | `infra/azure-setup.sh` (database) + `infra/azure-deploy.sh` (environment, app, job) | done |
| Secrets | Cosmos key as Container Apps secret via `secretref` (D21); GitHub OIDC -> Azure next | in progress |
| IAM | Service principal / federated identity with least privilege | planned |
| Scheduling | Container Apps Job `roadsense-collector`, cron `*/30 * * * *` (D18) | done |
| Cloud deployment | https://roadsense-api.gentlebush-f249f038.swedencentral.azurecontainerapps.io (D18, D19) | done |
| Logging | Python `logging` -> Container Apps Log Analytics (stdout) | done |
