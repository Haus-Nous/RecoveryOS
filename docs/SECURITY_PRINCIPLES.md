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
