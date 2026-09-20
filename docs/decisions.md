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
