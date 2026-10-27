import logging


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    # Never log SQL parameters, connection configuration or feature rows.
    # Connector exceptions may contain remote diagnostics; API logs use fixed event names.
    logging.getLogger("databricks.sql").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
