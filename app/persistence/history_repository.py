"""Bounded SQLAlchemy queries and atomic PostgreSQL ON CONFLICT insertion."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.contracts.history import HistoryQuery, HistoryRecord, PredictionRecord
from app.core.config import Settings
from app.persistence.database import Database, DatabaseUnavailable
from app.persistence.models import NATURAL_KEY, prediction_history


def insert_statement(records: list[PredictionRecord]):
    return (
        insert(prediction_history)
        .values([r.model_dump() for r in records])
        .on_conflict_do_nothing(constraint="uq_prediction_history_source_model")
        .returning(prediction_history.c.id)
    )


def history_statement(query: HistoryQuery, start: datetime, end: datetime):
    table = prediction_history.c
    statement = select(prediction_history).where(
        table.prediction_generated_at >= start, table.prediction_generated_at <= end
    )
    if query.route_id is not None:
        statement = statement.where(table.route_id == query.route_id)
    if query.predicted_major_delay is not None:
        statement = statement.where(table.predicted_major_delay == query.predicted_major_delay)
    return statement.order_by(table.prediction_generated_at.desc(), table.id.desc()).limit(
        query.limit
    )


class PredictionHistoryRepository:
    def __init__(self, database: Database, settings: Settings):
        self.database, self.settings = database, settings

    def insert_batch(self, records: list[PredictionRecord]) -> int:
        if not self.settings.enable_prediction_persistence:
            raise DatabaseUnavailable("Prediction persistence disabled")
        if not 1 <= len(records) <= self.settings.inference_max_batch_rows:
            raise ValueError("Invalid persistence batch size")
        keys = [tuple(r.model_dump()[k] for k in NATURAL_KEY) for r in records]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate source observations within batch")
        with self.database.session() as session:
            inserted = len(session.execute(insert_statement(records)).scalars().all())
        # The transaction has committed before returning success.
        return inserted

    def history(self, query: HistoryQuery) -> list[HistoryRecord]:
        if query.limit > self.settings.history_max_rows:
            raise ValueError("History row limit exceeded")
        start, end = query.bounded_range(self.settings.history_max_range_days)
        with self.database.session() as session:
            rows = session.execute(history_statement(query, start, end)).mappings().all()
            return [HistoryRecord.model_validate(dict(row)) for row in rows]
