"""Normalization mapper for Razorpay API entities into provider-neutral DTOs."""

from datetime import UTC, datetime
from typing import Any

from app.domain.values.currency import Currency
from app.providers.errors import (
    ProviderMalformedResponseError,
    ProviderUnsupportedCurrencyError,
)
from app.providers.types import (
    PaymentProviderName,
    ProviderFailure,
    ProviderOrderSnapshot,
    ProviderOrderStatus,
    ProviderPaymentMethod,
    ProviderPaymentSnapshot,
    ProviderPaymentStatus,
)


class RazorpayMapper:
    """Pure mapper translating Razorpay JSON payloads to normalized provider-neutral snapshots."""

    @staticmethod
    def map_order(data: dict[str, Any], *, connection_id: str) -> ProviderOrderSnapshot:
        """Normalize a Razorpay order entity into ProviderOrderSnapshot."""
        if not isinstance(data, dict):
            raise ProviderMalformedResponseError(
                f"Order data must be dict, got {type(data).__name__}"
            )

        order_id = data.get("id")
        if not order_id or not isinstance(order_id, str):
            raise ProviderMalformedResponseError(
                "Order response missing required 'id' string field"
            )

        raw_amount = data.get("amount")
        if raw_amount is None or not isinstance(raw_amount, int):
            raise ProviderMalformedResponseError(
                "Order response missing required integer 'amount' field"
            )

        raw_currency = data.get("currency")
        if not raw_currency or not isinstance(raw_currency, str):
            raise ProviderMalformedResponseError("Order response missing required 'currency' field")

        try:
            Currency.from_str(raw_currency)
        except Exception as exc:
            raise ProviderUnsupportedCurrencyError(
                f"Unsupported provider currency: '{raw_currency}'"
            ) from exc

        raw_created_at = data.get("created_at")
        if raw_created_at is None:
            raise ProviderMalformedResponseError(
                "Order response missing required 'created_at' timestamp"
            )

        try:
            created_at = datetime.fromtimestamp(int(raw_created_at), tz=UTC)
        except Exception as exc:
            raise ProviderMalformedResponseError(
                f"Invalid created_at timestamp: '{raw_created_at}'"
            ) from exc

        raw_status = str(data.get("status", "")).lower()
        if raw_status == "created":
            status = ProviderOrderStatus.CREATED
        elif raw_status == "attempted":
            status = ProviderOrderStatus.ATTEMPTED
        elif raw_status == "paid":
            status = ProviderOrderStatus.PAID
        else:
            status = ProviderOrderStatus.UNKNOWN

        return ProviderOrderSnapshot(
            provider=PaymentProviderName.RAZORPAY,
            provider_order_id=order_id,
            merchant_connection_id=connection_id,
            amount_minor=raw_amount,
            amount_paid_minor=int(data.get("amount_paid", 0)),
            amount_due_minor=int(data.get("amount_due", raw_amount)),
            currency=raw_currency.upper(),
            status=status,
            attempts=int(data.get("attempts", 0)),
            receipt=data.get("receipt"),
            notes=data.get("notes") or {},
            created_at=created_at,
            raw_status=raw_status,
            raw_data=dict(data),
        )

    @staticmethod
    def map_payment(data: dict[str, Any]) -> ProviderPaymentSnapshot:
        """Normalize a Razorpay payment entity into ProviderPaymentSnapshot.

        CRITICAL PII MINIMIZATION:
        Customer email, contact phone, card object, card_id, bank, and VPA details
        are intentionally DROPPED.
        """
        if not isinstance(data, dict):
            raise ProviderMalformedResponseError(
                f"Payment data must be dict, got {type(data).__name__}"
            )

        payment_id = data.get("id")
        if not payment_id or not isinstance(payment_id, str):
            raise ProviderMalformedResponseError(
                "Payment response missing required 'id' string field"
            )

        raw_amount = data.get("amount")
        if raw_amount is None or not isinstance(raw_amount, int):
            raise ProviderMalformedResponseError(
                "Payment response missing required integer 'amount' field"
            )

        raw_currency = data.get("currency")
        if not raw_currency or not isinstance(raw_currency, str):
            raise ProviderMalformedResponseError(
                "Payment response missing required 'currency' field"
            )

        try:
            Currency.from_str(raw_currency)
        except Exception as exc:
            raise ProviderUnsupportedCurrencyError(
                f"Unsupported provider currency: '{raw_currency}'"
            ) from exc

        raw_created_at = data.get("created_at")
        if raw_created_at is None:
            raise ProviderMalformedResponseError(
                "Payment response missing required 'created_at' timestamp"
            )

        try:
            created_at = datetime.fromtimestamp(int(raw_created_at), tz=UTC)
        except Exception as exc:
            raise ProviderMalformedResponseError(
                f"Invalid created_at timestamp: '{raw_created_at}'"
            ) from exc

        # Status normalization
        raw_status = str(data.get("status", "")).lower()
        if raw_status == "created":
            status = ProviderPaymentStatus.CREATED
        elif raw_status == "authorized":
            status = ProviderPaymentStatus.AUTHORIZED
        elif raw_status == "captured":
            status = ProviderPaymentStatus.CAPTURED
        elif raw_status == "refunded":
            status = ProviderPaymentStatus.REFUNDED
        elif raw_status == "failed":
            status = ProviderPaymentStatus.FAILED
        else:
            status = ProviderPaymentStatus.UNKNOWN

        # Method normalization
        raw_method = str(data.get("method", "")).lower()
        if raw_method == "card":
            method = ProviderPaymentMethod.CARD
        elif raw_method == "upi":
            method = ProviderPaymentMethod.UPI
        elif raw_method == "netbanking":
            method = ProviderPaymentMethod.NETBANKING
        elif raw_method == "wallet":
            method = ProviderPaymentMethod.WALLET
        elif raw_method == "emi":
            method = ProviderPaymentMethod.EMI
        else:
            method = ProviderPaymentMethod.OTHER

        # Failure details mapping (safe diagnostics, zero PII)
        failure: ProviderFailure | None = None
        has_failure = any(
            data.get(k) is not None
            for k in (
                "error_code",
                "error_description",
                "error_source",
                "error_step",
                "error_reason",
            )
        )
        if has_failure or status == ProviderPaymentStatus.FAILED:
            failure = ProviderFailure(
                code=data.get("error_code"),
                description=data.get("error_description"),
                source=data.get("error_source"),
                step=data.get("error_step"),
                reason=data.get("error_reason"),
                provider_payment_id=payment_id,
                provider_order_id=data.get("order_id"),
            )

        # Sanitize raw_data to completely remove customer PII
        pii_keys = {"email", "contact", "card", "card_id", "vpa", "bank"}
        sanitized_raw_data = {k: v for k, v in data.items() if k not in pii_keys}

        return ProviderPaymentSnapshot(
            provider=PaymentProviderName.RAZORPAY,
            provider_payment_id=payment_id,
            provider_order_id=data.get("order_id"),
            amount_minor=raw_amount,
            currency=raw_currency.upper(),
            status=status,
            method=method,
            captured=bool(data.get("captured", False)),
            fee_minor=data.get("fee"),
            tax_minor=data.get("tax"),
            amount_refunded_minor=int(data.get("amount_refunded", 0)),
            refund_status=data.get("refund_status"),
            created_at=created_at,
            failure=failure,
            raw_status=raw_status,
            raw_method=raw_method,
            raw_data=sanitized_raw_data,
        )
