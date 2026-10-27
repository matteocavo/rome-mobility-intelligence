"""BuildKit entry point. Only fixed error text can reach build logs."""

import argparse
import json
from pathlib import Path

from app.core.artifact_bootstrap import Source, bootstrap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--trusted-digest-file", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if (
            args.source_config.stat().st_size > 16384
            or args.trusted_digest_file.stat().st_size > 128
        ):
            raise ValueError
        source = Source(**json.loads(args.source_config.read_text(encoding="utf-8")))
        digest = args.trusted_digest_file.read_text(encoding="ascii").strip()
        root = args.destination.parent
        root.mkdir(mode=0o755, parents=True, exist_ok=True)
        bootstrap(source, args.destination, root=root, digest=digest)
    except Exception:
        raise SystemExit("Model artifact bootstrap failed") from None


if __name__ == "__main__":
    main()
