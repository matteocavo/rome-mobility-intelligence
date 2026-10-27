"""Transaction/constraint simulator for unit tests, not PostgreSQL equivalence evidence."""

from contextlib import contextmanager
from copy import deepcopy
from threading import Lock
from unittest.mock import Mock

from sqlalchemy.dialects import postgresql

from app.persistence.database import DatabaseUnavailable
from app.persistence.models import NATURAL_KEY


class FakeDatabase:
    configured = True

    def __init__(self):
        self.rows = {}
        self.lock = Lock()
        self.fail_after = None
        self.rollbacks = 0

    @contextmanager
    def session(self):
        with self.lock:
            pending = deepcopy(self.rows)

            def execute(statement):
                params = statement.compile(dialect=postgresql.dialect()).params
                indexes = sorted({int(k.rsplit("_m", 1)[1]) for k in params if "_m" in k})
                ids = []
                for index in indexes:
                    suffix = f"_m{index}"
                    row = {k[: -len(suffix)]: v for k, v in params.items() if k.endswith(suffix)}
                    key = tuple(row[name] for name in NATURAL_KEY)
                    if key not in pending:
                        pending[key] = row
                        ids.append(len(pending))
                    if self.fail_after is not None and index >= self.fail_after:
                        raise DatabaseUnavailable("simulated transaction failure")
                result = Mock()
                result.scalars.return_value.all.return_value = ids
                return result

            session = Mock()
            session.execute.side_effect = execute
            try:
                yield session
            except BaseException:
                self.rollbacks += 1
                raise
            else:
                self.rows = pending
