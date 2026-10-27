import argparse
import json

import numpy as np
import pandas as pd

from app.contracts.operational_ml import CATEGORICAL, NUMERIC
from app.ml.artifacts import load, probabilities


def main():
    parser = argparse.ArgumentParser(description="Validate a trusted local artifact")
    parser.add_argument("artifact", type=__import__("pathlib").Path)
    parser.add_argument("--trusted-root", type=__import__("pathlib").Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()
    pipeline, metadata = load(
        args.artifact,
        trusted_root=args.trusted_root,
        expected_manifest_sha256=args.expected_manifest_sha256,
    )
    # Explicit synthetic smoke vector, not a claim about real-world prediction quality.
    row = {**dict.fromkeys(NUMERIC, 0.0), **dict.fromkeys(CATEGORICAL, "__UNSEEN_SMOKE__")}
    row.update(route_type=999, direction_id=999)
    p = probabilities(pipeline, pd.DataFrame([row]))
    if not np.isfinite(p).all():
        raise ValueError("Smoke inference failed")
    print(
        json.dumps(
            {
                "status": "PASS",
                "synthetic_model": metadata.synthetic,
                "threshold": metadata.threshold,
                "feature_hash": metadata.feature_contract_hash,
            }
        )
    )


if __name__ == "__main__":
    main()
