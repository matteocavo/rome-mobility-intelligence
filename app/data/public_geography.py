"""Immutable public GTFS static-stop lookup. Never invents a vehicle position or route shape."""

import hashlib
import json
from pathlib import Path

from app.contracts.public import RouteGeometry


class PublicGeography:
    def __init__(self, settings=None):
        data = json.loads(
            (Path(__file__).parent / "reference/stops.json").read_text(encoding="utf-8")
        )
        self.stops = data["stops"]
        self.source_sha256 = data["sha256"]

        catalog = json.loads(
            (Path(__file__).parent / "reference/routes.json").read_text(encoding="utf-8")
        )
        self.catalog = catalog
        self.routes = {row["route_id"]: row for row in catalog["items"]}

    def matching_routes(self, query):
        needle = query.casefold()
        return [
            key
            for key, row in self.routes.items()
            if any(
                needle in str(row[field]).casefold()
                for field in ("route_id", "route_short_name", "route_long_name")
            )
        ]

    def route_map(self, route, trip):
        unavailable = RouteGeometry(route_id=route, trip_id=trip, available=False)
        if route not in self.routes:
            return unavailable
        filename = hashlib.sha256(route.encode()).hexdigest() + ".json"
        data = json.loads(
            (Path(__file__).parent / "reference/maps" / filename).read_text(encoding="utf-8")
        )
        shape_id = data["trips"].get(trip)
        if shape_id is None:
            return unavailable
        coordinates = data["shapes"][shape_id]
        if not 2 <= len(coordinates) <= 5000:
            return unavailable
        return RouteGeometry(
            route_id=route, trip_id=trip, shape_id=shape_id, coordinates=coordinates, available=True
        )
