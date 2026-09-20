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
