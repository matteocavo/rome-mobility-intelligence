"""Immutable public GTFS static-stop lookup. Never invents a vehicle position or route shape."""

import json
from pathlib import Path


class PublicGeography:
    def __init__(self, settings=None):
        data = json.loads(
            (Path(__file__).parent / "reference/stops.json").read_text(encoding="utf-8")
        )
        self.stops = data["stops"]
        self.source_sha256 = data["sha256"]
