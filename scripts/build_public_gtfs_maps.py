"""Build reviewed static GTFS map indexes; offline only, never reads runtime credentials."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def build(source, destination):
    def rows(name):
        with (source / name).open(encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)

    routes = {r["route_id"] for r in rows("routes.txt")}
    stops = {r["stop_id"] for r in rows("stops.txt")}
    trips = {r["trip_id"]: r for r in rows("trips.txt")}
    shapes = defaultdict(list)
    for row in rows("shapes.txt"):
        lat, lon = float(row["shape_pt_lat"]), float(row["shape_pt_lon"])
        assert -90 <= lat <= 90 and -180 <= lon <= 180
        shapes[row["shape_id"]].append((int(row["shape_pt_sequence"]), lat, lon))
    for points in shapes.values():
        points.sort()
        assert len({p[0] for p in points}) == len(points)
    stop_times = missing_stops = missing_trips = 0
    for row in rows("stop_times.txt"):
        stop_times += 1
        missing_stops += row["stop_id"] not in stops
        missing_trips += row["trip_id"] not in trips
    assert not missing_stops and not missing_trips
    grouped = defaultdict(dict)
    for trip_id, row in trips.items():
        assert row["route_id"] in routes and row["shape_id"] in shapes
        grouped[row["route_id"]][trip_id] = row["shape_id"]
    destination.mkdir(parents=True, exist_ok=True)
    for route_id in sorted(routes):
        trip_shapes = grouped[route_id]
        data = {
            "route_id": route_id,
            "trips": trip_shapes,
            "shapes": {
                key: [[lat, lon] for _, lat, lon in shapes[key]]
                for key in sorted(set(trip_shapes.values()))
            },
        }
        filename = hashlib.sha256(route_id.encode()).hexdigest() + ".json"
        (destination / filename).write_text(
            json.dumps(data, separators=(",", ":")), encoding="utf-8"
        )
    hashes = {}
    for name in ("routes.txt", "trips.txt", "stop_times.txt", "stops.txt", "shapes.txt"):
        with (source / name).open("rb") as stream:
            hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {
        "source": "core/data/reference/gtfs_static",
        "sha256": hashes,
        "routes": len(routes),
        "stops": len(stops),
        "trips": len(trips),
        "shapes": len(shapes),
        "stop_times": stop_times,
        "missing_trip_refs": missing_trips,
        "missing_stop_refs": missing_stops,
        "acquired_at": None,
    }
    (destination.parent / "gtfs_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.source, args.destination)
