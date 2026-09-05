"""Payment Provider Connections API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import require_permission
from app.api.dependencies.provider import get_payment_provider_service
from app.api.schemas.provider_connection import (
    CreateProviderConnectionRequest,
    CreateTestOrderRequest,
    ProviderConnectionResponse,
    TestOrderResponse,
    VerifyProviderConnectionResponse,
)
from app.application.services.auth_service import AuthorizationContext
from app.application.services.provider_service import PaymentProviderService
from app.core.exceptions import DuplicateEntityError
from app.domain.types import MerchantId
from app.identity.domain.models import Permission
from app.providers.errors import (
    ProviderAmbiguousWriteError,
    ProviderAuthenticationError,
    ProviderCredentialResolutionError,
    ProviderLiveModeForbiddenError,
    ProviderNetworkError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.providers.types import ProviderCreateOrderRequest

router = APIRouter(
    prefix="/api/v1/merchants/{merchant_id}/provider-connections", tags=["Payment Providers"]
)


@router.get(
    "",
    response_model=list[ProviderConnectionResponse],
    summary="List Provider Connections",
    description="List all payment provider connections registered for this merchant. Requires MERCHANT_READ.",
)
async def list_provider_connections(
    merchant_id: str,
    auth_ctx: Annotated[
        AuthorizationContext, Depends(require_permission(Permission.MERCHANT_READ))
    ],
    service: Annotated[PaymentProviderService, Depends(get_payment_provider_service)],
) -> list[ProviderConnectionResponse]:
    connections = await service.list_connections(MerchantId(merchant_id))
    return [ProviderConnectionResponse.model_validate(c) for c in connections]


@router.post(
    "",
    response_model=ProviderConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Provider Connection",
    description="Register a new payment provider connection in Test Mode. Requires MERCHANT_MANAGE.",
)
async def create_provider_connection(
    merchant_id: str,
    req: CreateProviderConnectionRequest,
    auth_ctx: Annotated[
        AuthorizationContext, Depends(require_permission(Permission.MERCHANT_MANAGE))
    ],
    service: Annotated[PaymentProviderService, Depends(get_payment_provider_service)],
) -> ProviderConnectionResponse:
    try:
        connection = await service.create_connection(
            merchant_id=MerchantId(merchant_id),
            provider=req.provider,
            mode=req.mode,
            credential_ref=req.credential_ref,
        )
        return ProviderConnectionResponse.model_validate(connection)
    except ProviderLiveModeForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ProviderCredentialResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except DuplicateEntityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{connection_id}/verify",
    response_model=VerifyProviderConnectionResponse,
    summary="Verify Provider Connection",
    description="Safely verify provider connection credentials against upstream Test Mode API. Requires MERCHANT_MANAGE.",
)
async def verify_provider_connection(
    merchant_id: str,
    connection_id: str,
    auth_ctx: Annotated[
        AuthorizationContext, Depends(require_permission(Permission.MERCHANT_MANAGE))
    ],
    service: Annotated[PaymentProviderService, Depends(get_payment_provider_service)],
) -> VerifyProviderConnectionResponse:
    try:
        result = await service.verify_connection(MerchantId(merchant_id), connection_id)
        return VerifyProviderConnectionResponse(
            is_valid=result.is_valid,
            verified_at=result.verified_at,
            provider=result.provider,
            mode=result.mode,
            key_id_fingerprint=result.key_id_fingerprint,
            message=result.message,
        )
    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProviderLiveModeForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (ProviderAuthenticationError, ProviderCredentialResolutionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (ProviderTimeoutError, ProviderNetworkError) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Upstream provider communication timed out: {exc}",
        ) from exc
    except ProviderRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc


@router.post(
    "/{connection_id}/test-orders",
    response_model=TestOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Test Order",
    description="Create a test order on the upstream payment provider. Strictly Test Mode. Requires MERCHANT_MANAGE.",
)
async def create_test_order(
    merchant_id: str,
    connection_id: str,
    req: CreateTestOrderRequest,
    auth_ctx: Annotated[
        AuthorizationContext, Depends(require_permission(Permission.MERCHANT_MANAGE))
    ],
    service: Annotated[PaymentProviderService, Depends(get_payment_provider_service)],
) -> TestOrderResponse:
    try:
        order = await service.create_test_order(
            merchant_id=MerchantId(merchant_id),
            connection_id=connection_id,
            request=ProviderCreateOrderRequest(
                amount_minor=req.amount_minor,
                currency=req.currency,
                receipt=req.receipt,
                notes=req.notes,
            ),
        )
        return TestOrderResponse(
            provider=order.provider,
            provider_order_id=order.provider_order_id,
            merchant_connection_id=order.merchant_connection_id,
            amount_minor=order.amount_minor,
            currency=order.currency,
            status=order.status,
            receipt=order.receipt,
            created_at=order.created_at,
            raw_status=order.raw_status,
        )
    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProviderLiveModeForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (ProviderAuthenticationError, ProviderCredentialResolutionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ProviderAmbiguousWriteError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Order creation status ambiguous: {exc}",
        ) from exc
    except (ProviderTimeoutError, ProviderNetworkError) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Upstream provider communication timed out: {exc}",
        ) from exc
    except ProviderRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
