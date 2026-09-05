"""API integration tests for Payment Provider Connections endpoints.

Verifies:
- RBAC permissions (OWNER/ADMIN vs OPERATOR/ANALYST/AUDITOR)
- Tenant isolation boundaries (cross-merchant separation)
- Live mode rejection (403)
- Non-allowlisted credential alias rejection (400)
- End-to-end verification and test-order creation flows
"""

import json
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies.auth import get_jwt_token_verifier
from app.api.dependencies.provider import get_credential_resolver, get_payment_provider_service
from app.application.services.provider_service import (
    PaymentProviderRegistry,
    PaymentProviderService,
)
from app.identity.domain.models import Role
from app.infrastructure.database import get_session_factory
from app.infrastructure.persistence.models.membership import MerchantMembershipModel
from app.infrastructure.persistence.models.merchant import MerchantModel
from app.infrastructure.persistence.models.user import UserIdentityModel, UserModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.credential_resolver import EnvProviderCredentialResolver
from app.infrastructure.security.jwt_verifier import JwtTokenVerifier
from app.main import create_app


@pytest.fixture(scope="module")
def api_ec_keypair() -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key()


@pytest.fixture
def make_jwt(
    api_ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> Any:
    priv, _ = api_ec_keypair

    def _make(sub: str, email: str = "user@test.com") -> str:
        now = int(time.time())
        payload = {
            "iss": "https://auth.recoveryos.test",
            "aud": "authenticated",
            "sub": sub,
            "email": email,
            "email_verified": True,
            "iat": now,
            "exp": now + 3600,
        }
        return jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "test-key-provider"})

    return _make


@pytest.fixture
def mock_razorpay_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/orders":
            return httpx.Response(200, json={"entity": "collection", "count": 0, "items": []})
        elif request.method == "POST" and request.url.path == "/v1/orders":
            body = json.loads(request.read())
            return httpx.Response(
                200,
                json={
                    "id": "order_test_api_99",
                    "entity": "order",
                    "amount": body["amount"],
                    "currency": body["currency"],
                    "status": "created",
                    "receipt": body["receipt"],
                    "created_at": 1700000000,
                    "notes": body.get("notes", {}),
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def provider_test_app(
    api_ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
    session_factory: async_sessionmaker[AsyncSession],
    mock_razorpay_transport: httpx.MockTransport,
) -> Any:
    _, pub = api_ec_keypair
    app = create_app()

    test_verifier = JwtTokenVerifier(
        issuer="https://auth.recoveryos.test",
        audience="authenticated",
        allowed_algorithms=["ES256"],
        static_keys={"test-key-provider": pub},
    )
    app.dependency_overrides[get_jwt_token_verifier] = lambda: test_verifier
    app.dependency_overrides[get_session_factory] = lambda: session_factory

    # Use mock transport in payment provider service
    def uow_factory() -> Any:
        return SqlAlchemyUnitOfWork(session_factory)

    test_resolver = EnvProviderCredentialResolver()
    test_registry = PaymentProviderRegistry(transport=mock_razorpay_transport)
    test_service = PaymentProviderService(
        uow_factory=uow_factory,
        credential_resolver=test_resolver,
        registry=test_registry,
        transport=mock_razorpay_transport,
    )

    app.dependency_overrides[get_credential_resolver] = lambda: test_resolver
    app.dependency_overrides[get_payment_provider_service] = lambda: test_service

    transport = ASGITransport(app=app)
    return lambda: AsyncClient(transport=transport, base_url="http://testserver")


async def setup_merchant(
    db_session: AsyncSession,
    merchant_id: str,
    slug: str,
) -> None:
    now = datetime.now(UTC)
    m = MerchantModel(
        id=merchant_id, name=f"Merchant {slug}", slug=slug, created_at=now, updated_at=now
    )
    db_session.add(m)
    await db_session.commit()


async def setup_user_and_membership(
    db_session: AsyncSession,
    merchant_id: str,
    user_id: str,
    role: Role,
) -> None:
    now = datetime.now(UTC)
    u = UserModel(id=user_id, created_at=now, updated_at=now)
    db_session.add(u)
    await db_session.flush()

    ident = UserIdentityModel(
        id=f"id_{user_id}",
        user_id=user_id,
        issuer="https://auth.recoveryos.test",
        subject=f"sub_{user_id}",
        email=f"{user_id}@test.com",
        email_verified=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(ident)
    await db_session.flush()

    mem = MerchantMembershipModel(
        id=f"mem_{user_id}",
        merchant_id=merchant_id,
        user_id=user_id,
        role=role.value,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
    )
    db_session.add(mem)
    await db_session.commit()


@pytest.mark.asyncio
async def test_provider_connections_unauthenticated_returns_401(provider_test_app: Any) -> None:
    async with provider_test_app() as client:
        resp = await client.get("/api/v1/merchants/m_any/provider-connections")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_provider_connections_rbac_and_crud(
    provider_test_app: Any,
    make_jwt: Any,
    db_session: AsyncSession,
) -> None:
    now_str = str(int(time.time()))
    m_id = f"m_rbac_{now_str}"
    u_owner = f"u_owner_{now_str}"
    u_admin = f"u_admin_{now_str}"
    u_operator = f"u_op_{now_str}"
    u_analyst = f"u_an_{now_str}"

    await setup_merchant(db_session, m_id, f"slug-{now_str}")
    await setup_user_and_membership(db_session, m_id, u_owner, Role.OWNER)
    await setup_user_and_membership(db_session, m_id, u_admin, Role.ADMIN)
    await setup_user_and_membership(db_session, m_id, u_operator, Role.OPERATOR)
    await setup_user_and_membership(db_session, m_id, u_analyst, Role.ANALYST)

    token_owner = make_jwt(sub=f"sub_{u_owner}", email=f"{u_owner}@test.com")
    token_admin = make_jwt(sub=f"sub_{u_admin}", email=f"{u_admin}@test.com")
    token_operator = make_jwt(sub=f"sub_{u_operator}", email=f"{u_operator}@test.com")
    token_analyst = make_jwt(sub=f"sub_{u_analyst}", email=f"{u_analyst}@test.com")

    # Set mock environment keys for alias
    os.environ["RAZORPAY_TEST_DEMO_KEY_ID"] = "rzp_test_mockKeyId12345"
    os.environ["RAZORPAY_TEST_DEMO_KEY_SECRET"] = "mockSecretKeySecret123"

    async with provider_test_app() as client:
        # 1. ANALYST can read (initially empty)
        resp = await client.get(
            f"/api/v1/merchants/{m_id}/provider-connections",
            headers={"Authorization": f"Bearer {token_analyst}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

        # 2. OPERATOR cannot create connection (requires MERCHANT_MANAGE) -> 403
        resp = await client.post(
            f"/api/v1/merchants/{m_id}/provider-connections",
            json={"provider": "razorpay", "mode": "TEST", "credential_ref": "RAZORPAY_TEST_DEMO"},
            headers={"Authorization": f"Bearer {token_operator}"},
        )
        assert resp.status_code == 403

        # 3. ADMIN cannot create LIVE mode connection -> 403
        resp = await client.post(
            f"/api/v1/merchants/{m_id}/provider-connections",
            json={"provider": "razorpay", "mode": "LIVE", "credential_ref": "RAZORPAY_TEST_DEMO"},
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert resp.status_code == 403
        assert (
            "Live mode provider connection creation is strictly prohibited" in resp.json()["detail"]
        )

        # 4. ADMIN cannot create connection with un-allowlisted alias -> 400
        resp = await client.post(
            f"/api/v1/merchants/{m_id}/provider-connections",
            json={"provider": "razorpay", "mode": "TEST", "credential_ref": "UNREGISTERED_ALIAS"},
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert resp.status_code == 400
        assert "is not registered in server allowlist" in resp.json()["detail"]

        # 5. ADMIN creates valid TEST connection with allowlisted alias -> 201
        resp = await client.post(
            f"/api/v1/merchants/{m_id}/provider-connections",
            json={"provider": "razorpay", "mode": "TEST", "credential_ref": "RAZORPAY_TEST_DEMO"},
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert resp.status_code == 201
        conn = resp.json()
        conn_id = conn["id"]
        assert conn["provider"] == "RAZORPAY"
        assert conn["mode"] == "TEST"
        assert conn["status"] == "UNVERIFIED"
        assert "secret" not in json.dumps(conn).lower()

        # 6. OPERATOR cannot verify connection -> 403
        resp = await client.post(
            f"/api/v1/merchants/{m_id}/provider-connections/{conn_id}/verify",
            headers={"Authorization": f"Bearer {token_operator}"},
        )
        assert resp.status_code == 403

        # 7. OWNER can verify connection -> 200
        resp = await client.post(
            f"/api/v1/merchants/{m_id}/provider-connections/{conn_id}/verify",
            headers={"Authorization": f"Bearer {token_owner}"},
        )
        assert resp.status_code == 200
        ver = resp.json()
        assert ver["is_valid"] is True
        assert ver["key_id_fingerprint"] is not None

        # Check connection status transitioned to ACTIVE
        resp = await client.get(
            f"/api/v1/merchants/{m_id}/provider-connections",
            headers={"Authorization": f"Bearer {token_analyst}"},
        )
        assert resp.status_code == 200
        conns = resp.json()
        assert len(conns) == 1
        assert conns[0]["status"] == "ACTIVE"

        # 8. OWNER creates test order -> 201
        resp = await client.post(
            f"/api/v1/merchants/{m_id}/provider-connections/{conn_id}/test-orders",
            json={
                "amount_minor": 10000,
                "currency": "INR",
                "receipt": "rcpt_api_test_01",
                "notes": {"phase": "phase_5"},
            },
            headers={"Authorization": f"Bearer {token_owner}"},
        )
        assert resp.status_code == 201
        order = resp.json()
        assert order["provider"] == "RAZORPAY"
        assert order["amount_minor"] == 10000
        assert order["status"] == "CREATED"
        assert order["receipt"] == "rcpt_api_test_01"


@pytest.mark.asyncio
async def test_provider_connections_tenant_isolation(
    provider_test_app: Any,
    make_jwt: Any,
    db_session: AsyncSession,
) -> None:
    now_str = str(int(time.time()))
    m1_id = f"m1_{now_str}"
    m2_id = f"m2_{now_str}"
    u1 = f"u1_{now_str}"
    u2 = f"u2_{now_str}"

    await setup_merchant(db_session, m1_id, f"slug-m1-{now_str}")
    await setup_user_and_membership(db_session, m1_id, u1, Role.OWNER)

    await setup_merchant(db_session, m2_id, f"slug-m2-{now_str}")
    await setup_user_and_membership(db_session, m2_id, u2, Role.OWNER)

    token_m1 = make_jwt(sub=f"sub_{u1}", email=f"{u1}@test.com")
    token_m2 = make_jwt(sub=f"sub_{u2}", email=f"{u2}@test.com")

    os.environ["RAZORPAY_TEST_DEMO_KEY_ID"] = "rzp_test_m1KeyId12345"
    os.environ["RAZORPAY_TEST_DEMO_KEY_SECRET"] = "m1SecretKeySecret123"

    async with provider_test_app() as client:
        # Create connection under M1
        resp = await client.post(
            f"/api/v1/merchants/{m1_id}/provider-connections",
            json={"provider": "razorpay", "mode": "TEST", "credential_ref": "RAZORPAY_TEST_DEMO"},
            headers={"Authorization": f"Bearer {token_m1}"},
        )
        assert resp.status_code == 201
        m1_conn_id = resp.json()["id"]

        # M2 tries to access M1's connections -> 403 Forbidden (cross-tenant access rejected by auth)
        resp = await client.get(
            f"/api/v1/merchants/{m1_id}/provider-connections",
            headers={"Authorization": f"Bearer {token_m2}"},
        )
        assert resp.status_code == 403

        # M2 tries to verify M1's connection under M2's path -> 404 Not Found (tenant-isolated repo)
        resp = await client.post(
            f"/api/v1/merchants/{m2_id}/provider-connections/{m1_conn_id}/verify",
            headers={"Authorization": f"Bearer {token_m2}"},
        )
        assert resp.status_code == 404
