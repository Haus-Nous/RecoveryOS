"""Comprehensive RBAC Role-Permission matrix test suite."""

from datetime import UTC, datetime

import pytest

from app.domain.types import MerchantId
from app.identity.domain.models import (
    MembershipStatus,
    MerchantMembership,
    Permission,
    Role,
    get_permissions_for_role,
)
from app.identity.domain.types import MembershipId, UserId

# Exhaustive list of all Phase 3 Permissions
ALL_PERMISSIONS = list(Permission)


@pytest.mark.parametrize("permission", ALL_PERMISSIONS)
def test_owner_has_all_permissions(permission: Permission) -> None:
    owner_permissions = get_permissions_for_role(Role.OWNER)
    assert permission in owner_permissions


@pytest.mark.parametrize(
    ("role", "expected_permissions", "expected_denied_permissions"),
    [
        (
            Role.ADMIN,
            {
                Permission.MERCHANT_READ,
                Permission.MERCHANT_MANAGE,
                Permission.MEMBERS_READ,
                Permission.MEMBERS_MANAGE,
                Permission.PAYMENTS_READ,
                Permission.RECOVERY_READ,
                Permission.RECOVERY_OPERATE,
                Permission.RECOVERY_APPROVE,
                Permission.POLICIES_READ,
                Permission.POLICIES_MANAGE,
                Permission.AUDIT_READ,
            },
            {
                Permission.OWNERSHIP_MANAGE,  # ADMIN strictly cannot mutate OWNER roles/memberships
            },
        ),
        (
            Role.OPERATOR,
            {
                Permission.MERCHANT_READ,
                Permission.MEMBERS_READ,
                Permission.PAYMENTS_READ,
                Permission.RECOVERY_READ,
                Permission.RECOVERY_OPERATE,
                Permission.POLICIES_READ,
            },
            {
                Permission.MERCHANT_MANAGE,
                Permission.MEMBERS_MANAGE,
                Permission.OWNERSHIP_MANAGE,
                Permission.RECOVERY_APPROVE,  # OPERATOR strictly cannot approve policy exceptions
                Permission.POLICIES_MANAGE,
                Permission.AUDIT_READ,
            },
        ),
        (
            Role.ANALYST,
            {
                Permission.MERCHANT_READ,
                Permission.MEMBERS_READ,
                Permission.PAYMENTS_READ,
                Permission.RECOVERY_READ,
                Permission.POLICIES_READ,
            },
            {
                Permission.MERCHANT_MANAGE,
                Permission.MEMBERS_MANAGE,
                Permission.OWNERSHIP_MANAGE,
                Permission.RECOVERY_OPERATE,
                Permission.RECOVERY_APPROVE,
                Permission.POLICIES_MANAGE,
                Permission.AUDIT_READ,
            },
        ),
        (
            Role.AUDITOR,
            {
                Permission.MERCHANT_READ,
                Permission.MEMBERS_READ,
                Permission.PAYMENTS_READ,
                Permission.RECOVERY_READ,
                Permission.POLICIES_READ,
                Permission.AUDIT_READ,
            },
            {
                Permission.MERCHANT_MANAGE,
                Permission.MEMBERS_MANAGE,
                Permission.OWNERSHIP_MANAGE,
                Permission.RECOVERY_OPERATE,
                Permission.RECOVERY_APPROVE,
                Permission.POLICIES_MANAGE,
            },
        ),
    ],
)
def test_role_permission_exact_matrix(
    role: Role,
    expected_permissions: set[Permission],
    expected_denied_permissions: set[Permission],
) -> None:
    actual = get_permissions_for_role(role)
    assert actual == expected_permissions
    for p in expected_denied_permissions:
        assert p not in actual


def test_deny_by_default_on_unknown_role() -> None:
    # Any role not in enum must return empty set
    assert get_permissions_for_role("SUPERUSER") == frozenset()  # type: ignore[arg-type]


def test_membership_status_enforcement() -> None:
    now = datetime.now(UTC)
    active_mem = MerchantMembership(
        id=MembershipId("m1"),
        merchant_id=MerchantId("merch_1"),
        user_id=UserId("u1"),
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    assert active_mem.has_permission(Permission.MERCHANT_MANAGE) is True

    invited_mem = MerchantMembership(
        id=MembershipId("m2_invited"),
        merchant_id=MerchantId("merch_1"),
        user_id=UserId("u2_invited"),
        role=Role.OWNER,
        status=MembershipStatus.INVITED,
        created_at=now,
        updated_at=now,
    )
    assert invited_mem.has_permission(Permission.MERCHANT_MANAGE) is False

    suspended_mem = MerchantMembership(
        id=MembershipId("m2"),
        merchant_id=MerchantId("merch_1"),
        user_id=UserId("u2"),
        role=Role.OWNER,
        status=MembershipStatus.SUSPENDED,
        created_at=now,
        updated_at=now,
    )
    assert suspended_mem.has_permission(Permission.MERCHANT_MANAGE) is False

    revoked_mem = MerchantMembership(
        id=MembershipId("m3"),
        merchant_id=MerchantId("merch_1"),
        user_id=UserId("u3"),
        role=Role.OWNER,
        status=MembershipStatus.REVOKED,
        created_at=now,
        updated_at=now,
    )
    assert revoked_mem.has_permission(Permission.MERCHANT_MANAGE) is False
