"""Persist a one-use TEST gate after validation selection, before TEST prediction."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib


def freeze_selection(path: Path, pipeline, selection: dict) -> None:
    # Existing gates are never overwritten: a repeat needs an explicitly new protocol.
    path.mkdir(parents=True, exist_ok=False)
    joblib.dump(pipeline, path / "frozen-pipeline.joblib")
    selection = {
        **selection,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_sha256": hashlib.sha256(
            (path / "frozen-pipeline.joblib").read_bytes()
        ).hexdigest(),
        "test_evaluation_invocations": 1,
    }
    (path / "selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
