# Application prediction history

PostgreSQL is the application history store, separate from Databricks source data.
SQLAlchemy 2.0 + psycopg 3 provide transactional access; Alembic owns schema changes.
No schema is created or migrated at application startup. No public deployment is approved.

## Schema and identity

Table: `public.prediction_history`, with identity primary key and created_at server timestamp.
Stored fields are source_feed_timestamp, prediction_generated_at, entity_id, route_id, trip_id,
vehicle_id, stop_id, stop_sequence, target_next_stop_id, current_arrival_delay_seconds,
major_delay_probability, predicted_major_delay, model_version, feature_contract_hash, threshold,
source_silver_version and feature_preparation_batch_id. Timestamps use TIMESTAMPTZ/UTC;
source_feed_timestamp remains the source epoch in seconds. Required identity fields are NOT NULL.

The source contract grain is `(feed_timestamp, entity_id, trip_id, stop_sequence, stop_id)`.
The database unique constraint adds model_version to that complete grain. Omitting entity_id
would collapse observations that the upstream contract considers distinct. Identifiers are
not truncated. Constraint name: `uq_prediction_history_source_model`.

An atomic multi-row INSERT uses `ON CONFLICT ON CONSTRAINT ... DO NOTHING RETURNING id`.
The response distinguishes evaluated, inserted and existing rows; a repeated source/model
batch inserts zero. Concurrent attempts rely on the PostgreSQL unique constraint, not a
check-then-insert race. A new model digest creates distinct history. A repeat using the same
source grain/model keeps the first prediction and lineage; no silent update of historical rows.
Changes in source preparation without a new feed do not overwrite an existing prediction.

model_version remains the immutable, content-addressed trusted manifest SHA-256, not a friendly
release name. Threshold and feature hash are stored per row, so model upgrades remain auditable.
Probability, threshold and decision consistency also have database CHECK constraints.
Every batch commits once; failure rolls back the batch. If a connection is lost during commit,
the caller may not know the outcome: retrying the same grain/model is the reconciliation path.

## Data minimization

No raw 47-feature vector, realized target, source payload, SQL, DSN, artifact path, credentials,
request body, IP address or application-consumer identity is persisted. target_next_stop_id is
the planned next stop, not a realized future label. The retained route/trip/stop/vehicle/entity
identifiers originate in the transit operational contract; no user/person identity is added.
This is data minimization, not a claim of anonymization. Access and retention policies are
still operator responsibilities; this PR introduces no retention scheduler or automatic deletion.

## Configuration and local setup

`DATABASE_URL` is a private PostgreSQL URL provided locally through environment or protected
configuration. Both `postgresql` and `postgresql+psycopg` URL schemes are accepted and use psycopg.
No host, role, port, database or password is supplied by application code. `.env.example` leaves
the DSN empty. Never paste a real DSN into chat, Git, logs, CI, command history or documentation.
Use an already provisioned, private local database; this PR installs/starts no OS service and
creates no production infrastructure. Keep DATABASE_URL out of tracked files.

Install only the pinned project dependencies, then provide DATABASE_URL privately for the
authorized migration role and run from the repository root:

```powershell
python -m pip install -r requirements-dev.lock
alembic upgrade head
```

Use a separate runtime-role DSN afterwards. Migration rollback is an explicit operator action:
`alembic downgrade base` drops prediction_history and its rows. Back up anything needed first.
`alembic upgrade head --sql` generates the initial PostgreSQL DDL without a database connection.
The migration role can perform DDL; the future runtime role must not be the migration owner.

Runtime defaults: ENABLE_PREDICTION_PERSISTENCE=false, DATABASE_POOL_SIZE=2, max overflow=0,
pool timeout=3s, connect timeout=5s, statement_timeout=5000ms, lock_timeout=5000ms and
idle_in_transaction_session_timeout=5000ms. Timeout settings apply to application connections,
not global PostgreSQL configuration. No unbounded pool or application retry loop is added.
Timeouts are server/pool/connect budgets, not a promise to kill a native socket call instantly.
Multiple application processes each own a pool; total connection capacity needs deployment sizing.
Transport encryption, local access control and protected DSN storage remain operator requirements.

## Manual persist trigger

`POST /predictions/current/persist?limit=50` is a **manual/local/internal endpoint**.
Writes require explicit ENABLE_PREDICTION_PERSISTENCE=true in every environment, including test
and local. Default disabled returns 503 before source/database work. Missing DSN also returns 503.
No body is accepted. The only query parameter is limit, positive, default min(50, max batch),
maximum INFERENCE_MAX_BATCH_ROWS (default/hard ceiling 100). Unknown/duplicate params are 422.

The trigger reuses CurrentScoringRepository, shared CurrentScoringService and ModelService:
fixed latest scoring feed → existing contract/lineage checks → trusted sklearn inference →
minimal prediction records → atomic PostgreSQL insert. It writes nothing to Databricks.
Preview `GET /predictions/current` uses the same scoring service and never persists implicitly.
`POST /predict` and `/predict/batch` remain stateless.

Summary fields: source_watermark, rows_evaluated, rows_inserted, rows_existing, model_version,
feature_contract_hash and threshold. No prediction rows are logged. The source may be stale:
no new source freshness SLA is claimed and source timestamp is preserved for interpretation.
Running again reads the latest feed again; exact idempotence comparison requires the same feed,
batch selection and model. No scheduler, polling, webhook, alert or n8n is introduced.

Local startup, with private runtime configuration and a trusted model already configured:

```powershell
$env:ENABLE_PREDICTION_PERSISTENCE="true"
python -m uvicorn app.main:app --host 127.0.0.1 --no-access-log
```

Do not expose this write trigger to the Internet. Authentication/authorization are not added
here. The enable flag is an operator guard, not an authentication mechanism.

## Read-only history API

`GET /predictions/history` uses only PostgreSQL, no model load requirement or Databricks query.
Persistence may be disabled while history reads remain available if a database is configured.
Allowed query filters: route_id, from, to, limit and optional predicted_major_delay.
Filters are bound values; no SQL, identifiers, arbitrary sort or WHERE clauses are accepted.
Unknown or duplicate query keys are rejected. Default limit=50, maximum HISTORY_MAX_ROWS=200
(configurable downwards). Ordering is prediction_generated_at DESC, then id DESC.

from/to filter **prediction_generated_at**, inclusively. Timezone-aware inputs are normalized to
UTC; naive values are rejected. `from > to` is 400; interval above HISTORY_MAX_RANGE_DAYS=7
(configurable downwards) is 413. No-filter range is the last seven days. Missing to defaults to
now; missing from defaults to end minus max range. A from-only request older than max range
is rejected rather than silently widened. Query rows are always bounded.

Typed response: rows, query_generated_at UTC and predictions containing the minimal persisted
fields. Observed current_arrival_delay_seconds is distinct from predicted next-stop major delay.
No raw features or realized future labels are returned.

400 semantic filters; 413 range too wide; 422 schema/limit/override or scoring contract invalid;
503 disabled/unconfigured/unavailable DB or source/model; 504 DB/pool timeout or source query
deadline. Errors and logs do not expose DSN, host, SQL parameters, paths or traceback.
Logs contain fixed event names and batch counts only. DB echo/parameter logging is disabled.
`/ready` exposes database_configured and prediction_persistence_enabled without connecting or
claiming database reachability. Existing model readiness and F01–F06 remain unchanged.

## Tests and remaining local validation

CI uses synthetic model/data fixtures and mocked transactional sessions. SQL is compiled with
the PostgreSQL dialect, including the unique constraint, conflict target, RETURNING and fixed
ordering. Alembic upgrade/downgrade DDL is tested offline. Fake concurrency/rollback tests
exercise application logic only; they do not prove PostgreSQL runtime behavior. SQLite is not
used as a substitute. No real credentials or models are supplied to CI.

Native integration is opt-in: provide TEST_DATABASE_URL privately for a **dedicated loopback
PostgreSQL test database**, then run `pytest tests/test_postgresql_optional.py -q`.
The test creates a randomly named temporary schema, applies the migration, verifies sequential
and concurrent idempotence, model changes, CHECK-failure atomic rollback, native timeout and
downgrade, then drops only that test schema. The test role needs schema creation permissions;
never use a production database or the future restricted application role for this test.
Non-loopback targets are rejected. Without explicit opt-in this test is skipped.

At implementation time (PR #15), PostgreSQL 16 was installed but stopped, with no DATABASE_URL
configured. No service was started or changed in that PR; native validation was deferred.
The later dated validation below completes that follow-up. For future local validation,
provision a private test DB, migrate, enable writes, persist at most 100 current rows and
repeat while the feed/model are unchanged, checking inserted=0/existing=batch.
Do not version prediction rows.

Validation for PR #15: baseline 149 passed / 2 skipped; final Windows suite 193 passed /
3 skipped (two platform checks plus native PostgreSQL opt-in). Ruff, compileall including
migrations, repository security policy, dependency consistency and diff checks passed.
Existing operational model checksum is unchanged. No Databricks query/write, migration
against a real database, PostgreSQL service change or real prediction persistence was executed
in PR #15.

## Native PostgreSQL validation — 2026-10-27

| Check | Result |
| --- | --- |
| PostgreSQL | 16.13 |
| Loopback-only | PASS |
| Migration | PASS |
| Runtime least privilege | PASS |
| Native integration | PASS |
| Real batch | PASS |
| Real idempotency | PASS |
| History API | PASS |
| Rollback | PASS |
| Concurrency | PASS |
| Timeout | PASS |

## Deployment boundary

Public deployment is NOT approved. Still required: separate OS service account without model
storage ownership or access to the operator's personal credential store; protected model/DSN;
dedicated PostgreSQL runtime role with SELECT/INSERT on prediction_history, schema access and
only necessary identity-sequence privileges, no CREATE/DROP/ALTER or superuser. A separate
migration role manages DDL. This PR creates neither production roles nor infrastructure.
No frontend or n8n is included.

References: [SQLAlchemy PostgreSQL ON CONFLICT](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert),
[PostgreSQL timeouts](https://www.postgresql.org/docs/current/runtime-config-client.html),
[Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
