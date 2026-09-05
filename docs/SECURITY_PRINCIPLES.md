# RecoveryOS — Security Principles & Guardrails

## 1. Zero Cardholder Data (PCI DSS Scope Minimization)
- **No PAN/CVV Storage**: RecoveryOS strictly prohibits the capture, ingestion, processing, or persistence of Primary Account Numbers (PAN), CVVs, or card PINs.
- Gateway tokenization references (e.g. Razorpay payment IDs, customer tokens) are utilized exclusively.

## 2. Least Privilege & Deny-by-Default
- All authorization decisions default to `DENY`.
- Actions require explicit deterministic policy rules with merchant tenant ownership boundaries.

## 3. Server-Side Verification & Webhook Integrity
- Webhooks from gateways (e.g., Razorpay HMAC SHA-256 signatures) must be verified *before* payload parsing or database persistence.
- External webhook payloads are treated as untrusted input.

## 4. Idempotency & Replay Resistance
- Every financial mutation and recovery action must supply an idempotency key.
- Redis and database unique constraints prevent double-execution of recovery actions.

## 5. Untrusted AI Boundaries
- LLM outputs are treated as untrusted proposals.
- No LLM output may directly trigger a database write, refund, payment capture, or external customer communication without deterministic schema validation and policy authorization.

## 6. Secrets Management
- No secrets, credentials, API keys, or certificates in source control.
- Configuration is provided strictly via environment variables.

## 7. Auditability & Forensic Traceability
- All proposals, policy evaluations, executions, and reconciliation events produce immutable, time-stamped audit entries.

## 8. Accurate Compliance Representation
- This application does not make false certification claims. We describe our architecture as "production-oriented" and "designed toward production-grade security practices."

## 9. Structural Multi-Tenant Data Isolation
- Every merchant-owned financial query and repository port must be explicitly scoped by `MerchantId`.
- Relational cross-tenant access is prohibited at both the application repository layer and physically via composite database foreign keys.
- Domain event logs and transactional outbox entries are strictly tenant-scoped.

## 10. Physical Environment Separation & Destructive Test Protection
- Production, Staging, Development, and Testing environments utilize physically isolated databases.
- Test suites operate strictly against dedicated test databases ending with `_test` under `APP_ENV=test`.
- Destructive migration routines and truncate fixtures enforce a fail-closed check to prevent data corruption or loss in non-test databases.

## 11. Threat Modeling & Defense Matrix (Phase 3)

| Threat | Attack Vector | Countermeasure & Defensive Architecture |
|---|---|---|
| **Stolen / Expired Token** | Attacker obtains an expired or forged JWT | Dynamic asymmetric verification against IdP JWKS endpoint (`ES256`/`RS256`), expiry validation (`exp`), not-before validation (`nbf`), clock-skew bounds (10s max). |
| **Role Claim Tampering** | Attacker inserts `"role": "OWNER"` or `"permissions": ["*"]` inside JWT | External token claims are strictly ignored for authorization. Roles and permissions are derived exclusively from the internal database membership table. |
| **Cross-Tenant Access (BOLA / IDOR)** | Attacker in Merchant A attempts to access Merchant B endpoints | Server-side `require_permission` dependency verifies tenant membership in DB; database composite foreign keys prevent cross-tenant data traversal. |
| **Instant Revocation Delay** | Revoked or suspended user continues to call API with still-valid token | Membership status is queried on every request. Statuses `SUSPENDED` and `REVOKED` immediately return HTTP 403 Forbidden without waiting for token expiry. |
| **Privilege Escalation** | `ADMIN` or `OPERATOR` attempts to mutate `OWNER` status or demote owners | Explicit `OWNERSHIP_MANAGE` permission required for owner-level changes. Row-level `SELECT FOR UPDATE` prevents demoting the last active owner. |
| **ReDoS / Token Flooding** | Attacker sends massive strings in `Authorization` header | Bounded token size check strictly enforces `<= 8192` bytes prior to parsing. |

