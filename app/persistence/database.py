"""Lazy bounded PostgreSQL engine and transactional sessions. No runtime DDL."""

import logging
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError, TimeoutError
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings

logger = logging.getLogger(__name__)


class DatabaseUnavailable(RuntimeError):
    pass


class DatabaseTimeout(DatabaseUnavailable):
    pass


def engine_options(settings: Settings) -> dict:
    timeout = settings.database_statement_timeout_ms
    return {
        "pool_size": settings.database_pool_size,
        "max_overflow": 0,
        "pool_timeout": settings.database_pool_timeout_seconds,
        "pool_recycle": 300,
        "hide_parameters": True,
        "echo": False,
        "connect_args": {
            "connect_timeout": settings.database_connect_timeout_seconds,
            "options": (
                f"-c statement_timeout={timeout} -c lock_timeout={timeout} "
                f"-c idle_in_transaction_session_timeout={timeout} -c timezone=UTC"
            ),
        },
    }


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine = None
        self._factory = None
        self._lock = Lock()

    @property
    def configured(self) -> bool:
        return bool(self.settings.database_url.get_secret_value())

    def _initialize(self):
        with self._lock:
            if self._engine is not None:
                return
            try:
                url = make_url(self.settings.database_url.get_secret_value())
                if url.drivername not in {"postgresql", "postgresql+psycopg"}:
                    raise ValueError("Only PostgreSQL with psycopg is supported")
                self._engine = create_engine(
                    url.set(drivername="postgresql+psycopg"), **engine_options(self.settings)
                )
                self._factory = sessionmaker(self._engine, expire_on_commit=False)
            except Exception:
                raise DatabaseUnavailable("Application database is not configured") from None

    @property
    def engine(self):
        self._initialize()
        return self._engine

    @contextmanager
    def session(self):
        self._initialize()
        try:
            with self._factory() as session, session.begin():
                yield session
        except (SQLAlchemyError, OSError) as error:
            # The session context has already rolled back before this translation.
            state = getattr(getattr(error, "orig", None), "sqlstate", None)
            if isinstance(error, TimeoutError) or state in {"57014", "55P03"}:
                logger.warning("prediction_database_timeout")
                raise DatabaseTimeout("Application database timeout") from None
            logger.warning("prediction_database_unavailable")
            raise DatabaseUnavailable("Application database unavailable") from None

    def dispose(self):
        if self._engine is not None:
            self._engine.dispose()
