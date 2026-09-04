"""Initial financial schema with strict domain constraints and indexes.

Revision ID: 0001_initial_financial_schema
Revises:
Create Date: 2026-09-04 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_financial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. merchants
    op.create_table(
        "merchants",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_merchants_slug", "merchants", ["slug"], unique=True)

    # 2. orders
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("amount_minor > 0", name="ck_orders_amount_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_orders_currency_iso3"),
        sa.UniqueConstraint("id", "merchant_id", name="uq_orders_id_merchant"),
    )
    op.create_index("ix_orders_merchant_id", "orders", ["merchant_id"])
    op.create_index("ix_orders_merchant_status", "orders", ["merchant_id", "status"])
    op.create_index("ix_orders_merchant_created_at", "orders", ["merchant_id", "created_at"])

    # 3. payments
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("failure_is_retryable_hint", sa.Boolean(), nullable=True),
        sa.Column("failure_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_payments_currency_iso3"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_payments_attempt_positive"),
        sa.UniqueConstraint("id", "merchant_id", name="uq_payments_id_merchant"),
        sa.ForeignKeyConstraint(
            ["order_id", "merchant_id"],
            ["orders.id", "orders.merchant_id"],
            name="fk_payments_order_merchant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_payments_merchant_id", "payments", ["merchant_id"])
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_merchant_order", "payments", ["merchant_id", "order_id"])
    op.create_index("ix_payments_merchant_state", "payments", ["merchant_id", "state"])
    op.create_index("ix_payments_merchant_created_at", "payments", ["merchant_id", "created_at"])

    # 4. recovery_cases
    op.create_table(
        "recovery_cases",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("payment_id", sa.String(length=64), nullable=False),
        sa.Column("amount_at_risk_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("terminal_reason", sa.String(length=512), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("failure_is_retryable_hint", sa.Boolean(), nullable=True),
        sa.Column("failure_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("amount_at_risk_minor > 0", name="ck_recovery_cases_amount_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_recovery_cases_currency_iso3"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_recovery_cases_attempt_non_negative"),
        sa.UniqueConstraint("id", "merchant_id", name="uq_recovery_cases_id_merchant"),
        sa.ForeignKeyConstraint(
            ["payment_id", "merchant_id"],
            ["payments.id", "payments.merchant_id"],
            name="fk_recovery_cases_payment_merchant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_recovery_cases_merchant_id", "recovery_cases", ["merchant_id"])
    op.create_index("ix_recovery_cases_payment_id", "recovery_cases", ["payment_id"])
    op.create_index("ix_recovery_cases_merchant_state", "recovery_cases", ["merchant_id", "state"])
    op.create_index(
        "ix_recovery_cases_merchant_opened_at", "recovery_cases", ["merchant_id", "opened_at"]
    )
    op.create_index(
        "uq_active_recovery_case_per_payment",
        "recovery_cases",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text("state NOT IN ('VERIFIED_RECOVERED', 'EXHAUSTED', 'CANCELLED')"),
    )

    # 5. recovery_proposals
    op.create_table(
        "recovery_proposals",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recovery_case_id", sa.String(length=64), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence_bps >= 0 AND confidence_bps <= 10000",
            name="ck_recovery_proposals_confidence_bps_range",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_case_id", "merchant_id"],
            ["recovery_cases.id", "recovery_cases.merchant_id"],
            name="fk_recovery_proposals_case_merchant",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_recovery_proposals_merchant_id", "recovery_proposals", ["merchant_id"])
    op.create_index(
        "ix_recovery_proposals_recovery_case_id", "recovery_proposals", ["recovery_case_id"]
    )
    op.create_index(
        "ix_recovery_proposals_merchant_case",
        "recovery_proposals",
        ["merchant_id", "recovery_case_id"],
    )
    op.create_index(
        "ix_recovery_proposals_merchant_created_at",
        "recovery_proposals",
        ["merchant_id", "created_at"],
    )

    # 6. policies
    op.create_table(
        "policies",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("max_retry_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("auto_action_amount_limit_minor", sa.BigInteger(), nullable=False),
        sa.Column("review_required_above_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("allowed_strategies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("max_retry_attempts >= 0", name="ck_policies_max_retries_non_negative"),
        sa.CheckConstraint("cooldown_seconds >= 0", name="ck_policies_cooldown_non_negative"),
        sa.CheckConstraint(
            "auto_action_amount_limit_minor >= 0", name="ck_policies_auto_limit_non_negative"
        ),
        sa.CheckConstraint(
            "review_required_above_minor >= 0", name="ck_policies_review_limit_non_negative"
        ),
        sa.CheckConstraint(
            "auto_action_amount_limit_minor <= review_required_above_minor",
            name="ck_policies_auto_limit_le_review_limit",
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_policies_currency_iso3"),
    )
    op.create_index("ix_policies_merchant_enabled", "policies", ["merchant_id", "enabled"])

    # 7. recovery_actions
    op.create_table(
        "recovery_actions",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recovery_case_id", sa.String(length=64), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("authorization_decision", sa.String(length=32), nullable=True),
        sa.Column("authorization_reference", sa.String(length=255), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_recovery_actions_attempt_positive"),
        sa.CheckConstraint(
            "(state NOT IN ('QUEUED', 'EXECUTING')) OR (COALESCE(authorization_decision, '') = 'ALLOW')",
            name="ck_recovery_actions_executable_must_be_allowed",
        ),
        sa.UniqueConstraint("id", "merchant_id", name="uq_recovery_actions_id_merchant"),
        sa.ForeignKeyConstraint(
            ["recovery_case_id", "merchant_id"],
            ["recovery_cases.id", "recovery_cases.merchant_id"],
            name="fk_recovery_actions_case_merchant",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_recovery_actions_merchant_id", "recovery_actions", ["merchant_id"])
    op.create_index(
        "ix_recovery_actions_recovery_case_id", "recovery_actions", ["recovery_case_id"]
    )
    op.create_index(
        "ix_recovery_actions_merchant_case", "recovery_actions", ["merchant_id", "recovery_case_id"]
    )
    op.create_index(
        "ix_recovery_actions_merchant_state", "recovery_actions", ["merchant_id", "state"]
    )
    op.create_index(
        "ix_recovery_actions_merchant_created_at", "recovery_actions", ["merchant_id", "created_at"]
    )

    # 8. recovery_outcomes
    op.create_table(
        "recovery_outcomes",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recovery_case_id", sa.String(length=64), nullable=False),
        sa.Column("recovery_action_id", sa.String(length=64), unique=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_recovered_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "verification_status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"
        ),
        sa.Column("verification_reference", sa.String(length=255), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "amount_recovered_minor >= 0", name="ck_recovery_outcomes_amount_non_negative"
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_recovery_outcomes_currency_iso3"),
        sa.CheckConstraint(
            "(verification_status != 'VERIFIED') OR (verification_reference IS NOT NULL AND verified_at IS NOT NULL AND status = 'RECOVERY_OBSERVED')",
            name="ck_recovery_outcomes_verified_requires_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_case_id", "merchant_id"],
            ["recovery_cases.id", "recovery_cases.merchant_id"],
            name="fk_recovery_outcomes_case_merchant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_action_id", "merchant_id"],
            ["recovery_actions.id", "recovery_actions.merchant_id"],
            name="fk_recovery_outcomes_action_merchant",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_recovery_outcomes_merchant_id", "recovery_outcomes", ["merchant_id"])
    op.create_index(
        "ix_recovery_outcomes_recovery_case_id", "recovery_outcomes", ["recovery_case_id"]
    )
    op.create_index(
        "ix_recovery_outcomes_merchant_case",
        "recovery_outcomes",
        ["merchant_id", "recovery_case_id"],
    )
    op.create_index(
        "ix_recovery_outcomes_merchant_status", "recovery_outcomes", ["merchant_id", "status"]
    )
    op.create_index(
        "ix_recovery_outcomes_merchant_verification",
        "recovery_outcomes",
        ["merchant_id", "verification_status"],
    )

    # 9. domain_events
    op.create_table(
        "domain_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=True),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_domain_events_merchant_id", "domain_events", ["merchant_id"])
    op.create_index(
        "ix_domain_events_aggregate",
        "domain_events",
        ["aggregate_type", "aggregate_id", "occurred_at"],
    )
    op.create_index(
        "ix_domain_events_merchant_occurred_at", "domain_events", ["merchant_id", "occurred_at"]
    )
    op.create_index("ix_domain_events_event_type", "domain_events", ["event_type"])

    # 10. outbox_messages
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), unique=True, nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_outbox_messages_merchant_id", "outbox_messages", ["merchant_id"])
    op.create_index(
        "ix_outbox_messages_unpublished", "outbox_messages", ["published_at", "created_at"]
    )
    op.create_index(
        "ix_outbox_messages_merchant_created", "outbox_messages", ["merchant_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("outbox_messages")
    op.drop_table("domain_events")
    op.drop_table("recovery_outcomes")
    op.drop_table("recovery_actions")
    op.drop_table("policies")
    op.drop_table("recovery_proposals")
    op.drop_table("recovery_cases")
    op.drop_table("payments")
    op.drop_table("orders")
    op.drop_table("merchants")
