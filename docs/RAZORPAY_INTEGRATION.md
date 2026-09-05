# Razorpay Provider Integration Contract & Specification

**Contract Review Date**: `2026-09-05`  
**API Specification**: Razorpay REST API (Test Mode)  
**Status**: Implemented & Sealed for Phase 5  

---

## 1. Upstream REST API Endpoints

RecoveryOS communicates with Razorpay Test Mode via standard HTTP Basic Authentication over TLS (`verify=True`, `follow_redirects=False`).

| Operation | Method | Endpoint | Query / Body Parameters | Purpose |
|---|---|---|---|---|
| **Create Order** | `POST` | `/v1/orders` | `{"amount": int, "currency": str, "receipt": str, "notes": dict}` | Order creation |
| **Fetch Order** | `GET` | `/v1/orders/{order_id}` | None | Retrieve order by ID |
| **List Orders by Receipt** | `GET` | `/v1/orders` | `receipt=<exact_receipt>` | Read-only receipt lookup for ambiguous write recovery |
| **Fetch Payment** | `GET` | `/v1/payments/{payment_id}` | None | Retrieve payment by ID |
| **List Order Payments** | `GET` | `/v1/orders/{order_id}/payments` | `count=10, skip=0` | Retrieve payments associated with an order |
| **Verify Connection** | `GET` | `/v1/orders` | `count=1` | Safe non-mutating credential ping |

---

## 2. Receipt Lookup Recovery Mechanics

As verified against official Razorpay REST documentation on **2026-09-05**, the `/v1/orders` collection endpoint supports direct filtering via query parameter `receipt`:

```http
GET /v1/orders?receipt=rcpt_recov_001 HTTP/1.1
Host: api.razorpay.com
Authorization: Basic <base64(key_id:key_secret)>
```

### Ambiguous Write Recovery Sequence
When `POST /v1/orders` fails due to a network timeout (`ReadTimeout`, `ConnectTimeout`, or connection drop):
1. **Never Blindly Re-POST**: The order may have been committed on Razorpay's database despite the client experiencing a socket timeout. Repeating the POST would risk creating duplicate charges.
2. **Execute Receipt Lookup**:
   The adapter immediately queries `GET /v1/orders?receipt=<receipt>`.
3. **Branch Decision**:
   - **Exactly 1 match**: The order was created upstream. Normalize and return the snapshot.
   - **0 matches**: The order was definitely not created (or has not yet committed). Re-raise `ProviderAmbiguousWriteError`.
   - **>1 matches**: Multiple orders share the receipt. Raise `ProviderAmbiguityError` to signal an upstream integrity violation.

---

## 3. Error Mapping Taxonomy

Razorpay returns structured error envelopes under the `error` dictionary:
```json
{
  "error": {
    "code": "BAD_REQUEST_ERROR",
    "description": "Authentication failed",
    "source": "NA",
    "step": "NA",
    "reason": "NA"
  }
}
```

RecoveryOS maps these status codes and descriptions to typed exceptions:

| Upstream Status | Condition / Code / Description | RecoveryOS Exception | Semantics |
|---|---|---|---|
| `401` | Any authentication error | `ProviderAuthenticationError` | Invalid key or secret |
| `400` | `description` contains "Authentication failed" or "invalid key" | `ProviderAuthenticationError` | Upstream credential rejection |
| `400` | Missing required fields, invalid amount or currency | `ProviderValidationError` | Request payload validation error |
| `400` | Other bad request errors | `ProviderBadRequestError` | Unprocessable parameters |
| `403` | Access denied | `ProviderAuthorizationError` | Forbidden permissions |
| `404` | Resource not found | `ProviderNotFoundError` | Missing entity |
| `429` | Rate limited | `ProviderRateLimitError` | Backoff respecting `Retry-After` (max 5.0s) |
| `500, 502, 503, 504` | Upstream gateway/server error | `ProviderUnavailableError` | Transient error; safe GET retry candidate |
| Any | Unparseable JSON or missing ID/amount | `ProviderMalformedResponseError` | Response parsing failure |
| Any | Inbound stream > 1,048,576 bytes | `ProviderResponseTooLargeError` | Response size exceeded |

---

## 4. Customer PII Minimization

To ensure GDPR and privacy compliance, all customer-identifiable information returned by Razorpay is scrubbed at the mapping boundary (`RazorpayMapper.map_payment`).

The following keys are permanently stripped and never passed to application memory or persistence:
- `email`
- `contact`
- `card`
- `card_id`
- `bank`
- `vpa`

Diagnostics retain only non-PII technical failure attributes (`error_code`, `error_description`, `error_source`, `error_step`, `error_reason`).

---

## 5. Developer CLI Diagnostics

The developer CLI provides safe command-line diagnostics without accepting secrets as flags:

```bash
# Verify connection using allowlisted alias
python -m app.providers.cli verify \
  --merchant-id m_default \
  --credential-ref RAZORPAY_TEST_DEMO

# Create test order
python -m app.providers.cli create-test-order \
  --merchant-id m_123 \
  --connection-id conn_456 \
  --amount-minor 50000 \
  --currency INR \
  --receipt rcpt_cli_001

# Fetch order details
python -m app.providers.cli fetch-order \
  --merchant-id m_123 \
  --connection-id conn_456 \
  --order-id order_EKwxwAgItmmXdp
```
