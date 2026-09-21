#!/usr/bin/env bash
# First-time deployment of RoadSense to Azure Container Apps (manual version of what the
# CI/CD pipeline will do). Re-runnable: `az containerapp create` updates an existing app.
#
# Prerequisites: infra/azure-setup.sh has run (resource group + Cosmos DB exist), and the
# image has been pushed to GHCR as a PUBLIC package:
#   docker buildx build --platform linux/amd64 -t ghcr.io/thio4/roadsense:<tag> --push .
# Usage: ./infra/azure-deploy.sh <image-tag>
set -euo pipefail

TAG="${1:?usage: azure-deploy.sh <image-tag>}"
RG="rg-roadsense"
LOCATION="swedencentral"
ENV_NAME="cae-roadsense"
APP="roadsense-api"
JOB="roadsense-collector"
IMAGE="ghcr.io/thio4/roadsense:$TAG"
COSMOS_ACCOUNT="cosmos-roadsense-$(az account show --query id -o tsv | cut -c1-8)"

# The containerapp commands live in a CLI extension.
az extension add --name containerapp --upgrade --only-show-errors

echo "==> Container Apps environment $ENV_NAME (creates a Log Analytics workspace, 5 GB/month free)"
# --environment-mode WorkloadProfiles: the preview CLI extension otherwise defaults to the new
# "Express" mode, which does not support Jobs (ExpressEnvironmentResourceNotSupported).
# The Consumption workload profile is the free, scale-to-zero one.
az containerapp env create --name "$ENV_NAME" --resource-group "$RG" --location "$LOCATION" \
  --environment-mode WorkloadProfiles -o none

# Read the database settings from Azure at deploy time: nothing is typed by hand, nothing
# is stored in the repo. The key becomes a Container Apps *secret*, referenced by env var.
COSMOS_ENDPOINT=$(az cosmosdb show --name "$COSMOS_ACCOUNT" --resource-group "$RG" --query documentEndpoint -o tsv)
COSMOS_KEY=$(az cosmosdb keys list --name "$COSMOS_ACCOUNT" --resource-group "$RG" --query primaryMasterKey -o tsv)
ENV_VARS=(COSMOS_ENDPOINT="$COSMOS_ENDPOINT" COSMOS_DATABASE=roadsense COSMOS_KEY=secretref:cosmos-key LOG_LEVEL=INFO)

echo "==> API: $APP  <- $IMAGE"
# --min-replicas 0: scale to zero when idle = no compute cost. 0.25 vCPU / 0.5 GiB is the
# smallest size and plenty for this API.
az containerapp create --name "$APP" --resource-group "$RG" --environment "$ENV_NAME" \
  --image "$IMAGE" --target-port 8000 --ingress external \
  --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
  --secrets cosmos-key="$COSMOS_KEY" --env-vars "${ENV_VARS[@]}" \
  -o none

echo "==> Collector job: $JOB  every 30 min"
# Same image, different command. A job runs to completion; exit code != 0 = failed run.
az containerapp job create --name "$JOB" --resource-group "$RG" --environment "$ENV_NAME" \
  --image "$IMAGE" --trigger-type Schedule --cron-expression "*/30 * * * *" \
  --replica-timeout 600 --replica-retry-limit 1 --parallelism 1 --replica-completion-count 1 \
  --cpu 0.25 --memory 0.5Gi \
  --secrets cosmos-key="$COSMOS_KEY" --env-vars "${ENV_VARS[@]}" \
  --command roadsense-collector collect \
  -o none

echo
echo "==> Deployed. Public URL:"
echo "https://$(az containerapp show --name "$APP" --resource-group "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
