"""Tests for Provider Credentials resolution, allowlist enforcement, and live mode blocking."""

from datetime import UTC, datetime

import pytest

from app.domain.types import MerchantId
from app.infrastructure.security.credential_resolver import (
    EnvProviderCredentialResolver,
)
from app.providers.errors import (
    ProviderCredentialResolutionError,
    ProviderInvalidKeyFormatError,
    ProviderLiveModeForbiddenError,
)
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderMode,
)


def _create_test_connection(
    credential_ref: str = "RAZORPAY_TEST_DEMO",
    mode: ProviderMode = ProviderMode.TEST,
) -> PaymentProviderConnection:
    now = datetime.now(UTC)
    return PaymentProviderConnection(
        id="conn_test_123",
        merchant_id=MerchantId("mer_test_alpha"),
        provider=PaymentProviderName.RAZORPAY,
        mode=mode,
        credential_ref=credential_ref,
        status=ProviderConnectionStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        version=1,
    )


async def test_registered_alias_resolves_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that a registered allowlisted alias resolves valid Test Mode credentials."""
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_ID", "rzp_test_1234567890ABCD")
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_SECRET", "super_secret_test_key_123")

    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection("RAZORPAY_TEST_DEMO")
    creds = await resolver.resolve(conn)

    assert creds.key_id == "rzp_test_1234567890ABCD"
    assert creds.key_secret.get_secret_value() == "super_secret_test_key_123"


async def test_secret_redacted_in_repr_and_str(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that ProviderCredentials repr and str never expose key_secret."""
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_ID", "rzp_test_1234567890ABCD")
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_SECRET", "super_secret_value_xyz")

    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection("RAZORPAY_TEST_DEMO")
    creds = await resolver.resolve(conn)

    assert "super_secret_value_xyz" not in repr(creds)
    assert "super_secret_value_xyz" not in str(creds)
    assert "[REDACTED]" in repr(creds)
    assert "[REDACTED]" in str(creds)


async def test_syntactically_valid_unregistered_alias_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that a syntactically valid alias NOT in the server allowlist fails closed."""
    monkeypatch.setenv("RAZORPAY_TEST_UNREGISTERED_KEY_ID", "rzp_test_unregistered")
    monkeypatch.setenv("RAZORPAY_TEST_UNREGISTERED_KEY_SECRET", "secret")

    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection("RAZORPAY_TEST_UNREGISTERED")

    with pytest.raises(
        ProviderCredentialResolutionError, match="not registered in server allowlist"
    ):
        await resolver.resolve(conn)


@pytest.mark.parametrize(
    "bad_alias",
    [
        "../../etc/passwd",
        "RAZORPAY;DROP TABLE",
        "RAZORPAY$USER",
        "RAZORPAY.TEST",
        "RAZORPAY/TEST",
        "RAZORPAY-TEST",
        "RAZORPAY TEST",
        "AB",  # too short
        "A" * 65,  # too long
    ],
)
async def test_invalid_syntax_aliases_rejected(bad_alias: str) -> None:
    """Verify that traversal, punctuation, or out-of-bounds aliases are rejected by regex."""
    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection(bad_alias)

    with pytest.raises(ProviderCredentialResolutionError, match="Invalid credential_ref syntax"):
        await resolver.resolve(conn)


async def test_cannot_resolve_unrelated_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that unrelated environment variables (e.g. DATABASE_URL) cannot be derived."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection("DATABASE_URL")

    with pytest.raises(
        ProviderCredentialResolutionError, match="not registered in server allowlist"
    ):
        await resolver.resolve(conn)


async def test_live_mode_connection_blocked_before_env_read() -> None:
    """Verify that LIVE mode connection is blocked with ProviderLiveModeForbiddenError."""
    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection("RAZORPAY_TEST_DEMO", mode=ProviderMode.LIVE)

    with pytest.raises(
        ProviderLiveModeForbiddenError, match="Live mode execution is strictly prohibited"
    ):
        await resolver.resolve(conn)


async def test_live_key_prefix_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that even with an allowlisted alias, if key_id starts with rzp_live_, it fails closed."""
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_ID", "rzp_live_1234567890ABCD")
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_SECRET", "live_secret_key_123")

    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection("RAZORPAY_TEST_DEMO")

    with pytest.raises(
        ProviderLiveModeForbiddenError, match="Live Razorpay Key ID prefix 'rzp_live_' detected"
    ):
        await resolver.resolve(conn)


async def test_invalid_key_prefix_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that non-rzp_test_ key ID format raises ProviderInvalidKeyFormatError."""
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_ID", "invalid_prefix_12345")
    monkeypatch.setenv("RAZORPAY_TEST_DEMO_KEY_SECRET", "secret_123")

    resolver = EnvProviderCredentialResolver()
    conn = _create_test_connection("RAZORPAY_TEST_DEMO")

    with pytest.raises(ProviderInvalidKeyFormatError, match="must start with 'rzp_test_'"):
        await resolver.resolve(conn)
