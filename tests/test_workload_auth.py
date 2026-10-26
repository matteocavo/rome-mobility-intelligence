from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.core.workload_auth import WorkloadAuthenticationError, WorkloadCredentials
from app.data.databricks_client import DataAccessError, DatabricksClient

CLIENT_ID = "11111111-1111-4111-8111-111111111111"


def config(**kwargs):
    return Settings(
        _env_file=None,
        **{
            "databricks_server_hostname": "fixture.cloud.databricks.com",
            "databricks_http_path": "/fixture",
            "databricks_client_id": CLIENT_ID,
            "databricks_client_secret": "fixture-only-secret",
            **kwargs,
        },
    )


def test_oauth_renewal_and_no_personal_profile(monkeypatch):
    from app.core import workload_auth as module

    exchange = MagicMock(
        return_value={"access_token": "fixture-only-token", "expires_in": 3600, "scope": "sql"}
    )
    monkeypatch.setattr(module, "exchange_token", exchange)
    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    provider = WorkloadCredentials(config())
    factory = provider()
    assert factory() == {"Authorization": "Bearer fixture-only-token"}
    factory()
    assert exchange.call_count == 1
    clock[0] += 3600
    factory()
    assert exchange.call_count == 2


def test_windows_credential_source(monkeypatch):
    from app.core import workload_auth as module

    reader = MagicMock(return_value="fixture-only-secret")
    monkeypatch.setattr(module, "read_windows_secret", reader)
    monkeypatch.setattr(
        module,
        "exchange_token",
        lambda *a: {
            "access_token": "fixture-only-token",
            "expires_in": 3600,
            "scope": "sql",
        },
    )
    provider = WorkloadCredentials(
        config(databricks_client_secret="", databricks_credential_target="fixture-target")
    )
    provider.headers()
    reader.assert_called_once_with("fixture-target", CLIENT_ID)


@pytest.mark.parametrize(
    "values",
    [
        {"databricks_token": "fixture-personal-token"},
        {"databricks_client_id": ""},
        {"databricks_server_hostname": "attacker.invalid"},
        {"databricks_server_hostname": "https://fixture.cloud.databricks.com"},
        {"databricks_server_hostname": "fixture.cloud.databricks.com/attacker"},
        {"databricks_client_secret": ""},
        {"databricks_credential_target": "second-source"},
    ],
)
def test_ambiguous_or_personal_auth_rejected(values):
    with pytest.raises(WorkloadAuthenticationError):
        WorkloadCredentials(config(**values))


@pytest.mark.parametrize(
    "response",
    [
        {"access_token": "fixture-token", "expires_in": 3600, "scope": "all-apis"},
        {"access_token": "fixture-token", "expires_in": 3600, "scope": "sql jobs"},
        {"access_token": "", "expires_in": 3600, "scope": "sql"},
        {"access_token": "fixture-token", "expires_in": 10, "scope": "sql"},
    ],
)
def test_response_scope_and_expiry_fail_closed(monkeypatch, response):
    from app.core import workload_auth as module

    monkeypatch.setattr(module, "exchange_token", lambda *args: response)
    with pytest.raises(WorkloadAuthenticationError):
        WorkloadCredentials(config()).headers()


def test_wrong_session_identity_blocks_requested_query():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.fetchone.return_value = ("fixture-personal-identity",)
    with pytest.raises(DataAccessError, match="workload identity"):
        DatabricksClient(config(), lambda **kwargs: connection).select("SELECT 42", max_rows=1)
    assert cursor.execute.call_count == 1
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_redirects_not_followed():
    from app.core.workload_auth import NoRedirect

    assert (
        NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.invalid")
        is None
    )
