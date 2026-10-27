# n8n primary: Community on OCI Always Free

**SELECTED / DEPLOYMENT PREPARED / NOT YET PROVISIONED**.
See [OCI deployment](oci/README.md) and [backup/restore](oci/BACKUP_RESTORE.md).
Primary workflow: 30 minutes, bounded warm-up and writes, optional history.
GitHub Actions is fallback only; **ONLY ONE scheduler active at a time**.
Make Free is secondary at degraded cadence; Retool is an optional future operations UI.
Existing Cloud integration remains available and untouched; no paid subscription is required.

## Workflow artifacts (Community; Cloud manual compatibility)

Existing development workspace: `m-cavo.app.n8n.cloud`. No account access or Admin API key is needed by this repo.

- `workflows/rome_mobility_orchestration.json`: inactive manual/schedule persistence workflow.
- `workflows/rome_mobility_webhook_boundary.json`: inactive native Header Auth/ACK boundary.

Import manually from the Community editor (or existing Cloud workspace for development). Configure the non-secret FastAPI Configuration node
and bind a private Header Auth credential to the Webhook node in the editor; exports carry
neither values nor account credential IDs. Keep both unpublished/inactive.

[Precise import, configuration, security and pending runtime steps](../../docs/N8N_CLOUD_ORCHESTRATION.md).

OCI Compose is prepared only; no local n8n service is started. No administrative API,
direct application DB/Databricks access or workflow shell/Code node.
The webhook only acknowledges a minimal event and cannot call back into FastAPI. The separate
schedule uses existing operation endpoints. Cloud cannot securely reach the current local
backend; no tunnel or temporary Internet exposure is authorized by these artifacts.
