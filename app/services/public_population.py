"""Bounded whole-current-population inference/cache, with page operations after global filters."""

import hashlib
import time
from collections import namedtuple
from datetime import datetime, timezone
from threading import Lock

import numpy as np
import pandas as pd

from app.contracts.operational_ml import FEATURES
from app.contracts.public import PublicPrediction, page_response
from app.data.databricks_client import DataAccessError
from app.services.public_summary import NetworkSummary, RouteRisk

# Immutable tuple storage has no per-row dict/fields-set. Pydantic validation still
# covers every source row; only the selected <=50 rows become response models.
PublicRow = namedtuple("PublicRow", PublicPrediction.model_fields)


class PublicPopulation:
    def __init__(self, repository, model_getter, geography, *, test_mode=False):
        self.repository, self.model_getter, self.geography = repository, model_getter, geography
        self.test_mode = test_mode
        self._lock, self._expires, self._failed_until = Lock(), 0, 0
        self._rows, self._summary = [], None
        self._snapshot = None

    def _ensure(self):
        cached = self._snapshot
        if cached is not None and time.monotonic() < min(self._expires, cached[2]):
            return cached
        if time.monotonic() < self._failed_until or not self._lock.acquire(blocking=False):
            raise DataAccessError("Current population temporarily unavailable")
        try:
            cached = self._snapshot
            if cached is not None and time.monotonic() < min(self._expires, cached[2]):
                return cached
            model = self.model_getter()
            if model is None or (model.metadata.synthetic and not self.test_mode):
                raise DataAccessError("Operational model unavailable")
            self._rows, self._summary, self._snapshot = [], None, None
            started = time.monotonic()
            frame = self.repository.population()
            if frame.empty:
                now = datetime.now(timezone.utc)
                self._summary = NetworkSummary(
                    status="no_data",
                    query_generated_at=now,
                    source_watermark=None,
                    source_age_seconds=None,
                    scored_count=0,
                    route_count=0,
                    observed_delay_count=0,
                    median_observed_delay_seconds=None,
                    p90_observed_delay_seconds=None,
                    major_delay_count=0,
                    major_delay_rate=None,
                    risk_status="no_current_observations",
                    observed_delay_distribution=dict(
                        early=0, minor=0, moderate=0, major=0, critical=0
                    ),
                )
                self._expires = time.monotonic() + 300
                self._snapshot = (self._rows, self._summary, self._expires)
                return self._snapshot
            # Inference uses only the reviewed, fixed current-source feature contract.
            values = np.empty(len(frame), dtype=np.float64)
            for start in range(0, len(frame), 1024):
                end = min(start + 1024, len(frame))
                values[start:end] = model.predict_proba(
                    frame.iloc[start:end].loc[:, list(FEATURES)]
                )
            if len(values) != len(frame) or not np.isfinite(values).all():
                raise ValueError("Invalid current population probabilities")
            # Inference/contract audit are complete; do not retain 47 features and
            # repeated lineage columns while building the public population.
            context = [
                "entity_id",
                "route_id",
                "route_type",
                "stop_id",
                "stop_sequence",
                "target_next_stop_id",
                "trip_id",
                "vehicle_id",
                "current_arrival_delay_seconds",
                "feed_timestamp",
            ]
            frame = frame.loc[:, [name for name in context if name in frame.columns]]
            now = datetime.now(timezone.utc)
            watermark = datetime.fromtimestamp(int(frame.feed_timestamp.iloc[0]), timezone.utc)
            result = []
            columns = list(frame.columns)
            for index, values_row in enumerate(frame.itertuples(index=False, name=None)):
                row = dict(zip(columns, values_row, strict=True))
                stop = self.geography.stops.get(str(row["stop_id"]), {})
                probability = float(values[index])
                observed = row["current_arrival_delay_seconds"]
                observed = None if pd.isna(observed) else float(observed)
                route = getattr(self.geography, "routes", {}).get(str(row.get("route_id")), {})
                route_type = route.get("route_type", row.get("route_type"))
                route_type = None if pd.isna(route_type) else int(route_type)
                grain = (row["entity_id"], row["trip_id"], row["stop_sequence"], row["stop_id"])
                item = PublicPrediction(
                    observation_id=hashlib.sha256(str((watermark, grain)).encode()).hexdigest()[
                        :24
                    ],
                    route_id=str(row["route_id"]) if pd.notna(row["route_id"]) else None,
                    stop_id=str(row["stop_id"]),
                    stop_sequence=int(row["stop_sequence"]),
                    target_next_stop_id=(
                        str(row["target_next_stop_id"])
                        if pd.notna(row["target_next_stop_id"])
                        else None
                    ),
                    trip_id=str(row["trip_id"]),
                    vehicle_id=str(row["vehicle_id"]) if pd.notna(row.get("vehicle_id")) else None,
                    route_type=route_type,
                    route_short_name=route.get("route_short_name"),
                    stop_name=stop.get("name"),
                    stop_lat=stop.get("lat"),
                    stop_lon=stop.get("lon"),
                    observed_current_delay_seconds=observed,
                    major_delay_probability=probability,
                    predicted_major_delay=probability >= model.threshold,
                    threshold=model.threshold,
                    source_watermark=watermark,
                    prediction_generated_at=now,
                )
                search = (
                    " ".join(
                        str(row.get(key) or "")
                        for key in ("route_id", "stop_id", "trip_id", "vehicle_id")
                    )
                    + " "
                    + stop.get("name", "")
                    + " "
                    + route.get("route_short_name", "")
                    + " "
                    + route.get("route_long_name", "")
                )
                result.append(
                    (
                        PublicRow(*(getattr(item, field) for field in PublicRow._fields)),
                        search.casefold(),
                    )
                )
            delays = pd.to_numeric(frame.current_arrival_delay_seconds, errors="coerce").dropna()
            if not np.isfinite(delays).all() or time.monotonic() - started > 150:
                raise DataAccessError("Current population budget exceeded")
            total = len(result)
            major = sum(item.predicted_major_delay for item, _ in result)
            route_groups = {}
            for item, _ in result:
                if item.route_id is None:
                    continue
                group = route_groups.setdefault(
                    item.route_id, {"count": 0, "major": 0, "types": set()}
                )
                group["count"] += 1
                group["major"] += int(item.predicted_major_delay)
                if item.route_type is not None:
                    group["types"].add(item.route_type)
            critical_routes = [
                RouteRisk(
                    route_id=key,
                    route_type=next(iter(value["types"])) if len(value["types"]) == 1 else None,
                    scored_count=value["count"],
                    major_delay_count=value["major"],
                    major_delay_rate=value["major"] / value["count"],
                )
                for key, value in route_groups.items()
            ]
            critical_routes.sort(
                key=lambda value: (
                    -value.major_delay_rate,
                    -value.major_delay_count,
                    value.route_id,
                )
            )
            summary = NetworkSummary(
                query_generated_at=now,
                source_watermark=watermark,
                source_age_seconds=(now - watermark).total_seconds(),
                critical_routes=critical_routes[:5],
                scored_count=total,
                route_count=int(frame.route_id.nunique()),
                observed_delay_count=len(delays),
                median_observed_delay_seconds=float(delays.median()) if len(delays) else None,
                p90_observed_delay_seconds=float(delays.quantile(0.9)) if len(delays) else None,
                major_delay_count=major,
                major_delay_rate=major / total if total else None,
                risk_status="complete_operational_model_population",
                observed_delay_distribution=dict(
                    early=int((delays < 0).sum()),
                    minor=int(((delays >= 0) & (delays < 120)).sum()),
                    moderate=int(((delays >= 120) & (delays < 300)).sum()),
                    major=int(((delays >= 300) & (delays < 600)).sum()),
                    critical=int((delays >= 600).sum()),
                ),
            )
            # Free features/probabilities before publishing the compact public cache.
            del frame, values, delays
            self._rows, self._summary = result, summary
            self._expires = time.monotonic() + 300
            self._snapshot = (self._rows, self._summary, self._expires)
            return self._snapshot
        except Exception:
            self._failed_until = time.monotonic() + 30
            raise
        finally:
            self._lock.release()

    def summary(self):
        _, summary, _ = self._ensure()
        return summary

    def page(self, query):
        rows, summary, _ = self._ensure()
        if query.from_at or query.to_at:
            raise ValueError("Time filters belong to history")
        if (
            query.mode != "all"
            and rows
            and not any(item.route_type is not None for item, _ in rows)
        ):
            raise DataAccessError("Route mode metadata unavailable")

        def matches(entry):
            item, text = entry
            probability = item.major_delay_probability
            return (
                (not query.route or item.route_id == query.route)
                and (not query.stop or item.stop_id == query.stop)
                and (not query.query or query.query.casefold() in text)
                and (query.mode == "all" or item.route_type == (3 if query.mode == "bus" else 0))
                and (
                    query.risk_class == "all"
                    or query.risk_class == "major"
                    and item.predicted_major_delay
                    or query.risk_class == "moderate"
                    and not item.predicted_major_delay
                    and probability >= 0.2
                    or query.risk_class == "regular"
                    and not item.predicted_major_delay
                    and probability < 0.2
                )
            )

        selected = [item for entry in rows if matches(entry) for item in [entry[0]]]
        keys = {
            "risk_desc": lambda item: (-item.major_delay_probability, item.observation_id),
            "delay_desc": lambda item: (
                item.observed_current_delay_seconds is None,
                -(item.observed_current_delay_seconds or 0),
                item.observation_id,
            ),
            "route_asc": lambda item: (item.route_id or "", item.observation_id),
            "time_desc": lambda item: (-item.source_watermark.timestamp(), item.observation_id),
        }
        selected.sort(key=keys[query.sort])
        start = (query.page - 1) * query.page_size
        return page_response(
            query,
            total=len(selected),
            items=[
                PublicPrediction.model_validate(item._asdict())
                for item in selected[start : start + query.page_size]
            ],
            coverage="current_scoring_population",
            watermark=summary.source_watermark,
            now=datetime.now(timezone.utc),
            generated=summary.query_generated_at,
            source_route_count=summary.route_count,
        )
