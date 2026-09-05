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
        ↓ (JIT Mapping on Demand)
Internal User & Identity (users, user_identities)
        ↓ (Tenant Membership Lookup)
MerchantMembership (role, status, version)
        ↓ (RBAC & Policy Evaluation)
Authorized Action / Route Handler
```

## 2. Token Verification Architecture

- **Protocol**: Standard asymmetric JSON Web Token verification (`ES256` / `RS256`).
- **Signing Keys**: Dynamic public keys fetched asynchronously from Identity Provider JWKS endpoint with in-memory TTL caching (`AUTH_JWKS_CACHE_TTL_SECONDS=3600`).
- **Fail-Closed Strategy**:
  - In `staging` and `production`, backend fails closed on startup if `AUTH_ISSUER` or `AUTH_JWKS_URL` is missing.
  - Symmetric HMAC (`HS256`) is explicitly prohibited in OIDC verification.
  - Algorithms `none`, unrecognized headers, or mismatched keys fail immediately.
  - Maximum token size is constrained to 8 KB (8192 bytes) to defend against ReDoS / allocation attacks.
  - Tokens missing `sub`, expired (`exp`), or with future validity beyond clock skew (`nbf`) fail closed with HTTP 401.

## 3. Zero Credential Persistence Invariant

- **Zero Password Storage**: RecoveryOS does NOT store passwords, password hashes (bcrypt/argon2), salt values, or identity secrets.
- **Zero Token Persistence**: Bearer tokens and refresh tokens are never written to PostgreSQL tables or server-side logs.
- **Client Safety**: Frontend React context stores only safe user and tenant metadata (`id`, `email`, `activeMerchant`). Raw tokens are accessed on demand from session cookies / auth provider state without global browser state leakage.
