from app.data.public_geography import PublicGeography


def test_static_gtfs_source_hash_and_real_stop_coordinates():
    geography = PublicGeography()
    assert len(geography.stops) == 8297
    assert (
        geography.source_sha256
        == "97c1b281575f6794a9c639a5527a26f95bb9bd8c2d054387a627c8f369325b62"
    )
    stop = geography.stops["05000"]
    assert stop["name"] == "TERMINI (MA-MB-FS)"
    assert stop["lat"] == 41.901308 and stop["lon"] == 12.500433
    assert "vehicle_lat" not in stop and "shape" not in stop


def test_complete_route_catalog_has_verified_provenance_and_searchable_names():
    geography = PublicGeography()
    assert geography.catalog["total"] == len(geography.routes) == 435
    assert (
        geography.catalog["sha256"]
        == "19ac1d2f24a096f47f9921809f7c645e57aa2027edce4592d458ee4d4c8319a6"
    )
    assert set(geography.routes["011"]) == {
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
    }
    assert "011" in geography.matching_routes("scavi ostia antica")
    assert "557" in geography.matching_routes("557")


def test_catalog_is_anonymous_static_read_only_and_independent_of_database_and_model():
    from unittest.mock import Mock

    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    with TestClient(create_app(Settings(_env_file=None, environment="test"))) as client:
        client.app.state.public_population = Mock()
        response = client.get("/public/routes")
        assert response.status_code == 200 and response.json()["total"] == 435
        client.app.state.public_population.summary.assert_not_called()
        assert client.get("/public/routes?table=other").status_code == 422
        assert client.post("/public/routes").status_code == 405


def test_shapes_are_exact_route_trip_joins_with_no_invented_fallback():
    geography = PublicGeography()
    geometry = geography.route_map("T01", "1#1-2")
    assert geometry.available and geometry.shape_id == "51509"
    assert 2 <= len(geometry.coordinates) <= 5000
    assert not geography.route_map("557", "1#1-2").available
    assert not geography.route_map("T01", "missing-trip").available
    assert not geography.route_map("../../other", "1#1-2").available


def test_map_public_parameters_are_closed_and_bounded():
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    with TestClient(create_app(Settings(_env_file=None, environment="test"))) as client:
        response = client.get("/public/route-map", params={"route": "T01", "trip": "1#1-2"})
        assert response.status_code == 200 and response.json()["available"]
        assert response.json()["source"] == "verified_static_gtfs"
        for params in (
            {"route": "../../other", "trip": "x"},
            {"route": "T01", "trip": "x", "path": "x"},
        ):
            assert client.get("/public/route-map", params=params).status_code == 422
        assert client.post("/public/route-map").status_code == 405
