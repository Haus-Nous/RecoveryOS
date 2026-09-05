"""Strict Pydantic schemas for authentication and identity administration endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.identity.domain.models import MembershipStatus, Role


class UserResponse(BaseModel):
    """Minimal safe representation of an authenticated user."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Internal user ID")
    email: str | None = Field(None, description="User email if available")
    email_verified: bool | None = Field(None, description="Whether email has been verified")
    created_at: datetime = Field(..., description="User creation timestamp")


class MerchantSummaryResponse(BaseModel):
    """Summary of a merchant tenant in which user has active membership."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    slug: str
    role: Role
    status: MembershipStatus


class MerchantCreateRequest(BaseModel):
    """Payload to create a new merchant tenant."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=255, description="Merchant commercial name")
    slug: str = Field(
        ...,
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9-]+$",
        description="URL-safe merchant slug",
    )


class MerchantResponse(BaseModel):
    """Detailed merchant tenant information."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    slug: str
    created_at: datetime


class MemberResponse(BaseModel):
    """Representation of a merchant membership."""

    model_config = ConfigDict(frozen=True)

    id: str
    user_id: str
    role: Role
    status: MembershipStatus
    created_at: datetime


class MemberCreateRequest(BaseModel):
    """Payload to add/invite a user into a merchant tenant."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1, description="Target user ID")
    role: Role = Field(default=Role.OPERATOR, description="Assigned role for member")
    status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE, description="Initial membership status"
    )


class MemberUpdateRequest(BaseModel):
    """Payload to update a member's role or lifecycle status."""

    model_config = ConfigDict(extra="forbid")

    role: Role | None = Field(None, description="New role for member")
    status: MembershipStatus | None = Field(None, description="New status for member")
