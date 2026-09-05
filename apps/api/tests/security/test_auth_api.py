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
from app.domain.types import MerchantId
from app.identity.domain.models import Permission, Role
from app.identity.domain.types import UserId
from app.infrastructure.database import get_session_factory
from app.infrastructure.persistence.models.membership import MerchantMembershipModel
from app.infrastructure.persistence.models.merchant import MerchantModel
from app.infrastructure.persistence.models.user import UserIdentityModel, UserModel
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


@pytest.mark.asyncio
async def test_invited_membership_returns_403(
    authed_client: Any,
    make_token: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An invited user has an INVITED membership but has not accepted yet -> receives 403."""
    token = make_token(sub="usr_invited_sub", email="invited@user.com")

    async with authed_client() as client:
        # Trigger JIT creation
        me_resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        user_id = me_resp.json()["id"]

        # Insert Merchant and INVITED membership in DB
        now = datetime.now(UTC)
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            m = MerchantModel(
                id="merch_invited_tenant",
                name="Invited Tenant",
                slug="invited-tenant",
                created_at=now,
                updated_at=now,
            )
            uow._session.add(m)  # type: ignore[union-attr]
            await uow._session.flush()  # type: ignore[union-attr]
            mem = MerchantMembershipModel(
                id="mem_invited_test",
                merchant_id="merch_invited_tenant",
                user_id=user_id,
                role="OPERATOR",
                status="INVITED",
                created_at=now,
                updated_at=now,
                version=1,
            )
            uow._session.add(mem)  # type: ignore[union-attr]
            await uow.commit()

        # Accessing merchant endpoint returns 403 Forbidden
        resp = await client.get(
            "/api/v1/merchants/merch_invited_tenant",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "pending invitation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_no_membership_user_access_matrix(
    authed_client: Any,
    make_token: Any,
) -> None:
    """User with no memberships can view /me and bootstrap a merchant, but gets 403 on merchant endpoints."""
    token = make_token(sub="usr_no_membership", email="nomembership@user.com")

    async with authed_client() as client:
        # /me is allowed (200)
        me_resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200

        # Merchant specific endpoint returns 403 Forbidden
        resp = await client.get(
            "/api/v1/merchants/merch_any_merchant",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "not a member" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_multi_merchant_role_isolation(
    authed_client: Any,
    make_token: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """One user has ADMIN on Merchant A and AUDITOR on Merchant B.

    Permissions must be strictly isolated per tenant.
    """
    token = make_token(sub="usr_multitenant_user", email="multi@tenant.com")

    async with authed_client() as client:
        # Create JIT user
        me_resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        user_id = me_resp.json()["id"]

        now = datetime.now(UTC)
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            # Create Merchant A and Merchant B
            ma = MerchantModel(
                id="merch_alpha_iso",
                name="Alpha Iso",
                slug="alpha-iso",
                created_at=now,
                updated_at=now,
            )
            mb = MerchantModel(
                id="merch_beta_iso",
                name="Beta Iso",
                slug="beta-iso",
                created_at=now,
                updated_at=now,
            )
            uow._session.add_all([ma, mb])  # type: ignore[union-attr]
            await uow._session.flush()  # type: ignore[union-attr]

            # Membership A: ADMIN
            mem_a = MerchantMembershipModel(
                id="mem_iso_a",
                merchant_id="merch_alpha_iso",
                user_id=user_id,
                role="ADMIN",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
                version=1,
            )
            # Membership B: AUDITOR
            mem_b = MerchantMembershipModel(
                id="mem_iso_b",
                merchant_id="merch_beta_iso",
                user_id=user_id,
                role="AUDITOR",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
                version=1,
            )
            uow._session.add_all([mem_a, mem_b])  # type: ignore[union-attr]
            await uow.commit()

        # In Merchant A (ADMIN): can view members (MEMBERS_READ)
        resp_a = await client.get(
            "/api/v1/merchants/merch_alpha_iso/members",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_a.status_code == 200

        # In Merchant B (AUDITOR): AUDITOR has AUDIT_READ and MEMBERS_READ, but lacks MEMBERS_MANAGE
        # Inviting a member requires MEMBERS_MANAGE
        invite_in_b = await client.post(
            "/api/v1/merchants/merch_beta_iso/members",
            json={"user_id": "usr_someone_else", "role": "OPERATOR"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert invite_in_b.status_code == 403
        assert "lacks required permission" in invite_in_b.json()["detail"]


@pytest.mark.asyncio
async def test_concurrent_last_owner_demotion_leaves_at_least_one_owner(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two owners concurrently attempt to demote each other.

    Row locking on merchants serializes the checks, guaranteeing at least one owner remains.
    """
    from app.application.services.auth_service import AuthService
    from app.core.exceptions import LastOwnerViolationError

    auth_service = AuthService(lambda: SqlAlchemyUnitOfWork(session_factory))
    now = datetime.now(UTC)

    merchant_id = "merch_dual_owner_test"
    u1_id = "usr_owner_one"
    u2_id = "usr_owner_two"

    # Setup: 1 merchant and 2 active owners
    uow = SqlAlchemyUnitOfWork(session_factory)
    async with uow:
        m = MerchantModel(
            id=merchant_id,
            name="Dual Owner Corp",
            slug="dual-owner-corp",
            created_at=now,
            updated_at=now,
        )
        u1 = UserModel(id=u1_id, created_at=now, updated_at=now)
        u2 = UserModel(id=u2_id, created_at=now, updated_at=now)
        uow._session.add_all([m, u1, u2])  # type: ignore[union-attr]
        await uow._session.flush()  # type: ignore[union-attr]

        id1 = UserIdentityModel(
            id="uid_owner_1",
            user_id=u1_id,
            issuer="https://auth.recoveryos.test",
            subject="sub_1",
            created_at=now,
            updated_at=now,
        )
        id2 = UserIdentityModel(
            id="uid_owner_2",
            user_id=u2_id,
            issuer="https://auth.recoveryos.test",
            subject="sub_2",
            created_at=now,
            updated_at=now,
        )
        uow._session.add_all([id1, id2])  # type: ignore[union-attr]
        await uow._session.flush()  # type: ignore[union-attr]

        m1 = MerchantMembershipModel(
            id="mem_owner_1",
            merchant_id=merchant_id,
            user_id=u1_id,
            role="OWNER",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            version=1,
        )
        m2 = MerchantMembershipModel(
            id="mem_owner_2",
            merchant_id=merchant_id,
            user_id=u2_id,
            role="OWNER",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            version=1,
        )
        uow._session.add_all([m1, m2])  # type: ignore[union-attr]
        await uow.commit()

    # Actor 1 context (Owner 1)
    async with uow:
        principal_1 = AuthenticatedPrincipal(issuer="https://auth.recoveryos.test", subject="sub_1")
        ctx_1 = await auth_service.resolve_authorization_context(
            uow,
            principal_1,
            MerchantId(merchant_id),
            Permission.OWNERSHIP_MANAGE,
        )

    # Actor 2 context (Owner 2)
    async with uow:
        principal_2 = AuthenticatedPrincipal(issuer="https://auth.recoveryos.test", subject="sub_2")
        ctx_2 = await auth_service.resolve_authorization_context(
            uow,
            principal_2,
            MerchantId(merchant_id),
            Permission.OWNERSHIP_MANAGE,
        )

    # Concurrently: Owner 1 demotes Owner 2, Owner 2 demotes Owner 1
    async def demote_1_to_2() -> str:
        try:
            await auth_service.update_member_role_or_status(
                actor_ctx=ctx_1,
                target_user_id=UserId(u2_id),
                new_role=Role.ADMIN,
            )
            return "SUCCESS"
        except LastOwnerViolationError:
            return "BLOCKED"

    async def demote_2_to_1() -> str:
        try:
            await auth_service.update_member_role_or_status(
                actor_ctx=ctx_2,
                target_user_id=UserId(u1_id),
                new_role=Role.ADMIN,
            )
            return "SUCCESS"
        except LastOwnerViolationError:
            return "BLOCKED"

    results = await asyncio.gather(demote_1_to_2(), demote_2_to_1())

    # Exactly one succeeded and one was blocked by last owner protection
    assert sorted(results) == ["BLOCKED", "SUCCESS"]

    # Verify database state has exactly 1 active owner remaining
    async with uow:
        owners = await uow.memberships.count_active_owners(MerchantId(merchant_id))
        assert owners == 1


@pytest.mark.asyncio
async def test_identity_and_membership_database_constraints(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify database uniqueness and check constraints directly at PostgreSQL level."""
    from sqlalchemy.exc import IntegrityError

    now = datetime.now(UTC)
    uow = SqlAlchemyUnitOfWork(session_factory)

    # 1. Duplicate issuer + subject is rejected
    async with uow:
        u_main = UserModel(id="usr_db_test_1", created_at=now, updated_at=now)
        u_dup = UserModel(id="usr_db_test_2", created_at=now, updated_at=now)
        uow._session.add_all([u_main, u_dup])  # type: ignore[union-attr]
        await uow._session.flush()  # type: ignore[union-attr]
        id1 = UserIdentityModel(
            id="uid_1",
            user_id="usr_db_test_1",
            issuer="https://issuer.test",
            subject="unique_sub_1",
            created_at=now,
            updated_at=now,
        )
        uow._session.add(id1)  # type: ignore[union-attr]
        await uow.commit()

    with pytest.raises(IntegrityError):
        async with uow:
            id2 = UserIdentityModel(
                id="uid_2",
                user_id="usr_db_test_2",
                issuer="https://issuer.test",
                subject="unique_sub_1",  # Duplicate (issuer, subject)
                created_at=now,
                updated_at=now,
            )
            uow._session.add(id2)  # type: ignore[union-attr]
            await uow.commit()

    # 2. Duplicate (merchant_id, user_id) membership is rejected
    async with uow:
        m = MerchantModel(
            id="merch_db_constraint",
            name="DB Constraint Corp",
            slug="db-constraint-corp",
            created_at=now,
            updated_at=now,
        )
        uow._session.add(m)  # type: ignore[union-attr]
        await uow._session.flush()  # type: ignore[union-attr]
        mem1 = MerchantMembershipModel(
            id="mem_uniq_1",
            merchant_id="merch_db_constraint",
            user_id="usr_db_test_1",
            role="OWNER",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            version=1,
        )
        uow._session.add(mem1)  # type: ignore[union-attr]
        await uow.commit()

    with pytest.raises(IntegrityError):
        async with uow:
            mem2 = MerchantMembershipModel(
                id="mem_uniq_2",
                merchant_id="merch_db_constraint",
                user_id="usr_db_test_1",  # Duplicate (merchant, user)
                role="ADMIN",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
                version=1,
            )
            uow._session.add(mem2)  # type: ignore[union-attr]
            await uow.commit()

    # 3. Invalid role check constraint
    with pytest.raises(IntegrityError):
        async with uow:
            mem_bad_role = MerchantMembershipModel(
                id="mem_bad_role",
                merchant_id="merch_db_constraint",
                user_id="usr_db_test_2",
                role="SUPER_ADMIN_INVALID",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
                version=1,
            )
            uow._session.add(mem_bad_role)  # type: ignore[union-attr]
            await uow.commit()

    # 4. Invalid status check constraint
    with pytest.raises(IntegrityError):
        async with uow:
            mem_bad_status = MerchantMembershipModel(
                id="mem_bad_status",
                merchant_id="merch_db_constraint",
                user_id="usr_db_test_2",
                role="OWNER",
                status="DELETED_INVALID",
                created_at=now,
                updated_at=now,
                version=1,
            )
            uow._session.add(mem_bad_status)  # type: ignore[union-attr]
            await uow.commit()
