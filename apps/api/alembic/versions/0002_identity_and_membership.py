"""Identity, external user identities, and merchant memberships.

Revision ID: 0002_identity_and_membership
Revises: 0001_initial_financial_schema
Create Date: 2026-09-05 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_identity_and_membership"
down_revision: str | None = "0001_initial_financial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. user_identities
    op.create_table(
        "user_identities",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_user_identities_issuer_subject"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
    op.create_index("ix_user_identities_issuer_subject", "user_identities", ["issuer", "subject"])

    # 3. merchant_memberships
    op.create_table(
        "merchant_memberships",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "merchant_id",
            sa.String(length=64),
            sa.ForeignKey("merchants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("merchant_id", "user_id", name="uq_merchant_memberships_merchant_user"),
        sa.CheckConstraint(
            "role IN ('OWNER', 'ADMIN', 'OPERATOR', 'ANALYST', 'AUDITOR')",
            name="ck_merchant_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'REVOKED')",
            name="ck_merchant_memberships_status",
        ),
    )
    op.create_index("ix_merchant_memberships_merchant_id", "merchant_memberships", ["merchant_id"])
    op.create_index("ix_merchant_memberships_user_id", "merchant_memberships", ["user_id"])
    op.create_index(
        "ix_merchant_memberships_merchant_status",
        "merchant_memberships",
        ["merchant_id", "status"],
    )
    op.create_index(
        "ix_merchant_memberships_user_status", "merchant_memberships", ["user_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("merchant_memberships")
    op.drop_table("user_identities")
    op.drop_table("users")
