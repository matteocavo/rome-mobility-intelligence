# Scheduled persistence incident — 2026-11-02

## Status: PARTIALLY PROVEN; not resolved

The current path still requires a validated Databricks current scoring snapshot.
No historical predictions or frontend bundle are replayed as current. A failed
source read happens before `BatchScoringService` calls `history.insert_batch`.

### Observed Actions runs (UTC)

| Run | Client start | Client end | Result |
| --- | --- | --- | --- |
| 41282580971 | Nov 1 06:53:08 | 06:54:17 | 100 evaluated / 100 inserted / 0 retries |
| 41315486531 | Nov 1 14:17:58 | 14:19:08 | 100 evaluated / 100 inserted / 0 retries |
| 41340626823 | Nov 1 19:13:25 | 19:15:51 | persistence HTTP 503 |
| 41359293514 | Nov 1 22:52:31 | 22:54:56 | persistence HTTP 503 |
| 41378375768 | Nov 2 02:33:40 | 02:36:04 | persistence HTTP 503 |
| 41425280318 | Nov 2 10:00:53 | 10:03:19 | persistence HTTP 503 |

Run links: `https://github.com/matteocavo/rome-mobility-intelligence/actions/runs/<run>`.

Render logs correlate all three attempts in each of the four recent failures
with `databricks_failure stage=select category=databricks_unknown`. For the latest
run these occur at 10:01:43, 10:02:15 and 10:03:19 UTC (Console displayed CET).
Connector failures take about 2–4 seconds, rather than reaching the 120-second
application query deadline. Earlier Oct 31 / Nov 1 failures instead logged
`databricks_compute_unavailable`. These categories must not be conflated.

A local probe with the existing workload identity reproduced an OpenSession
HTTP 400 / `databricks_unknown`; the subsequent warehouse metadata GET returned
HTTP 200 and STOPPED. This independently proves that local M2M authentication
and warehouse metadata access work. It does **not** prove that the production
failures have exactly that HTTP status or that Free quota caused the 400.
No query reached scoring, no rows were persisted by these probes, and no
warehouse Start/Stop/configuration API was called explicitly.

## What this patch changes

- Internal connector warning adds only numeric HTTP status and an allowlisted
  RPC label, retaining the original category. HTTP 400 remains unknown rather
  than being mislabeled transient quota exhaustion.
- Actions emits one fixed diagnostic event per persistence attempt: attempt,
  status, category, elapsed milliseconds, and intended retry delay.
- No bodies, headers, credentials, arbitrary URLs, SQL, IDs or exception messages
  are emitted by these additions.
- Tests cover unknown 400, nested connector contexts, invalid metadata, bounded
  retries and eventual idempotent success.

## Policy intentionally unchanged pending evidence

The schedule remains `17,47 * * * *`, the maximum remains three POST attempts,
with 30/60-second waits and 140-second request timeouts. Health/readiness share
a separate 240-second wake budget. The theoretical total remains 750 seconds,
below the 15-minute Actions job limit. Readiness proves local configuration and
model readiness, not successful upstream SQL session availability.

Actual scheduled starts in the observed period are hours apart. A nominal
half-hour cron is not evidence of a half-hour execution guarantee. There is no
evidence yet that a different offset or more aggressive retry policy fixes the
current OpenSession rejection. A daily quota exhaustion would not be cured by
several more retries in the same window either.

Do not merge or deploy this as a proven reliability fix. First obtain the
warehouse health/activity explanation or equivalent safe upstream evidence.
Then choose a targeted configuration correction or bounded delayed retry policy
only for proven transient failures; authentication/authorization and permanent
request/configuration errors must not be blindly retried.

## Production acceptance still required

After root cause is identified and the actual fix passes CI, merge/deploy within
the authorized scope, perform one controlled persistence test, and verify a real
subsequent scheduled success, natural-key idempotence, unchanged snapshot/live
semantics and Render memory. No patch release is recommended on diagnostics
alone. The current incident is not declared resolved.

Local verification: 92 targeted tests passed (Actions scheduler, persistence,
Databricks diagnostics and persistence diagnostics), Ruff, compileall,
repository policy and diff checks passed. The full local suite stalled after
13% and was interrupted; no full-suite PASS is claimed. Linux CI remains a
separate required check. Production verification has not been performed for
this patch and no production reliability claim follows from these unit tests.
