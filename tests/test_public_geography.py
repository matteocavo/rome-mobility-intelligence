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
