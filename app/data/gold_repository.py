"""Bounded, manifest-pinned Gold SELECTs. Never read Silver or start a warehouse."""

import json
import re
import urllib.request

from app.core.workload_auth import NoRedirect, WorkloadCredentials
from app.data.databricks_client import DataAccessError, DatabricksClient

TABLES = {
    "overview": "executive_overview",
    "routes": "route_reliability",
    "stops": "stop_reliability",
    "temporal": "temporal_reliability",
}
PREFIX = "rome_transport.gold."
COLUMNS = """ops_observation_count AS total, ops_known_delay_count AS known,
ops_missing_delay_count AS missing, ops_major_delay_count AS major,
ops_mean_delay_seconds AS mean_seconds, ops_median_delay_seconds AS median_seconds,
ops_p90_delay_seconds AS p90_seconds, ops_first_feed_timestamp AS first_feed,
ops_latest_feed_timestamp AS last_feed, ops_release_id, ops_source_version, ops_metric_definition"""


def require_running(settings):
    match = re.fullmatch(r"/sql/1\.0/warehouses/([a-f0-9]{16})", settings.databricks_http_path)
    if not match:
        raise DataAccessError("Gold warehouse configuration unavailable")
    credentials = WorkloadCredentials(settings)
    request = urllib.request.Request(
        "https://" + settings.databricks_server_hostname + "/api/2.0/sql/warehouses/" + match[1],
        headers=credentials.headers(),
        method="GET",
    )
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=5) as response:
        raw = response.read(65537)
    if len(raw) > 65536 or json.loads(raw).get("state") != "RUNNING":
        raise DataAccessError("Gold warehouse is not running")


class GoldRepository:
    def __init__(self, settings):
        self.settings = settings.model_copy(
            update={
                "databricks_warehouse_wake_enabled": False,
                "databricks_query_timeout_seconds": 8.0,
            }
        )
        self.client = DatabricksClient(self.settings)

    def select(self, query, parameters=None, *, rows):
        require_running(self.settings)
        return self.client.select(query, parameters, max_rows=rows, max_bytes=2_000_000)

    def manifest(self):
        frame = self.select(
            """SELECT refresh_id, unix_timestamp(refresh_timestamp) AS refresh_timestamp,
          gold_versions_json,
          quality_status, dashboard_ready, ops_status, ops_source_table, ops_source_version,
          ops_scoring_version, ops_latest_feed_timestamp, ops_observation_count
          FROM rome_transport.gold.analytics_refresh_metadata""",
            rows=2,
        )
        if len(frame) != 1:
            raise ValueError("One Gold manifest required")
        return frame.iloc[0].to_dict()

    def read(self, view, version, release_id, source_version, start=None, end=None):
        table = TABLES[view]
        if type(version) is not int or version < 0:
            raise ValueError("Invalid Delta version")
        params = {"release": release_id, "source": source_version}
        where = (
            "ops_observation_count IS NOT NULL AND ops_release_id = :release "
            "AND ops_source_version = :source"
        )
        if view == "overview":
            extra, order, cap = "'network' AS key", "ops_observation_count DESC", 1
        elif view in {"routes", "stops"}:
            key = "route_id" if view == "routes" else "stop_id"
            name = "ops_route_short_name" if view == "routes" else "ops_stop_name"
            extra = f"CAST({key} AS STRING) AS key, {name} AS name"
            where += " AND ops_ranking_eligible = true"
            order, cap = f"ops_major_delay_rate DESC, ops_known_delay_count DESC, {key}", 20
        else:
            extra = (
                "CAST(service_date AS STRING) AS key, service_date, "
                "day_of_week AS weekday, feed_hour AS hour"
            )
            where += " AND service_date >= :start AND service_date <= :end"
            params.update(start=start, end=end)
            order, cap = "service_date, feed_hour", 744
        limit = cap if view in {"routes", "stops"} else cap + 1
        return self.select(
            f"SELECT {extra}, {COLUMNS} FROM {PREFIX}{table} VERSION AS OF {version} "
            f"WHERE {where} ORDER BY {order} LIMIT {limit}",
            params,
            rows=cap,
        )
