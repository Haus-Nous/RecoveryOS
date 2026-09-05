"""Repository ports for User, UserIdentity, and MerchantMembership."""

from collections.abc import Sequence
from typing import Protocol

from app.domain.types import MerchantId
from app.identity.domain.models import MerchantMembership, User, UserIdentity
from app.identity.domain.types import UserId
from app.infrastructure.persistence.models.merchant import MerchantModel


class UserRepository(Protocol):
    """Repository port for User aggregates."""

    async def get_by_id(self, user_id: UserId) -> User | None:
        """Fetch user by ID."""
        ...

    async def create(self, user: User) -> User:
        """Persist a new user."""
        ...


class UserIdentityRepository(Protocol):
    """Repository port for external UserIdentity mappings."""

    async def get_by_issuer_subject(self, issuer: str, subject: str) -> UserIdentity | None:
        """Find external identity mapping by (issuer, subject)."""
        ...

    async def create(self, identity: UserIdentity) -> UserIdentity:
        """Persist an external identity mapping."""
        ...


class MembershipRepository(Protocol):
    """Repository port for MerchantMembership aggregates."""

    async def get_membership(
        self, merchant_id: MerchantId, user_id: UserId
    ) -> MerchantMembership | None:
        """Fetch user's membership for a specific merchant tenant."""
        ...

    async def list_user_memberships(self, user_id: UserId) -> Sequence[MerchantMembership]:
        """List all merchant memberships belonging to an authenticated user (Identity-scoped)."""
        ...

    async def list_merchant_members(
        self, merchant_id: MerchantId, limit: int = 100, offset: int = 0
    ) -> Sequence[MerchantMembership]:
        """List all member memberships for a specific merchant tenant (Tenant-scoped)."""
        ...

    async def count_active_owners(self, merchant_id: MerchantId) -> int:
        """Count the number of active owners for a merchant (used with row locking)."""
        ...

    async def lock_merchant_for_membership_update(self, merchant_id: MerchantId) -> None:
        """Acquire a row-level lock on the merchant to serialize membership role/status updates."""
        ...

    async def get_merchant_by_slug(self, slug: str) -> MerchantModel | None:
        """Fetch merchant model by slug."""
        ...

    async def get_merchant_by_id(self, merchant_id: MerchantId) -> MerchantModel | None:
        """Fetch merchant model by id."""
        ...

    async def create_merchant(self, merchant: MerchantModel) -> MerchantModel:
        """Persist a new merchant tenant."""
        ...

    async def save(
        self,
        merchant_id: MerchantId,
        membership: MerchantMembership,
        expected_version: int | None = None,
    ) -> MerchantMembership:
        """Persist or update merchant membership with tenant verification and optimistic concurrency check."""
        ...
