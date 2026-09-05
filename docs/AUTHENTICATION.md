# RecoveryOS — Authentication Specification (Phase 3)

## 1. Core Authentication Principles

RecoveryOS enforces strict separation between:
1. **AUTHENTICATION**: "Who is this principal?" (Cryptographically verified OIDC / JWT token).
2. **AUTHORIZATION**: "What can this principal do for this merchant?" (Internal role and permissions).
3. **TENANT ISOLATION**: "Which merchant's records may this request reach?" (Server-side merchant scoping).

```
External Identity Provider (Supabase Auth / OIDC)
        ↓ (Asymmetric JWT via JWKS)
AuthenticatedPrincipal (iss, sub, email, email_verified)
        ↓ (JIT Mapping on Demand: UNIQUE(issuer, subject))
Internal User & Identity (users, user_identities)
        ↓ (Tenant Membership Lookup: (merchant_id, user_id))
MerchantMembership (role, status, version)
        ↓ (RBAC & Policy Evaluation)
Authorized Action / Route Handler
```

---

## 2. Authentication vs Authorization Semantics (401 vs 403)

| Scenario | HTTP Status | Error Detail / Behavior |
|---|---|---|
| Missing Bearer token header | `401 Unauthorized` | "Authentication credentials were not provided." |
| Malformed Bearer token / header | `401 Unauthorized` | "Authentication token is missing or malformed." |
| Token expired (`exp`) | `401 Unauthorized` | "Authentication token has expired." |
| Token not valid yet (`nbf`) | `401 Unauthorized` | "Authentication token not valid yet (nbf)." |
| Issuer mismatch (`iss`) | `401 Unauthorized` | "Token issuer mismatch." |
| Audience mismatch (`aud`) | `401 Unauthorized` | "Token audience mismatch." |
| Invalid signature | `401 Unauthorized` | "Invalid cryptographic signature." |
| Algorithm `none` or disallowed | `401 Unauthorized` | "Forbidden or unsupported token algorithm." |
| Missing `sub` claim | `401 Unauthorized` | "Token payload missing required 'sub' claim." |
| Oversized token (> 8 KB) | `401 Unauthorized` | "Authentication token exceeds maximum permitted size." |
| Unknown key ID (`kid`) | `401 Unauthorized` | Refreshes JWKS once; if key remains unknown, fails closed. |
| User has no membership in target merchant | `403 Forbidden` | "User is not a member of merchant '{merchant_id}'." |
| Membership `INVITED` (pending acceptance) | `403 Forbidden` | "Membership in merchant '{merchant_id}' is pending invitation acceptance." |
| Membership `SUSPENDED` | `403 Forbidden` | "Membership in merchant '{merchant_id}' is suspended." |
| Membership `REVOKED` | `403 Forbidden` | "Membership in merchant '{merchant_id}' has been revoked." |
| Insufficient RBAC permission | `403 Forbidden` | "Role '{role}' lacks required permission '{permission}'." |

---

## 3. JWT Verification Matrix & Algorithms

- **Supported & Allowed Algorithms**: `ES256`, `RS256` (asymmetric).
- **Prohibited Algorithms**: `none`, `HS256`, `HS384`, `HS512` (symmetric HMAC is prohibited in production/staging).
- **Dynamic JWKS Caching & Rotation**:
  - In-memory thread-safe TTL caching (`AUTH_JWKS_CACHE_TTL_SECONDS=300`).
  - Cache hits perform 0 network requests.
  - An unknown `kid` triggers exactly ONE cache invalidation and JWKS refresh before failing closed.
- **Fail-Closed Configuration**:
  - `APP_ENV=production` or `APP_ENV=staging` strictly requires `AUTH_ISSUER`, `AUTH_AUDIENCE`, and `AUTH_JWKS_URL` to be present and non-empty.
  - Startup or request handling with missing/insecure auth settings raises a fatal `ValueError`.

---

## 4. Supabase Status & Compatibility

- **Supabase-Compatible JWT Verifier**: `YES` (asymmetric `ES256`/`RS256` verification via Supabase project JWKS URL).
- **Frontend Supabase Client Adapter**: `YES` (`AuthProvider` in `apps/web/src/lib/auth-context.tsx`).
- **Live Supabase Project Configured**: `NOT CONFIGURED` (fails closed until deployment environment variables are supplied).

---

## 5. Zero Credential & Token Persistence Policy

- **Zero Passwords**: RecoveryOS does NOT store passwords, password hashes, or identity secrets.
- **Zero Database Token Storage**: Access tokens, bearer tokens, and refresh tokens are NEVER persisted in PostgreSQL tables.
- **Frontend Token Safety**: React `AuthContext` does NOT store raw bearer tokens or refresh tokens in application state, `localStorage`, or `sessionStorage`. Tokens are acquired on demand from the provider session.
- **Zero Token Logging**: Request logging middleware strictly sanitizes and omits `Authorization` headers, bearer tokens, and secret payloads.

---

## 6. User Identity & PII Policy

- **`users` Table**: UUID primary key (`usr_...`), created/updated timestamps. Does not store duplicate PII.
- **`user_identities` Table**: Maps external IdP `(issuer, subject)` to internal `user_id`. Stores email for contact / display only.
- **Authorization Identity Source**: Authorization is ALWAYS performed via `(issuer, subject)` -> `user_id` -> `merchant_memberships`. Email or name is NEVER used to authorize tenant access.
