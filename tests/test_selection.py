import json

import pytest

from app.ml.selection import freeze_selection


def test_selection_gate_persists_before_test_and_refuses_repeat(tmp_path, trained):
    pipeline, _ = trained
    path = tmp_path / "selection"
    freeze_selection(path, pipeline, {"threshold": 0.3, "selected_candidate": "fixture"})
    data = json.loads((path / "selection.json").read_text())
    assert data["test_evaluation_invocations"] == 1
    assert len(data["pipeline_sha256"]) == 64
    assert data["threshold"] == 0.3
    with pytest.raises(FileExistsError):
        freeze_selection(path, pipeline, {"threshold": 0.5})
