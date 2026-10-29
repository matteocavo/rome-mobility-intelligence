"""Allowlisted projection shared by paginated public history reads."""

import hashlib
from datetime import datetime, timezone

from app.contracts.public import PublicPrediction

PUBLIC_COLUMNS = (
    "trip_id",
    "vehicle_id",
    "route_id",
    "stop_id",
    "stop_sequence",
    "target_next_stop_id",
    "current_arrival_delay_seconds",
    "major_delay_probability",
    "predicted_major_delay",
    "source_feed_timestamp",
    "prediction_generated_at",
    "threshold",
)


def prediction(row):
    # Select and construct separately: extra fields from a driver/mock cannot widen the API.
    public_id = hashlib.sha256(
        str(
            (
                row.get("_row_id"),
                row["source_feed_timestamp"],
                row["route_id"],
                row["stop_id"],
                row["stop_sequence"],
                row["prediction_generated_at"],
            )
        ).encode()
    ).hexdigest()[:24]
    return PublicPrediction(
        observation_id=public_id,
        trip_id=row.get("trip_id"),
        vehicle_id=row.get("vehicle_id"),
        route_id=row["route_id"],
        stop_id=row["stop_id"],
        stop_sequence=row["stop_sequence"],
        target_next_stop_id=row["target_next_stop_id"],
        observed_current_delay_seconds=row["current_arrival_delay_seconds"],
        major_delay_probability=row["major_delay_probability"],
        predicted_major_delay=row["predicted_major_delay"],
        threshold=row["threshold"],
        source_watermark=datetime.fromtimestamp(row["source_feed_timestamp"], timezone.utc),
        prediction_generated_at=row["prediction_generated_at"],
    )
