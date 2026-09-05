"""Domain entities, enums, and RBAC permission models for Identity & Membership."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.types import MerchantId
from app.identity.domain.types import MembershipId, UserId, UserIdentityId


class Role(StrEnum):
    """Finite roles in RecoveryOS."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    AUDITOR = "AUDITOR"


class MembershipStatus(StrEnum):
    """Lifecycle status of a user's merchant membership."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class Permission(StrEnum):
    """Finite permissions for RBAC enforcement."""

    MERCHANT_READ = "MERCHANT_READ"
    MERCHANT_MANAGE = "MERCHANT_MANAGE"
    MEMBERS_READ = "MEMBERS_READ"
    MEMBERS_MANAGE = "MEMBERS_MANAGE"
    OWNERSHIP_MANAGE = "OWNERSHIP_MANAGE"
    PAYMENTS_READ = "PAYMENTS_READ"
    RECOVERY_READ = "RECOVERY_READ"
    RECOVERY_OPERATE = "RECOVERY_OPERATE"
    RECOVERY_APPROVE = "RECOVERY_APPROVE"
    POLICIES_READ = "POLICIES_READ"
    POLICIES_MANAGE = "POLICIES_MANAGE"
    AUDIT_READ = "AUDIT_READ"


# Centralized, explicit, non-negotiable Role-to-Permission mapping
ROLE_PERMISSIONS_MAP: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(
        {
            Permission.MERCHANT_READ,
            Permission.MERCHANT_MANAGE,
            Permission.MEMBERS_READ,
            Permission.MEMBERS_MANAGE,
            Permission.OWNERSHIP_MANAGE,
            Permission.PAYMENTS_READ,
            Permission.RECOVERY_READ,
            Permission.RECOVERY_OPERATE,
            Permission.RECOVERY_APPROVE,
            Permission.POLICIES_READ,
            Permission.POLICIES_MANAGE,
            Permission.AUDIT_READ,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.MERCHANT_READ,
            Permission.MERCHANT_MANAGE,
            Permission.MEMBERS_READ,
            Permission.MEMBERS_MANAGE,
            # Note: ADMIN strictly does NOT have OWNERSHIP_MANAGE
            Permission.PAYMENTS_READ,
            Permission.RECOVERY_READ,
            Permission.RECOVERY_OPERATE,
            Permission.RECOVERY_APPROVE,
            Permission.POLICIES_READ,
            Permission.POLICIES_MANAGE,
            Permission.AUDIT_READ,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Permission.MERCHANT_READ,
            Permission.MEMBERS_READ,
            Permission.PAYMENTS_READ,
            Permission.RECOVERY_READ,
            Permission.RECOVERY_OPERATE,
            # Note: OPERATOR strictly does NOT have RECOVERY_APPROVE
            Permission.POLICIES_READ,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.MERCHANT_READ,
            Permission.MEMBERS_READ,
            Permission.PAYMENTS_READ,
            Permission.RECOVERY_READ,
            Permission.POLICIES_READ,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.MERCHANT_READ,
            Permission.MEMBERS_READ,
            Permission.PAYMENTS_READ,
            Permission.RECOVERY_READ,
            Permission.POLICIES_READ,
            Permission.AUDIT_READ,
        }
    ),
}


def get_permissions_for_role(role: Role) -> frozenset[Permission]:
    """Retrieve explicit permissions for a role, with fail-closed deny-by-default."""
    return ROLE_PERMISSIONS_MAP.get(role, frozenset())


@dataclass(frozen=True)
class User:
    """Internal user entity."""

    id: UserId
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class UserIdentity:
    """External identity provider mapping (e.g. Supabase Auth)."""

    id: UserIdentityId
    user_id: UserId
    issuer: str
    subject: str
    email: str | None
    email_verified: bool | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MerchantMembership:
    """Merchant tenant membership binding a user to a merchant with a specific role and status."""

    id: MembershipId
    merchant_id: MerchantId
    user_id: UserId
    role: Role
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime
    version: int = 1

    @property
    def is_active(self) -> bool:
        """Only ACTIVE status grants access; SUSPENDED and REVOKED fail closed."""
        return self.status == MembershipStatus.ACTIVE

    def has_permission(self, permission: Permission) -> bool:
        """Check if active membership has the specified permission."""
        if not self.is_active:
            return False
        return permission in get_permissions_for_role(self.role)
