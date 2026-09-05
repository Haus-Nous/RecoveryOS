from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.types import MerchantId


class PaymentProviderName(StrEnum):
    """Supported payment provider integrations."""

    RAZORPAY = "RAZORPAY"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            for member in cls:
                if member.value.upper() == value.upper():
                    return member
        return None


class ProviderMode(StrEnum):
    """Operation mode for provider connection."""

    TEST = "TEST"
    LIVE = "LIVE"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            for member in cls:
                if member.value.upper() == value.upper():
                    return member
        return None


class ProviderConnectionStatus(StrEnum):
    """Lifecycle status of a provider connection."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    UNVERIFIED = "UNVERIFIED"


class ProviderOrderStatus(StrEnum):
    """Normalized provider order status."""

    CREATED = "CREATED"
    ATTEMPTED = "ATTEMPTED"
    PAID = "PAID"
    UNKNOWN = "UNKNOWN"


class ProviderPaymentStatus(StrEnum):
    """Normalized provider payment status.

    Note: AUTHORIZED and CAPTURED are distinct economic states.
    """

    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ProviderPaymentMethod(StrEnum):
    """Normalized payment method."""

    CARD = "CARD"
    UPI = "UPI"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"
    EMI = "EMI"
    OTHER = "OTHER"


class ProviderFailure(BaseModel):
    """Safe diagnostic failure details stripped of customer PII."""

    model_config = ConfigDict(frozen=True)

    code: str | None = None
    source: str | None = None
    step: str | None = None
    reason: str | None = None
    description: str | None = None
    provider_payment_id: str | None = None
    provider_order_id: str | None = None


class ProviderCreateOrderRequest(BaseModel):
    """Provider-neutral request to create an order."""

    model_config = ConfigDict(frozen=True)

    amount_minor: int = Field(gt=0, description="Amount in minor units (e.g. paise for INR)")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    receipt: str = Field(
        min_length=1, max_length=40, description="Unique non-PII correlation receipt"
    )
    notes: dict[str, str] = Field(default_factory=dict)
    partial_payment: bool = False


class ProviderOrderSnapshot(BaseModel):
    """Provider-neutral normalized order snapshot."""

    model_config = ConfigDict(frozen=True)

    provider: PaymentProviderName
    provider_order_id: str
    merchant_connection_id: str
    amount_minor: int
    amount_paid_minor: int = 0
    amount_due_minor: int = 0
    currency: str
    status: ProviderOrderStatus
    attempts: int = 0
    receipt: str | None = None
    notes: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    raw_status: str
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ProviderPaymentSnapshot(BaseModel):
    """Provider-neutral normalized payment snapshot with zero customer PII."""

    model_config = ConfigDict(frozen=True)

    provider: PaymentProviderName
    provider_payment_id: str
    provider_order_id: str | None = None
    amount_minor: int
    currency: str
    status: ProviderPaymentStatus
    method: ProviderPaymentMethod
    captured: bool
    fee_minor: int | None = None
    tax_minor: int | None = None
    amount_refunded_minor: int = 0
    refund_status: str | None = None
    created_at: datetime
    failure: ProviderFailure | None = None
    raw_status: str
    raw_method: str
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @property
    def order_id(self) -> str | None:
        return self.provider_order_id


class ProviderConnectionVerificationResult(BaseModel):
    """Safe connection verification result."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    verified_at: datetime
    provider: PaymentProviderName
    mode: ProviderMode
    key_id_fingerprint: str | None = None
    message: str = "Connection verified successfully"


class PaymentProviderConnection(BaseModel):
    """Merchant-owned payment provider connection configuration."""

    model_config = ConfigDict(frozen=True)

    id: str
    merchant_id: MerchantId
    provider: PaymentProviderName
    mode: ProviderMode
    credential_ref: str
    status: ProviderConnectionStatus
    key_id_fingerprint: str | None = None
    last_verified_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1
