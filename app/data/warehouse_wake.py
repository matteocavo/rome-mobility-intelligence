"""Bounded recovery for a stopped existing warehouse, never provision/configure compute."""

import json
import logging
import re
import time
import urllib.request

from app.core.workload_auth import NoRedirect

logger = logging.getLogger(__name__)
WAKE_BUDGET_SECONDS = 60


def recover_stopped_warehouse(
    settings, credentials, cancelled, *, opener=None, clock=time.monotonic, sleep=time.sleep,
):
    """One start at most; use only the existing workload's CAN USE grant.

    Called only after an OpenSession HTTP 400. Never turn an unknown 400 into a
    quota classification, never retry auth errors, and never create compute.
    """
    match = re.fullmatch(r"/sql/1\.0/warehouses/([a-f0-9]{16})", settings.databricks_http_path)
    if not match:
        return False
    base = (
        "https://" + settings.databricks_server_hostname
        + "/api/2.0/sql/warehouses/" + match[1]
    )
    opener = opener or urllib.request.build_opener(NoRedirect())
    deadline = clock() + WAKE_BUDGET_SECONDS

    def request(method, suffix=""):
        remaining = deadline - clock()
        if cancelled.is_set() or remaining <= 0:
            raise TimeoutError("Warehouse wake deadline expired")
        req = urllib.request.Request(
            base + suffix, method=method,
            data=b"{}" if method == "POST" else None,
            headers={**credentials.headers(), "Content-Type": "application/json"},
        )
        with opener.open(req, timeout=min(10, remaining)) as response:
            payload = response.read(65537)
            if len(payload) > 65536:
                raise ValueError("Invalid warehouse metadata")
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ValueError("Invalid warehouse metadata")
            return value

    state = request("GET").get("state")
    if state not in {"STOPPED", "STARTING"}:
        return False
    if state == "STOPPED":
        request("POST", "/start")
        logger.info("databricks_warehouse_wake stage=start_requested")
    # A STARTING warehouse is observed, never issued another start request.
    while not cancelled.is_set() and deadline - clock() > 5:
        sleep(5)
        state = request("GET").get("state")
        if state == "RUNNING":
            logger.info("databricks_warehouse_wake stage=running")
            return True
        if state != "STARTING":
            return False
    raise TimeoutError("Warehouse wake deadline expired")
