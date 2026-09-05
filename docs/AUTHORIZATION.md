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
- **Untrusted Claims**: External JWT claims containing roles or permissions are discarded by design. Roles and permissions are strictly computed from internal database memberships.

---

## 2. Separation of Duties & RBAC Matrix

| Role | Permissions | Scope & Constraints |
|---|---|---|
| **OWNER** | `MERCHANT_READ`, `MERCHANT_MANAGE`, `MEMBERS_READ`, `MEMBERS_MANAGE`, `OWNERSHIP_MANAGE`, `PAYMENTS_READ`, `RECOVERY_READ`, `RECOVERY_OPERATE`, `RECOVERY_APPROVE`, `POLICIES_READ`, `POLICIES_MANAGE`, `AUDIT_READ` | Full control over the merchant tenant. Exclusive holder of `OWNERSHIP_MANAGE`. Protected by the Last Active Owner constraint. |
| **ADMIN** | `MERCHANT_READ`, `MERCHANT_MANAGE`, `MEMBERS_READ`, `MEMBERS_MANAGE`, `PAYMENTS_READ`, `RECOVERY_READ`, `RECOVERY_OPERATE`, `RECOVERY_APPROVE`, `POLICIES_READ`, `POLICIES_MANAGE`, `AUDIT_READ` | Full operational and policy management. **STRICTLY LACKS** `OWNERSHIP_MANAGE` — cannot add, modify, demote, or revoke `OWNER` memberships. |
| **OPERATOR** | `MERCHANT_READ`, `PAYMENTS_READ`, `RECOVERY_READ`, `RECOVERY_OPERATE`, `POLICIES_READ`, `AUDIT_READ` | Day-to-day operations and case execution (`RECOVERY_OPERATE`). **STRICTLY LACKS** `RECOVERY_APPROVE` and membership/policy mutation permissions. |
| **ANALYST** | `MERCHANT_READ`, `PAYMENTS_READ`, `RECOVERY_READ`, `POLICIES_READ` | Operational reporting and analytics read-only. Lacks `AUDIT_READ`, execution, and modification permissions. |
| **AUDITOR** | `MERCHANT_READ`, `PAYMENTS_READ`, `RECOVERY_READ`, `POLICIES_READ`, `AUDIT_READ` | Compliance and auditing read-only. Includes `AUDIT_READ`. Lacks execution and modification permissions. |

---

## 3. Last Active Owner Protection

- **Invariant**: A merchant tenant cannot be left without at least one `ACTIVE` `OWNER`.
- **Enforcement**: Any attempt to demote (`role != OWNER`) or deactivate (`status != ACTIVE`) an active owner triggers a `SELECT FOR UPDATE` transaction lock on the merchant record.
- **Safety**: If `count_active_owners <= 1`, the operation is aborted with a `LastOwnerViolationError` (HTTP 400).
