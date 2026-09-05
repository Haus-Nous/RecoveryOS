"""Payment provider connections schema.

Revision ID: 0003_payment_provider_connections
Revises: 0002_identity_and_membership
Create Date: 2026-09-05 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_provider_connections"
down_revision: str | None = "0002_identity_and_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_provider_connections",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("credential_ref", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("key_id_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "merchant_id",
            "provider",
            "mode",
            "credential_ref",
            name="uq_payment_provider_connections_merchant_provider_mode_ref",
        ),
        sa.CheckConstraint(
            "provider IN ('RAZORPAY')",
            name="ck_provider_connections_provider",
        ),
        sa.CheckConstraint(
            "mode IN ('TEST', 'LIVE')",
            name="ck_provider_connections_mode",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED', 'UNVERIFIED')",
            name="ck_provider_connections_status",
        ),
    )
    op.create_index(
        "ix_payment_provider_connections_merchant_id",
        "payment_provider_connections",
        ["merchant_id"],
    )
    op.create_index(
        "ix_payment_provider_connections_merchant_status",
        "payment_provider_connections",
        ["merchant_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("payment_provider_connections")
