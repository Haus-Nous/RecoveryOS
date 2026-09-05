# RecoveryOS — Multi-Tenant Authorization & RBAC Specification (Phase 3)

## 1. Multi-Tenant Authorization Invariant

```
IDENTITY AUTHENTICATES.
MEMBERSHIP SCOPES.
PERMISSION AUTHORIZES.
DATABASE CONSTRAINS.
```

- **Tenant Scoping**: All merchant entities and operations require an active `MerchantMembership` record for `(merchant_id, user_id)` in `ACTIVE` status.
- **Immediate Invalidation**: Membership state is verified dynamically against PostgreSQL per-request. Demotions, suspensions (`SUSPENDED`), and revocations (`REVOKED`) take effect immediately without waiting for token expiration.
- **Untrusted Claims**: External JWT claims containing roles, permissions, or merchant IDs are discarded by design. Roles and permissions are strictly computed from internal database memberships.

---

## 2. Membership Status Lifecycle

| Status | Tenant Access Permitted | RBAC Evaluation | Description |
|---|---|---|---|
| **ACTIVE** | **YES** | Evaluates role permissions | Fully active member with tenant operational access. |
| **INVITED** | **NO** (403 Forbidden) | None (Fails closed) | Invited user awaiting acceptance; cannot access tenant resources. |
| **SUSPENDED** | **NO** (403 Forbidden) | None (Fails closed) | Temporarily disabled membership; access denied immediately. |
| **REVOKED** | **NO** (403 Forbidden) | None (Fails closed) | Permanently terminated membership; access denied immediately. |

---

## 3. Separation of Duties & RBAC Role-Permission Matrix

| Permission | OWNER | ADMIN | OPERATOR | ANALYST | AUDITOR |
|---|:---:|:---:|:---:|:---:|:---:|
| `MERCHANT_READ` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `MERCHANT_MANAGE` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `MEMBERS_READ` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `MEMBERS_MANAGE` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `OWNERSHIP_MANAGE` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `PAYMENTS_READ` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `RECOVERY_READ` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `RECOVERY_OPERATE` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `RECOVERY_APPROVE` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `POLICIES_READ` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POLICIES_MANAGE` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `AUDIT_READ` | ✅ | ✅ | ❌ | ❌ | ✅ |

### Key Duty Separation Rules:
1. **`OWNER`**: Full permissions including `OWNERSHIP_MANAGE`.
2. **`ADMIN`**: Full operational/member management, but strictly lacks `OWNERSHIP_MANAGE` (cannot promote, demote, or modify `OWNER` memberships).
3. **`OPERATOR`**: May execute recoveries (`RECOVERY_OPERATE`), but strictly lacks `RECOVERY_APPROVE` (cannot approve policy exceptions).
4. **`ANALYST`**: Read-only operational visibility (`MERCHANT_READ`, `MEMBERS_READ`, `PAYMENTS_READ`, `RECOVERY_READ`, `POLICIES_READ`). Lacks `AUDIT_READ` and mutations.
5. **`AUDITOR`**: Compliance read-only (`MERCHANT_READ`, `MEMBERS_READ`, `PAYMENTS_READ`, `RECOVERY_READ`, `POLICIES_READ`, `AUDIT_READ`). Lacks mutations and execution.

---

## 4. Owner Safety & Concurrency Locking

- **Last Active Owner Constraint**: A merchant tenant must always have at least one `ACTIVE` `OWNER`. Demoting or deactivating the last active owner is rejected with `LastOwnerViolationError` (HTTP 400).
- **Pessimistic Row Locking**: All membership role and status mutations lock the merchant tenant record (`SELECT id FROM merchants WHERE id = :merchant_id FOR UPDATE`), serializing concurrent modifications and preventing race conditions from creating a zero-owner state.
- **Owner Role Protection**: Assigning or modifying an `OWNER` membership requires the caller to hold `OWNERSHIP_MANAGE` (exclusive to `OWNER` role).

---

## 5. API Endpoints & Permission Enforcement

| Endpoint | Method | Required Permission | Description |
|---|---|---|---|
| `/api/v1/me` | `GET` | Authenticated Principal | Returns authenticated user profile. |
| `/api/v1/me/merchants` | `GET` | Authenticated User | Lists merchant memberships for user. |
| `/api/v1/merchants` | `POST` | Authenticated Principal | Bootstraps new merchant; provisions caller as `OWNER`. |
| `/api/v1/merchants/{id}` | `GET` | `MERCHANT_READ` | Returns merchant tenant details. |
| `/api/v1/merchants/{id}/members` | `GET` | `MEMBERS_READ` | Lists memberships in tenant. |
| `/api/v1/merchants/{id}/members` | `POST` | `MEMBERS_MANAGE` | Adds or invites a member (requires `OWNERSHIP_MANAGE` if role is `OWNER`). |
| `/api/v1/merchants/{id}/members/{user_id}` | `PATCH` | `MEMBERS_MANAGE` | Updates member role/status (requires `OWNERSHIP_MANAGE` if target is `OWNER`). |

---

## 6. Frontend Protection Mechanism

- **FastAPI API Boundary**: FastAPI remains the ultimate authorization enforcement boundary on every single request.
- **Client Session Management**: `AuthProvider` exposes authenticated session state, tenant switching, role indicators, and sign-out capabilities.
- **Non-Disclosure**: Cross-tenant requests return `403 Forbidden` without revealing tenant resource details.
- **No Statically Shared Cache**: Authenticated user/merchant views are dynamically resolved per request and never statically cached across principals.
