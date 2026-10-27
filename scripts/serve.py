"""Single-worker production entry point. HTTPS belongs to the explicitly configured edge."""

import argparse
import logging
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.environ.setdefault("ENVIRONMENT", "production")
    if os.environ["ENVIRONMENT"] != "production":
        raise RuntimeError("Production entry point requires production environment")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        workers=1,
        proxy_headers=False,
        access_log=False,
        server_header=False,
        timeout_keep_alive=5,
        h11_max_incomplete_event_size=16384,
        log_level="warning",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger("app.server").error("server_start_failed")
        raise SystemExit(1) from None
