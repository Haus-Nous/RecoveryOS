"""FastAPI dependencies for PaymentProviderService."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends

from app.api.dependencies.auth import get_uow_factory
from app.application.ports.provider_credentials import ProviderCredentialResolver
from app.application.ports.unit_of_work import UnitOfWork
from app.application.services.provider_service import PaymentProviderService
from app.infrastructure.security.credential_resolver import (
    EnvProviderCredentialResolver,
)


def get_credential_resolver() -> ProviderCredentialResolver:
    """Provide singleton ProviderCredentialResolver."""
    return EnvProviderCredentialResolver()


def get_payment_provider_service(
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
    credential_resolver: Annotated[ProviderCredentialResolver, Depends(get_credential_resolver)],
) -> PaymentProviderService:
    """Provide PaymentProviderService instance."""
    return PaymentProviderService(
        uow_factory=uow_factory,
        credential_resolver=credential_resolver,
    )
