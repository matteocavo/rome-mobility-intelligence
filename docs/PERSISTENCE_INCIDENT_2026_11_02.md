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
No rows were persisted by these initial probes and no warehouse Start/Stop API
was called at that stage.

### Controlled recovery experiment

After explicit user approval of **one** Start request, the existing warehouse
Start API returned 200, its state became RUNNING, and the same local `SELECT 1`
succeeded. Production then returned `/health` 200 after a 52.44-second wake and
`/public/summary` 200 in 43.28 seconds. No persistence POST was sent by this
experiment. This establishes a viable state-dependent recovery for the observed
failure. The reason the platform did not auto-start on the earlier OpenSession
request remains unknown; the exact HTTP status of those past production failures
cannot be retroactively proven from their category-only logs.

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
- Opt-in `DATABRICKS_WAREHOUSE_WAKE_ENABLED` (default false) enables a narrowly
  guarded recovery: only after OpenSession HTTP 400, read the existing configured
  warehouse state; only if STOPPED request one Start; if already STARTING only
  wait; allow at most 60 seconds and one reconnect. Other states, authentication,
  authorization, unrelated 400s and non-warehouse paths cannot trigger Start.
- Recovery remains within the original SELECT concurrency gate and application
  deadline. It uses the same workload identity, fixed existing warehouse and
  existing CAN USE grant. There is no compute provisioning, grant/config/schema
  change or new credential in Actions. If recovery fails, persistence still fails.

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

This remains a candidate fix, not a demonstrated scheduled reliability result.
The opt-in must not be enabled without approval for automatic starts; the user's
one-time diagnostic Start authorization does not imply repeated future starts.
The schedule offset and generic retry timings are unchanged because neither is
proven responsible. Authentication/authorization and permanent errors must not
be blindly retried. A Free compute quota rejection still cannot be solved by a
wake request and must remain a visible failure.

## Production acceptance still required

After root cause is identified and the actual fix passes CI, merge/deploy within
the authorized scope, perform one controlled persistence test, and verify a real
subsequent scheduled success, natural-key idempotence, unchanged snapshot/live
semantics and Render memory. No patch release is recommended on diagnostics
alone. The current incident is not declared resolved.

Local verification: 141 targeted tests passed (warehouse wake, Actions scheduler,
persistence, Databricks client/diagnostics, query budget and persistence
diagnostics); Ruff passed. The first diagnostics-only revision passed Linux CI:
536 tests, 2 skipped, 26 subtests, plus frontend, ARM64 and Docker smoke. Its full
local suite had stalled after 13% and was interrupted. The subsequent opt-in wake
revision requires its own CI result. No deployment or production reliability
claim follows from these unit tests. No tags/releases were changed.
