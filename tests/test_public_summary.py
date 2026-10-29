from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.data.databricks_client import DataAccessError, QueryTimeoutError
from app.main import create_app
from tests.test_public_api import public_api  # noqa: F401


@pytest.mark.parametrize("path", ["/public/status", "/public/summary"])
def test_network_kpis_do_not_use_display_limit(public_api, path):  # noqa: F811
    client, _ = public_api
    response = client.get(path)
    assert response.status_code == 200 and response.json()["scored_count"] == 25000
    assert client.get(path + "?page_size=20").status_code == 422


@pytest.mark.parametrize(
    "error,code", [(DataAccessError("PRIVATE"), 503), (QueryTimeoutError("SECRET"), 504)]
)
def test_summary_errors_are_safe(error, code):
    with TestClient(create_app(Settings(_env_file=None, environment="test"))) as client:
        client.app.state.public_population = Mock()
        client.app.state.public_population.summary.side_effect = error
        response = client.get("/public/summary")
        assert response.status_code == code
        assert "PRIVATE" not in response.text and "SECRET" not in response.text
