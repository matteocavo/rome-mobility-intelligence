"""Opt-in native PostgreSQL checks. Never runs against an external/public database."""

import importlib.util
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.persistence.database import Database, DatabaseTimeout, DatabaseUnavailable
from app.persistence.history_repository import PredictionHistoryRepository
from app.persistence.models import prediction_history
from tests.test_prediction_persistence import records as records


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Local PostgreSQL opt-in not set"
)
def test_native_postgresql_migration_idempotence_concurrency_rollback_timeout(records):
    dsn = os.environ["TEST_DATABASE_URL"]
    if make_url(dsn).host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Integration tests require an explicitly configured loopback PostgreSQL")
    settings = Settings(_env_file=None, database_url=dsn, enable_prediction_persistence=True)
    database = Database(settings)
    original = database.engine
    schema = "rmi_test_" + uuid.uuid4().hex
    try:
        with original.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = original.execution_options(schema_translate_map={"public": schema})
        database._engine = engine
        database._factory = sessionmaker(engine, expire_on_commit=False)
        path = Path("alembic/versions/0001_prediction_history.py")
        spec = importlib.util.spec_from_file_location("initial_history_migration", path)
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()
            constraints = inspect(connection).get_unique_constraints(
                "prediction_history", schema=schema
            )
            assert any(c["name"] == "uq_prediction_history_source_model" for c in constraints)
        repo = PredictionHistoryRepository(database, settings)
        assert repo.insert_batch(records) == 2
        assert repo.insert_batch(records) == 0
        newer = [r.model_copy(update={"model_version": "b" * 64}) for r in records]
        with ThreadPoolExecutor(max_workers=4) as pool:
            counts = list(pool.map(lambda _: repo.insert_batch(newer), range(4)))
        assert sum(counts) == 2
        invalid_batch = [
            r.model_copy(update={"source_feed_timestamp": 1700000001}) for r in records
        ]
        invalid_batch[1] = invalid_batch[1].model_copy(update={"major_delay_probability": 2.0})
        with pytest.raises(DatabaseUnavailable):
            repo.insert_batch(invalid_batch)
        with database.session() as session:
            assert session.scalar(select(func.count()).select_from(prediction_history)) == 4
        with pytest.raises(DatabaseTimeout):
            with database.session() as session:
                session.execute(text("SET LOCAL statement_timeout='100ms'"))
                session.execute(text("SELECT pg_sleep(0.3)"))
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                revision.downgrade()
            assert "prediction_history" not in inspect(connection).get_table_names(schema=schema)
    finally:
        with original.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        database.dispose()
