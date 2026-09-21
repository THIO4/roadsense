# Cleanup checklist (run after the course is graded)

Goal: leave nothing that can ever bill. Azure groups everything under a *resource group*,
so deleting it removes all resources at once.

- [ ] `az group delete --name rg-roadsense --yes` (removes Container Apps environment, API app, collector job, Cosmos DB, Log Analytics)
- [ ] Verify in the portal: Cost Management shows EUR 0 and no resources remain
- [ ] Delete the GitHub OIDC federated credential / app registration in Entra ID
- [ ] Remove GitHub repository secrets (AZURE_*)
- [ ] Optionally delete the GHCR package
