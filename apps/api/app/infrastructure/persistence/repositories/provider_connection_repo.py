"""SQLAlchemy implementation of ProviderConnectionRepository."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.provider_connection_repo import (
    ProviderConnectionRepository,
)
from app.core.exceptions import ConcurrencyError
from app.domain.types import MerchantId
from app.infrastructure.persistence.mappers.provider_connection_mapper import (
    ProviderConnectionMapper,
)
from app.infrastructure.persistence.models.provider_connection import (
    PaymentProviderConnectionModel,
)
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderMode,
)


class SqlAlchemyProviderConnectionRepository(ProviderConnectionRepository):
    """PostgreSQL repository for merchant payment provider connections with strict tenant isolation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, merchant_id: MerchantId, connection_id: str
    ) -> PaymentProviderConnection | None:
        """Fetch provider connection by ID strictly scoped by merchant_id."""
        stmt = select(PaymentProviderConnectionModel).where(
            PaymentProviderConnectionModel.merchant_id == str(merchant_id),
            PaymentProviderConnectionModel.id == connection_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return ProviderConnectionMapper.to_domain(model)

    async def get_by_provider_and_mode(
        self, merchant_id: MerchantId, provider: PaymentProviderName, mode: ProviderMode
    ) -> list[PaymentProviderConnection]:
        """Fetch provider connections for a merchant by provider and mode."""
        stmt = (
            select(PaymentProviderConnectionModel)
            .where(
                PaymentProviderConnectionModel.merchant_id == str(merchant_id),
                PaymentProviderConnectionModel.provider == provider.value,
                PaymentProviderConnectionModel.mode == mode.value,
            )
            .order_by(PaymentProviderConnectionModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [ProviderConnectionMapper.to_domain(m) for m in models]

    async def get_by_credential_ref(
        self,
        merchant_id: MerchantId,
        provider: PaymentProviderName,
        mode: ProviderMode,
        credential_ref: str,
    ) -> PaymentProviderConnection | None:
        """Fetch specific connection by merchant, provider, mode, and credential_ref."""
        stmt = select(PaymentProviderConnectionModel).where(
            PaymentProviderConnectionModel.merchant_id == str(merchant_id),
            PaymentProviderConnectionModel.provider == provider.value,
            PaymentProviderConnectionModel.mode == mode.value,
            PaymentProviderConnectionModel.credential_ref == credential_ref,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return ProviderConnectionMapper.to_domain(model)

    async def save(self, merchant_id: MerchantId, connection: PaymentProviderConnection) -> None:
        """Save or update a provider connection enforcing tenant ownership."""
        if str(connection.merchant_id) != str(merchant_id):
            raise ValueError(
                f"Tenant isolation violation: connection merchant_id {connection.merchant_id} "
                f"does not match repo merchant_id {merchant_id}"
            )

        stmt = select(PaymentProviderConnectionModel).where(
            PaymentProviderConnectionModel.id == connection.id,
            PaymentProviderConnectionModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            new_model = ProviderConnectionMapper.to_model(connection)
            self._session.add(new_model)
        else:
            if existing.version != connection.version:
                raise ConcurrencyError(
                    f"Optimistic lock violation for connection {connection.id}: "
                    f"DB version {existing.version} != aggregate version {connection.version}"
                )
            existing.status = connection.status.value
            existing.credential_ref = connection.credential_ref
            existing.key_id_fingerprint = connection.key_id_fingerprint
            existing.last_verified_at = connection.last_verified_at
            existing.updated_at = datetime.now(UTC)
            existing.version = connection.version + 1

    async def list_for_merchant(self, merchant_id: MerchantId) -> list[PaymentProviderConnection]:
        """List all provider connections for a merchant."""
        stmt = (
            select(PaymentProviderConnectionModel)
            .where(PaymentProviderConnectionModel.merchant_id == str(merchant_id))
            .order_by(PaymentProviderConnectionModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [ProviderConnectionMapper.to_domain(m) for m in models]
