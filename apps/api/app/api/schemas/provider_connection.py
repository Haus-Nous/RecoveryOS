"""Pydantic schemas for Payment Provider Connections API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.providers.types import (
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderMode,
    ProviderOrderStatus,
)


class CreateProviderConnectionRequest(BaseModel):
    """Request payload to register a new payment provider connection metadata."""

    model_config = ConfigDict(extra="forbid")

    provider: PaymentProviderName = Field(default=PaymentProviderName.RAZORPAY)
    mode: ProviderMode = Field(default=ProviderMode.TEST)
    credential_ref: str = Field(
        min_length=3,
        max_length=64,
        description="Allowlisted server-side credential alias (e.g. RAZORPAY_TEST_DEMO)",
    )


class ProviderConnectionResponse(BaseModel):
    """Safe public metadata response for a payment provider connection.

    CRITICAL INVARIANT:
    Never exposes key_secret, Authorization, or raw credentials.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    provider: PaymentProviderName
    mode: ProviderMode
    credential_ref: str
    status: ProviderConnectionStatus
    key_id_fingerprint: str | None = None
    last_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class VerifyProviderConnectionResponse(BaseModel):
    """Connection verification result."""

    is_valid: bool
    verified_at: datetime
    provider: PaymentProviderName
    mode: ProviderMode
    key_id_fingerprint: str | None = None
    message: str


class CreateTestOrderRequest(BaseModel):
    """Test order creation request for developer and testing workflows."""

    model_config = ConfigDict(extra="forbid")

    amount_minor: int = Field(gt=0, description="Amount in currency minor units (paise for INR)")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    receipt: str = Field(min_length=1, max_length=40)
    notes: dict[str, str] = Field(default_factory=dict)


class TestOrderResponse(BaseModel):
    """Normalized test order response."""

    provider: PaymentProviderName
    provider_order_id: str
    merchant_connection_id: str
    amount_minor: int
    currency: str
    status: ProviderOrderStatus
    receipt: str | None = None
    created_at: datetime
    raw_status: str
