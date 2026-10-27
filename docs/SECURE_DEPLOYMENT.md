# Secure backend deployment preparation

## Zero-cost candidate (supersedes provider-selection gaps below)

P0 is 0 EUR recurring owner infrastructure cost. GitHub Actions is the proposed production
orchestrator; n8n is **OPTIONAL / DEMO / USER-PROVIDED EXTERNAL ORCHESTRATOR**. No deployment
is performed. [Zero-cost design, exact setup and remaining gates](ZERO_COST_DEPLOYMENT.md)
selects Render Free + Neon Free and private build-time delivery via Dockerfile.zero-cost.
The original Dockerfile remains the mount-based alternative. Build secrets never enter
layers; verified model files in the provider's private image are root-owned/read-only to
the non-root runtime. Independent runtime pin and trusted loader checks remain mandatory.
Local Docker/WSL are unavailable; CI synthetic Linux smoke does not validate real-model RAM.
The historical audit and preparation baseline below remain evidence, not activation instructions.

Provider-neutral preparation only: **no public deployment is approved or performed**.
No provider/account/domain was selected or provisioned, no paid resource was created and no
tunnel, firewall, reverse proxy or n8n activation was performed.

## Audit at baseline 502f13b

| Surface | Verified baseline / design |
| --- | --- |
| Startup | app/main.py loads the model once in lifespan, initializes lazy repositories and closes the DB pool |
| Model | Existing ModelService/trusted loader, external manifest pin, ordered contract and verified bytes |
| Artifact storage | Protected development copy outside Git; no personal paths or local credential store belong in an image |
| Databricks | Read-only OAuth M2M, session identity check and F06 budgets; no PAT/personal CLI fallback |
| PostgreSQL | Private SecretStr DSN, bounded lazy pool/timeouts, explicit Alembic migration |
| n8n | Private outbound webhook config and inactive Cloud exports; no account/Admin API access |
| HTTP exposure | Baseline lacked inbound auth, rate/body limits, CORS and host middleware |
| Health | No expensive dependency query at health/readiness; configuration flags are not dependency availability |
| Proxy/logging | No explicit proxy target; source driver logs suppressed, no existing request audit middleware |
| Deployment | No Dockerfile or provider-specific configuration existed |
| Python | Project supports 3.11+; new container pins Python 3.12 and existing reviewed package versions |

## API separation and service authentication

Only GET /health and reduced GET /ready remain anonymous. /predict, /predict/batch,
/predictions/current, /predictions/current/persist, /predictions/history and /model/info require
**X-RMI-Service-Key** in every environment, including local/test. No anonymous inference is
enabled while future public-client authorization is undefined. Existing tests now explicitly
configure/send a synthetic service key; there is no test-mode authentication bypass.

N8N_SERVICE_API_KEY is SecretStr, 32–256 URL-safe characters. Supply a strong random value
through protected runtime secret injection. It must differ from N8N_WEBHOOK_SECRET; reuse is
rejected. Neither is a n8n administrative key. Auth uses timing-safe comparison before body
buffering/parsing. Missing/wrong keys return 401; missing/invalid server credential returns
generic 503. No secret value/name, URL or rejected header is reflected in errors.

The future public frontend must use separately authenticated/authorized public FastAPI
functions, never this service key, webhook secret or DB/workload credentials. A user/session/
token model, authorization and user-specific quotas remain deployment/product gaps.

## Production fail-closed configuration

[Production env template](../ops/backend/.env.example) is intentionally incomplete and cannot
start as supplied. ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS are JSON lists. Default hosts allow
only local development/test names. Production requires explicit DNS hosts without wildcard,
local/placeholder suffixes or ports; no real domain is invented here.

ENVIRONMENT=production requires a valid distinct service key, explicit hosts, absolute model
path/root and a 64-character external manifest digest. Databricks credentials must be M2M
credentials injected for the runtime, not the operator's Windows Credential Manager target
or a personal token. Configured PostgreSQL must use sslmode=verify-full; enabled persistence
also requires a DSN. Configuration failures use fixed messages without interpolating settings.
Missing/untrusted model files never cause fallback to a synthetic model.

Production docs/Redoc/OpenAPI URLs are disabled. Model metadata is service-protected and keeps
its existing allowlist. URL/secret settings are never included in readiness or model info.

## HTTP controls, CORS and proxy policy

REQUEST_MAX_BYTES defaults to 262144, maximum 1 MiB. Declared lengths and actual chunks are
checked before JSON parsing, including absent/chunked Content-Length. Oversize bodies return
413; invalid/ambiguous framing is rejected. The inference max batch remains 100. The edge
must additionally enforce body/header timeouts, connection limits and matching size caps.

Global per-process sliding-window budgets default to 10 inference requests, 2 persistence
writes and 60 reads per 60 seconds. Configure RATE_LIMIT_INFERENCE/WRITE/READ and
RATE_LIMIT_WINDOW_SECONDS. Each category retains at most its configured limit (maximum 1000
timestamps); there is no unbounded client dictionary. Exhaustion returns sanitized 429 and
Retry-After. GET /health is exempt for cheap liveness. Auth failures are rejected before costly
work. This is a shared capacity budget, not per-user fairness, brute-force or DDoS protection;
appropriate edge rate limiting is still required before exposure.

The limiter never uses client IP, X-Forwarded-For or client-provided request IDs, so spoofing
them cannot create fresh buckets. The production server disables proxy-header trust. No
implicit proxy count/CIDR or wildcard trust is configured. If client-based limits are added
later, validate explicit trusted proxy CIDRs and the complete header chain. No Redis is added.

CORS defaults empty/disabled; configured origins must be exact, HTTPS in production and never
wildcard. Credentialed browser CORS is disabled. Content-Type is allowed cross-origin; the
service key is deliberately not a browser CORS header. CORS is not authentication and no
future Google AI Studio origin is invented. Host validation uses the actual Host allowlist,
rejects malformed/duplicate hosts and ignores X-Forwarded-Host. Trailing-slash redirects are
disabled rather than manufacturing scheme-dependent redirects behind a proxy.

Responses add nosniff, Cache-Control=no-store, Referrer-Policy=no-referrer and a generated
X-Request-ID. Logs contain that ID, known endpoint name (otherwise unmatched), method, status,
latency and sanitized category. No raw URL/query, body, header, SQL, DSN, client ID, model path
or source rows are logged. Unexpected exceptions return generic errors without traceback.
No CSP is added for a JSON API.

## Liveness versus readiness

/health is liveness only. Anonymous /ready returns only status and 200/503 for a trusted loaded
operational model. A valid service key returns the detailed flags n8n needs: model_ready,
artifact_integrity, workload_identity_configured, database_configured and
prediction_persistence_enabled. These configuration/model flags do not prove dependency
availability or source freshness. Provider probes must not repeatedly query Databricks/DB.
Perform explicit bounded dependency smoke separately. The container healthcheck is liveness,
not model/dependency readiness; configure traffic readiness separately at the provider.

## Server, worker budget and HTTPS

Use the production entry point, not --reload:

```powershell
python -m scripts.serve --host 127.0.0.1 --port 8000
```

It requires production environment and uses exactly **one Uvicorn worker**, no proxy-header
trust/access logs/server banner, and bounded incomplete HTTP headers. F06 concurrency, the DB
pool, model lock and HTTP budgets are per process: additional workers/replicas multiply them.
Do not scale until coordinated query/rate budgets and connection capacity have been designed.

Terminate TLS at a selected managed platform or explicit reverse proxy. Public traffic must
be HTTPS only; redirect/disable HTTP and set HSTS at the verified HTTPS edge. The application
does not invent certificates or trust client X-Forwarded-Proto for HTTPS/HSTS decisions.
Keep backend listeners private and reachable only through the approved edge.

## Container and artifact delivery

[Dockerfile](../Dockerfile) pins an official Python 3.12 slim image by immutable digest. It
installs reviewed binary wheels in a builder and runs as UID/GID 10001 with root-owned code.
No compiler is installed. Runtime versions match existing development pins, including numpy,
pandas, scipy and sklearn. The deny-by-default [.dockerignore](../.dockerignore) admits only
application code, pinned requirements and selected server scripts. It excludes models, local
env/credential stores, source exports and DB data. No n8n Docker Compose is introduced.

```powershell
docker build -t rmi-backend:review .
```

Docker is unavailable locally: image build/run have static validation only. No container or
host port was started/published. The Docker command binds a private container port, not an
approved public endpoint. Native build, dependency and real artifact smoke remain required.

The mount-based option delivers the approved real model through private artifact storage
and a **read-only runtime mount**. The zero-cost option instead uses a verified private
build-time bundle, root-owned and read-only to the runtime. The service must not own or
write the model/config root in either production design.
Use separate owner/admin permissions, no symlinks/reparse points or group/world-write bits,
and only the necessary read access for the runtime UID. Configure MODEL_ARTIFACT_ROOT/PATH
for that mount. Supply the approved manifest pin independently through protected configuration;
do not auto-approve a downloaded bundle by hashing its own manifest. F02 checks regular files,
sizes, external pin, payloads, contract/sklearn version and the same bytes before joblib.load.

Artifact distribution, mount/ownership enforcement and loading the Windows-trained artifact
inside Linux remain provider-dependent requirements. No external infrastructure is invented
and no real/synthetic model binary is copied into Git/image. No training is performed.

## PostgreSQL, Databricks and runtime identity

The local validation DB is not a production database. Production needs managed/dedicated
PostgreSQL, verified TLS/CA, private access (no unrestricted public DB port), backups/restore
tests, connection limits and protected DSN storage. Runtime role: CONNECT, schema USAGE,
SELECT/INSERT and only necessary identity-sequence access. A separate migration role owns DDL;
runtime must have no CREATE/ALTER/DROP/UPDATE/DELETE/TRUNCATE, superuser or general ownership.
Retain connect/pool/statement/lock timeouts. Run Alembic explicitly with the migration role,
never automatically at API startup. This PR provisions no production DB or roles.

Databricks keeps the dedicated read-only workload identity, protected scoped client credentials,
SQL warehouse CAN USE and the existing approved feature-table SELECT grants. No PAT, personal
CLI fallback, Bronze/Gold expansion or write permission is introduced. Session identity checks
and query timeout/cancel/concurrency/row/byte budgets remain unchanged.

Use a dedicated non-admin OS/service identity with no model ownership or indiscriminate
secret-store access. Grant only scoped required credentials; do not mount the operator's
Windows profile or credential store. Provider-specific secret/runtime identity setup remains
pending because no deployment target/account configuration is available or used.

## n8n setup and remaining gate

In every HTTP Request node, bind Generic Credential Type → Header Auth manually in n8n Cloud:
Name=X-RMI-Service-Key; Value from N8N_SERVICE_API_KEY. No credential ID/value is exported.
Missing binding fails instead of making anonymous calls. The separate webhook credential
continues to use X-RMI-Orchestration-Key/N8N_WEBHOOK_SECRET; do not reuse it for API service auth.

Before the later Cloud smoke: select/configure secure HTTPS hosting, restricted runtime
identity, production DB/TLS/secrets, approved artifact delivery, native image/model smoke,
explicit host allowlist and the n8n service credential. Do not publish n8n, create a frontend,
tunnel or public backend as part of this PR. Historical local validation does not substitute
for the deployment checks. No resource costs are incurred.

References: [Uvicorn settings](https://www.uvicorn.org/settings/),
[Starlette middleware](https://www.starlette.io/middleware/).
