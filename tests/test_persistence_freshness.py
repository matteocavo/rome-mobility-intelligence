from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.batch_scoring import (
    PersistenceFreshnessError,
    validate_persistence_freshness,
)


@pytest.mark.parametrize("age", [0, 1, 7199, 7200])
def test_inclusive_batch_window(age):
    validate_persistence_freshness(
        [SimpleNamespace(source_feed_timestamp=100000)],
        datetime.fromtimestamp(100000 + age, timezone.utc),
    )


@pytest.mark.parametrize("age", [-1, 7200.000001, 7201])
def test_outside_batch_window(age):
    with pytest.raises(PersistenceFreshnessError):
        validate_persistence_freshness(
            [SimpleNamespace(source_feed_timestamp=100000)],
            datetime.fromtimestamp(100000 + age, timezone.utc),
        )


def test_any_stale_row_rejects_entire_batch():
    with pytest.raises(PersistenceFreshnessError):
        validate_persistence_freshness(
            [
                SimpleNamespace(source_feed_timestamp=100000),
                SimpleNamespace(source_feed_timestamp=90000),
            ],
            datetime.fromtimestamp(100001, timezone.utc),
        )
