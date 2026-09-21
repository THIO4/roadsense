# Operating RoadSense — runbook

For whoever runs this after development: how to check, stop, start, update, roll back and
finally tear down the application. All commands assume `az login` (Azure for Students) and
`gh auth login` have been done once on this machine, and you are in the repository folder.

```bash
RG=rg-roadsense                       # everything lives in this resource group
URL=https://roadsense-api.gentlebush-f249f038.swedencentral.azurecontainerapps.io
```

## 1. Three different places the code can run

| | Local development | Local Docker | Cloud (Azure) |
|---|---|---|---|
| What runs | `.venv/bin/uvicorn …` on your Mac | `docker compose up` containers on your Mac | Container App + Container Apps Job in Sweden Central |
| Image | none (source files) | `roadsense:local` built on your Mac | `ghcr.io/thio4/roadsense:<sha>` built by GitHub Actions |
| Database | the same cloud Cosmos DB (via `.env`) | the same cloud Cosmos DB (via `.env`) | the same cloud Cosmos DB (via Container Apps secret) |
| Needs your Mac on? | yes | yes | **no** |
| Needs Docker Desktop? | no | yes | **no** |
| Who else can reach it | nobody (127.0.0.1) | nobody (localhost:8000) | anyone with the URL |
| Stopped by | Ctrl+C | `docker compose down` | `az containerapp …` (see §4) |

The three are independent. Closing Docker Desktop, stopping local containers, or shutting the
Mac down has **no effect** on the cloud application. The only thing all three share is the
database: a local collector run writes into the same Cosmos DB the cloud reads from.

## 2. What is running in the cloud, and what it costs

| Resource | Type | Behaviour when idle | Cost |
|---|---|---|---|
| `roadsense-api` | Container App | scales to **0 replicas** after a few minutes without requests; the first request wakes it (~1–3 s) | consumption grant (180k vCPU-s, 2M requests/month) → €0 at this usage |
| `roadsense-collector` | Container Apps Job | nothing runs between executions; cron `*/30 * * * *` starts a ~30 s run | same grant → €0 |
| `cosmos-roadsense-4ea173e5` | Cosmos DB | always on (it is a database) | **free tier, permanent** (1000 RU/s, 25 GB) |
| `cae-roadsense` | Container Apps environment | container for the two above | free (consumption) |
| `workspace-…` | Log Analytics | stores logs | 5 GB/month free; we produce a few MB |
| `id-github-roadsense` | Managed identity | identity for CI | free |

**Things that could cause cost or shutdown:**
- Nothing here can bill while inside the free tiers, and there is no card on the subscription.
- Azure for Students expires **12 months after activation** unless renewed (you get emails). At
  expiry the subscription is disabled and resources stop — nothing is charged.
- Azure deletes a Container Apps environment that is idle for **90 days** (no apps or jobs running).
  The cron job counts as activity, so this does not apply while the job is scheduled.
- Observations auto-delete after 7 days (TTL), so storage stays far below 25 GB.

**Scheduled / background activity that continues with your computer off:** the collector job
(every 30 min), the Log Analytics retention, and the GitHub Actions workflow (only when someone
pushes). Nothing else.

## 3. Checking that it is running

```bash
curl -s $URL/health                                   # {"status":"ok"} = API alive
open $URL                                             # the UI

# API: active revision, image tag (= git commit), current replicas (0 = idle, fine)
az containerapp revision list -n roadsense-api -g $RG \
  --query "[?properties.active].{revision:name, image:properties.template.containers[0].image, replicas:properties.replicas}" -o table

# Collector: recent executions (should be Succeeded every 30 min)
az containerapp job execution list -n roadsense-collector -g $RG \
  --query "[].{start:properties.startTime, status:properties.status}" -o table

# Is the data fresh? newest observation should be < 45 min old
curl -s "$URL/conditions?province=Uusimaa" | python3 -c \
  "import json,sys; b=json.load(sys.stdin); print(max(s['latest']['measured_at'] for s in b['stations'] if s['latest']))"

# All resources still there?
az resource list -g $RG -o table
```

**Portal:** https://portal.azure.com → Resource groups → `rg-roadsense`.
- `roadsense-api` → *Overview* (URL, status), *Revisions and replicas*, *Log stream*, *Metrics*.
- `roadsense-collector` → *Execution history*.
- `cosmos-roadsense-…` → *Data Explorer* (browse documents), *Metrics* (RU usage).
- Subscription → *Cost Management → Cost analysis* (should be €0).

## 4. Logs

```bash
# Live tail of the API container (wakes it if scaled to zero)
az containerapp logs show -n roadsense-api -g $RG --follow

# Collector logs from Log Analytics (ingestion delay ~1-3 min)
WS=$(az monitor log-analytics workspace list -g $RG --query "[0].customerId" -o tsv)
az monitor log-analytics query -w $WS --analytics-query \
  "ContainerAppConsoleLogs_CL | where ContainerJobName_s == 'roadsense-collector' | project TimeGenerated, Log_s | order by TimeGenerated desc | take 20" -o table

# Pipeline logs
gh run list --repo THIO4/roadsense --limit 5
gh run view <run-id> --repo THIO4/roadsense --log
```

Portal: Container App → *Log stream* (live) or *Logs* (KQL queries over history).

## 5. Stop, start, pause

The API needs no manual stopping: at 0 replicas it costs nothing. If you want it unreachable:

```bash
az containerapp stop  -n roadsense-api -g $RG     # URL returns errors, config kept
az containerapp start -n roadsense-api -g $RG     # back within ~30 s, same URL
```

Pause the collector (stop the schedule without deleting the job):

```bash
# a cron date that never occurs (31 Feb) = effectively disabled
az containerapp job update -n roadsense-collector -g $RG --cron-expression "0 0 31 2 *"
# resume
az containerapp job update -n roadsense-collector -g $RG --cron-expression "*/30 * * * *"
# run one collection right now (does not need the schedule)
az containerapp job start  -n roadsense-collector -g $RG
```

Restart the API (new replica, same image) — useful if it behaves oddly:

```bash
az containerapp revision restart -n roadsense-api -g $RG \
  --revision $(az containerapp revision list -n roadsense-api -g $RG --query "[?properties.active].name" -o tsv)
```

## 6. Updating: what a push does

Pushing to `main` on GitHub runs `.github/workflows/ci-cd.yml`:

1. `test` — ruff + pytest. Fails → nothing else happens; the cloud is untouched.
2. `build` — builds the image on GitHub's amd64 runner, pushes `ghcr.io/thio4/roadsense:<short-sha>` and `:latest`.
3. `deploy` — logs into Azure via OIDC, points the API **and** the job at the new tag, waits for
   `/health`. Container Apps creates a new *revision*; traffic moves to it once it is healthy.
   The collector uses the new image from its next scheduled run.

A pull request runs steps 1–2 without pushing; the cloud is never touched by a PR.

So: **the deployed application changes only when a push to `main` passes the tests.** Watch it
at https://github.com/THIO4/roadsense/actions or `gh run watch`.

## 7. Deploying manually (if GitHub Actions is unavailable)

```bash
TAG=$(git rev-parse --short HEAD)
gh auth token | docker login ghcr.io -u THIO4 --password-stdin
docker buildx build --platform linux/amd64 -t ghcr.io/thio4/roadsense:$TAG --push .   # amd64! Azure is not arm64
az containerapp update     -n roadsense-api       -g $RG --image ghcr.io/thio4/roadsense:$TAG
az containerapp job update -n roadsense-collector -g $RG --image ghcr.io/thio4/roadsense:$TAG
curl -s $URL/health
```

## 8. Rolling back

Every image is tagged by commit, so rolling back = deploying an older tag.

Preferred (keeps history honest, goes through tests):
```bash
git revert <bad-commit> && git push        # pipeline deploys the reverted code
```

Fast (no pipeline, ~1 min):
```bash
gh run list --repo THIO4/roadsense --limit 10          # find the last good commit SHA
az containerapp update     -n roadsense-api       -g $RG --image ghcr.io/thio4/roadsense:<good-sha>
az containerapp job update -n roadsense-collector -g $RG --image ghcr.io/thio4/roadsense:<good-sha>
```
The next push to `main` will deploy HEAD again, so also fix or revert the code.

## 9. Secrets and access — what to know

- The only secret is the Cosmos key, stored as Container Apps secret `cosmos-key` on both the
  app and the job, and in `.env` on your Mac. If you suspect it leaked:
  `az cosmosdb keys regenerate -n cosmos-roadsense-4ea173e5 -g $RG --key-kind primary`, then
  re-run `./infra/azure-deploy.sh <current-tag>` (it re-reads the key) and update `.env`.
- CI authenticates with the managed identity `id-github-roadsense` via OIDC; there is no
  password to rotate. If the repo is renamed or moved, the federated credential subject must be
  updated (it embeds the numeric repo id).
- GitHub Secrets hold three IDs only.

## 10. Bringing it back after a long stop

- Subscription still active, resources present → nothing to do; the URL wakes on request.
- Environment deleted (90-day idle rule) or you tore everything down → run
  `./infra/azure-setup.sh` (Cosmos; skips what exists) then `./infra/azure-deploy.sh <tag>`,
  then `roadsense-collector seed` once (station metadata), and re-create the managed identity
  + federated credential + role assignment for CI (commands in D23 of `docs/decisions.md`) and
  update `AZURE_CLIENT_ID` in GitHub Secrets. The URL will be different; update README.

## 11. Final teardown (when the project is over)

Order matters only for tidiness; the first command removes everything billable.

```bash
az group delete --name rg-roadsense --yes          # API, job, environment, Cosmos, logs, identity
az resource list -g rg-roadsense                   # should error: not found
gh secret delete AZURE_CLIENT_ID       --repo THIO4/roadsense
gh secret delete AZURE_TENANT_ID       --repo THIO4/roadsense
gh secret delete AZURE_SUBSCRIPTION_ID --repo THIO4/roadsense
```
Optionally delete the GHCR package (GitHub → Packages → roadsense → settings) and remove
`COSMOS_*` from your local `.env`. The pipeline will then fail at `deploy` on future pushes —
expected; delete or disable the workflow if you keep developing without Azure.

## 12. Local machine hygiene

```bash
docker compose down            # stop local containers (does nothing to the cloud)
docker image rm roadsense:local
deactivate                     # leave the venv
```
