"""Initial minimal application prediction history, not a Databricks output table."""

import sqlalchemy as sa

from alembic import op

revision = "0001_prediction_history"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prediction_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_feed_timestamp", sa.BigInteger(), nullable=False),
        sa.Column("prediction_generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entity_id", sa.String(512), nullable=False),
        sa.Column("route_id", sa.String(512)),
        sa.Column("trip_id", sa.String(512), nullable=False),
        sa.Column("vehicle_id", sa.String(512)),
        sa.Column("stop_id", sa.String(512), nullable=False),
        sa.Column("stop_sequence", sa.BigInteger(), nullable=False),
        sa.Column("target_next_stop_id", sa.String(512)),
        sa.Column("current_arrival_delay_seconds", sa.Float()),
        sa.Column("major_delay_probability", sa.Float(), nullable=False),
        sa.Column("predicted_major_delay", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("feature_contract_hash", sa.String(64), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("source_silver_version", sa.BigInteger()),
        sa.Column("feature_preparation_batch_id", sa.String(512)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "source_feed_timestamp",
            "entity_id",
            "trip_id",
            "stop_sequence",
            "stop_id",
            "model_version",
            name="uq_prediction_history_source_model",
        ),
        sa.CheckConstraint("source_feed_timestamp >= 0", name="ck_history_feed"),
        sa.CheckConstraint("stop_sequence >= 0", name="ck_history_stop_sequence"),
        sa.CheckConstraint(
            "major_delay_probability >= 0 AND major_delay_probability <= 1",
            name="ck_history_probability",
        ),
        sa.CheckConstraint("threshold > 0 AND threshold < 1", name="ck_history_threshold"),
        sa.CheckConstraint(
            "predicted_major_delay = (major_delay_probability >= threshold)",
            name="ck_history_decision",
        ),
        sa.CheckConstraint("model_version ~ '^[a-f0-9]{64}$'", name="ck_history_model_digest"),
        sa.CheckConstraint(
            "feature_contract_hash ~ '^[a-f0-9]{64}$'", name="ck_history_feature_hash"
        ),
        schema="public",
    )
    op.create_index(
        "ix_history_generated_id",
        "prediction_history",
        [sa.text("prediction_generated_at DESC"), sa.text("id DESC")],
        schema="public",
    )
    op.create_index(
        "ix_history_route_generated_id",
        "prediction_history",
        ["route_id", sa.text("prediction_generated_at DESC"), sa.text("id DESC")],
        schema="public",
    )


def downgrade():
    op.drop_index("ix_history_route_generated_id", table_name="prediction_history", schema="public")
    op.drop_index("ix_history_generated_id", table_name="prediction_history", schema="public")
    op.drop_table("prediction_history", schema="public")
