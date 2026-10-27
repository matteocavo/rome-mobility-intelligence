"""Minimal prediction history. Natural key follows the complete source contract grain."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Identity,
    Index,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
)

metadata = MetaData()
NATURAL_KEY = (
    "source_feed_timestamp",
    "entity_id",
    "trip_id",
    "stop_sequence",
    "stop_id",
    "model_version",
)

prediction_history = Table(
    "prediction_history",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("source_feed_timestamp", BigInteger, nullable=False),
    Column("prediction_generated_at", DateTime(timezone=True), nullable=False),
    Column("entity_id", String(512), nullable=False),
    Column("route_id", String(512)),
    Column("trip_id", String(512), nullable=False),
    Column("vehicle_id", String(512)),
    Column("stop_id", String(512), nullable=False),
    Column("stop_sequence", BigInteger, nullable=False),
    Column("target_next_stop_id", String(512)),
    Column("current_arrival_delay_seconds", Float),
    Column("major_delay_probability", Float, nullable=False),
    Column("predicted_major_delay", Boolean, nullable=False),
    Column("model_version", String(64), nullable=False),
    Column("feature_contract_hash", String(64), nullable=False),
    Column("threshold", Float, nullable=False),
    Column("source_silver_version", BigInteger),
    Column("feature_preparation_batch_id", String(512)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint(*NATURAL_KEY, name="uq_prediction_history_source_model"),
    CheckConstraint("source_feed_timestamp >= 0", name="ck_history_feed"),
    CheckConstraint("stop_sequence >= 0", name="ck_history_stop_sequence"),
    CheckConstraint(
        "major_delay_probability >= 0 AND major_delay_probability <= 1",
        name="ck_history_probability",
    ),
    CheckConstraint("threshold > 0 AND threshold < 1", name="ck_history_threshold"),
    CheckConstraint(
        "predicted_major_delay = (major_delay_probability >= threshold)", name="ck_history_decision"
    ),
    CheckConstraint("model_version ~ '^[a-f0-9]{64}$'", name="ck_history_model_digest"),
    CheckConstraint("feature_contract_hash ~ '^[a-f0-9]{64}$'", name="ck_history_feature_hash"),
    schema="public",
)
Index(
    "ix_history_generated_id",
    prediction_history.c.prediction_generated_at.desc(),
    prediction_history.c.id.desc(),
)
Index(
    "ix_history_route_generated_id",
    prediction_history.c.route_id,
    prediction_history.c.prediction_generated_at.desc(),
    prediction_history.c.id.desc(),
)
