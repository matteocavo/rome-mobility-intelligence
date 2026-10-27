# n8n Cloud workflow artifacts

Target workspace: `m-cavo.app.n8n.cloud`. No account access or Admin API key is needed by this repo.

- `workflows/rome_mobility_orchestration.json`: inactive manual/schedule persistence workflow.
- `workflows/rome_mobility_webhook_boundary.json`: inactive native Header Auth/ACK boundary.

Import manually from the Cloud editor. Configure the non-secret FastAPI Configuration node
and bind a private Header Auth credential to the Webhook node in the editor; exports carry
neither values nor account credential IDs. Keep both unpublished/inactive.

[Precise import, configuration, security and pending runtime steps](../../docs/N8N_CLOUD_ORCHESTRATION.md).

No Docker Compose, local n8n, administrative API, direct DB/Databricks access or shell/Code node.
The webhook only acknowledges a minimal event and cannot call back into FastAPI. The separate
schedule uses existing operation endpoints. Cloud cannot securely reach the current local
backend; no tunnel or temporary Internet exposure is authorized by these artifacts.
