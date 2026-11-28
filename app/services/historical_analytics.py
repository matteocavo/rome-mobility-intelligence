"""Observed-history projections with bounded process cache and failure backoff."""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from numbers import Real
from threading import Lock
from zoneinfo import ZoneInfo

import pandas as pd

from app.contracts.analytics import AnalyticsItem, AnalyticsResponse, CountBucket
from app.data.databricks_client import DataAccessError
from app.data.gold_repository import PREFIX, TABLES

MAX_BYTES = 256_000


def instant(value):
    if pd.isna(value):
        return None
    if isinstance(value, Real):
        return datetime.fromtimestamp(value, timezone.utc)
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    return stamp.to_pydatetime().astimezone(timezone.utc)


def buckets(items, key):
    groups = {}
    for item in items:
        name = key(item)
        group = groups.setdefault(name, [0, 0, 0])
        for index, value in enumerate((item.total, item.known, item.major)):
            group[index] += value
    return [
        CountBucket(
            key=k, total=v[0], known=v[1], major=v[2], major_rate=v[2] / v[1] if v[1] else None
        )
        for k, v in sorted(groups.items())
    ]


class HistoricalAnalytics:
    def __init__(self, repository, *, clock=time.monotonic):
        self.repository, self.clock = repository, clock
        self.lock = Lock()
        self.manifest_cache = None
        self.cache = {}
        self.failed_until = 0

    def get(self, query):
        if not self.lock.acquire(blocking=False):
            raise DataAccessError("Gold request already in progress")
        try:
            now = self.clock()
            if now < self.failed_until:
                raise DataAccessError("Gold unavailable; retry later")
            try:
                if self.manifest_cache is None or now >= self.manifest_cache[0]:
                    raw = self.repository.manifest()
                    if (
                        raw["quality_status"] != "PASSED"
                        or raw["dashboard_ready"] != "YES"
                        or raw["ops_status"] != "PINNED_INPUT_ALIGNED"
                        or raw["ops_source_table"]
                        != "rome_transport.silver.realtime_enriched_observations"
                    ):
                        raise ValueError("Gold release not validated")
                    uuid.UUID(raw["refresh_id"])
                    versions = json.loads(raw["gold_versions_json"])
                    for table in TABLES.values():
                        if (
                            type(versions[PREFIX + table]) is not int
                            or versions[PREFIX + table] < 0
                        ):
                            raise ValueError("Invalid Gold manifest version")
                    watermark = instant(int(raw["ops_latest_feed_timestamp"]))
                    refreshed = instant(raw["refresh_timestamp"])
                    utc = datetime.now(timezone.utc)
                    if watermark is None or refreshed is None or watermark > utc or refreshed > utc:
                        raise ValueError("Invalid Gold release timestamps")
                    self.manifest_cache = (
                        now + 600,
                        dict(raw, versions=versions, watermark=watermark, refreshed=refreshed),
                    )
                    self.cache.clear()
                manifest = self.manifest_cache[1]
                start, end = query.from_date, query.to_date
                if query.view == "temporal" and start is None:
                    end = manifest["watermark"].astimezone(ZoneInfo("Europe/Rome")).date()
                    start = end - timedelta(days=27)
                key = (query.view, start, end)
                if key in self.cache:
                    return self.cache[key]
                version = manifest["versions"][PREFIX + TABLES[query.view]]
                frame = self.repository.read(
                    query.view,
                    version,
                    manifest["refresh_id"],
                    int(manifest["ops_source_version"]),
                    start,
                    end,
                )
                items = []
                for row in frame.to_dict("records"):
                    if (
                        row.pop("ops_release_id") != manifest["refresh_id"]
                        or int(row.pop("ops_source_version")) != int(manifest["ops_source_version"])
                        or row.pop("ops_metric_definition")
                        != "reported_current_stop_arrival_delay_seconds"
                    ):
                        raise ValueError("Mixed Gold release")
                    clean = {k: None if pd.isna(v) else v for k, v in row.items()}
                    for name in ("total", "known", "missing", "major"):
                        value = clean[name]
                        if isinstance(value, bool) or value is None or int(value) != value:
                            raise ValueError("Non-integral aggregate count")
                        clean[name] = int(value)
                    clean["first_feed"], clean["last_feed"] = (
                        instant(clean["first_feed"]),
                        instant(clean["last_feed"]),
                    )
                    clean["major_rate"] = (
                        clean["major"] / clean["known"] if clean["known"] else None
                    )
                    item = AnalyticsItem.model_validate(clean)
                    if item.last_feed and item.last_feed > manifest["watermark"]:
                        raise ValueError("Aggregate ahead of manifest")
                    if query.view == "overview" and (
                        item.total != int(manifest["ops_observation_count"])
                        or item.last_feed != manifest["watermark"]
                    ):
                        raise ValueError("Overview does not reconcile with manifest")
                    if query.view == "temporal":
                        if (
                            item.service_date is None
                            or item.hour is None
                            or item.weekday is None
                            or not start <= item.service_date <= end
                        ):
                            raise ValueError("Invalid temporal grain")
                    items.append(item)
                identities = [(v.key, v.weekday, v.hour) for v in items]
                if len(identities) != len(set(identities)) or (
                    query.view == "overview" and len(items) != 1
                ):
                    raise ValueError("Invalid Gold aggregate grain")
                response = AnalyticsResponse(
                    view=query.view,
                    release_id=manifest["refresh_id"],
                    source_table=manifest["ops_source_table"],
                    source_version=int(manifest["ops_source_version"]),
                    scoring_version=int(manifest["ops_scoring_version"]),
                    gold_versions={PREFIX + TABLES[query.view]: version},
                    refreshed_at=manifest["refreshed"],
                    source_watermark=manifest["watermark"],
                    query_generated_at=datetime.now(timezone.utc),
                    period_from=start,
                    period_to=end,
                    items=[] if query.view == "temporal" else items,
                    daily=buckets(items, lambda v: str(v.service_date))
                    if query.view == "temporal"
                    else [],
                    hourly=buckets(items, lambda v: f"{v.hour:02}")
                    if query.view == "temporal"
                    else [],
                    heatmap=buckets(items, lambda v: f"{v.weekday}-{v.hour:02}")
                    if query.view == "temporal"
                    else [],
                )
                if len(response.model_dump_json().encode()) > MAX_BYTES:
                    raise ValueError("Gold public response budget exceeded")
                if len(self.cache) >= 32:
                    self.cache.clear()
                self.cache[key] = response
                return response
            except Exception:
                self.failed_until = self.clock() + 600
                raise
        finally:
            self.lock.release()
