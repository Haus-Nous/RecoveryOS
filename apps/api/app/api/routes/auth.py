"""Authentication and Identity administration API routes."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies.auth import (
    get_auth_service,
    get_current_principal,
    get_current_user,
    get_uow_factory,
    require_permission,
)
from app.api.schemas.auth import (
    MemberResponse,
    MemberUpdateRequest,
    MerchantCreateRequest,
    MerchantResponse,
    MerchantSummaryResponse,
    UserResponse,
)
from app.application.ports.authentication import AuthenticatedPrincipal
from app.application.ports.unit_of_work import UnitOfWork
from app.application.services.auth_service import AuthorizationContext, AuthService
from app.core.exceptions import (
    AuthorizationError,
    DuplicateEntityError,
    EntityNotFoundError,
    LastOwnerViolationError,
)
from app.domain.types import MerchantId
from app.identity.domain.models import Permission, User
from app.identity.domain.types import UserId
from app.infrastructure.persistence.models.merchant import MerchantModel

router = APIRouter(prefix="/api/v1", tags=["Authentication & Multi-Tenancy"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User",
    description="Returns minimal safe identity details for the authenticated user.",
)
async def get_me(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=principal.email,
        email_verified=principal.email_verified,
        created_at=user.created_at,
    )


@router.get(
    "/me/merchants",
    response_model=list[MerchantSummaryResponse],
    summary="List User Merchants",
    description="Returns all active merchant memberships for the authenticated user.",
)
async def list_my_merchants(
    user: Annotated[User, Depends(get_current_user)],
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
) -> list[MerchantSummaryResponse]:
    async with uow_factory() as uow:
        memberships = await uow.memberships.list_user_memberships(user.id)
        # For each membership, fetch merchant details
        results: list[MerchantSummaryResponse] = []
        session = uow._session  # type: ignore[attr-defined]
        for m in memberships:
            stmt = select(MerchantModel).where(MerchantModel.id == str(m.merchant_id))
            merchant = (await session.execute(stmt)).scalar_one_or_none()
            if merchant:
                results.append(
                    MerchantSummaryResponse(
                        id=merchant.id,
                        name=merchant.name,
                        slug=merchant.slug,
                        role=m.role,
                        status=m.status,
                    )
                )
        return results


@router.post(
    "/merchants",
    response_model=MerchantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bootstrap Merchant",
    description="Atomically creates a new merchant and provisions the caller as OWNER.",
)
async def create_merchant(
    req: MerchantCreateRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MerchantResponse:
    try:
        merchant, _ = await auth_service.bootstrap_merchant(
            principal=principal,
            name=req.name,
            slug=req.slug,
        )
        return MerchantResponse(
            id=merchant.id,
            name=merchant.name,
            slug=merchant.slug,
            created_at=merchant.created_at,
        )
    except DuplicateEntityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/merchants/{merchant_id}",
    response_model=MerchantResponse,
    summary="Get Merchant Details",
    description="Retrieves merchant details. Requires MERCHANT_READ permission.",
)
async def get_merchant(
    merchant_id: str,
    auth_ctx: Annotated[
        AuthorizationContext, Depends(require_permission(Permission.MERCHANT_READ))
    ],
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
) -> MerchantResponse:
    async with uow_factory() as uow:
        session = uow._session  # type: ignore[attr-defined]
        stmt = select(MerchantModel).where(MerchantModel.id == merchant_id)
        merchant = (await session.execute(stmt)).scalar_one_or_none()
        if not merchant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Merchant '{merchant_id}' not found.",
            )
        return MerchantResponse(
            id=merchant.id,
            name=merchant.name,
            slug=merchant.slug,
            created_at=merchant.created_at,
        )


@router.get(
    "/merchants/{merchant_id}/members",
    response_model=list[MemberResponse],
    summary="List Merchant Members",
    description="Lists all memberships in merchant. Requires MEMBERS_READ permission.",
)
async def list_merchant_members(
    merchant_id: str,
    auth_ctx: Annotated[AuthorizationContext, Depends(require_permission(Permission.MEMBERS_READ))],
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[MemberResponse]:
    async with uow_factory() as uow:
        members = await uow.memberships.list_merchant_members(
            MerchantId(merchant_id), limit=limit, offset=offset
        )
        return [
            MemberResponse(
                id=str(m.id),
                user_id=str(m.user_id),
                role=m.role,
                status=m.status,
                created_at=m.created_at,
            )
            for m in members
        ]


@router.patch(
    "/merchants/{merchant_id}/members/{target_user_id}",
    response_model=MemberResponse,
    summary="Update Member Role or Status",
    description="Updates role or status. Requires MEMBERS_MANAGE (or OWNERSHIP_MANAGE if target/new role is OWNER).",
)
async def update_merchant_member(
    merchant_id: str,
    target_user_id: str,
    req: MemberUpdateRequest,
    auth_ctx: Annotated[
        AuthorizationContext, Depends(require_permission(Permission.MEMBERS_MANAGE))
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MemberResponse:
    try:
        updated = await auth_service.update_member_role_or_status(
            actor_ctx=auth_ctx,
            target_user_id=UserId(target_user_id),
            new_role=req.role,
            new_status=req.status,
        )
        return MemberResponse(
            id=str(updated.id),
            user_id=str(updated.user_id),
            role=updated.role,
            status=updated.status,
            created_at=updated.created_at,
        )
    except LastOwnerViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
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
