from dataclasses import asdict

import pytest

from app.data.training_repository import temporal_split
from app.ml.artifacts import persist
from app.ml.fixtures import FIXTURE_PLAN, synthetic_frame
from app.ml.training import train


@pytest.fixture(scope="session")
def frame():
    return synthetic_frame()


@pytest.fixture(scope="session")
def trained(frame):
    return train(
        temporal_split(frame, FIXTURE_PLAN),
        reference={"source": "synthetic_fixture_only", "temporal_plan": asdict(FIXTURE_PLAN)},
        code_sha="fixture-test",
        synthetic=True,
    )


@pytest.fixture
def bundle(tmp_path, trained):
    path = tmp_path / "bundle"
    persist(path, *trained)
    return path
