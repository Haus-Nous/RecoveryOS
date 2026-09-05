"""Comprehensive standards-based JWT / OIDC token verification test suite."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app.core.exceptions import AuthenticationError
from app.infrastructure.security.jwt_verifier import JwtTokenVerifier


@pytest.fixture(scope="module")
def ec_keypair() -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    """Generate in-memory ES256 keypair for testing."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate in-memory RS256 keypair for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.mark.asyncio
async def test_valid_es256_token_accepted(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    priv, pub = ec_keypair
    issuer = "https://example-supabase.supabase.co/auth/v1"
    audience = "authenticated"
    subject = "usr_01JTESTSUB0000000000000000"

    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "email": "owner@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 3600,
    }

    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "test-es256-key"})

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience=audience,
        allowed_algorithms=["ES256", "RS256"],
        static_keys={"test-es256-key": pub},
    )

    principal = await verifier.verify_token(token)
    assert principal.issuer == issuer
    assert principal.subject == subject
    assert principal.email == "owner@example.com"
    assert principal.email_verified is True
    assert principal.issued_at is not None


@pytest.mark.asyncio
async def test_valid_rs256_token_accepted(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    priv, pub = rsa_keypair
    issuer = "https://auth.recoveryos.internal"
    audience = "recoveryos-api"
    subject = "usr_01JRSA00000000000000000000"

    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": now,
        "exp": now + 3600,
    }

    token = jwt.encode(payload, priv, algorithm="RS256", headers={"kid": "test-rsa-key"})

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience=audience,
        allowed_algorithms=["RS256"],
        static_keys={"test-rsa-key": pub},
    )

    principal = await verifier.verify_token(token)
    assert principal.subject == subject


@pytest.mark.asyncio
async def test_expired_token_rejected(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    priv, pub = ec_keypair
    issuer = "https://auth.recoveryos.internal"
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "authenticated",
        "sub": "usr_expired",
        "exp": now - 100,  # Expired in past
    }
    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "k1"})

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="authenticated",
        static_keys={"k1": pub},
        clock_skew_seconds=5,
    )

    with pytest.raises(AuthenticationError, match="expired"):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_wrong_issuer_rejected(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    priv, pub = ec_keypair
    now = int(time.time())
    payload = {
        "iss": "https://malicious-issuer.com",
        "aud": "authenticated",
        "sub": "usr_victim",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "k1"})

    verifier = JwtTokenVerifier(
        issuer="https://trusted.recoveryos.internal",
        audience="authenticated",
        static_keys={"k1": pub},
    )

    with pytest.raises(AuthenticationError, match="issuer mismatch"):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_wrong_audience_rejected(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    priv, pub = ec_keypair
    issuer = "https://auth.recoveryos.internal"
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "wrong-service-aud",
        "sub": "usr_victim",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "k1"})

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="recoveryos-api",
        static_keys={"k1": pub},
    )

    with pytest.raises(AuthenticationError, match="audience mismatch"):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_invalid_signature_rejected(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    priv, _ = ec_keypair
    other_priv = ec.generate_private_key(ec.SECP256R1())
    other_pub = other_priv.public_key()

    issuer = "https://auth.recoveryos.internal"
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "authenticated",
        "sub": "usr_attacker",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "k1"})

    # Verifier only knows other_pub
    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="authenticated",
        static_keys={"k1": other_pub},
    )

    with pytest.raises(AuthenticationError, match="Invalid cryptographic signature"):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_algorithm_none_rejected(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    _, pub = ec_keypair
    issuer = "https://auth.recoveryos.internal"
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "authenticated",
        "sub": "usr_attacker",
        "exp": now + 3600,
    }
    # Unsigned token
    token = jwt.encode(payload, key="", algorithm="none")

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="authenticated",
        allowed_algorithms=["ES256", "RS256"],
        static_keys={"k1": pub},
    )

    with pytest.raises(AuthenticationError, match="Forbidden or unsupported token algorithm"):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_missing_subject_rejected(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    priv, pub = ec_keypair
    issuer = "https://auth.recoveryos.internal"
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "authenticated",
        # missing sub
        "exp": now + 3600,
    }
    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "k1"})

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="authenticated",
        static_keys={"k1": pub},
    )

    with pytest.raises(AuthenticationError, match='missing the "sub" claim'):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_future_nbf_beyond_skew_rejected(
    ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    priv, pub = ec_keypair
    issuer = "https://auth.recoveryos.internal"
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "authenticated",
        "sub": "usr_future",
        "nbf": now + 3600,  # 1 hour in future
        "exp": now + 7200,
    }
    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "k1"})

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="authenticated",
        clock_skew_seconds=10,
        static_keys={"k1": pub},
    )

    with pytest.raises(AuthenticationError, match="not valid yet"):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_unknown_kid_fails_closed() -> None:
    priv = ec.generate_private_key(ec.SECP256R1())
    issuer = "https://auth.recoveryos.internal"
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "authenticated",
        "sub": "usr_test",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "unknown-kid-xyz"})

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="authenticated",
        static_keys={"valid-kid": priv.public_key()},
    )

    with pytest.raises(AuthenticationError, match="No signing keys or JWKS endpoint configured"):
        await verifier.verify_token(token)


@pytest.mark.asyncio
async def test_oversized_token_rejected_immediately() -> None:
    oversized = "a." + ("b" * 9000) + ".c"
    verifier = JwtTokenVerifier(issuer="https://auth.recoveryos.internal")

    with pytest.raises(AuthenticationError, match="maximum permitted size"):
        await verifier.verify_token(oversized)


@pytest.mark.asyncio
async def test_jwks_cache_ttl_and_unknown_kid_refresh(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    from unittest.mock import AsyncMock, patch

    priv, pub = rsa_keypair
    jwk_dict = jwt.algorithms.RSAAlgorithm.to_jwk(pub, as_dict=True)
    jwk_dict["kid"] = "rotated-rsa-key-1"
    jwk_dict["alg"] = "RS256"

    issuer = "https://auth.recoveryos.internal"
    jwks_url = "https://auth.recoveryos.internal/.well-known/jwks.json"

    verifier = JwtTokenVerifier(
        issuer=issuer,
        audience="authenticated",
        jwks_url=jwks_url,
        allowed_algorithms=["RS256"],
        jwks_cache_ttl_seconds=300,
    )

    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": "authenticated",
        "sub": "usr_jwks_test",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, priv, algorithm="RS256", headers={"kid": "rotated-rsa-key-1"})

    mock_response = AsyncMock()
    mock_response.json = lambda: {"keys": [jwk_dict]}
    mock_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # First verify -> fetches JWKS (1 network call)
        p1 = await verifier.verify_token(token)
        assert p1.subject == "usr_jwks_test"
        assert mock_get.call_count == 1

        # Second verify -> uses cached JWKS (0 additional network calls)
        p2 = await verifier.verify_token(token)
        assert p2.subject == "usr_jwks_test"
        assert mock_get.call_count == 1

        # Unknown kid token triggers cache refresh
        unknown_kid_token = jwt.encode(
            payload, priv, algorithm="RS256", headers={"kid": "unknown-rotated-key"}
        )
        with pytest.raises(AuthenticationError, match="not found after JWKS refresh"):
            await verifier.verify_token(unknown_kid_token)
        assert mock_get.call_count == 2
