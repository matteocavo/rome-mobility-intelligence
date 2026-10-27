"""Container liveness only, no credentials or database/warehouse probe."""

import json
import os
import sys
import urllib.request


def main():
    try:
        host = json.loads(os.environ["ALLOWED_HOSTS"])[0]
        request = urllib.request.Request("http://127.0.0.1:8000/health", headers={"Host": host})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=2) as response:
            if response.status != 200 or json.loads(response.read(512)).get("status") != "ok":
                raise ValueError
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
