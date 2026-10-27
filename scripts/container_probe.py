"""Linux offline probe. Print memory stages only, never model/data/credentials."""

import json
import resource
import threading
import time
import urllib.request


def memory(stage):
    with open("/proc/self/status", encoding="ascii") as stream:
        rss = next(int(line.split()[1]) for line in stream if line.startswith("VmRSS:"))
    print(
        json.dumps(
            {
                "stage": stage,
                "rss_mib": round(rss / 1024, 1),
                "peak_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            }
        ),
        flush=True,
    )


def main():
    memory("process_start")
    import uvicorn

    from app.core.config import Settings
    from app.main import create_app

    memory("imports_loaded")
    cfg = Settings()
    application = create_app(cfg)
    server = uvicorn.Server(
        uvicorn.Config(
            application,
            host="127.0.0.1",
            port=8000,
            log_level="error",
            access_log=False,
            proxy_headers=False,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 60
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started or application.state.model is None:
        raise RuntimeError("Container model unavailable")
    memory("model_loaded")
    # Synthetic inputs only; works with approved real bundles without exporting data.
    from app.contracts.operational_ml import CATEGORICAL, FEATURES

    row = {name: "synthetic-probe" if name in CATEGORICAL else 0 for name in FEATURES}
    # Numeric categorical fields use integer categories per the closed API schema.
    row.update(route_type=3, direction_id=0, current_status="IN_TRANSIT_TO")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for path, payload in (("/predict", row), ("/predict/batch", [row] * 100)):
        request = urllib.request.Request(
            "http://127.0.0.1:8000" + path,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Host": "api.example.org",
                "X-RMI-Service-Key": cfg.n8n_service_api_key.get_secret_value(),
            },
        )
        with opener.open(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError("Container inference failed")
            response.read(65536)
        memory(path)
    # No current-source call: network=none intentionally forbids external effects.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(
        json.dumps(
            {
                "probe": "PASS",
                "synthetic": application.state.model.metadata.synthetic,
                "fit": "FAIL" if peak >= 512 else "HIGH RISK" if peak > 450 else "PASS",
                "peak_mib": round(peak, 1),
            }
        ),
        flush=True,
    )
    server.should_exit = True
    thread.join(timeout=10)
    if peak >= 512:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Container probe failed; diagnostics suppressed") from None
