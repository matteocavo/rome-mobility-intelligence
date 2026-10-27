"""No DSN in Alembic configuration or logs; migrations run only by operator command."""

from alembic import context
from app.core.config import Settings
from app.persistence.database import Database
from app.persistence.models import metadata

if context.is_offline_mode():
    context.configure(dialect_name="postgresql", target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    database = Database(Settings())
    try:
        with database.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata)
            with context.begin_transaction():
                context.run_migrations()
    except Exception:
        raise RuntimeError("Migration unavailable; verify private database configuration") from None
    finally:
        database.dispose()
