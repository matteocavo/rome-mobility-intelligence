"""Validate sanitized Cloud n8n artifacts without importing n8n or connecting to services."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "ops/n8n/workflows/rome_mobility_orchestration.json"
BOUNDARY = ROOT / "ops/n8n/workflows/rome_mobility_webhook_boundary.json"
ALLOWED = {
    "n8n-nodes-base." + x
    for x in ("manualTrigger", "scheduleTrigger", "httpRequest", "if", "set", "wait")
}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate(workflow: dict):
    check(workflow.get("active") is False, "Workflow must be inactive")
    check(not workflow.get("pinData"), "Execution/pinned data must not be exported")
    check(
        set(workflow) <= {"name", "active", "nodes", "connections", "settings", "pinData", "tags"},
        "Unexpected workflow metadata",
    )
    encoded = json.dumps(workflow)
    check(
        not re.search(
            r"(?i)password|token|secret|authorization|bearer |databricks|postgres|"
            r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|(?<![A-Za-z])[A-Z]:\\|postgresql://",
            encoded,
        ),
        "Forbidden secret, identifier, direct source or path in export",
    )
    check(
        not re.search(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", encoded, re.I),
        "Unexpected account/credential UUID",
    )
    check(all("credentials" not in n for n in workflow["nodes"]), "No credential IDs in export")
    names = {n["name"] for n in workflow["nodes"]}
    check(len(names) == len(workflow["nodes"]), "Duplicate node names")
    check(all(n["type"] in ALLOWED for n in workflow["nodes"]), "Forbidden execution/source node")
    http_nodes = [n for n in workflow["nodes"] if n["type"].endswith(".httpRequest")]
    expected = {
        "/health",
        "/ready",
        "/predictions/current/persist?limit=100",
        "/predictions/history?limit=10",
    }
    paths = set()
    for node in http_nodes:
        params = node["parameters"]
        url = params["url"]
        check(
            url.startswith("={{ $('FastAPI Configuration').first().json.RMI_API_BASE_URL + "),
            "URL must use only trusted workflow configuration",
        )
        path = url.split('"')[1]
        paths.add(path)
        check(path in expected, "Unapproved HTTP endpoint")
        check(params["method"] == ("POST" if "/persist?" in path else "GET"), "Unexpected method")
        check(
            not any(
                k in params
                for k in (
                    "body",
                    "jsonBody",
                    "sendBody",
                    "sendHeaders",
                    "headerParameters",
                )
            ),
            "No body/auth input",
        )
        check(
            params.get("authentication") == "genericCredentialType"
            and params.get("genericAuthType") == "httpHeaderAuth"
            and "credentials" not in node,
            "Service Header Auth must be bound manually; no credential IDs in export",
        )
        check(
            "X-RMI-Service-Key" in node.get("notes", ""),
            "Required service header must be documented",
        )
        check(node.get("retryOnFail") is False, "Built-in indiscriminate retries forbidden")
        check(
            node.get("onError") == "continueRegularOutput", "Transport errors need terminal summary"
        )
        options = params["options"]
        check(options["redirect"]["redirect"]["followRedirects"] is False, "Redirects forbidden")
        check(0 < options["timeout"] <= 140000, "HTTP timeout missing/unbounded")
        response = options["response"]["response"]
        check(
            response == {"fullResponse": True, "neverError": True, "responseFormat": "json"},
            "HTTP status must be available for selective retries",
        )
    check(paths == expected and len(http_nodes) == 6, "Missing/unexpected HTTP attempts")
    settings = workflow["settings"]
    check(
        settings["timezone"] == "Europe/Rome" and settings["executionTimeout"] == 600,
        "Timezone/workflow deadline incorrect",
    )
    for key, value in {
        "saveDataSuccessExecution": "none",
        "saveDataErrorExecution": "none",
        "saveManualExecutions": False,
        "saveExecutionProgress": False,
    }.items():
        check(settings.get(key) == value, "Execution data retention must be disabled")
    schedule = next(n for n in workflow["nodes"] if n["type"].endswith(".scheduleTrigger"))
    check(
        schedule["parameters"]["rule"]["interval"] == [{"field": "minutes", "minutesInterval": 15}],
        "Schedule must be 15 minutes",
    )
    waits = sorted(
        n["parameters"]["amount"] for n in workflow["nodes"] if n["type"].endswith(".wait")
    )
    check(waits == [30, 60], "Exactly two bounded backoffs required")
    graph = workflow["connections"]
    for source, connections in graph.items():
        check(source in names, "Unknown graph source")
        for output in connections["main"]:
            check(len(output) <= 1, "Fan-out could duplicate persistence")
            check(all(edge["node"] in names for edge in output), "Unknown graph target")

    def walk(name, stack):
        check(name not in stack, "Retry graph must be acyclic")
        for output in graph.get(name, {}).get("main", []):
            for edge in output:
                walk(edge["node"], stack | {name})

    for start in ("Manual Trigger", "Schedule Every 15 Minutes"):
        walk(start, set())
    terminals = names - set(graph)
    for node in workflow["nodes"]:
        if node["name"] in terminals:
            check(
                node["type"].endswith(".set") and node["parameters"]["includeOtherFields"] is False,
                "Terminal must drop HTTP data",
            )
            keys = {a["name"] for a in node["parameters"]["assignments"]["assignments"]}
            check(not {"body", "predictions", "headers", "error"} & keys, "Raw data in summary")


def validate_boundary(workflow: dict):
    check(
        workflow.get("active") is False and not workflow.get("pinData"), "Boundary must be inactive"
    )
    encoded = json.dumps(workflow)
    check(
        not re.search(r"(?i)credentials|password|secret|token|authorization|api/v1|@", encoded),
        "No credential material/admin API in boundary export",
    )
    nodes = {n["name"]: n for n in workflow["nodes"]}
    check(
        {n["type"] for n in nodes.values()}
        == {"n8n-nodes-base.webhook", "n8n-nodes-base.if", "n8n-nodes-base.respondToWebhook"},
        "Boundary can only authenticate, validate and acknowledge",
    )
    webhook = nodes["Authenticated Webhook"]["parameters"]
    check(
        webhook["authentication"] == "headerAuth" and webhook["httpMethod"] == "POST",
        "Native Header Auth is mandatory",
    )
    check(webhook["responseMode"] == "responseNode", "Explicit minimal response required")
    for node in nodes.values():
        if node["type"].endswith(".respondToWebhook"):
            body = json.loads(node["parameters"]["responseBody"])
            check(
                set(body) == {"accepted"} and type(body["accepted"]) is bool,
                "No reflected payload or headers in acknowledgement",
            )
    for key, value in {
        "saveDataSuccessExecution": "none",
        "saveDataErrorExecution": "none",
        "saveManualExecutions": False,
        "saveExecutionProgress": False,
    }.items():
        check(
            workflow["settings"].get(key) == value, "Do not retain webhook headers/execution data"
        )


def main():
    validate(json.loads(WORKFLOW.read_text()))
    validate_boundary(json.loads(BOUNDARY.read_text()))
    print("n8n Cloud artifact policy PASS; account import/runtime validation is separate")


if __name__ == "__main__":
    main()
