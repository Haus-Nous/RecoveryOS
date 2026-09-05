"""FastAPI dependencies for JWT authentication, identity mapping, and multi-tenant RBAC."""

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Path, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.authentication import AuthenticatedPrincipal, TokenVerifier
from app.application.ports.unit_of_work import UnitOfWork
from app.application.services.auth_service import AuthorizationContext, AuthService
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError, EntityNotFoundError
from app.domain.types import MerchantId
from app.identity.domain.models import Permission, User
from app.infrastructure.database import get_session_factory
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.jwt_verifier import JwtTokenVerifier

# HTTPBearer security scheme with OpenAPI configuration
bearer_security = HTTPBearer(auto_error=False)


def get_uow_factory(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> Callable[[], UnitOfWork]:
    """Provide UnitOfWork factory."""
    return lambda: SqlAlchemyUnitOfWork(session_factory)


@lru_cache(maxsize=1)
def get_jwt_token_verifier() -> TokenVerifier:
    """Initialize singleton TokenVerifier using application settings."""
    settings = get_settings()
    return JwtTokenVerifier(
        issuer=settings.auth_issuer,
        audience=settings.auth_audience,
        jwks_url=settings.auth_jwks_url,
        allowed_algorithms=settings.auth_allowed_algorithms,
        jwks_cache_ttl_seconds=settings.auth_jwks_cache_ttl_seconds,
        clock_skew_seconds=settings.auth_clock_skew_seconds,
    )


def get_auth_service(
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
) -> AuthService:
    """Provide AuthService instance."""
    return AuthService(uow_factory=uow_factory)


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_security)],
    verifier: Annotated[TokenVerifier, Depends(get_jwt_token_verifier)],
) -> AuthenticatedPrincipal:
    """Extract and verify Bearer token from request Authorization header.

    Raises:
        HTTPException 401: If token is missing, expired, or invalid.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        principal = await verifier.verify_token(credentials.credentials)
        return principal
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
) -> User:
    """Resolve internal User from verified principal."""
    async with uow_factory() as uow:
        user, _ = await auth_service.get_or_create_user_from_principal(uow, principal)
        await uow.commit()
        return user


def require_permission(
    permission: Permission | None = None,
) -> Any:
    """Build a FastAPI dependency that enforces active merchant membership and permission check.

    Extracts `merchant_id` from route path parameters.
    """

    async def _dependency(
        merchant_id: Annotated[str, Path(description="Target Merchant Tenant ID")],
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
        auth_service: Annotated[AuthService, Depends(get_auth_service)],
        uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
    ) -> AuthorizationContext:
        async with uow_factory() as uow:
            try:
                auth_ctx = await auth_service.resolve_authorization_context(
                    uow=uow,
                    principal=principal,
                    merchant_id=MerchantId(merchant_id),
                    required_permission=permission,
                )
                await uow.commit()
                return auth_ctx
            except AuthorizationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=str(exc),
                ) from exc
            except EntityNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc

    return _dependency
