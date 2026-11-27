import json
import logging
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.scoring_diagnostics import diagnose, stage
from tests.test_current_repository import scoring_frame as scoring_frame
from tests.test_history_api import history_api as history_api
from tests.test_inference_api import api as api

PRIVATE = "Bearer secret-token alice@example.com postgresql://user:password@private/db"


def events(caplog):
    return [
        json.loads(r.message.split(" ", 1)[1])
        for r in caplog.records
        if r.message.startswith("scoring_contract_failure ")
    ]


@pytest.mark.parametrize(
    "failure,expected,kind,field",
    [
        ("empty", "snapshot_size", "ValueError", None),
        ("oversize", "snapshot_size", "ValueError", None),
        ("feature", "feature_validation", "ValidationError", "vehicle_speed"),
        ("missing_feature", "feature_validation", "KeyError", None),
        ("future", "watermark_validation", "ValueError", None),
        ("record", "persistence_record_validation", "ValidationError", "entity_id"),
        ("repository", "snapshot_read_validation", "ValueError", None),
        ("inference", "inference", "TypeError", None),
        ("response", "response_validation", "ValidationError", "major_delay_probability"),
        ("insert", "persistence_insert", "ValueError", None),
    ],
)
def test_diagnostic_stage_and_public_422_unchanged(
    history_api,
    monkeypatch,
    caplog,
    failure,
    expected,
    kind,
    field,
):
    api, database = history_api
    source = api.app.state.current_repository.latest.return_value
    if failure == "empty":
        api.app.state.current_repository.latest.return_value = source.iloc[:0]
    elif failure == "oversize":
        api.app.state.current_repository.latest.return_value = source.iloc[[0, 1, 0]]
    elif failure == "feature":
        source["vehicle_speed"] = PRIVATE
    elif failure == "missing_feature":
        api.app.state.current_repository.latest.return_value = source.drop(columns="vehicle_speed")
    elif failure == "future":
        source["feed_timestamp"] += 3600
    elif failure == "record":
        source["entity_id"] = ""
    elif failure == "repository":
        api.app.state.current_repository.latest.side_effect = ValueError(PRIVATE)
    elif failure == "inference":
        monkeypatch.setattr(
            api.app.state.model, "predict_batch", Mock(side_effect=TypeError(PRIVATE))
        )
    elif failure == "response":
        monkeypatch.setattr(
            api.app.state.model,
            "predict_batch",
            Mock(
                return_value=[
                    {"major_delay_probability": 2.0, "predicted_major_delay": True},
                    {"major_delay_probability": 2.0, "predicted_major_delay": True},
                ]
            ),
        )
    elif failure == "insert":
        api.app.state.history_repository = Mock()
        api.app.state.history_repository.insert_batch.side_effect = ValueError(PRIVATE)
    with caplog.at_level(logging.WARNING):
        response = api.post("/predictions/current/persist?limit=2")
    assert response.status_code == 422
    assert response.json() == {"detail": "Current scoring contract is invalid"}
    details = events(caplog)
    assert len(details) == 1
    assert details[0]["stage"] == expected and details[0]["exception_type"] == kind
    UUID(details[0]["local_correlation_id"])
    if field:
        assert any(field in issue["path"] for issue in details[0]["validation_errors"])
    for value in [PRIVATE, "secret-token", "alice@example.com", "password", "private/db"]:
        assert value not in caplog.text
    assert database.rows == {}


def test_pydantic_context_input_and_unknown_locations_never_logged(caplog):
    error = ValidationError.from_exception_data(
        "private-model",
        [
            {
                "type": "value_error",
                "loc": (PRIVATE, 123456),
                "input": PRIVATE,
                "ctx": {"error": ValueError(PRIVATE)},
            }
        ],
    )

    @diagnose
    def fail():
        stage("feature_validation")
        raise error

    with caplog.at_level(logging.WARNING), pytest.raises(ValidationError) as caught:
        fail()
    assert caught.value is error
    assert events(caplog)[0]["validation_errors"] == [
        {"path": ["[redacted]", "[redacted]"], "category": "value_error"}
    ]
    assert PRIVATE not in caplog.text and "123456" not in caplog.text
    assert "private-model" not in caplog.text and "input" not in events(caplog)[0]


def test_diagnostic_context_is_reset_and_no_log_on_success(caplog):
    @diagnose
    def call(fail):
        stage("snapshot_size")
        if fail:
            raise ValueError(PRIVATE)
        return 42

    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            with pytest.raises(ValueError):
                call(True)
        assert call(False) == 42
    assert len(events(caplog)) == 2
    assert len({item["local_correlation_id"] for item in events(caplog)}) == 2


def test_optional_logging_failure_does_not_change_original_exception(monkeypatch):
    error = KeyError(PRIVATE)
    monkeypatch.setattr(
        "app.core.scoring_diagnostics.logger.warning", Mock(side_effect=RuntimeError())
    )

    @diagnose
    def fail():
        stage("snapshot_read_validation")
        raise error

    with pytest.raises(KeyError) as caught:
        fail()
    assert caught.value is error


def test_freshness_response_remains_separate(history_api, caplog):
    api, database = history_api
    api.app.state.current_repository.latest.return_value["feed_timestamp"] -= 10000
    with caplog.at_level(logging.WARNING):
        response = api.post("/predictions/current/persist?limit=2")
    assert response.status_code == 422
    assert response.json() == {"detail": "Source snapshot must be between 0 and 7200 seconds old"}
    assert events(caplog) == [] and database.rows == {}


@pytest.mark.parametrize(
    "column,value,expected",
    [
        ("grain_rows", 2, "snapshot_identity"),
        ("feature_contract_hash", "private-hash", "snapshot_contract"),
        ("source_silver_version_count", 0, "snapshot_lineage"),
        ("feature_prepared_at_consistent", False, "snapshot_lineage"),
        ("target_next_stop_sequence", 0, "target_identity"),
        ("feed_timestamp", -1, "source_temporal"),
    ],
)
def test_repository_gate_is_identified_without_sql_changes(
    history_api,
    scoring_frame,
    caplog,
    column,
    value,
    expected,
):
    from app.data.current_repository import CurrentScoringRepository

    api, database = history_api
    scoring_frame[column] = value
    client = Mock()
    client.select.return_value = scoring_frame
    api.app.state.current_repository = CurrentScoringRepository(client, api.app.state.settings)
    with caplog.at_level(logging.WARNING):
        response = api.post("/predictions/current/persist?limit=2")
    assert response.status_code == 422 and database.rows == {}
    assert events(caplog)[0]["stage"] == expected
    client.select.assert_called_once()
    assert "private-hash" not in caplog.text
