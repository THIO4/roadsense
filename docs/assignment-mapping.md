# Assignment 2 -> RoadSense mapping

Updated at every milestone. Status: planned / in progress / done.

| Assignment concept | RoadSense implementation | Status |
|---|---|---|
| Pipeline | GitHub Actions: lint + test -> build -> push -> deploy | planned |
| Continuous Integration | ruff + pytest on every push / PR | planned (tests exist locally) |
| Automated testing | pytest: parser (fixtures), HTTP client (MockTransport), later API (TestClient) | in progress |
| Containerization | Multi-stage Dockerfile; Docker Compose for local dev | planned |
| Container registry | GitHub Container Registry, images tagged by git SHA | planned |
| Continuous Deployment | `az containerapp update` from Actions on `main` | planned |
| Cloud client / SDK | `azure-cosmos` Python SDK in collector + API; `az` CLI in pipeline | planned |
| Cloud database | Azure Cosmos DB (NoSQL, free tier): `stations`, `observations` | planned |
| Environment variables | `pydantic-settings`, `.env.example`, Container Apps env | done (config.py) |
| Secrets | GitHub OIDC -> Azure (no stored password); Cosmos key as Container Apps secret | planned |
| IAM | Service principal / federated identity with least privilege | planned |
| Scheduling | Container Apps Job with cron trigger | planned |
| Cloud deployment | Public Container App URL | planned |
| Logging | Python `logging` -> Container Apps log stream | done (collector) |
