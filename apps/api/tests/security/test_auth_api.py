"""Comprehensive security integration tests for Authentication, Multi-Tenancy, and RBAC."""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies.auth import get_jwt_token_verifier
from app.application.ports.authentication import AuthenticatedPrincipal
from app.infrastructure.database import get_session_factory
from app.infrastructure.persistence.models.membership import MerchantMembershipModel
from app.infrastructure.persistence.models.merchant import MerchantModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.jwt_verifier import JwtTokenVerifier
from app.main import create_app


@pytest.fixture(scope="module")
def auth_ec_keypair() -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key()


@pytest.fixture
def make_token(
    auth_ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> Any:
    priv, _ = auth_ec_keypair

    def _make(
        sub: str,
        iss: str = "https://auth.recoveryos.test",
        aud: str = "authenticated",
        email: str = "test@example.com",
        exp_offset: int = 3600,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        payload = {
            "iss": iss,
            "aud": aud,
            "sub": sub,
            "email": email,
            "email_verified": True,
            "iat": now,
            "exp": now + exp_offset,
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, priv, algorithm="ES256", headers={"kid": "test-key-1"})

    return _make


@pytest.fixture
def authed_client(
    auth_ec_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
    session_factory: async_sessionmaker[AsyncSession],
) -> Any:
    _, pub = auth_ec_keypair
    app = create_app()

    # Override token verifier with test static key
    test_verifier = JwtTokenVerifier(
        issuer="https://auth.recoveryos.test",
        audience="authenticated",
        allowed_algorithms=["ES256"],
        static_keys={"test-key-1": pub},
    )
    app.dependency_overrides[get_jwt_token_verifier] = lambda: test_verifier
    app.dependency_overrides[get_session_factory] = lambda: session_factory

    transport = ASGITransport(app=app)
    return lambda: AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_get_me_unauthenticated_returns_401(authed_client: Any) -> None:
    async with authed_client() as client:
        resp = await client.get("/api/v1/me")
        assert resp.status_code == 401
        assert "Authentication credentials were not provided" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_me_authenticated(authed_client: Any, make_token: Any) -> None:
    token = make_token(sub="usr_test_sub_1", email="alice@merchanta.com")
    async with authed_client() as client:
        resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "alice@merchanta.com"
        assert data["email_verified"] is True
        assert data["id"].startswith("usr_")


@pytest.mark.asyncio
async def test_bootstrap_merchant_creates_owner_membership(
    authed_client: Any, make_token: Any
) -> None:
    token = make_token(sub="usr_bootstrap_owner", email="owner@newmerchant.com")
    async with authed_client() as client:
        # Create merchant
        create_resp = await client.post(
            "/api/v1/merchants",
            json={"name": "New Alpha Corp", "slug": "new-alpha-corp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        merchant = create_resp.json()
        merchant_id = merchant["id"]
        assert merchant["name"] == "New Alpha Corp"
        assert merchant["slug"] == "new-alpha-corp"

        # List user's merchants
        list_resp = await client.get(
            "/api/v1/me/merchants", headers={"Authorization": f"Bearer {token}"}
        )
        assert list_resp.status_code == 200
        merchants = list_resp.json()
        assert any(m["id"] == merchant_id and m["role"] == "OWNER" for m in merchants)

        # Get merchant details
        get_resp = await client.get(
            f"/api/v1/merchants/{merchant_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_external_role_claim_attack_is_ignored(
    authed_client: Any,
    make_token: Any,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An attacker provides a valid JWT with spoofed claims {'role': 'OWNER', 'permissions': ['*']}.

    The attacker has only an ANALYST membership in the DB.
    RecoveryOS MUST ignore the JWT claims and deny operator/admin operations.
    """
    now = datetime.now(UTC)

    # 1. Create a merchant in DB
    m = MerchantModel(
        id="merch_victim_claims",
        name="Victim Corp",
        slug="victim-corp",
        created_at=now,
        updated_at=now,
    )
    db_session.add(m)
    await db_session.commit()

    # 2. Authenticate as user with spoofed JWT claims
    malicious_token = make_token(
        sub="usr_attacker_sub",
        email="attacker@corp.com",
        extra_claims={
            "role": "OWNER",
            "permissions": ["*"],
            "merchant_id": "merch_victim_claims",
        },
    )

    async with authed_client() as client:
        # First query /me to trigger JIT user creation
        me_resp = await client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {malicious_token}"}
        )
        user_id = me_resp.json()["id"]

        # Insert ANALYST membership in DB
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            mem = MerchantMembershipModel(
                id="mem_attacker_analyst",
                merchant_id="merch_victim_claims",
                user_id=user_id,
                role="ANALYST",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
                version=1,
            )
            uow._session.add(mem)  # type: ignore[union-attr]
            await uow.commit()

        # 3. Attacker can read merchant details (ANALYST has MERCHANT_READ)
        read_resp = await client.get(
            "/api/v1/merchants/merch_victim_claims",
            headers={"Authorization": f"Bearer {malicious_token}"},
        )
        assert read_resp.status_code == 200

        # 4. Attacker attempts to update a member role (requires MEMBERS_MANAGE) -> MUST BE 403 FORBIDDEN
        update_resp = await client.patch(
            "/api/v1/merchants/merch_victim_claims/members/usr_target",
            json={"role": "ADMIN"},
            headers={"Authorization": f"Bearer {malicious_token}"},
        )
        assert update_resp.status_code == 403
        assert "lacks required permission" in update_resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_access_is_forbidden(
    authed_client: Any,
    make_token: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """User A in Merchant A attempts to access Merchant B."""
    token_a = make_token(sub="usr_tenant_a", email="a@tenanta.com")
    token_b = make_token(sub="usr_tenant_b", email="b@tenantb.com")

    async with authed_client() as client:
        # User B bootstraps Merchant B
        b_create = await client.post(
            "/api/v1/merchants",
            json={"name": "Tenant B Corp", "slug": "tenant-b-corp"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        merchant_b_id = b_create.json()["id"]

        # User A attempts to access Merchant B -> MUST BE 403 FORBIDDEN
        a_access = await client.get(
            f"/api/v1/merchants/{merchant_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert a_access.status_code == 403
        assert "not a member" in a_access.json()["detail"]


@pytest.mark.asyncio
async def test_membership_revocation_and_suspension_immediate_403(
    authed_client: Any,
    make_token: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Proves revocation and suspension reject immediately without waiting for token expiry."""
    token = make_token(sub="usr_revocation_test", email="victim@revoked.com")

    async with authed_client() as client:
        # 1. Bootstrap merchant
        create_resp = await client.post(
            "/api/v1/merchants",
            json={"name": "Revoke Test Corp", "slug": "revoke-test-corp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        merchant_id = create_resp.json()["id"]

        # 2. Access succeeds initially
        ok_resp = await client.get(
            f"/api/v1/merchants/{merchant_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ok_resp.status_code == 200

        # 3. Suspend membership in DB
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            stmt = text(
                "UPDATE merchant_memberships SET status = 'SUSPENDED' WHERE merchant_id = :mid"
            )
            await uow._session.execute(stmt, {"mid": merchant_id})  # type: ignore[union-attr]
            await uow.commit()

        # 4. Next request with identical valid token receives 403 immediately
        susp_resp = await client.get(
            f"/api/v1/merchants/{merchant_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert susp_resp.status_code == 403
        assert "suspended" in susp_resp.json()["detail"]

        # 5. Revoke membership in DB
        async with uow:
            stmt = text(
                "UPDATE merchant_memberships SET status = 'REVOKED' WHERE merchant_id = :mid"
            )
            await uow._session.execute(stmt, {"mid": merchant_id})  # type: ignore[union-attr]
            await uow.commit()

        # 6. Next request receives 403 immediately
        rev_resp = await client.get(
            f"/api/v1/merchants/{merchant_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rev_resp.status_code == 403
        assert "revoked" in rev_resp.json()["detail"]


@pytest.mark.asyncio
async def test_last_active_owner_protection(
    authed_client: Any,
    make_token: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Attempting to demote or revoke the sole active owner is blocked."""
    token = make_token(sub="usr_sole_owner", email="sole@owner.com")

    async with authed_client() as client:
        # Bootstrap
        create_resp = await client.post(
            "/api/v1/merchants",
            json={"name": "Sole Owner Corp", "slug": "sole-owner-corp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        merchant_id = create_resp.json()["id"]

        me_resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        user_id = me_resp.json()["id"]

        # Attempt to demote sole active owner to ADMIN
        demote_resp = await client.patch(
            f"/api/v1/merchants/{merchant_id}/members/{user_id}",
            json={"role": "ADMIN"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert demote_resp.status_code == 400
        assert "Cannot demote or deactivate the last ACTIVE owner" in demote_resp.json()["detail"]

        # Attempt to revoke sole active owner
        revoke_resp = await client.patch(
            f"/api/v1/merchants/{merchant_id}/members/{user_id}",
            json={"status": "REVOKED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert revoke_resp.status_code == 400
        assert "Cannot demote or deactivate the last ACTIVE owner" in revoke_resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_cannot_mutate_owner_membership(
    authed_client: Any,
    make_token: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """ADMIN has MEMBERS_MANAGE but strictly lacks OWNERSHIP_MANAGE."""
    owner_token = make_token(sub="usr_real_owner", email="owner@company.com")
    admin_token = make_token(sub="usr_real_admin", email="admin@company.com")

    async with authed_client() as client:
        # 1. Owner creates merchant
        create_resp = await client.post(
            "/api/v1/merchants",
            json={"name": "Company Corp", "slug": "company-corp"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        merchant_id = create_resp.json()["id"]

        # Owner user id
        owner_id = (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {owner_token}"})
        ).json()["id"]

        # JIT admin user
        admin_id = (
            await client.get("/api/v1/me", headers={"Authorization": f"Bearer {admin_token}"})
        ).json()["id"]

        # 2. Add admin membership in DB
        now = datetime.now(UTC)
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            admin_mem = MerchantMembershipModel(
                id="mem_admin_test",
                merchant_id=merchant_id,
                user_id=admin_id,
                role="ADMIN",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
                version=1,
            )
            uow._session.add(admin_mem)  # type: ignore[union-attr]
            await uow.commit()

        # 3. Admin attempts to demote Owner -> 403 Forbidden
        admin_demote_owner = await client.patch(
            f"/api/v1/merchants/{merchant_id}/members/{owner_id}",
            json={"role": "ADMIN"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_demote_owner.status_code == 403
        assert "Only an OWNER with OWNERSHIP_MANAGE" in admin_demote_owner.json()["detail"]


@pytest.mark.asyncio
async def test_concurrent_jit_user_creation_is_safe(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two concurrent requests with the exact same (issuer, subject) create exactly ONE User."""
    from app.application.services.auth_service import AuthService

    auth_service = AuthService(lambda: SqlAlchemyUnitOfWork(session_factory))
    principal = AuthenticatedPrincipal(
        issuer="https://auth.recoveryos.test",
        subject="usr_concurrent_jit_subject",
        email="concurrent@test.com",
    )

    async def _resolve() -> str:
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            user, _ = await auth_service.get_or_create_user_from_principal(uow, principal)
            await uow.commit()
            return str(user.id)

    # Launch concurrently
    results = await asyncio.gather(_resolve(), _resolve())
    assert results[0] == results[1]
