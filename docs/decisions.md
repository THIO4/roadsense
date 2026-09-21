# Decision log

Short record of *why* things are the way they are. Newest at the bottom.

## D1 - Cloud provider: Azure (2026-09-20)
Options: GCP (Cloud Run + Firestore), Azure (Container Apps + Cosmos DB), AWS (App Runner +
DynamoDB), no-card PaaS (Render + Supabase). Chosen Azure because **Azure for Students**
provides $100 credit and free tiers with no credit card, and Container Apps + Cosmos DB both
have permanent free grants that cover this workload. Hard constraint: EUR 0 total cost.

## D2 - Database: Azure Cosmos DB (NoSQL) instead of Postgres
Postgres was the first idea, but every managed Postgres on the big-3 clouds bills per hour
(Azure Database for PostgreSQL ~EUR 15+/month; Cloud SQL ~EUR 8+/month). Cosmos DB free tier
(1000 RU/s, 25 GB) is permanent. Observations are simple documents, so a document store fits.

## D3 - Container registry: GitHub Container Registry (GHCR)
Azure Container Registry has no free tier (~EUR 5/month). GHCR is free for public repos and
is a standard OCI registry that Container Apps can pull from.

## D4 - Digitraffic: one bulk request, all 528 stations
`/api/weather/v1/stations/data` returns every station in one ~360 KB call. Storing all
stations costs ~25k small documents/day - negligible - and lets "select an area" be a
query-time province filter instead of collector-side configuration.

## D5 - Store 8 sensors, not 95
Each station reports ~95 sensors, mostly diagnostics. We keep only what the index and UI use:
ILMA (air temp), TIE_1 (road temp), KELI_1 (road condition code + label), KITKA1 (friction),
SADE_INTENSITEETTI (precipitation), NÄKYVYYS_M (visibility), KESKITUULI (wind), VAROITUS_1
(station warning). All optional: sensors differ per station and can fault.

## D6 - Tests never touch the network
Parser tests use JSON fixtures captured from the real API; client tests use
`httpx.MockTransport`. CI must be deterministic - a red build must always mean *our* bug.

## D7 - Cosmos data model: `latest` embedded in the station document
Containers: `stations` (pk `/id`, station metadata + `latest` observation) and
`observations` (pk `/station_id`, 7-day TTL history). The UI's main query - "all stations in
province X with current conditions" - becomes a single query on `stations`. The cost is one
extra patch per observation on write, which is cheap. Observation `id` is
`"<station_id>:<measured_at>"`, so upserts of unchanged data are no-ops and the collector is
idempotent. Filtering by province is cross-partition; at ~530 documents that costs a few RU.

## D8 - Repository abstraction; no local Cosmos emulator
`db/repository.py` defines the storage interface; `InMemoryRepository` backs unit tests and
`--dry-run`, `CosmosRepository` is the only cloud-specific module. The Cosmos emulator is
x86-only (the Mac is arm64), and the real free-tier account costs nothing, so local
development uses the real cloud database.

## D9 - Authentication to Cosmos: account key as a secret (for now)
The key is read from `COSMOS_KEY` (never defaulted, never committed; `SecretStr` keeps it out
of logs). In Azure it becomes a Container Apps secret. Upgrade path, if time permits: managed
identity + Entra RBAC, which removes the secret entirely.

## D10 - Infrastructure as a script
`infra/azure-setup.sh` creates every Azure resource with the `az` CLI, so the setup is
reproducible and reviewable. Full IaC (Bicep/Terraform) would be the production answer but
is out of scope for the course.

## D11 - Region: swedencentral (forced by Azure Policy)
The first deployment to northeurope failed with `RequestDisallowedByAzure`: Azure for
Students subscriptions carry a policy (`sys.regionrestriction`) allowing only belgiumcentral,
swedencentral, denmarkeast, switzerlandnorth and austriaeast. Policy sits above IAM - it can
veto an owner. Sweden Central is the closest allowed region to Finland. Discovered with
`az policy assignment list --disable-scope-strict-match`.

## D12 - Quiet library loggers
The Cosmos SDK logs every request + headers at INFO (2.6 MB for one collection run).
`logging_setup.configure_logging` pins `azure`, `httpx`, `httpcore` to WARNING. Observed
cost per run: ~1024 requests, ~10 RU per observation upsert + ~2 RU per station patch.

## D13 - Index: explainable penalties, max-not-sum for surface, null on missing data
See docs/index.md. The API returns the applied factors with every score so the UI (and the
report) can explain any number. Road condition code and friction both describe grip, so the
larger penalty wins rather than double counting. Sensor fault (KELI code 0) is treated as
"no data", not as a penalty - a bug we would otherwise have shipped (station 1005).

## D14 - API is read-only; dependency injection for storage
The API only reads (`list_*`); the collector is the only writer. `Depends(get_repo)` supplies
the Repository, and tests override it with InMemoryRepository, so the full HTTP layer is tested
offline. Response models (api/schemas.py) are separate from internal dataclasses so the public
contract can evolve independently.

## D15 - Frontend: static files served by FastAPI, no framework, no build
Plain HTML/CSS/JS in `src/roadsense/static/`, mounted at `/static`, `index.html` at `/`.
One container and one URL; same origin as the API so no CORS. Leaflet + OpenStreetMap tiles
(free, no key) for the map. Status colours from an accessibility-checked palette, and the band
*word* is always shown next to the score - colour never carries meaning alone. Package data is
declared in pyproject so the files ship inside the installed package (and the Docker image).

## D16 - One image, two roles; multi-stage; non-root
A single Dockerfile builds one image used for both the API (default CMD: uvicorn) and the
collector (command override: `python -m roadsense.collector collect`). Multi-stage build
keeps pip caches/build tools out of the runtime image (273 MB, mostly the python:3.12-slim
base). The process runs as user `app` (uid 1000), not root. `.dockerignore` excludes `.env`,
`.venv`, `.git`, tests and docs - verified: no `.env` inside the image, no secret in image env.
Python is pinned to 3.12 in the image (all deps ship wheels for it) even though the laptop
runs 3.14 - the image, not the host, decides the runtime.

## D17 - Docker Compose for local dev only
`compose.yaml` runs the API with `.env` and exposes a `collector` service under the `tools`
profile for on-demand runs. There is no local database service (see D8); both services talk
to the free-tier Cosmos account. Compose is a developer convenience, not used in Azure.

## D18 - Deployment target: Azure Container Apps (consumption, scale to zero)
API = Container App (`roadsense-api`, external HTTPS ingress, 0.25 vCPU / 0.5 GiB,
min 0 / max 1 replicas). Collector = Container Apps Job (`roadsense-collector`, cron
`*/30 * * * *`, same image, command `roadsense-collector collect`). Both in environment
`cae-roadsense`. Free consumption grant (180k vCPU-s, 2M requests/month) covers this; the
API bills nothing while idle. First-time deploy is `infra/azure-deploy.sh <tag>`.

## D19 - Environment mode must be WorkloadProfiles
The preview containerapp CLI extension (1.3.0b5) creates "Express" environments by default,
which do not support Jobs (`ExpressEnvironmentResourceNotSupported`). Recreated with
`--environment-mode WorkloadProfiles`. Tearing down and recreating from the script took
~5 minutes and proved the deployment is reproducible.

## D20 - Images: GHCR, public package, tagged by git SHA, built for linux/amd64
Every image is tagged with the short commit SHA (`ghcr.io/thio4/roadsense:<sha>`) so a
running container can always be traced to exact source; `latest` is a convenience alias.
The package is public so Azure pulls anonymously (source is public anyway; the image holds
no secrets). The laptop is arm64 but Azure is amd64: local pushes use
`docker buildx build --platform linux/amd64`; CI runners are amd64 natively.

## D21 - Secrets in Azure: Container Apps secret + secretref
The Cosmos key is read from Azure at deploy time and stored as the Container Apps secret
`cosmos-key`; the container sees `COSMOS_KEY=secretref:cosmos-key` resolved at runtime.
`az containerapp secret list` shows names only. The value never appears in the repo, the
image, the CLI output or the portal.
