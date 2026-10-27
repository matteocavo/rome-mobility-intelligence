# n8n Cloud orchestration

**LOW-CODE/NO-CODE ORCHESTRATOR: SELECTION PENDING**. n8n is an
implemented candidate low-code integration; production role pending zero-cost selection.
A meaningful low-code/no-code layer remains required, with the primary orchestration role
when technically sustainable at 0 EUR/month. A paid n8n Cloud subscription cannot be mandatory.
**GitHub Actions: zero-cost fallback scheduler**, opt-in only, with bounded cold-start handling.
Existing n8n code, inactive exports, service authentication and webhook boundary are retained;
accounts/workflows are not activated. The 15-minute example is not a selected production
cadence. Do not enable concurrent orchestrators. No n8n Community, Make or Retool selection
is made here; evaluate candidates in ZERO-COST LOW-CODE ORCHESTRATION SELECTION. [Zero-cost design](ZERO_COST_DEPLOYMENT.md).

## FastAPI service authentication

All HTTP Request nodes require Generic Credential Type → Header Auth, configured manually
with Name=`X-RMI-Service-Key`, Value from the private backend `N8N_SERVICE_API_KEY`.
No credential ID/value is exported. Missing binding must be resolved before execution.
This inbound API key is distinct from the outbound webhook secret below; reuse is rejected.
Operational endpoints and full /ready require service auth. Anonymous /ready is reduced and
cannot satisfy the workflow guard. Never give the service credential to the frontend.
[Production configuration and remaining HTTPS gate](SECURE_DEPLOYMENT.md).

Target workspace: `m-cavo.app.n8n.cloud`. The operator imports/configures workflows manually.
This implementation does not access the account and never asks for an administrative API key.
There are no n8n Admin API calls, Docker Compose files, global npm installs or local n8n service.

## Two independent flows, no callback loop

`Rome Mobility - Prediction Orchestration` is the main manual/schedule template:
15-minute Schedule Trigger → trusted FastAPI Configuration → health/ready checks →
POST /predictions/current/persist?limit=100 → inspect response →
GET /predictions/history?limit=10 → compact summary.
The workflow is inactive/unpublished by default, timezone Europe/Rome. API timestamps remain UTC.

`Rome Mobility - Authenticated Integration Boundary` is a separate webhook template:
POST Webhook with native Header Auth → validate minimal event → constant ACK 202 or rejection 400.
It makes **no callback to FastAPI** and does not trigger persistence. Its ACK means only that
the authenticated minimal event was accepted, not that predictions were generated or saved.
This prepares the future server-to-server boundary without introducing an unauthenticated
public trigger, duplicate persistence path or FastAPI → n8n → same-FastAPI-endpoint loop.

The backend N8nClient is available for future internal integration but is not called from
existing routes, startup, inference or persistence. No new HTTP route exposes it. A future
authorized application route can use it after authentication/rate limiting is designed.
No ML/threshold/SQL/contract/idempotency logic moves into n8n. Databricks and PostgreSQL remain
behind FastAPI; n8n receives no credentials for them and has no direct source/database nodes.

## Server-side client configuration

All settings are absent by default:

- N8N_WEBHOOK_URL: private full webhook URL, represented as SecretStr.
- N8N_WEBHOOK_SECRET: private URL-safe random value (32–256 characters), SecretStr.
- N8N_WEBHOOK_ALLOWED_HOST: exact workspace hostname configured by the server operator.
- N8N_WEBHOOK_TIMEOUT_SECONDS: default 5, bounded between 0.1 and 10 seconds.

Configure them privately through the backend process environment/protected configuration;
do not paste values into chat, docs, Git, frontend code or workflow exports. Set the allowed
host to the intended Cloud workspace, never a wildcard. URL/secret are not returned by
/ready, /model/info or OpenAPI and are not logged. No n8n administrative credential is accepted.

The client validates HTTPS, exact configured `*.app.n8n.cloud` workspace hostname, standard
HTTPS port and a simple /webhook/ or /webhook-test/ path. It rejects userinfo, query strings,
fragments, whitespace, alternate ports, admin paths and untrusted hosts. Explicit localhost
HTTP mocks are allowed only under ENVIRONMENT=test. Normal development has no HTTP exemption.
The public request cannot supply a URL, payload, header or host: the client method accepts no
arguments. The allowlist is server configuration, not a general-purpose proxy parameter.

Requests use POST with X-RMI-Orchestration-Key, no inherited proxy, TLS verification and no
redirect following. There is no automatic retry in this client. Only a bounded 64 KiB response
with status 202 and exactly `{"accepted":true}` is accepted. Errors/timeouts omit remote
diagnostics and secrets. Return value is an acknowledgement with the server-generated request ID.
Connection/socket timeout and bounded response are not a distributed exactly-once guarantee.

Outgoing payload contains only event=`prediction_orchestration_requested`, generated request_id
and generated_at UTC. No raw features, prediction rows, DSN, SQL, artifact path, source warehouse
identifier or model credential is sent to the webhook. Native Header Auth authenticates before
workflow actions; the workflow then rejects extra payload fields and malformed identifiers/time.

## Manual Cloud import

1. Sign into the workspace yourself; open Workflows and create a new workflow.
2. Use Import from File and select
   [rome_mobility_orchestration.json](../ops/n8n/workflows/rome_mobility_orchestration.json).
3. Keep it unpublished/inactive. Edit **FastAPI Configuration** and set its RMI_API_BASE_URL
   field to the future secure HTTPS backend base URL, without trailing slash/path prefix.
   It is empty by default and the graph rejects missing, local or placeholder destinations
   before any HTTP call. This Set-node configuration works without plan-dependent Cloud variables.
4. Do not publish the schedule. Confirm the 15-minute interval and Europe/Rome timezone.
   Bind the dedicated API Header Auth credential to every HTTP node before execution;
   never use the n8n administrative key or reuse the webhook secret as backend auth.
5. Create/import a second workflow using
   [rome_mobility_webhook_boundary.json](../ops/n8n/workflows/rome_mobility_webhook_boundary.json).
6. In its Webhook node, keep Authentication=Header Auth. Create/select a **Header Auth**
   credential privately: Name=`X-RMI-Orchestration-Key`, Value equal to the backend secret.
   The export deliberately has no credential ID or secret. Until credential binding is complete,
   the authenticated boundary is not ready; do not switch Authentication to None.
7. Keep the boundary unpublished. Use Listen for Test Event only for a deliberate authenticated
   webhook test, copying the test URL privately into N8N_WEBHOOK_URL in the backend process.
   Publishing/production webhook registration is a separate operator action, not part of import.

No import was performed by this agent. Account configuration, native authentication behavior
and actual import compatibility still need manual verification. No administrative API/key is
required for these steps. Never export credentials or pinned execution data back to Git.

## Connectivity restriction

**n8n Cloud cannot securely reach local FastAPI yet.** A Cloud HTTP node's localhost refers
to its Cloud runtime, not the operator's computer. A secure reachable backend deployment and
appropriate authentication/reverse proxy are prerequisites to the real schedule smoke.
Do not expose the local backend, open a firewall port or create ngrok/cloudflared/public
tunnels to make this test pass. No backend deployment or tunnel was created or approved here.
The configured Cloud workflow URL guard accepts HTTPS DNS backend hosts, not localhost/IPs or
placeholder .invalid/.local/.internal targets. Server-side configuration is trusted operator
input; this graph guard is not a general network firewall or DNS-rebinding defense.

## Ready checks, retry and summaries

Health must return 200/status=ok. Ready must return 200 plus model_ready=true,
artifact_integrity=verified, workload_identity_configured=true, database_configured=true and
prediction_persistence_enabled=true. A failure stops with a controlled summary, no readiness
retry and no write. These configuration flags do not establish a new source freshness SLA.

Persistence is POST without body, limit=100. Only HTTP 503/504 retry, at most twice, after
30 then 60 seconds. HTTP 422 and other statuses do not retry; transport failures stop safely.
Built-in indiscriminate HTTP retry is disabled. Persistence request timeout is 140 seconds;
health/ready/history use ten seconds, with a 600-second workflow deadline. FastAPI retains its
independent SQL deadline, cancellation request and concurrency budgets. Cancellation requests
are not a guarantee of immediate remote termination.

A confirmed write is followed by ten history rows at most. History failure yields
history_followup_failed with persistence_succeeded=true and the confirmed write counts;
it never repeats the write. Same source/model replay with inserted=0/existing=N is success_idempotent,
not a failure. Deduplication remains the backend PostgreSQL constraint. A later retry can see
a newer current source feed; the summary reports the successful watermark and does not claim
exactly-once delivery or a frozen source snapshot.

Final summary contains UTC execution timestamp, source watermark, evaluated/inserted/existing,
model version, threshold, history row count, status, retry count, HTTP status and confirmation
of persistence. Unknown counts are null, not false zero-success claims. No raw history rows,
headers, features or diagnostics are copied into the terminal Set item. Controlled failure
branches can technically complete in n8n: inspect final operational status, not only completion.
The schedule is inactive; avoid overlapping manual runs or publishing until deployment controls
are in place. No distributed scheduler/lock is introduced in this PR.

## Tests and data handling

Client tests use mock transport: unconfigured/invalid hosts and schemes, Header Auth, minimal
payload, no URL override, bounded response, disabled redirects/proxy and sanitized errors/timeouts.
Workflow tests validate inactive JSON, endpoint allowlist, native Header Auth configuration,
no forbidden nodes/credential data and bounded retries. A controlled Node.js interpreter evaluates
the actual export expressions/branches with synthetic responses and simulated waits. It does
not execute the n8n engine or prove Cloud import, authentication or real timing.

Workflow settings disable success/error/manual/progress execution-data saving. Confirm the
Cloud account honors those settings before tests: Webhook node inputs can contain the secret
header, and history HTTP nodes receive ten rows transiently. Do not pin, export or share node
input/output. The acknowledgement never echoes input headers/body, and the terminal schedule
summary drops history rows. Account retention/storage remains an operator responsibility.

```powershell
python -m scripts.validate_n8n_workflow
pytest tests/test_n8n_client.py tests/test_n8n_workflow.py -q
```

No account access, real webhook call, Cloud import or Cloud end-to-end smoke was performed.
The schedule smoke remains pending secure backend deployment. No credentials are required by CI.

## Future public application boundary

Google AI Studio/public frontend → authenticated/rate-limited FastAPI → ML/PostgreSQL services
and optional server-side n8n integration. Public users never receive the webhook secret,
administrative key, database/workload credentials or unrestricted workflow controls, and never
call n8n Admin API. No frontend or Google AI Studio implementation is included.

Public deployment remains unapproved. Separate OS service account, protected model/credential
storage, production PostgreSQL roles/infrastructure, API authorization/rate limiting,
HTTPS/reverse proxy, coordinated budgets for multiple processes, Cloud retention/backups and
monitoring/alerting are future deployment work. No training, model/threshold update, schema
change, Databricks write or Job/schedule/pipeline change is part of this integration.

References: [n8n Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/),
[Webhook Header Auth](https://docs.n8n.io/integrations/builtin/credentials/webhook/).
