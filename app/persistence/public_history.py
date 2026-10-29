"""Server-side filtered/countable history. All identifiers/orderings are fixed and values bound."""

from contextlib import contextmanager
from datetime import datetime, timezone
from threading import BoundedSemaphore

from sqlalchemy import case, func, or_, select, text

from app.contracts.public import PredictionAggregate, page_response
from app.persistence.database import DatabaseUnavailable
from app.persistence.models import prediction_history
from app.persistence.public_repository import PUBLIC_COLUMNS, prediction

C = prediction_history.c


def filtered(query, geography):
    conditions = []
    if query.route:
        conditions.append(C.route_id == query.route)
    if query.stop:
        conditions.append(C.stop_id == query.stop)
    if query.from_at:
        conditions.append(C.prediction_generated_at >= query.from_at)
    if query.to_at:
        conditions.append(C.prediction_generated_at <= query.to_at)
    if query.query:
        escaped = query.query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stop_ids = [
            key
            for key, value in geography.stops.items()
            if query.query.casefold() in value["name"].casefold()
        ]
        expressions = [
            C[name].ilike("%" + escaped + "%", escape="\\")
            for name in ("route_id", "stop_id", "trip_id", "vehicle_id")
        ]
        route_ids = (
            geography.matching_routes(query.query) if hasattr(geography, "matching_routes") else []
        )
        if route_ids:
            expressions.append(C.route_id.in_(route_ids))
        if stop_ids:
            expressions.append(C.stop_id.in_(stop_ids))
        conditions.append(or_(*expressions))
    if query.risk_class == "major":
        conditions.append(C.predicted_major_delay.is_(True))
    elif query.risk_class == "moderate":
        conditions.extend([C.predicted_major_delay.is_(False), C.major_delay_probability >= 0.2])
    elif query.risk_class == "regular":
        conditions.extend([C.predicted_major_delay.is_(False), C.major_delay_probability < 0.2])
    return conditions


class PublicHistory:
    def __init__(self, database, geography):
        self.database, self.geography = database, geography
        self._slot = BoundedSemaphore(1)

    @contextmanager
    def _read(self):
        if not self.database.configured or not self._slot.acquire(blocking=False):
            raise DatabaseUnavailable("History temporarily unavailable")
        try:
            with self.database.session() as session:
                session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                session.execute(text("SET LOCAL statement_timeout = '2000ms'"))
                session.execute(text("SET LOCAL lock_timeout = '1000ms'"))
                yield session
        finally:
            self._slot.release()

    def aggregate(self, query):
        if query.mode != "all":
            raise DatabaseUnavailable("History mode metadata unavailable")
        conditions = filtered(query, self.geography)
        major = func.coalesce(func.sum(case((C.predicted_major_delay.is_(True), 1), else_=0)), 0)
        hour = func.date_trunc("hour", func.timezone("UTC", C.prediction_generated_at))
        with self._read() as session:
            totals = (
                session.execute(
                    select(
                        func.count().label("total"),
                        major.label("major_count"),
                        func.max(C.source_feed_timestamp).label("watermark"),
                    ).where(*conditions)
                )
                .mappings()
                .one()
            )
            buckets = (
                session.execute(
                    select(
                        hour.label("hour"),
                        func.count().label("count"),
                        major.label("major_count"),
                    )
                    .where(*conditions)
                    .group_by(hour)
                    .order_by(hour.desc())
                    .limit(72)
                )
                .mappings()
                .all()
            )
        hourly = [
            {
                "hour": row["hour"].replace(tzinfo=timezone.utc),
                "count": row["count"],
                "major_count": int(row["major_count"]),
            }
            for row in reversed(buckets)
        ]
        return PredictionAggregate(
            coverage="persisted_prediction_history",
            total=totals["total"],
            major_count=int(totals["major_count"]),
            hourly=hourly,
            source_watermark=(
                datetime.fromtimestamp(totals["watermark"], timezone.utc)
                if totals["total"]
                else None
            ),
            query_generated_at=datetime.now(timezone.utc),
        )

    def page(self, query):
        if query.mode != "all":
            raise DatabaseUnavailable("History mode metadata unavailable")
        now = datetime.now(timezone.utc)
        conditions = filtered(query, self.geography)
        orders = {
            "risk_desc": C.major_delay_probability.desc(),
            "delay_desc": C.current_arrival_delay_seconds.desc().nulls_last(),
            "route_asc": C.route_id.asc().nulls_last(),
            "time_desc": C.prediction_generated_at.desc(),
        }
        with self._read() as session:
            stats = (
                session.execute(
                    select(
                        func.count().label("total"),
                        select(func.count(func.distinct(C.route_id)))
                        .correlate(None)
                        .scalar_subquery()
                        .label("source_route_count"),
                        func.max(C.source_feed_timestamp).label("watermark"),
                    ).where(*conditions)
                )
                .mappings()
                .one()
            )
            rows = (
                session.execute(
                    select(*(C[name] for name in PUBLIC_COLUMNS), C.id.label("_row_id"))
                    .where(*conditions)
                    .order_by(orders[query.sort], C.id.desc())
                    .offset((query.page - 1) * query.page_size)
                    .limit(query.page_size)
                )
                .mappings()
                .all()
            )
        # Historical route mode is not inferred from current metadata; coordinates are static only.
        items = []
        for row in rows:
            item = prediction(row)
            stop = self.geography.stops.get(item.stop_id, {})
            route = getattr(self.geography, "routes", {}).get(item.route_id, {})
            items.append(
                item.model_copy(
                    update={
                        "route_short_name": route.get("route_short_name"),
                        "route_type": route.get("route_type"),
                        "stop_name": stop.get("name"),
                        "stop_lat": stop.get("lat"),
                        "stop_lon": stop.get("lon"),
                    }
                )
            )
        watermark = (
            datetime.fromtimestamp(stats["watermark"], timezone.utc) if stats["total"] else None
        )
        return page_response(
            query,
            total=stats["total"],
            items=items,
            coverage="persisted_prediction_history",
            watermark=watermark,
            now=now,
            source_route_count=stats["source_route_count"],
        )
