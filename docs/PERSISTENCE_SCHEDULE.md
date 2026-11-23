# Persistence schedule alignment — 23 November 2026

Change only the persistence cron from `17 */3 * * *` to `40 1-23/3 * * *` UTC.
Eight nominal executions per day: 01:40, 04:40, 07:40, 10:40, 13:40, 16:40,
19:40 and 22:40. The scheduler flag, script, retries, limit=100, idempotency,
HTTP 422 handling and server admission window of 0–7200 seconds are unchanged.
No dependency on Databricks completion is introduced.

## Observed timing (UTC; existing job metadata and saved outputs only)

| Date | Downstream run | Start | Complete | Source watermark verified |
| --- | --- | --- | --- | --- |
| 22 Nov | 843660403734979 | 09:31:21 | 10:28:27 | 09:29:01 |
| 22 Nov | 80487467741980 | 12:31:21 | 13:32:01 | 12:29:34 |
| 22 Nov | 1050019012386423 | 15:31:21 | 16:31:36 | 15:29:23 |
| 22 Nov | 221647161230414 | 18:31:22 | 19:28:25 | Not read in this review |
| 22 Nov | 77711696029557 | 21:31:21 | 22:30:44 | Not read in this review |
| 23 Nov | 31029654140036 | 06:31:21 | 07:30:33 | 06:29:27 (staging v247) |
| 23 Nov | 966690145975397 | 09:31:23 | 10:31:28 | 09:29:20 (staging v249) |

The latest eight-run listing also contained run 461748908053783, started
23 Nov 12:31:21 and still running; no completion assumed. No 00:31 or 03:31 run
appeared in that listing. Their absence is not explained by this cron change.

Actions observations with the old cron:

| Run | Actual creation UTC | Result |
| --- | --- | --- |
| 45061844901 | 22 Nov 19:37:49 | HTTP 200; 100 inserted, 0 existing, no retry |
| 45096031053 | 23 Nov 01:42:02 | Three HTTP 503; warehouse start BAD_REQUEST |
| 45175857234 | 23 Nov 12:36:08 | One HTTP 422; source age rejected, no retry |

There is no scheduled-for timestamp in these run records. If these executions
correspond to the immediately preceding nominal ticks, delays were approximately
81, 85 and 19 minutes respectively; missing/delayed schedules cannot be separated
with certainty from these records. Creation time is not POST time.

## Expected margin, not a guarantee

The proposed tick is 7m58s after the latest observed cycle completion at :32:02,
and approximately 8–12 minutes after the observed completed cycles. For measured
watermarks near :29, nominal source age at the new tick is 70m26s–70m59s;
remaining age budget is approximately 49 minutes, shared by GitHub queue delay,
cold start, SQL/scoring, persistence and retries. At the old nominal tick, the
previous cycle's :29 source was already approximately 2h48m old, while the new
cycle had not yet completed. Delayed GitHub starts sometimes happened to land
after completion, explaining the observed successful run.

This is a phase improvement, not reliable completion triggering: observed GitHub
delays can exceed the remaining budget, cycles may run late or be absent, and
warehouse availability is a separate blocker. HTTP 422 must continue to reject
expired data without retry. Do not widen the admission policy to improve success.

Rollback: revert only the cron and corresponding workflow assertion. Historical
pilot documentation records its original configuration and remains unchanged.
Merge is required for this schedule to become active on main; no dispatch or
production setting changes were performed while preparing this change.
