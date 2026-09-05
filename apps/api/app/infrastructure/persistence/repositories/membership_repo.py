"""SQLAlchemy implementation of MembershipRepository."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.identity_repositories import MembershipRepository
from app.core.exceptions import ConcurrencyError
from app.domain.types import MerchantId
from app.identity.domain.models import MembershipStatus, MerchantMembership, Role
from app.identity.domain.types import MembershipId, UserId
from app.infrastructure.persistence.models.membership import MerchantMembershipModel
from app.infrastructure.persistence.models.merchant import MerchantModel


class SqlAlchemyMembershipRepository(MembershipRepository):
    """PostgreSQL repository for Merchant Memberships."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: MerchantMembershipModel) -> MerchantMembership:
        return MerchantMembership(
            id=MembershipId(model.id),
            merchant_id=MerchantId(model.merchant_id),
            user_id=UserId(model.user_id),
            role=Role(model.role),
            status=MembershipStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    async def get_membership(
        self, merchant_id: MerchantId, user_id: UserId
    ) -> MerchantMembership | None:
        stmt = select(MerchantMembershipModel).where(
            MerchantMembershipModel.merchant_id == str(merchant_id),
            MerchantMembershipModel.user_id == str(user_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_user_memberships(self, user_id: UserId) -> Sequence[MerchantMembership]:
        """List all memberships belonging to a user (across merchants)."""
        stmt = (
            select(MerchantMembershipModel)
            .where(MerchantMembershipModel.user_id == str(user_id))
            .order_by(MerchantMembershipModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def list_merchant_members(
        self, merchant_id: MerchantId, limit: int = 100, offset: int = 0
    ) -> Sequence[MerchantMembership]:
        stmt = (
            select(MerchantMembershipModel)
            .where(MerchantMembershipModel.merchant_id == str(merchant_id))
            .order_by(MerchantMembershipModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def lock_merchant_for_membership_update(self, merchant_id: MerchantId) -> None:
        """Acquire a row-level lock on the merchant record to serialize ownership mutations."""
        stmt = (
            select(MerchantModel.id).where(MerchantModel.id == str(merchant_id)).with_for_update()
        )
        await self._session.execute(stmt)

    async def count_active_owners(self, merchant_id: MerchantId) -> int:
        stmt = (
            select(func.count())
            .select_from(MerchantMembershipModel)
            .where(
                MerchantMembershipModel.merchant_id == str(merchant_id),
                MerchantMembershipModel.role == Role.OWNER.value,
                MerchantMembershipModel.status == MembershipStatus.ACTIVE.value,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_merchant_by_slug(self, slug: str) -> MerchantModel | None:
        stmt = select(MerchantModel).where(MerchantModel.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_merchant_by_id(self, merchant_id: MerchantId) -> MerchantModel | None:
        stmt = select(MerchantModel).where(MerchantModel.id == str(merchant_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_merchant(self, merchant: MerchantModel) -> MerchantModel:
        self._session.add(merchant)
        await self._session.flush()
        return merchant

    async def save(
        self,
        merchant_id: MerchantId,
        membership: MerchantMembership,
        expected_version: int | None = None,
    ) -> MerchantMembership:
        if str(merchant_id) != str(membership.merchant_id):
            raise ValueError(
                f"Tenant mismatch: Repository merchant_id '{merchant_id}' != membership.merchant_id '{membership.merchant_id}'"
            )

        stmt = select(MerchantMembershipModel).where(
            MerchantMembershipModel.id == str(membership.id),
            MerchantMembershipModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is None:
            model = MerchantMembershipModel(
                id=str(membership.id),
                merchant_id=str(merchant_id),
                user_id=str(membership.user_id),
                role=membership.role.value,
                status=membership.status.value,
                created_at=membership.created_at,
                updated_at=now,
                version=1,
            )
            self._session.add(model)
            await self._session.flush()
            return self._to_domain(model)

        if expected_version is not None and existing.version != expected_version:
            raise ConcurrencyError(
                f"Optimistic concurrency conflict on MerchantMembership {membership.id}: expected {expected_version}, found {existing.version}"
            )

        existing.role = membership.role.value
        existing.status = membership.status.value
        existing.updated_at = now
        existing.version += 1
        await self._session.flush()
        return self._to_domain(existing)
