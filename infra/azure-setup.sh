#!/usr/bin/env bash
# Create the RoadSense cloud database on Azure (free tier). Idempotent: safe to re-run.
#
# Prerequisites: az login  (Azure for Students subscription selected)
# Usage:         ./infra/azure-setup.sh
# Cleanup:       see docs/cleanup.md  (az group delete --name rg-roadsense)
set -euo pipefail

# --- names: change these once, everything else derives from them ---
RG="rg-roadsense"
LOCATION="northeurope"                 # Ireland: closest region with all services enabled
COSMOS_ACCOUNT="cosmos-roadsense-$(az account show --query id -o tsv | cut -c1-8)"  # must be globally unique
DATABASE="roadsense"

echo "==> Registering resource providers (one-time per subscription, free)"
# Azure disables most services until you opt in. DocumentDB = Cosmos DB, App = Container Apps.
for ns in Microsoft.DocumentDB Microsoft.App Microsoft.OperationalInsights; do
  az provider register --namespace "$ns" --wait
done

echo "==> Resource group $RG"
# A resource group is a folder for resources. Deleting it deletes everything inside -
# that is our EUR 0 guarantee at the end of the course.
az group create --name "$RG" --location "$LOCATION" -o none

echo "==> Cosmos DB account $COSMOS_ACCOUNT (takes ~5 min the first time)"
# --enable-free-tier: first 1000 RU/s + 25 GB free forever. Only ONE per subscription.
# Session consistency is the default and fine for us. No geo-replication = no extra cost.
az cosmosdb create \
  --name "$COSMOS_ACCOUNT" --resource-group "$RG" \
  --locations regionName="$LOCATION" failoverPriority=0 isZoneRedundant=False \
  --enable-free-tier true \
  --default-consistency-level Session \
  -o none

echo "==> Database $DATABASE with 1000 RU/s SHARED across containers"
# Throughput set at database level is shared by all its containers. 1000 RU/s = exactly
# the free-tier allowance. Do NOT also set throughput per container - that would bill.
az cosmosdb sql database create \
  --account-name "$COSMOS_ACCOUNT" --resource-group "$RG" \
  --name "$DATABASE" --throughput 1000 -o none

echo "==> Containers"
az cosmosdb sql container create \
  --account-name "$COSMOS_ACCOUNT" --resource-group "$RG" --database-name "$DATABASE" \
  --name stations --partition-key-path /id -o none
# --ttl 604800: documents auto-expire after 7 days -> history never grows unbounded.
az cosmosdb sql container create \
  --account-name "$COSMOS_ACCOUNT" --resource-group "$RG" --database-name "$DATABASE" \
  --name observations --partition-key-path /station_id --ttl 604800 -o none

echo
echo "==> Done. Put these in your .env (the key is a SECRET - never commit it):"
echo "COSMOS_ENDPOINT=$(az cosmosdb show --name "$COSMOS_ACCOUNT" --resource-group "$RG" --query documentEndpoint -o tsv)"
echo "COSMOS_KEY=$(az cosmosdb keys list --name "$COSMOS_ACCOUNT" --resource-group "$RG" --query primaryMasterKey -o tsv)"
echo "COSMOS_DATABASE=$DATABASE"
