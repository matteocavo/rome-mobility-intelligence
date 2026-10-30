from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from weakref import ref

import numpy as np
import pandas as pd
import pytest
from sqlalchemy.dialects import postgresql

from app.contracts.public import PageQuery
from app.data.databricks_client import DataAccessError
from app.ml.fixtures import synthetic_frame
from app.persistence.public_history import filtered
from app.services.public_population import PublicPopulation


def population(rows=101):
    frame = synthetic_frame(rows)
    frame["feed_timestamp"] = int(datetime.now(timezone.utc).timestamp()) - 120
    frame["target_next_stop_id"] = "target-stop"
    frame["route_id"] = ["557" if i % 2 else "85" for i in range(rows)]
    frame["vehicle_id"] = [f"real-fixture-vehicle-{i}" for i in range(rows)]
    repository = Mock()
    repository.population.return_value = frame
    model = Mock(metadata=SimpleNamespace(synthetic=False), threshold=0.35)
    model.predict_proba.return_value = np.linspace(0, 0.99, rows)
    geography = SimpleNamespace(
        stops={"fixture-stop": {"name": "A real fixture name", "lat": 41.9, "lon": 12.5}}
    )
    return PublicPopulation(repository, lambda: model, geography), model, repository


def test_global_sort_pagination_and_summary_are_not_limited_to_first_page():
    service, model, repository = population()
    first = service.page(PageQuery(page=1, page_size=20, sort="risk_desc"))
    second = service.page(PageQuery(page=2, page_size=20, sort="risk_desc"))
    assert first.total == 101 and first.total_pages == 6 and len(first.items) == 20
    assert first.items[0].major_delay_probability == 0.99
    assert second.items[0].major_delay_probability < first.items[-1].major_delay_probability
    assert not {v.observation_id for v in first.items} & {v.observation_id for v in second.items}
    assert service.summary().scored_count == 101
    assert service.summary().major_delay_count == 65
    repository.population.assert_called_once()
    model.predict_proba.assert_called_once()


def test_search_filters_full_population_before_page_slice():
    service, _, _ = population()
    result = service.page(PageQuery(query="557", page_size=10))
    assert result.total == 50 and len(result.items) == 10 and result.total_pages == 5
    by_vehicle = service.page(PageQuery(query="real-fixture-vehicle-0"))
    assert by_vehicle.total == 1
    major = service.page(PageQuery(risk_class="major", page_size=10))
    assert major.total == 65 and all(item.predicted_major_delay for item in major.items)


def test_cached_whole_population_failure_never_returns_partial_old_page():
    service, _, repository = population()
    service.summary()
    service._expires = 0
    repository.population.side_effect = DataAccessError("PRIVATE")
    with pytest.raises(DataAccessError):
        service.page(PageQuery())
    with pytest.raises(DataAccessError):
        service.page(PageQuery())
    assert repository.population.call_count == 2


def test_retired_cache_is_released_before_loading_replacement():
    class WeakRows(list):
        pass

    service, _, repository = population()
    service.summary()
    # A weak-referenceable list proves object lifetime, not an unreliable RSS guess.
    service._rows = WeakRows(service._rows)
    service._snapshot = (service._rows, service._summary, service._expires)
    retired = ref(service._rows)
    service._expires = 0
    source = repository.population.return_value

    def reload():
        assert retired() is None, "Expired rows must not overlap the next source DataFrame"
        return source

    repository.population.side_effect = reload
    assert service.summary().scored_count == 101


def test_replacement_does_not_mutate_snapshot_owned_by_an_existing_reader():
    service, _, repository = population()
    reader_snapshot = service._ensure()
    original_ids = [row.observation_id for row, _ in reader_snapshot[0]]
    service._expires = 0
    assert service.summary().scored_count == 101
    assert repository.population.call_count == 2
    assert [row.observation_id for row, _ in reader_snapshot[0]] == original_ids
    assert service._snapshot[0] is not reader_snapshot[0]


def test_native_reclamation_only_runs_at_rebuild_boundaries_not_cached_pages():
    service, _, repository = population()
    with patch("app.services.public_population.reclaim_unused_memory") as reclaim:
        service.page(PageQuery())
        assert reclaim.call_count == 2
        service.summary()
        service.page(PageQuery(page=2))
        service.aggregate(PageQuery())
        assert reclaim.call_count == 2
        service._expires = 0
        service.page(PageQuery())
        assert reclaim.call_count == 4
    assert repository.population.call_count == 2


def test_history_filters_bind_user_values_and_never_accept_identifier_input():
    from sqlalchemy import select

    from app.persistence.models import prediction_history

    query = PageQuery(query="x%_'; DROP TABLE nope", route="557", risk_class="major")
    sql = select(prediction_history.c.id).where(*filtered(query, SimpleNamespace(stops={})))
    compiled = sql.compile(dialect=postgresql.dialect())
    assert "DROP" not in str(compiled) and "557" not in str(compiled)
    assert "ILIKE" in str(compiled) and "predicted_major_delay IS true" in str(compiled)
    assert any("DROP" in str(value) for value in compiled.params.values())


@pytest.mark.parametrize("size", [10, 20, 50])
def test_allowed_page_sizes_are_parsed_from_http_strings(size):
    assert PageQuery.model_validate({"page_size": str(size)}).page_size == size


def test_current_population_rejects_truncated_result_before_model_scoring():
    from app.data.current_repository import CurrentScoringRepository

    repository = CurrentScoringRepository(Mock(), Mock())
    repository._latest = Mock(return_value=pd.DataFrame({"snapshot_rows": [3, 3]}))
    with pytest.raises(DataAccessError, match="budget"):
        repository.population()
    repository._latest.assert_called_once_with(50000, 48_000_000, allow_empty=True)


def test_empty_population_is_honest_and_never_runs_inference():
    service, model, repository = population()
    repository.population.return_value = pd.DataFrame()
    result = service.page(PageQuery())
    assert result.total == 0 and result.items == []
    assert service.summary().scored_count == 0 and service.summary().major_delay_rate is None
    model.predict_proba.assert_not_called()


def test_catalog_names_are_searchable_globally_and_routes_without_data_remain_empty():
    service, _, _ = population()
    service.geography.routes = {
        "557": {
            "route_short_name": "SHORT",
            "route_long_name": "Catalog terminus",
            "route_type": 3,
        },
        "UNOBSERVED": {
            "route_short_name": "EMPTY",
            "route_long_name": "No observations",
            "route_type": 0,
        },
    }
    result = service.page(PageQuery(query="catalog terminus", page_size=10))
    assert result.total == 50 and result.source_route_count == 2
    assert result.items[0].route_short_name == "SHORT"
    empty = service.page(PageQuery(route="UNOBSERVED"))
    assert empty.total == 0 and empty.items == []
    assert "UNOBSERVED" in service.geography.routes


def test_history_name_search_uses_catalog_ids_as_bound_values():
    from sqlalchemy import select

    from app.data.public_geography import PublicGeography
    from app.persistence.models import prediction_history

    sql = select(prediction_history.c.id).where(
        *filtered(PageQuery(query="scavi ostia antica"), PublicGeography())
    )
    compiled = sql.compile(dialect=postgresql.dialect())
    assert "scavi" not in str(compiled) and "011" not in str(compiled)
    assert any(isinstance(value, list) and "011" in value for value in compiled.params.values())


def test_population_inference_is_chunked_and_every_row_remains_available():
    service, model, _ = population(2051)
    model.predict_proba.side_effect = lambda frame: np.full(len(frame), 0.4)
    result = service.page(PageQuery(page=103, page_size=20))
    assert result.total == 2051 and len(result.items) == 11
    assert service.summary().major_delay_count == 2051
    assert [len(call.args[0]) for call in model.predict_proba.call_args_list] == [1024, 1024, 3]
    # Cache rows have no per-record Pydantic dictionaries/fields-set.
    assert not hasattr(service._snapshot[0][0][0], "__dict__")


def test_chunking_preserves_model_probabilities_exactly(bundle, bundle_trust):
    from app.contracts.operational_ml import FEATURES
    from app.services.model_service import ModelService

    model = ModelService(bundle, **bundle_trust)
    frame = synthetic_frame(2051).loc[:, list(FEATURES)]
    complete = model.predict_proba(frame)
    chunked = np.concatenate(
        [
            model.predict_proba(frame.iloc[start : start + 1024])
            for start in range(0, len(frame), 1024)
        ]
    )
    np.testing.assert_array_equal(complete, chunked)
