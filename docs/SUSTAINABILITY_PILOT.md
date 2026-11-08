# Controlled 72-hour sustainability pilot

Status **PREPARED — START PENDING**. The observation window begins only after all
three proposed schedules are active and read back successfully. Record that instant
as T0 in UTC and Europe/Rome, together with the corresponding main commit. The
evaluation cutoff is T0 + 72 hours. A merge alone does not establish T0.

| Component | Existing setting | Approved pilot setting |
| --- | --- | --- |
| Databricks job 195066091322974, ingestion 05 | periodic 10 MINUTES, UNPAUSED | periodic 20 MINUTES, UNPAUSED |
| Databricks job 1084265487272426, downstream 06→07→08→13 | periodic 2 HOURS, UNPAUSED | periodic 3 HOURS, UNPAUSED |
| persist-current-predictions.yml, workflow 398572611 | 17,47 * * * * UTC, active | 17 */3 * * * UTC, active |

RMI_ORCHESTRATION_ENABLED was true at preparation. Both jobs had
max_concurrent_runs=1. At the preflight on 2026-11-08 at 17:59:44 UTC, ingestion
had no active run, and downstream had one periodic run, 93402959874430. Check
active runs again at rollout. Its preceding completed run had finished before
this run started. Preserve task definitions, concurrency, credentials and data.

## Rollout and rollback

The owner approves the cron PR before rollout. Read the current job definitions
and active runs again. Compare them with the private original backups and stop
if unrelated changes, overlapping downstream runs or incompatible manual runs
are present. Update only each job's trigger interval, preserving its periodic
unit and UNPAUSED state. Read back the complete settings and verify that every
field outside trigger is identical to the pre-update settings. Check that
running work has not been canceled or restarted by the change.

After the cron is on main and the two job triggers are verified, record T0 and
the 72-hour cutoff. Natural scheduled runs provide the execution evidence.
The cron is best-effort and does not establish a dependency on the Databricks
publication. An hourly offset cannot guarantee publication order.

For an owner-approved rollback, use Jobs update with only new_settings.trigger
set to the complete saved original trigger for each job. Restore cron
17,47 * * * * through a reviewed follow-up PR. Read back the trigger states and
main workflow. A runtime rollback requires explicit approval. Keep the record
of the partially observed pilot if the window is interrupted.

## Observation method

Use existing Jobs run metadata and GitHub job logs. Queries to the metadata
APIs do not require starting a SQL warehouse. No monitoring SQL is needed.
At checks near T0, T0+24h, T0+48h and T0+72h, collect the bounded run list for
each job using /api/2.2/jobs/runs/list with job_id, start_time_from,
start_time_to, expand_tasks=true and pagination. Deduplicate by run_id and
retain task attempts. Preserve the cutoff so repeated audits compare the same
window. A delayed run created after the cutoff belongs to a later window.

| Indicator | Existing source and interpretation |
| --- | --- |
| Expected and observed runs | Trigger intervals and T0 window, compared with actual start times. Missing nominal starts remain separate from failed runs. |
| Success, failure, cancellation, active | Parent and task state fields. Canceled parents can contain failed quota-limited tasks. |
| Acquisition gaps | Successive ingestion start times and successive successful completion times. Edge gaps from T0 and to cutoff must also be reported. |
| Duration and overlap | start_time/end_time, task timings and attempt numbers. Exclude active runs from completed-duration averages and flag overlapping intervals. |
| Free quota failures | RESOURCE_EXHAUSTED plus the explicit free daily limit message in existing state/output. Read only the error portion of failed run output. |
| SQL session/start refusals | Existing structured Render logs, operation=session_open/warehouse_start/warehouse_get/warehouse_poll, status, category and sanitized code. |
| Persistence 503 and retry counts | Existing GitHub persistence attempt JSON, elapsed_ms, status and retry delay. |
| Persisted rows and avoided duplicates | Existing rows_evaluated/rows_inserted/rows_existing/result logs. Preserve source/model identity semantics. |
| Published source watermark | Existing task 08 cell output records selected_feed_timestamp, feed_age_seconds and batch identity. If unavailable in retained output, mark NOT OBSERVED. Job completion time cannot substitute for the feed watermark. |
| Dashboard age and origin | Already available UI/session observations and LKG capturedAt/source_watermark. Record source timestamp, displayed age and observation time independently. |
| Quota utilization | Task durations and explicit quota rejections are proxies. Free remaining allowance and DBU usage have not been measured by this method. |

Do not call current/summary or persistence endpoints solely to populate the
monitoring report. Those requests can open SQL sessions. Existing traffic and
retained task outputs provide the allowed evidence. Preserve missing evidence
explicitly when the watermark or displayed age cannot be observed.

## Baseline and evaluation

Baseline window 2026-11-05 17:47:19 UTC through 2026-11-08 17:47:19 UTC.
Ingestion had 298 runs, 297 successful and one failed. Downstream had 25 runs,
23 successful and two canceled, with explicit quota failures in the canceled
parents' task outputs. GitHub had 13 scheduled runs, ten successful and three
failed, with 19 POST attempts, six unsuccessful retry POSTs, 900 inserted rows
and 100 existing rows. Median successful ingestion duration was 55.7 seconds,
downstream 52.2 minutes. The longest start gaps were 8.5 and 10 hours.

Compare actual acquisition continuity, missing nominal runs, successful task
time, SQL failures, explicit quota errors, watermark advancement, age at
publication/display and persistence outcomes. Include edge gaps, delayed runs
and unknown watermark intervals. A high success rate among observed runs is
insufficient to accept the pilot. Increasing GitHub's realized cadence after
an irregular baseline can increase actual SQL demand despite a lower nominal
cron frequency.

Target a complete 72-hour comparison, including two full nights. Report
whether to keep, adjust or restore the previous settings, with evidence and
uncertainty. New regressions, dashboard data unavailability, systematic errors
or impact beyond the documented tradeoff require an operator decision. Report
the stop condition immediately and stop rollout/progression. Do not apply an
automatic rollback or introduce a fourth schedule profile.

The separate freshness UI PR is reviewed and deployed independently. Its merge
is not a prerequisite for T0. This pilot is operational v1.0.1 work.
