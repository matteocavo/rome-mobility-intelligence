# n8n Community on OCI Always Free

**PRIMARY LOW-CODE ORCHESTRATOR: n8n Community Edition on OCI Always Free**

**SELECTED / DEPLOYMENT PREPARED / NOT YET PROVISIONED**

Mandatory recurring infrastructure cost: **0 EUR/month**. These assets do not provision
OCI, request a certificate, create a credential or start a service. Only use the commands
below after separate provisioning/deployment authorization. Make Free is a second choice
at degraded cadence; Retool is an optional future operations UI. GitHub Actions remains
the opt-in fallback, not the primary scheduler.

## OCI hard guardrails

Target: supported Ubuntu LTS ARM64 (e.g. 24.04), **VM.Standard.A1.Flex**, project allocation
maximum **2 OCPU**, initial **4 GB RAM**, persistent boot volume about **50 GB**, in an EU
home region if capacity is available. Console must explicitly show **Always Free-eligible**
for the shape and volume before creation. Never exceed the currently displayed entitlement
across the entire tenancy; existing allocations also count. **NO PAYG**, no account upgrade,
no paid shape, capacity reservation, trial-credit dependency or automatic paid fallback.
If the entitlement/price cannot be verified: STOP. No resource is created by this repository.

If **Out of host capacity** occurs: STOP, try another available availability domain in the
home region, or retry later. Do not upgrade or use a paid region/shape. OCI idle reclamation
can recover lightly used VMs; the HTTP-only scheduler may meet idle criteria. Do not generate
fake load or artificial keep-alives. There is no SLA. A lost VM does not justify relaxing P0.

## Minimal services and ARM64 evidence

Only n8n + Caddy. No extra database, Redis, AI sandbox, ML runtime, Terraform or Kubernetes.
SQLite is **n8n's internal metadata only**, not application prediction history. n8n calls
FastAPI only and receives no Databricks, application PostgreSQL or model-storage credential.

Both images have an immutable index digest and explicit `platform: linux/arm64` in
[compose.yaml](compose.yaml). [image-lock.json](image-lock.json) records the exact ARM64
child digests verified by anonymous Docker Registry v2 GET on 2026-10-27. n8n is 2.45.4;
Caddy is 2.11.7-alpine. CI uses a native standard GitHub ARM64 runner to validate Compose,
Caddy configuration and import/export the inactive synthetic/unconfigured workflow with
network disabled. No OCI account or live backend is involved. No floating latest tag.

Container limits: n8n 2 GiB / 1.5 CPUs; Caddy 256 MiB / 0.25 CPU, leaving OS headroom in
4 GB. This is a configuration budget, not a measured production VM result. n8n runs UID/GID
1000:1000, with read-only root, private writable data/cache/tmp, dropped capabilities and
no-new-privileges. Caddy has only NET_BIND_SERVICE; no Docker socket/daemon is exposed.

## Persistent host paths and secrets

Use [.env.example](.env.example) as the nonsecret schema; production copy belongs outside
Git at `/etc/rome-mobility-n8n/deployment.env`, root-owned 0600. Example paths:

| Host path | Container/use | Ownership / mode |
| --- | --- | --- |
| `/var/lib/rome-mobility-n8n/n8n` | `/home/node/.n8n`, SQLite/workflows/credentials | 1000:1000, 0700 |
| `/var/lib/rome-mobility-n8n/caddy-data` | `/data`, persistent TLS state | root:root, 0700 |
| `/var/lib/rome-mobility-n8n/caddy-config` | `/config` | root:root, 0700 |
| `/etc/rome-mobility-n8n/encryption.key` | read-only Compose secret | 1000:1000, 0400 |

Create directories explicitly on persistent disk before deploying; the n8n bind mount
refuses to auto-create missing paths. Mount the key file alone, not the operator home.
`N8N_ENCRYPTION_KEY_FILE` in deployment.env is a path, not the value. The file contains the
operator-generated **N8N_ENCRYPTION_KEY**, supplied with n8n's documented `_FILE` convention.
Generate privately outside Git and never print/paste/export it. Keep an independent secure
backup: loss can make credentials unrecoverable. Do not reuse the API service key.

Important: the pinned n8n version also writes its encryptionKey into `.n8n/config`, even
when supplied externally. Treat that directory as sensitive; it is not a credential-free
volume. The backup helper omits the key-bearing config and archives nonsecret settings
separately. Never upload raw directories, SQLite, credentials or backup archives to Git/CI.

## OS, firewall and TLS

Before starting containers, set SSH key authentication, disable SSH password login and root
SSH, and verify a second administrative session before closing the original. Restrict TCP
22 to the operator source IP/CIDR where feasible. Apply matching OCI security-list/NSG and
host firewall rules: TCP 443 for HTTPS; TCP 80 only for ACME HTTP challenge and HTTP redirect.
**Never expose TCP 5678** or Docker API ports. Docker forwarding can bypass simple UFW rules:
verify DOCKER-USER/forwarding policy as well as OCI ingress, not just INPUT rules. No UDP
443 is published. Outbound HTTPS to FastAPI and required OS/DNS/NTP traffic must work.

Use supported OS security updates, with controlled reboot windows and a recovery plan. Do
not grant general Docker-group access to untrusted users: Docker administration is host-root
equivalent. Keep the n8n owner setup inaccessible to other users until completed, then
require owner login. Restrict editor ingress to administrative sources when practical.
This schedule needs only outbound FastAPI access; the separate webhook boundary can remain
unpublished. No public, unauthenticated workflow editor is acceptable.

Set N8N_HOST to an owned bare DNS hostname, never a URL, port, IP or localhost. A free DNS
subdomain (for example DuckDNS) is sufficient; the assets do not hardcode a DNS provider or
require buying a domain. Point it to the VM and verify control before starting Caddy. Caddy
obtains/renews free certificates; DNS and network capacity still have to be verified. It
redirects HTTP to HTTPS. Certificate state persists across restarts to avoid unnecessary
issuance. CI validates configuration only and never issues a production certificate.

N8N_PROTOCOL=https, secure cookies, editor base URL and public webhook base URL all use that
hostname. N8N_PROXY_HOPS=1 trusts the sole Caddy hop on the private Compose bridge; do not add
untrusted proxies. The pinned n8n version uses N8N_WEBHOOK_URL; WEBHOOK_URL is also supplied
as a matching compatibility value (deprecated by n8n). Timezone is Europe/Rome. Do not use
the localhost-only container health probe URL as a public application URL.

Authorized future operator commands, from the repository root:

```sh
docker compose --env-file /etc/rome-mobility-n8n/deployment.env -f ops/n8n/oci/compose.yaml config --quiet
docker compose --env-file /etc/rome-mobility-n8n/deployment.env -f ops/n8n/oci/compose.yaml pull
# Only after account, DNS, key, owner-setup protection and firewall verification:
docker compose --env-file /etc/rome-mobility-n8n/deployment.env -f ops/n8n/oci/compose.yaml up -d
```

Do not run unredacted `config`/`inspect`/environment dumps in shared logs. Do not add paid
resources to make these commands succeed. Check N8N_HOST is not replace.invalid before up.

## Primary visual workflow

Import [rome_mobility_orchestration.json](../workflows/rome_mobility_orchestration.json), keep
unpublished/inactive and bind native Header Auth to **every HTTP node**:
Name=X-RMI-Service-Key, Value from the protected backend N8N_SERVICE_API_KEY. The export
intentionally has no credential ID/value; binding is manual. The API URL is empty by default
and rejected before any HTTP request. Enter only the approved HTTPS FastAPI origin in
FastAPI Configuration. FETCH_HISTORY is a boolean switch, true by default, not a new source.

The 30-minute workflow is visual Schedule -> health -> readiness -> persist -> optional
history -> minimal summary. No Code, shell, direct SQL/warehouse/model node is introduced.
Health: three 15-second attempts, Wait 30/45 seconds (~120 seconds total). Readiness: same
bounded pattern, only HTTP 200/status=ready with all required true flags and verified artifact
can reach persistence. Warm-up retries only 502/503/504 or recognized transport timeout;
readiness also waits for incomplete 200 flags. 400/401/403/413/422 stop immediately.
Each attempt has an explicit outcome/counter node and the graph is acyclic.

Persistence: maximum three 140-second requests, waits 30/60 seconds, retries only 503/504
or recognized ETIMEDOUT/ESOCKETTIMEDOUT/timeout message. Unknown transport/DNS/TLS errors
terminate without retry or diagnostic reflection. A timeout can mean a write already committed;
database uniqueness remains the idempotency boundary. Zero inserted and all existing is success.
Malformed 200 counts are rejected. Optional history failure yields degraded confirmed-write
summary and never traverses back to persistence. With history disabled, a terminal success
skips the GET. No path can fan out into duplicate writes. Full deadline: 840 seconds, below
the 30-minute schedule. This does not implement a distributed lock across other clients.

Success/error/manual/progress payload retention is disabled at workflow and instance level;
pruning defaults to 24h/100 records for any residual metadata. Wait nodes can retain transient
state; disable pinning and avoid viewing/exporting raw HTTP items. Summaries contain counts,
watermark/model ID, fixed status and retry count, no prediction rows, headers or diagnostics.
Controlled failure terminals may still appear green in n8n: inspect summary.status and
persistence_succeeded, not only the n8n execution result. No live import/smoke is claimed.

## ONLY ONE scheduler active at a time

* Normal: n8n primary published; `RMI_ORCHESTRATION_ENABLED` absent/false in GitHub.
* Failover: unpublish/stop n8n (including its old VM), confirm no execution is in flight,
  then explicitly enable the Actions fallback. If VM reachability is uncertain, isolate it
  at OCI or revoke/rotate its dedicated API credential before failover; otherwise STOP.
* Recovery: restore with all workflows unpublished; disable Actions, wait for its running
  run to finish, confirm no pending concurrent scheduler, then publish n8n once.

Do not enable both because persistence is idempotent: retries can read different snapshots.
Do not enable Make as an additional scheduler. OCI reclamation uses the same manual failover
procedure, never fake utilization to evade recovery policy. Existing n8n Cloud stays untouched.

## Backup, recovery, updates and observability

Follow [BACKUP_RESTORE.md](BACKUP_RESTORE.md). No paid backup/monitoring service is required.
Workflow JSON in Git is sanitized, while encrypted operator backups and the key stay outside
Git. No scheduled backup job is installed by this PR. Owner performs regular backup/restore
verification and maintains enough storage under Always Free limits.

Updates: backup -> read release/security notes -> intentionally update version AND index/ARM
digest evidence -> validate Compose and import offline -> smoke -> roll back if needed.
Never unattended major upgrades or automatic deploy from Dependabot. A downgrade can require
restoring the pre-upgrade SQLite snapshot; an image rollback alone is not a DB rollback.

Lightweight checks: `docker compose ... ps`, container health, `df -h`, free RAM, disk growth,
sanitized warning logs, summary failure state, last successful source watermark, VM reachability.
No paid agents. Disabled payload retention means no durable complete execution archive is
promised; record only minimal operational status privately and protect any UI screenshots.
Actions monitoring remains optional fallback support, never artificial anti-sleep traffic.

## Remaining gates

OCI account eligibility/capacity, separate provisioning authorization, persistent disk and
permissions, key generation, DNS/TLS/firewall and owner configuration; native import/live
HTTP error-shape and cold-start smoke with the real backend; backup restore drill; approved
real-model Linux RSS/current connector peak/private Render delivery. Synthetic/backend CI
does not prove production fit. No model, feature, threshold, training or application DB schema
is changed. No live schedule is enabled by these files.

References checked 2026-10-27: [OCI Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm),
[OCI FAQ](https://www.oracle.com/cloud/free/faq/), [n8n reverse proxy](https://docs.n8n.io/hosting/configuration/configuration-examples/webhook-url/),
[n8n encryption](https://docs.n8n.io/hosting/configuration/configuration-examples/encryption-key/),
[n8n execution settings](https://docs.n8n.io/hosting/configuration/environment-variables/executions/),
[Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/).
