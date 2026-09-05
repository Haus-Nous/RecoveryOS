# Payment Provider Abstraction Architecture

## 1. Overview & Architectural Goals

RecoveryOS acts as an autonomous payment reliability and revenue recovery control plane. To avoid vendor lock-in and preserve strict architectural boundaries, the application layer never communicates directly with third-party payment service providers (PSPs) such as Razorpay, Stripe, or Cashfree.

Instead, RecoveryOS establishes a hardened provider boundary characterized by:
1. **Provider-neutral Ports & DTOs**: Standard domain-adjacent protocols and normalized snapshots.
2. **Strict Multi-Tenancy & Tenant Scoping**: Provider connections belong strictly to a single merchant tenant.
3. **Zero Secret Persistence**: Databases store only server-controlled credential references (`credential_ref`), never API keys, secrets, or basic auth strings.
4. **Zero Customer PII Storage**: Snapshots scrub customer email, phone numbers, card details, VPAs, and bank identifiers immediately at the transport mapper boundary.
5. **Fail-Closed Live Mode Prohibition**: Phase 5 operates strictly in `TEST` mode. Any attempt to register or execute against `LIVE` credentials fails closed immediately.
6. **Resilient Network Semantics**: Bounded streaming response limits (1MB), safe idempotent GET retries, rate-limit backoff capping, and zero blind retries on mutating writes.

---

## 2. Core Components

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RecoveryOS API & Services                       │
│                                                                        │
│   PaymentProviderService        PaymentProviderConnection (DB Entity)   │
└──────────────┬───────────────────────────────────┬─────────────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────────────┐    ┌──────────────────────────────────┐
│   ProviderCredentialResolver  │    │      PaymentProvider (Port)      │
│   (Env Allowlist Resolver)   │    │  (create_order, fetch_order,...) │
└──────────────┬───────────────┘    └──────────────┬───────────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────────────┐    ┌──────────────────────────────────┐
│      ProviderCredentials     │───▶│         RazorpayAdapter          │
│      (SecretStr / Redacted)  │    │  (Receipt Recovery & Mapping)    │
└──────────────────────────────┘    └──────────────┬───────────────────┘
                                                   │
                                                   ▼
                                    ┌──────────────────────────────────┐
                                    │        RazorpayHttpClient        │
                                    │   (TLS, Size Limit, Rate Limits) │
                                    └──────────────────────────────────┘
```

### 2.1 Domain & Snapshot Types (`app.providers.types`)
- `PaymentProviderName`: Provider enum (`RAZORPAY`, extensible to `STRIPE`, etc.).
- `ProviderMode`: `TEST` or `LIVE` (Phase 5 rejects `LIVE`).
- `ProviderConnectionStatus`: `UNVERIFIED`, `ACTIVE`, `DISABLED`.
- `ProviderOrderSnapshot`: Normalized snapshot containing `provider_order_id`, `amount_minor`, `currency`, `status`, `receipt`, `notes`, and UTC timestamps.
- `ProviderPaymentSnapshot`: Normalized payment snapshot containing `provider_payment_id`, `amount_minor`, `currency`, `status`, `method`, `fee_minor`, `tax_minor`, and optional `ProviderFailure`. Customer PII is guaranteed absent.
- `ProviderFailure`: Diagnostic taxonomy capturing `code`, `description`, `source`, `step`, and `reason` without customer-identifiable data.

### 2.2 Persistence Model (`PaymentProviderConnectionModel`)
- Table: `payment_provider_connections`
- Schema:
  - `id`: `VARCHAR(64)` primary key (`conn_<uuid>`).
  - `merchant_id`: `VARCHAR(64)` foreign key to `merchants.id` with `ON DELETE CASCADE`.
  - `provider`: `VARCHAR(32)` check constrained (`RAZORPAY`).
  - `mode`: `VARCHAR(16)` check constrained (`TEST`, `LIVE`).
  - `credential_ref`: `VARCHAR(64)` allowlisted alias.
  - `status`: `VARCHAR(32)` (`UNVERIFIED`, `ACTIVE`, `DISABLED`).
  - `key_id_fingerprint`: `VARCHAR(64)` safe truncated key identifier (e.g. `rzp_test_...1234`).
  - `last_verified_at`: `TIMESTAMP WITH TIME ZONE`.
  - `created_at`, `updated_at`: `TIMESTAMP WITH TIME ZONE`.
  - `version`: `INTEGER` optimistic locking counter.
- Constraints:
  - Unique constraint: `(merchant_id, provider, mode, credential_ref)` allowing a merchant to configure multiple test keys/staging aliases cleanly without accidental duplication.
  - Index on `(merchant_id, status)` for fast tenant lookups.

---

## 3. Security Invariants

### 3.1 Credential Resolution & Allowlisting
- RecoveryOS uses the **Indirection Pattern**: the database stores only aliases such as `RAZORPAY_TEST_DEMO`.
- `EnvProviderCredentialResolver` checks each alias against a server-controlled allowlist (`DEFAULT_CREDENTIAL_ALLOWLIST`).
- Any attempt to provide arbitrary environment variable names, path traversal tokens, or un-allowlisted references raises `ProviderCredentialResolutionError` immediately.
- `ProviderCredentials` wraps API secrets inside Pydantic's `SecretStr`. Its `__repr__` and `__str__` always output `[REDACTED]`.

### 3.2 Strict Live Mode Hard-Blocking
- If `connection.mode == ProviderMode.LIVE`: rejected with `ProviderLiveModeForbiddenError` before resolving credentials or initiating network requests.
- If resolved `key_id` starts with `rzp_live_`: fails closed with `ProviderLiveModeForbiddenError`.

### 3.3 Customer PII Scrubbing
- Razorpay API responses may contain customer-identifying fields (`email`, `contact`, `card`, `card_id`, `vpa`, `bank`).
- In `RazorpayMapper.map_payment`, these keys are explicitly filtered out from both typed fields and raw diagnostic dictionaries.

---

## 4. Operational Invariants

### 4.1 Bounded Streamed Response Size
- Provider endpoints limit inbound payload size to `1MB` (`DEFAULT_MAX_RESPONSE_BYTES = 1048576`).
- Pre-flight validation checks the `Content-Length` header if supplied.
- For streaming or chunk-encoded responses, bytes are counted incrementally during consumption. If accumulated bytes exceed 1MB, the stream is aborted immediately and `ProviderResponseTooLargeError` is raised.

### 4.2 Safe Idempotent GET Retries
- Only read-only `GET` requests are retried upon encountering transient errors (502, 503, 504) or network timeouts.
- Up to 3 attempts with exponential backoff.
- HTTP 429 Rate Limiting respects upstream `Retry-After` headers, capped strictly at `MAX_RETRY_AFTER_SECONDS = 5.0s`.

### 4.3 Mutating POST Writes & Ambiguity Recovery
- `POST /v1/orders` is **never blindly retried** upon timeout or socket drop.
- Network timeouts raise `ProviderAmbiguousWriteError`.
- `RazorpayAdapter` executes an ambiguous-write recovery sequence by querying `GET /v1/orders?receipt=<exact_receipt>`:
  - If **1** matching order is returned: successfully normalized and returned.
  - If **0** matching orders are returned: re-raises `ProviderAmbiguousWriteError`.
  - If **>1** matching orders are returned: raises `ProviderAmbiguityError` (upstream data integrity violation).
