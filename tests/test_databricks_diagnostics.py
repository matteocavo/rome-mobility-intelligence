import logging
import urllib.error
from unittest.mock import Mock

import pytest
from databricks.sql.exc import ProgrammingError, RequestError

from app.core.config import Settings
from app.core.databricks_diagnostics import failure_category
from app.core.workload_auth import WorkloadAuthenticationError, exchange_token
from app.data.databricks_client import DataAccessError, DatabricksClient
from app.services.batch_scoring import BatchScoringService
from tests.test_databricks_client import configured

PRIVATE = "private-token private-host private-query"


def test_scoring_failure_never_calls_history_insert():
    scoring, history = Mock(), Mock()
    scoring.score.side_effect = DataAccessError(PRIVATE)
    settings = Settings(_env_file=None, enable_prediction_persistence=True)
    with pytest.raises(DataAccessError):
        BatchScoringService(scoring, history, settings).run(2)
    history.insert_batch.assert_not_called()


@pytest.mark.parametrize("error,category", [
    (RequestError(PRIVATE, {"http-code": 401}), "databricks_authentication"),
    (RequestError(PRIVATE, {"http-code": 403}), "databricks_authorization"),
    (RequestError(PRIVATE, {"http-code": 503}), "databricks_compute_unavailable"),
    (RequestError(PRIVATE, {"http-code": 504}), "databricks_timeout"),
    (RequestError(PRIVATE, {"http-code": 400, "error-message": "Free daily limit"}),
     "databricks_compute_unavailable"),
    (TimeoutError(PRIVATE), "databricks_timeout"),
    (urllib.error.URLError(PRIVATE), "databricks_connectivity"),
    (ProgrammingError(PRIVATE), "databricks_query_error"),
    (RuntimeError(PRIVATE), "databricks_unknown"),
])
def test_failure_categories_do_not_export_messages(error, category):
    assert failure_category(error) == category


def test_nested_oauth_category_survives_connector_wrapper():
    error = RequestError(PRIVATE, {"original-exception": WorkloadAuthenticationError(
        PRIVATE, "databricks_authentication"
    )})
    assert failure_category(error) == "databricks_authentication"


def test_connection_failure_log_and_exception_are_sanitized(caplog):
    connect = Mock(side_effect=RequestError(PRIVATE, {"http-code": 403}))
    with caplog.at_level(logging.WARNING), pytest.raises(DataAccessError) as caught:
        DatabricksClient(configured(), connect).select("SELECT 1", max_rows=1)
    assert "databricks_authorization" in caplog.text
    assert PRIVATE not in caplog.text + str(caught.value)
    assert "fixture.cloud.databricks.com" not in caplog.text


@pytest.mark.parametrize("status,category", [
    (401, "databricks_authentication"), (403, "databricks_authorization"),
])
def test_oauth_status_is_preserved_without_secret_output(monkeypatch, caplog, status, category):
    opener = Mock()
    opener.open.side_effect = urllib.error.HTTPError(
        "https://private.invalid", status, PRIVATE, {}, None
    )
    monkeypatch.setattr("app.core.workload_auth.urllib.request.build_opener", lambda *a: opener)
    with caplog.at_level(logging.WARNING), pytest.raises(WorkloadAuthenticationError) as caught:
        exchange_token("fixture.cloud.databricks.com", "fixture-id", PRIVATE)
    assert caught.value.category == category
    assert category in caplog.text
    assert PRIVATE not in caplog.text + str(caught.value)
