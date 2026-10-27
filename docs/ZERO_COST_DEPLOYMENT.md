# Zero-cost runtime preparation

P0: recurring infrastructure cost charged to the owner must be **0 EUR**. Quota
exhaustion, cold starts, autosuspend and temporary unavailability are acceptable;
trials, metered billing and mandatory paid orchestration are not. This is a candidate
architecture, not a deployed service or an uptime SLA. No resources, accounts,
billing, model uploads, production secrets or databases are created by this change.

## Target and activation boundary

**LOW-CODE/NO-CODE ORCHESTRATOR: SELECTION PENDING**.
**GitHub Actions: zero-cost fallback scheduler**.

A meaningful low-code/no-code layer is a P0 requirement alongside mandatory infrastructure
cost of **0 EUR/month**. It should be the primary orchestrator if technically sustainable.
The next task, **ZERO-COST LOW-CODE ORCHESTRATION SELECTION**, evaluates n8n Community,
Make Free or equivalent before choosing. No candidate is selected in this PR.

```text
Databricks Free -> FastAPI -> PostgreSQL Free
                     ^
                     | HTTPS: authenticated operational orchestration
LOW-CODE / NO-CODE ORCHESTRATOR (selection pending)
  candidates: n8n Community / Make Free / equivalent

Fallback only: GitHub Actions -> HTTPS FastAPI
Future: Google AI Studio / public frontend -> FastAPI public/user-authenticated layer

Private Neon Object Storage -> Render BuildKit secret -> bounded verified bundle
  -> root-owned model in Render's private built image -> trusted runtime loader
```

n8n is an **implemented candidate low-code integration; production role pending zero-cost
selection**. Its client, inactive workflows, documentation, service authentication and
webhook boundary remain intact. A paid n8n Cloud subscription cannot be required. Retool
is not implemented or selected; it may be considered only as a future operational/admin UI.
Do not run competing schedulers concurrently. No n8n account, Admin API, PAT, direct database
or warehouse credential belongs in the Actions fallback. Future frontend hosting must also
be free, with user auth separate from the service key. Orchestrator, Databricks, FastAPI,
PostgreSQL and model storage/delivery each have a mandatory 0 EUR/month infrastructure target.

The fallback workflow runs only on main and only after the operator sets repository variable
`RMI_ORCHESTRATION_ENABLED=true`. This PR does neither. Required Actions repository secrets:
`RMI_API_BASE_URL` (HTTPS origin only) and `RMI_SERVICE_API_KEY`. Never put the service key
in a URL, logs, summary, repository variable, artifact or frontend. Checkout is necessary
for the reviewed stdlib client; its credentials are not persisted. No dependencies are
installed during scheduled runs. Permissions are contents:read only. Concurrency permits
one running job, with cancel-in-progress:false; timeout is 15 minutes. This prevents overlap
between this workflow's runs, not with independent manual clients/n8n.

## Schedule and failure semantics

Fallback cron `17,47 * * * *` UTC performs real persistence every 30 minutes when explicitly enabled.
This cadence does not select the future low-code production orchestrator or its schedule. To change
cadence, review the cron in `.github/workflows/persist-current-predictions.yml`; GitHub cron
does not interpolate repository variables. 15 minutes is not validated or required.
At 30 minutes there are 1,440 triggers/30-day month (1,488/31-day month). GitHub may delay/drop
scheduled jobs and disables schedules in inactive public repositories after 60 days.
Do not use keep-alive traffic to prevent Render sleep.

The client first checks /health, then authenticated /ready. Each stage has a 120-second
budget, at most three requests (15 seconds each) and waits 30/45 seconds. Health requires
HTTP 200/status=ok. Readiness requires HTTP 200/status=ready, model_ready=true,
artifact_integrity=verified, workload_identity_configured=true, database_configured=true,
prediction_persistence_enabled=true. These flags do not prove source freshness or dependency
availability. Health retries only 502/503/504/timeout; readiness also waits on an incomplete
200 response. 401/403 and other nonretryable statuses stop before a write.

POST /predictions/current/persist?limit=100 retries only 503/504 or transport timeout,
at most twice after 30/60 seconds. Other TLS/DNS/network errors fail rather than retrying a
write blindly. A timed-out request may already have committed: the existing database unique
constraint makes replay idempotent. A later attempt may read a newer current snapshot;
this is not exactly-once processing. Zero inserted plus N existing is success. Optional
history follow-up is disabled by default; its failure cannot repeat a confirmed write.
Only bounded integer counts, fixed status and retry count reach stdout. No response rows,
source errors, credentials or remote diagnostic text are logged. Redirects and proxy-env
inheritance are disabled; response bodies are bounded to 64 KiB.

## Free tiers and no-payment policy

| Component | Selected configuration | Owner recurring cost |
| --- | --- | --- |
| Actions fallback | Standard ubuntu-latest, public repository, opt-in only | 0 EUR |
| Primary low-code/no-code orchestrator | Selection pending; must meet zero-cost target | 0 EUR target |
| Render | Hobby + Free web service; no payment method, no paid disk/compute | 0 EUR |
| Neon PostgreSQL | Free only, one project, no paid upgrade | 0 EUR |
| Neon Object Storage | Same Free project, private | 0 EUR |
| Databricks | Existing Free workspace; no plan changes | 0 EUR (operator-provided existing plan) |
| n8n integration | Implemented candidate; production role pending selection; paid Cloud cannot be mandatory | 0 EUR mandatory target |

Render Free: 512 MB RAM, 0.1 CPU, 750 shared instance hours/month, sleep after 15 minutes
idle, approximately one-minute wake-up, ephemeral filesystem, no free persistent disk.
Hobby includes 5 GB/month outbound bandwidth. Without a payment method, excess usage can
suspend services/builds instead of billing. High service-initiated outbound traffic can
also cause suspension; accept unavailability rather than upgrade. Do not add a payment
method or enable paid compute, storage, registry, larger Actions runners or autoscaling.
Budget notifications alone are not hard caps.

Neon Free at review date 2026-10-27: 1 GB PostgreSQL/project, 100 CU-hours/project/month,
5-minute compute autosuspend, 5 GB Object Storage/project and **5 GB/month public egress
shared across products**. Choose fixed 0.25 CU where supported. About 112 direct connections
at that size greatly exceed the application's pool of two. With 48 wakes/day and roughly
five active minutes per wake, baseline compute is about 30 CU-hours/month at 0.25 CU,
plus query time, wake maintenance and other clients. Continuous activity would consume
about 180 CU-hours/30 days and exhaust the free allowance. No dependency health probes query
the DB repeatedly. Free quota exhaustion must stop work, not upgrade. Restore history is
six hours with a change-volume cap; automated long-term backups are not included. Do not
claim a durable backup policy has been implemented by this PR.

## Artifact delivery decision

| Pattern | Decision |
| --- | --- |
| Runtime HTTPS bootstrap | Implemented, disabled by default; unsuitable as the normal 30-minute Free path |
| Render private build with BuildKit secrets | **Preferred**, avoids storage download on spin-up |
| Actions builds/pushes a private GHCR image | Not selected; no registry/package/credentials are provisioned or account privacy settings verified |
| Model in public Git, image, Actions artifacts or public URL | Forbidden |
| Existing operator-provided read-only mount | Still supported with the original Dockerfile |

Use `Dockerfile.zero-cost` for the later **Git-backed Render** build. Render documents
securely stored built images and BuildKit secret mounts. Its Docker build args must never
carry credentials; use mounts only. Add two secret files manually later:

* `model-bootstrap.json`: JSON with `url`, `allowed_host`, optional `authorization`,
  optional `max_bytes` (up to 33554432) and `timeout_seconds` (up to 120, default 60).
  Prefer a short-lived authenticated S3 presigned HTTPS GET for the exact private bundle.
  The URL is a bearer credential: generate it privately outside Git and never log it.
  It must be refreshed before builds after expiry. Neon supports presigned object access.
* `model-manifest.sha256`: the previously approved independent checksums.json digest.
  Do not calculate approval from the downloaded source. At runtime separately set
  MODEL_ARTIFACT_MANIFEST_SHA256 to that approved value too.

Render's documented secret IDs replace punctuation with underscores, hence Dockerfile IDs
`model-bootstrap_json` and `model-manifest_sha256`. The deny-by-default build context excludes
secret files. Mounts never enter image layers; only the verified bundle is copied into the
final image. No source URL, auth credential or pin-file content is printed or copied. Runtime
does not need storage credentials. Render may also mount configured secret files at runtime;
therefore the presigned URL should be short lived. Do not use a long-lived storage write/admin
credential. Configuration storage remains in the provider trust boundary, not isolated from
a compromised provider account. No image is pushed to GHCR/Docker Hub or exposed publicly.

The standalone bootstrap is stdlib only, independent of FastAPI/sklearn. It accepts **gzip TAR
with exactly four root-level regular files**: checksums.json, pipeline.joblib, metadata.json,
contract.json. No nested directories, duplicate names, PAX metadata, traversal, absolute paths,
symlinks, hardlinks, devices or other members. Compressed download <=32 MiB; extracted file
total <=32 MiB; decompressed TAR including padding <=32 MiB + 10 KiB. HTTPS uses an exact
configured DNS hostname, no redirects, no inherited proxy, bounded socket/total transfer time.
This is trusted operator configuration, not a user-controlled downloader or an SSRF sandbox
against a compromised operator/DNS/network. No HTTP endpoint exposes the bootstrap.

Staging is on the destination filesystem, under a checked root without links/reparse points
or group/world-write bits. Existing operational bundles are never replaced. Manifest is
verified against the independent pin, then all payload hashes, before same-filesystem rename.
Failed downloads/extractions remove staging; no partial bundle is published. Bootstrap never
calls joblib. The existing loader rechecks trust and deserializes verified in-memory bytes only.

Build-time files are root-owned 0444 in a 0555 directory, read by UID/GID 10001. Runtime cannot
chmod them. Runtime delivery, if deliberately enabled on another platform, uses
MODEL_BOOTSTRAP_ENABLED, MODEL_ARTIFACT_SOURCE_URL (SecretStr), MODEL_ARTIFACT_SOURCE_HOST,
MODEL_ARTIFACT_SOURCE_AUTH (SecretStr), MODEL_ARTIFACT_MAX_BYTES and
MODEL_ARTIFACT_DOWNLOAD_TIMEOUT_SECONDS plus existing MODEL_ARTIFACT_ROOT/PATH/PIN.
The root must already exist and destination must not. Failure leaves /ready false. In this
mode runtime ownership permits chmod reversal; external digest, loader checks and absence of
artifact write APIs compensate, but do not isolate a fully compromised process/configuration.

## Downloads and egress

Real bundle total is 14,583,500 bytes (about 14.6 MB); TAR gzip actual size has not been
measured or uploaded. Conservatively assume no compression saving. Runtime download every
30 minutes would cost about **21 GB/month** of storage egress and is rejected for this cadence.
Build-time delivery costs zero object downloads per schedule execution. Estimate four fresh
builds/month = four downloads, about **58.4 MB/month**, plus DB egress. Ten fresh builds would
use about 146 MB. Restarts/spin-down reuse model-bearing deployed image layers; do not trigger
builds on scheduled persistence. Build cache may reduce downloads but is not a cost guarantee.
No upper bound is promised if the operator deploys without limit. An expired URL on a fresh
build fails closed; it must not fall back to public storage or unverified artifacts.

## Linux/memory validation gate

Local Docker and WSL are unavailable. CI adds a real Docker build and offline synthetic
container probe on Python 3.12, with --memory=512m, --cpus=0.1, read-only root, read-only
bundle mount, no network and one Uvicorn worker. No bundle, image, cache or runtime data is
uploaded as an Actions artifact/package. Synthetic fixtures are test-only; real training,
weights, threshold and metadata are unchanged. This does not prove the real bundle fits.

The probe reports process start/import/model/predict/batch RSS and peak RSS without input or
model contents. Current-scoring network path is intentionally not exercised. A later Linux
test with the approved real bundle must remain private and report only memory stages.
Prefer <=400 MiB, >450 MiB HIGH RISK, >=512 MiB FAIL; 400-450 MiB needs explicit margin review.
Windows baseline (~264 MiB peak) is not Linux evidence. Do not claim Render fit PASS before
the real Linux model and connector/scoring workload are measured. Metadata is parsed fully
into ArtifactMetadata and retains provenance dictionaries: 14.4 MB JSON can cause substantial
temporary and retained memory. Slimming it would change the pinned bundle; analysis only,
not performed here and not silently applied during delivery.
Inspection of serialized field sizes locates approximately 8.04 MB of compact JSON in
training_data_reference, versus ~28 KB in candidate_validation and ~7 KB in threshold_grid.
The larger 14.4 MB file also includes formatting. Removing formatting alone would require
updating the approved manifest and would not reduce the retained provenance object graph.
No metadata, manifest, model version or threshold is changed here.

## PostgreSQL retention design (not executed)

Use PostgreSQL verify-full plus trusted CA and the true DNS hostname. Separate migration
owner from runtime CONNECT/schema USAGE/SELECT/INSERT and necessary sequence USAGE. No DDL,
UPDATE/DELETE/TRUNCATE or ownership for runtime. Existing bounded pool/session timeouts remain.

History has 19 fields, primary key, natural unique key and two read indexes. Estimated typical
row+indexes is **1-2 KiB**, depending on ID lengths and page fill; 512-character field maxima
can make rows much larger. This is an estimate, not pg_total_relation_size measurement.
At 100 new rows every 30 min: 4,800/day, 144,000/30 days, roughly **141-281 MiB/month** before
bloat/WAL/other tables. At 15 min: 288,000/month, 281-563 MiB/month. Reserve at least half of
the nominal 1 GB for uncertainty and database overhead: 1-2 KiB typical rows imply roughly
50-100 days at 30 min, not an infinite history guarantee. Recommend **14 days initially**
(67,200 rows, ~66-131 MiB typical), review actual relation/index sizes, and consider 30 days
only after measurement. Long IDs or abnormal growth require shorter retention/stop ingestion.
Maintenance DELETE/retention needs a separate role and explicit future approval; no automatic
deletion, grants or database changes are implemented in this PR.

## Remaining deployment gates

1. CI Linux image/synthetic smoke must pass; approved real Linux bundle, peak RAM and
   connector/current-scoring memory remain unverified without uploading the real model.
2. Operator confirms Render no payment method/Free and Neon Free, private object delivery,
   provider-built image privacy and BuildKit behavior with a nonsecret synthetic source first.
3. Separately authorized private model upload, production DB/TLS/roles and scoped secrets;
   real read-only source + idempotent persistence smoke; retention/backup operational choice.
4. Complete ZERO-COST LOW-CODE ORCHESTRATION SELECTION before selecting the primary
   orchestrator. Configure Actions secrets/opt-in only if fallback use is explicitly chosen
   after secure deployment. Neither Actions nor n8n is activated by this PR.

## Official references (checked 2026-10-27)

* [GitHub standard runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
* [Scheduled events and limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
* [Render Free](https://render.com/docs/free), [compute](https://render.com/docs/compute-plans)
* [Render Docker BuildKit secrets](https://render.com/docs/docker-secrets)
* [Render image confidentiality guidance](https://render.com/docs/docker-secrets)
* [Neon current plans](https://neon.com/docs/introduction/plans)
* [Neon private storage authentication](https://neon.com/docs/storage/authentication)
* [Neon TLS](https://neon.com/docs/connect/connect-securely)
* [GHCR currently free, policy may change](https://docs.github.com/en/billing/concepts/product-billing/github-packages)

GHCR private containers currently have free storage/transfer and Render supports private
pulls with registry credentials. It is not selected because it introduces a registry token,
visibility/permission configuration and another model-bearing distribution boundary, none
verified/provisioned here. Public repository visibility must never imply public model package.
