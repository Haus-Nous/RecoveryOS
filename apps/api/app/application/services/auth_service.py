import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.application.ports.authentication import AuthenticatedPrincipal
from app.application.ports.unit_of_work import UnitOfWork
from app.core.exceptions import (
    AuthorizationError,
    DuplicateEntityError,
    EntityNotFoundError,
    LastOwnerViolationError,
)
from app.core.logging import get_logger
from app.domain.types import MerchantId
from app.identity.domain.models import (
    MembershipStatus,
    MerchantMembership,
    Permission,
    Role,
    User,
    UserIdentity,
    get_permissions_for_role,
)
from app.identity.domain.types import MembershipId, UserId, UserIdentityId
from app.infrastructure.persistence.models.merchant import MerchantModel

logger = get_logger("recoveryos.security.auth_service")


@dataclass(frozen=True)
class AuthorizationContext:
    """Server-side verified context containing authenticated user and tenant-scoped role/permissions."""

    principal: AuthenticatedPrincipal
    user: User
    merchant_id: MerchantId
    membership: MerchantMembership
    role: Role
    permissions: frozenset[Permission]


class AuthService:
    """Application service for identity resolution, RBAC enforcement, and merchant tenant management."""

    def __init__(self, uow_factory: type[UnitOfWork] | Any) -> None:
        self._uow_factory = uow_factory

    async def get_or_create_user_from_principal(
        self, uow: UnitOfWork, principal: AuthenticatedPrincipal
    ) -> tuple[User, UserIdentity]:
        """Resolve internal User from external identity with concurrency-safe JIT provisioning."""
        existing_identity = await uow.user_identities.get_by_issuer_subject(
            principal.issuer, principal.subject
        )
        if existing_identity is not None:
            user = await uow.users.get_by_id(existing_identity.user_id)
            if user is None:
                raise EntityNotFoundError(
                    f"User {existing_identity.user_id} not found for identity"
                )
            return user, existing_identity

        # JIT create User and UserIdentity in the current transaction
        now = datetime.now(UTC)
        user_id = UserId(f"usr_{uuid.uuid4().hex}")
        user = User(id=user_id, created_at=now, updated_at=now)
        await uow.users.create(user)

        identity_id = UserIdentityId(f"uid_{uuid.uuid4().hex}")
        identity = UserIdentity(
            id=identity_id,
            user_id=user_id,
            issuer=principal.issuer,
            subject=principal.subject,
            email=principal.email,
            email_verified=principal.email_verified,
            created_at=now,
            updated_at=now,
        )
        await uow.user_identities.create(identity)

        # In case of concurrent creation where another transaction inserted first:
        # Re-fetch authoritative UserIdentity to guarantee canonical user_id mapping
        canonical_identity = await uow.user_identities.get_by_issuer_subject(
            principal.issuer, principal.subject
        )
        if canonical_identity is not None and canonical_identity.user_id != user_id:
            canonical_user = await uow.users.get_by_id(canonical_identity.user_id)
            if canonical_user is not None:
                return canonical_user, canonical_identity

        return user, identity

    async def resolve_authorization_context(
        self,
        uow: UnitOfWork,
        principal: AuthenticatedPrincipal,
        merchant_id: MerchantId,
        required_permission: Permission | None = None,
    ) -> AuthorizationContext:
        """Resolve user and verify merchant membership status and RBAC permissions.

        Raises:
            AuthorizationError: If membership is missing, suspended, revoked, or lacks permission.
        """
        user, _ = await self.get_or_create_user_from_principal(uow, principal)

        membership = await uow.memberships.get_membership(merchant_id, user.id)
        if membership is None:
            logger.warning(
                "Access denied: User has no membership in merchant",
                extra={"user_id": str(user.id), "merchant_id": str(merchant_id)},
            )
            raise AuthorizationError(f"User is not a member of merchant '{merchant_id}'.")

        if membership.status == MembershipStatus.SUSPENDED:
            logger.warning(
                "Access denied: Membership suspended",
                extra={"user_id": str(user.id), "merchant_id": str(merchant_id)},
            )
            raise AuthorizationError(f"Membership in merchant '{merchant_id}' is suspended.")

        if membership.status == MembershipStatus.REVOKED:
            logger.warning(
                "Access denied: Membership revoked",
                extra={"user_id": str(user.id), "merchant_id": str(merchant_id)},
            )
            raise AuthorizationError(f"Membership in merchant '{merchant_id}' has been revoked.")

        permissions = get_permissions_for_role(membership.role)
        if required_permission is not None and required_permission not in permissions:
            logger.warning(
                "Access denied: Insufficient permission",
                extra={
                    "user_id": str(user.id),
                    "merchant_id": str(merchant_id),
                    "role": membership.role.value,
                    "required_permission": required_permission.value,
                },
            )
            raise AuthorizationError(
                f"Role '{membership.role.value}' lacks required permission '{required_permission.value}'."
            )

        return AuthorizationContext(
            principal=principal,
            user=user,
            merchant_id=merchant_id,
            membership=membership,
            role=membership.role,
            permissions=permissions,
        )

    async def bootstrap_merchant(
        self, principal: AuthenticatedPrincipal, name: str, slug: str
    ) -> tuple[MerchantModel, MerchantMembership]:
        """Atomically create a new Merchant, JIT user (if needed), and OWNER membership in one commit."""
        now = datetime.now(UTC)
        clean_slug = slug.strip().lower()
        clean_name = name.strip()

        async with self._uow_factory() as uow:
            # 1. Check slug uniqueness
            existing = await uow.memberships.get_merchant_by_slug(clean_slug)
            if existing is not None:
                raise DuplicateEntityError(f"Merchant with slug '{clean_slug}' already exists.")

            # 2. Get or create user
            user, _ = await self.get_or_create_user_from_principal(uow, principal)

            # 3. Create merchant
            merchant_id = MerchantId(f"merch_{uuid.uuid4().hex}")
            merchant_model = MerchantModel(
                id=str(merchant_id),
                name=clean_name,
                slug=clean_slug,
                created_at=now,
                updated_at=now,
            )
            await uow.memberships.create_merchant(merchant_model)

            # 4. Create OWNER membership
            membership = MerchantMembership(
                id=MembershipId(f"mem_{uuid.uuid4().hex}"),
                merchant_id=merchant_id,
                user_id=user.id,
                role=Role.OWNER,
                status=MembershipStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                version=1,
            )
            saved_membership = await uow.memberships.save(merchant_id, membership)
            await uow.commit()

            return merchant_model, saved_membership

    async def update_member_role_or_status(
        self,
        actor_ctx: AuthorizationContext,
        target_user_id: UserId,
        new_role: Role | None = None,
        new_status: MembershipStatus | None = None,
    ) -> MerchantMembership:
        """Update a member's role or status with strict RBAC and concurrency-safe last-owner protection."""
        merchant_id = actor_ctx.merchant_id

        async with self._uow_factory() as uow:
            # Concurrency-safe: lock the merchant record to serialize ownership modifications
            await uow.memberships.lock_merchant_for_membership_update(merchant_id)

            target_membership = await uow.memberships.get_membership(merchant_id, target_user_id)
            if target_membership is None:
                raise EntityNotFoundError(
                    f"Membership for user '{target_user_id}' not found in merchant '{merchant_id}'."
                )

            is_owner_mutation = target_membership.role == Role.OWNER or new_role == Role.OWNER

            # Authorization check:
            # - If target is OWNER or becoming OWNER -> actor MUST have OWNERSHIP_MANAGE (Owner-only)
            # - If target is non-owner -> actor MUST have MEMBERS_MANAGE
            if is_owner_mutation:
                if Permission.OWNERSHIP_MANAGE not in actor_ctx.permissions:
                    raise AuthorizationError(
                        "Only an OWNER with OWNERSHIP_MANAGE permission may modify an owner membership."
                    )
            else:
                if Permission.MEMBERS_MANAGE not in actor_ctx.permissions:
                    raise AuthorizationError(
                        "MEMBERS_MANAGE permission required to update member role/status."
                    )

            # Check if this change would demote or deactivate an active owner
            is_active_owner = (
                target_membership.role == Role.OWNER
                and target_membership.status == MembershipStatus.ACTIVE
            )
            will_remain_active_owner = (new_role or target_membership.role) == Role.OWNER and (
                new_status or target_membership.status
            ) == MembershipStatus.ACTIVE

            if is_active_owner and not will_remain_active_owner:
                active_owner_count = await uow.memberships.count_active_owners(merchant_id)
                if active_owner_count <= 1:
                    raise LastOwnerViolationError(
                        f"Cannot demote or deactivate the last ACTIVE owner of merchant '{merchant_id}'."
                    )

            updated_membership = MerchantMembership(
                id=target_membership.id,
                merchant_id=merchant_id,
                user_id=target_membership.user_id,
                role=new_role if new_role is not None else target_membership.role,
                status=new_status if new_status is not None else target_membership.status,
                created_at=target_membership.created_at,
                updated_at=datetime.now(UTC),
                version=target_membership.version,
            )

            saved = await uow.memberships.save(
                merchant_id, updated_membership, expected_version=target_membership.version
            )
            await uow.commit()
            return saved
