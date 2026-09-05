"""Bi-directional mapper for PaymentProviderConnection entity and ORM model."""

from datetime import UTC

from app.domain.types import MerchantId
from app.infrastructure.persistence.models.provider_connection import (
    PaymentProviderConnectionModel,
)
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderMode,
)


class ProviderConnectionMapper:
    """Explicit mapping between PaymentProviderConnection entity and ORM model."""

    @staticmethod
    def to_domain(model: PaymentProviderConnectionModel) -> PaymentProviderConnection:
        """Map ORM model to PaymentProviderConnection entity."""
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        updated_at = model.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)

        last_verified_at = model.last_verified_at
        if last_verified_at is not None and last_verified_at.tzinfo is None:
            last_verified_at = last_verified_at.replace(tzinfo=UTC)

        return PaymentProviderConnection(
            id=model.id,
            merchant_id=MerchantId(model.merchant_id),
            provider=PaymentProviderName(model.provider),
            mode=ProviderMode(model.mode),
            credential_ref=model.credential_ref,
            status=ProviderConnectionStatus(model.status),
            key_id_fingerprint=model.key_id_fingerprint,
            last_verified_at=last_verified_at,
            created_at=created_at,
            updated_at=updated_at,
            version=model.version,
        )

    @staticmethod
    def to_model(entity: PaymentProviderConnection) -> PaymentProviderConnectionModel:
        """Map PaymentProviderConnection entity to ORM model."""
        return PaymentProviderConnectionModel(
            id=entity.id,
            merchant_id=str(entity.merchant_id),
            provider=entity.provider.value,
            mode=entity.mode.value,
            credential_ref=entity.credential_ref,
            status=entity.status.value,
            key_id_fingerprint=entity.key_id_fingerprint,
            last_verified_at=entity.last_verified_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )
