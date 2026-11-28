# Observed Historical Analytics and prediction archive

## Two independent domains

- `/public/analytics/observed` reads only the existing `rome_transport.gold` tables, projecting **ops_** observed current-stop delay metrics. They are observation-weighted (trip × stop × snapshot), not unique visits, passengers, future labels or ML probabilities.
- Existing `/public/predictions/history` and `/aggregate` remain Neon prediction history: only persisted batches, not complete Silver. The persist workflow is bounded and the archive is not a representative sample of all observations. Its date filter and hourly buckets refer to prediction generation. The UI separately shows source-feed time; model/batch metadata unavailable in the existing public DTO remain unavailable.
- Current model sklearn threshold stays `p >= 0.35`. Historical Spark reference evidence (`p > 0.45`) and historical labeled Gold columns are never projected by this API.

## Verified source contract, not a production data attestation

The schema is taken from canonical `13_current_operational_analytics.py` and `13_gold_analytics.py` on the Data/ML repository main. No notebooks or jobs were changed. This implementation did not start compute, execute production SQL, or verify live Gold versions, grants, time-travel readability or current coverage. Values are exposed only after successful runtime manifest/data validation; unit-test fixtures are synthetic and are never part of the product.

Existing Gold sources: executive_overview, route_reliability, stop_reliability, temporal_reliability, plus analytics_refresh_metadata. The manifest must say PASSED / YES / PINNED_INPUT_ALIGNED and reference the expected enriched source. Each data query uses the exact allowlisted table and integer Delta version from gold_versions_json and the same release/source version. Old-only historical rows with null ops_ metrics are excluded. Schema, count, key, coverage, or lineage failures return a fixed sanitized 503 rather than guessed values.

## API

`GET /public/analytics/observed?view=overview|routes|stops|temporal`

- overview: one network aggregate, full published coverage, counts and native Gold median/P90.
- routes/stops: first 20 eligible aggregates by major-delay share, known count and identifier; full coverage, no period/route filters. Existing eligibility thresholds are 1,000 known route observations / 500 known stop observations.
- temporal: optional `from=YYYY-MM-DD&to=YYYY-MM-DD`, both inclusive **service dates**, maximum 31 dates. Default is the last 28 dates ending at the published source-feed date in Europe/Rome. Returns daily, local-hour and feed-weekday × hour count buckets, not raw observations or averaged percentiles. Repeated DST hours are combined as in Gold. Missing buckets remain missing, never fabricated zero.

Unsupported parameters (including route × period), duplicate query parameters or invalid ranges return 422. No arbitrary SQL, table identifiers or Delta versions are accepted from the caller.

Response includes coverage=gold_observed_history, release_id, source table/version, scoring version, selected Gold version, Gold publication time, source watermark, query generation time, timezone, weighting, metric definition and period. Percentages divide by known-delay counts, not all rows. NULL stays NULL, including zero-denominator rates. Zero measured delay is preserved. Percentiles are returned only at their native aggregate grain; daily/hourly/heatmap metrics are additive counts and rates only. Distinct trips/stops/vehicles are not summed or exposed as invented totals.

Gold observed bands: early < -60s; on-time [-60,180); moderate [180,300); major >=300s. These differ intentionally from the current dashboard's display buckets.

## Bounds and availability

- Read-only existing Databricks client, Gold-only SELECTs, no model inference, no Silver scan, no Neon writes.
- 8-second SQL deadline per statement, existing process-wide warehouse concurrency gate, bounded 2 MB internal result and row caps. Cold request: one manifest SELECT and one aggregate SELECT; cache hits do neither.
- GET warehouse metadata (5-second transport timeout) must report RUNNING before SQL. Recovery/wake is disabled for this client, no `/start` requests, no retry or provisioning. OAuth uses existing workload configuration. A state change between this check and OpenSession remains an external race; server behavior is not a guarantee of zero compute usage.
- Manifest and result cache: 600 seconds, max 32 result scopes. Failure backoff: 600 seconds, including Free quota, missing permissions, schema mismatch and unreadable pinned versions. Concurrent cache misses fail promptly rather than queue more Gold queries. Cache is per process, not durable storage.
- Successful public JSON <=256,000 UTF-8 bytes. Oversized/malformed data fail closed. Temporal raw aggregate rows never go to the browser: only the small additive projections are returned.
- Frontend loads on explicit request only, one GET, no polling/retry, 45-second client timeout; Gold unavailability is isolated from current predictions and Neon archive. No synthetic fallback. Source/refresh timestamps remain visible even for old Gold releases.

## UX and validation

IT/EN views retain the existing bordeaux design. Network/route/stop KPIs, temporal trend/profile and heatmap have text denominators, accessible labels and empty/loading/unavailable states. Dates display in Europe/Rome. Neon local date input is interpreted in Europe/Rome, rejecting nonexistent or ambiguous DST times rather than silently selecting an offset. The archive labels API versus LKG separately.

Validation uses synthetic repository/transport fixtures and rendered frontend tests, without production SQL, warehouse start, scoring or persistence. No claim of production Gold availability is made before a separately authorized runtime verification/deployment. No pipeline changes or new infrastructure are required by this implementation.

Local browser preview could not be reached by the available browser/loopback connection. Responsive structure and essential accessibility are covered by rendered-component tests and responsive CSS; screenshot-based verification of the new view is NOT VERIFIED. The isolated preview server was stopped. This is not a production availability finding.
