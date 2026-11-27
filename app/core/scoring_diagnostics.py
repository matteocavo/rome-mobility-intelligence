"""Value-free diagnostics for scoring failures; no change to exception handling."""

import json
import logging
from contextvars import ContextVar
from functools import wraps
from uuid import uuid4

from pydantic import ValidationError

from app.contracts.history import PredictionRecord
from app.contracts.inference import CurrentPredictionsResponse, PredictRequest

logger = logging.getLogger(__name__)
_state = ContextVar("scoring_diagnostic_state", default=None)
_FIELDS = frozenset(
    (
        *PredictRequest.model_fields,
        *PredictionRecord.model_fields,
        *CurrentPredictionsResponse.model_fields,
    )
)
_STAGES = frozenset(
    {
        "configuration",
        "snapshot_read_validation",
        "snapshot_size",
        "snapshot_limit",
        "snapshot_query",
        "snapshot_identity",
        "snapshot_contract",
        "snapshot_lineage",
        "target_identity",
        "source_temporal",
        "feature_validation",
        "watermark_validation",
        "inference",
        "prediction_enrichment",
        "response_validation",
        "scoring",
        "persistence_record_validation",
        "freshness",
        "persistence_insert",
        "persistence_summary",
    }
)
_TYPES = frozenset(
    {
        "missing",
        "extra_forbidden",
        "string_type",
        "string_too_short",
        "string_too_long",
        "string_pattern_mismatch",
        "int_type",
        "int_parsing",
        "int_from_float",
        "float_type",
        "float_parsing",
        "finite_number",
        "bool_type",
        "bool_parsing",
        "greater_than",
        "greater_than_equal",
        "less_than",
        "less_than_equal",
        "datetime_type",
        "datetime_parsing",
        "datetime_from_date_parsing",
        "timezone_aware",
        "value_error",
        "list_type",
        "model_type",
    }
)


def stage(name):
    state = _state.get()
    if state is not None:
        state["stage"] = name if name in _STAGES else "unknown"


def record_failure(error):
    """Keep field paths and error categories only; never messages, ctx, inputs or repr."""
    state = _state.get()
    if state is None or state["logged"] or state["stage"] == "freshness":
        return
    state["logged"] = True
    try:
        kind = next(
            (
                name
                for cls, name in (
                    (ValidationError, "ValidationError"),
                    (KeyError, "KeyError"),
                    (TypeError, "TypeError"),
                    (OverflowError, "OverflowError"),
                    (ValueError, "ValueError"),
                )
                if isinstance(error, cls)
            ),
            "OtherError",
        )
        issues = []
        if isinstance(error, ValidationError):
            errors = error.errors(include_input=False, include_context=False, include_url=False)
            for item in errors[:8]:
                path = [
                    part if type(part) is str and part in _FIELDS else "[redacted]"
                    for part in item.get("loc", ())[:8]
                ]
                category = item.get("type")
                issues.append(
                    {
                        "path": path,
                        "category": category if category in _TYPES else "other_validation",
                    }
                )
        logger.warning(
            "scoring_contract_failure %s",
            json.dumps(
                {
                    "stage": state["stage"],
                    "exception_type": kind,
                    "local_correlation_id": state["correlation_id"],
                    "validation_errors": issues,
                },
                sort_keys=True,
            ),
        )
    except Exception:
        # Optional logging must not replace, wrap or retry the original failure.
        pass


def diagnose(function):
    """One local correlation scope per call tree; nested stages share it."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        if _state.get() is not None:
            return function(*args, **kwargs)
        token = _state.set({"stage": "unknown", "logged": False, "correlation_id": str(uuid4())})
        try:
            return function(*args, **kwargs)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            record_failure(error)
            raise
        finally:
            _state.reset(token)

    return wrapped
