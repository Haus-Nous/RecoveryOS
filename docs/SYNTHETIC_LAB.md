# RecoveryOS — Synthetic Payment Laboratory (Phase 4)

## 1. Architectural Invariant & Purpose

```
AI PROPOSES.
POLICY AUTHORIZES.
INFRASTRUCTURE EXECUTES.
LEDGER VERIFIES.

IDENTITY AUTHENTICATES.
MEMBERSHIP SCOPES.
PERMISSION AUTHORIZES.
DATABASE CONSTRAINS.

SYNTHETIC DATA IS REPRODUCIBLE.
GROUND TRUTH IS EXPLICIT.
FAILURES ARE CONTROLLED.
EVALUATION IS MEASURABLE.
```

The **Synthetic Payment Laboratory** (`app.lab`) is the evaluation foundation for RecoveryOS. Downstream phases (Phases 6–20) implement webhook ingestion, payment journey reconstruction, revenue-loss detection, failure diagnosis, recoverability scoring, policy authorization, recovery action execution, and financial outcome verification.

Evaluating automated recovery systems requires datasets where the ground truth is unequivocally known. The Synthetic Payment Laboratory creates realistic, deterministically generated payment journeys with controlled failure modes, network anomalies, and explicit multi-attempt ground truth labels.

### Strict Phase Boundaries (Non-Goals)
- **NO live PSP communication**: No Razorpay SDK, webhook ingestion endpoints, or live signature verification (Phases 5 & 6).
- **NO AI/ML models or prompts**: No LLM diagnostics or machine-learning failure classifiers (Phases 7 & 8).
- **NO recovery workers or actions**: No retry dispatchers, customer notification workers, or ledger reconciliation (Phases 9–14).
- **NO public generator API**: No unauthenticated endpoints exposed on the FastAPI server.
- **NO domain model modifications**: The core financial domain (`apps/api/app/domain/`) remains 100% frozen.

---

## 2. Why Synthetic Data Exists

Real payment gateway logs pose severe constraints for developing and evaluating autonomous recovery systems:
1. **Lack of Objective Ground Truth**: Gateway logs record that a payment failed, but rarely reveal whether a payer had insufficient funds permanently or temporarily, whether an OTP timed out due to network congestion versus customer abandonment, or whether a retry would have succeeded.
2. **PII and PCI-DSS Constraints**: Real payment streams contain sensitive cardholder data, customer identifiers, phone numbers, and banking details that cannot be freely utilized in unit and integration test suites.
3. **Imbalanced Failure Distributions**: Severe edge cases (such as gateway 503 outages, out-of-order webhooks, or configuration errors) occur infrequently in production, preventing reliable test coverage.
4. **Reproducibility**: Evaluating improvements to diagnostic prompts or policy engines requires running identical input streams with bit-for-bit repeatability.

The Synthetic Payment Laboratory solves these challenges by generating synthetic payment journeys with mathematically verified determinism and exact oracle labels.

---

## 3. Observed Data vs. Ground Truth Separation

A foundational principle of RecoveryOS is that **observed payment data must never leak ground truth labels**. Downstream diagnostic engines must operate exclusively on data that would naturally be visible in production.

```
+-------------------------------------------------------------------------------+
|                       Synthetic Payment Laboratory                            |
+-------------------------------------------------------------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
+-----------------------------+               +-----------------------------+
|   Observed Lifecycle        |               |   Hidden Ground Truth       |
|   (Public / Ingested)       |               |   (Evaluation Oracle)       |
+-----------------------------+               +-----------------------------+
| • observed_events.jsonl     |               | • ground_truth.jsonl        |
| • journeys.jsonl            |               |   - scenario_id             |
|   - event_id, merchant_id   |               |   - failure_category        |
|   - order_id, payment_id    |               |   - root_cause              |
|   - amount, currency        |               |   - recoverability          |
|   - payment_method          |               |   - expected_recovery_strat |
|   - event_type, status      |               |   - attempt_truths[]        |
|   - payload                 |               |   - transport_anomalies[]   |
|   - last_observed_state     |               |                             |
+-----------------------------+               +-----------------------------+
         |                                                 |
         v                                                 v
  RecoveryOS Ingestion                           Evaluation Benchmark
  (Phases 6-12 Diagnostic Engine)                (Accuracy & Policy Scoring)
```

### Strict Forbidden Keys Scan & Allowed Schema Validation
The independent validator (`app.lab.validator`) enforces a dual-layer check on all observed files:
1. **Forbidden Keys Scan**: Any presence of `scenario_id`, `recoverability`, `root_cause`, `expected_strategy`, `ground_truth`, `is_revenue_at_risk`, or transport annotations causes immediate validation failure.
2. **Allowed Schema Validation**: Every field in `observed_events.jsonl` and `journeys.jsonl` must match the exact allowed model fields. Unknown fields are strictly rejected.

---

## 4. Recoverability Taxonomy & Evaluation Horizon

Recoverability represents whether a failed payment can be successfully recovered through automated intervention or payer re-engagement.

```python
class Recoverability(str, Enum):
    RECOVERABLE = "RECOVERABLE"
    CONDITIONALLY_RECOVERABLE = "CONDITIONALLY_RECOVERABLE"
    NON_RECOVERABLE = "NON_RECOVERABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
```

### Evaluation Horizon (`RECOVERABILITY_HORIZON_HOURS = 72`)
Recoverability is explicitly bounded by a 72-hour window:
- **`RECOVERABLE`**: The failure is transient (e.g., temporary issuer decline, gateway 503, processing error) and can be recovered within 72 hours via automated retry or smart re-routing.
- **`CONDITIONALLY_RECOVERABLE`**: Recovery is possible within 72 hours contingent on payer action (e.g., customer adds funds, completes authentication, or updates expired details).
- **`NON_RECOVERABLE`**: The failure cannot be recovered within 72 hours (e.g., permanent account closure, fraud/risk decline, customer abandonment beyond 72 hours, invalid instrument).
- **`NOT_APPLICABLE`**: The payment was successful on the initial attempt or resolved automatically at the processor without recovery intervention (e.g., S01 immediate success, S05 network timeout with underlying processor success, S17 late asynchronous webhook success).

### Recovery Strategy Ground Truth Classes
```python
class RecoveryStrategyClass(str, Enum):
    NO_RECOVERY_NEEDED = "NO_RECOVERY_NEEDED"
    RETRY_SAME_METHOD = "RETRY_SAME_METHOD"
    WAIT_AND_RETRY = "WAIT_AND_RETRY"
    SWITCH_PAYMENT_METHOD = "SWITCH_PAYMENT_METHOD"
    CUSTOMER_ACTION_REQUIRED = "CUSTOMER_ACTION_REQUIRED"
    DO_NOT_RETRY = "DO_NOT_RETRY"
```

---

## 5. Scenario Catalog (22 Scenarios)

The catalog defines 22 comprehensive payment journey archetypes with integer basis point (BPS) weights totaling exactly 10,000 bps (100.00%):

| ID | Name | Method Compatibility | Failure Category | Recoverability (72h) | Strategy Class | Eventual Outcome | Transport Anomaly |
|:---|:---|:---|:---|:---|:---|:---|:---:|
| `S01` | Immediate Success | All | `NONE` | `NOT_APPLICABLE` | `NO_RECOVERY_NEEDED` | `CAPTURED` | No |
| `S02` | Temporary Issuer Decline | CARD, NETBANKING | `ISSUER_DECLINE` | `RECOVERABLE` | `RETRY_SAME_METHOD` | `CAPTURED` | No |
| `S03` | Insufficient Funds (Recovered) | CARD, UPI, WALLET | `INSUFFICIENT_FUNDS` | `CONDITIONALLY_RECOVERABLE` | `WAIT_AND_RETRY` | `CAPTURED` | No |
| `S04` | Insufficient Funds (Permanent) | CARD, UPI, WALLET | `INSUFFICIENT_FUNDS` | `NON_RECOVERABLE` | `DO_NOT_RETRY` | `FAILED` | No |
| `S05` | Network Timeout (Underlying Success) | CARD, UPI, NETBANKING | `NETWORK_TIMEOUT` | `NOT_APPLICABLE` | `NO_RECOVERY_NEEDED` | `CAPTURED` | **Timeout / Success** |
| `S06` | Network Timeout (Retry Success) | CARD, UPI, NETBANKING | `NETWORK_TIMEOUT` | `RECOVERABLE` | `RETRY_SAME_METHOD` | `CAPTURED` | No |
| `S07` | Auth Failure (Payer Resolves) | CARD, NETBANKING | `AUTHENTICATION_FAILURE` | `CONDITIONALLY_RECOVERABLE` | `CUSTOMER_ACTION_REQUIRED` | `CAPTURED` | No |
| `S08` | Auth Abandonment (Permanent) | CARD, NETBANKING | `AUTHENTICATION_FAILURE` | `NON_RECOVERABLE` | `CUSTOMER_ACTION_REQUIRED` | `FAILED` | No |
| `S09` | Expired Card Instrument | CARD | `EXPIRED_INSTRUMENT` | `NON_RECOVERABLE` | `DO_NOT_RETRY` | `FAILED` | No |
| `S10` | Invalid Instrument Details | CARD, UPI | `INVALID_INSTRUMENT` | `NON_RECOVERABLE` | `CUSTOMER_ACTION_REQUIRED` | `FAILED` | No |
| `S11` | Gateway Outage / 503 | All | `GATEWAY_UNAVAILABLE` | `RECOVERABLE` | `WAIT_AND_RETRY` | `CAPTURED` | No |
| `S12` | Provider Processing Error | CARD, UPI, NETBANKING | `PROCESSING_ERROR` | `RECOVERABLE` | `RETRY_SAME_METHOD` | `CAPTURED` | No |
| `S13` | Duplicate Attempt on Paid Order | CARD, UPI, NETBANKING | `DUPLICATE_ATTEMPT` | `NOT_APPLICABLE` | `NO_RECOVERY_NEEDED` | `CAPTURED` | No |
| `S14` | Fraud / Risk Rule Decline | CARD, UPI | `FRAUD_OR_RISK_DECLINE` | `NON_RECOVERABLE` | `DO_NOT_RETRY` | `FAILED` | No |
| `S15` | Customer Abandonment at Checkout | CARD, UPI, WALLET | `CUSTOMER_ABANDONMENT` | `CONDITIONALLY_RECOVERABLE` | `CUSTOMER_ACTION_REQUIRED` | `CAPTURED` | No |
| `S16` | Multiple Transient Failures | CARD, NETBANKING | `ISSUER_DECLINE` | `RECOVERABLE` | `RETRY_SAME_METHOD` | `CAPTURED` | No |
| `S17` | Late Asynchronous Success | UPI, NETBANKING | `NONE` | `NOT_APPLICABLE` | `NO_RECOVERY_NEEDED` | `CAPTURED` | **Delayed Event** |
| `S18` | Out-of-Order Delivery | CARD, UPI | `NONE` | `NOT_APPLICABLE` | `NO_RECOVERY_NEEDED` | `CAPTURED` | **Out-of-Order** |
| `S19` | Duplicate Event Delivery | CARD, UPI | `ISSUER_DECLINE` | `RECOVERABLE` | `RETRY_SAME_METHOD` | `CAPTURED` | **Duplicate Event** |
| `S20` | Missing Intermediate Event | CARD, NETBANKING | `NONE` | `NOT_APPLICABLE` | `NO_RECOVERY_NEEDED` | `CAPTURED` | **Missing Event** |
| `S21` | UPI Collect Expired (Recovered) | UPI | `NETWORK_TIMEOUT` | `CONDITIONALLY_RECOVERABLE` | `CUSTOMER_ACTION_REQUIRED` | `CAPTURED` | No |
| `S22` | Provider Configuration Error | All | `PROVIDER_CONFIGURATION` | `NON_RECOVERABLE` | `DO_NOT_RETRY` | `FAILED` | No |

---

## 6. Payment Methods & Compatibility

The laboratory models 5 primary payment methods:
- `CARD`: Credit and debit cards. Compatible with 3D-Secure challenges, issuer declines, expired cards, and tokenized payments.
- `UPI`: Unified Payments Interface (intent and collect flows). High throughput, subject to collect timeouts (S21) and VPA validation errors.
- `NETBANKING`: Retail and corporate direct bank integrations. Susceptible to bank portal timeouts and gateway maintenance windows.
- `WALLET`: Prepaid digital wallet balances. Susceptible to insufficient balance and user authorization drop-offs.
- `EMI`: Equated Monthly Installments. Credit eligibility validation and provider plan constraints.

---

## 7. Merchant Archetypes & Financial Profiles

The laboratory defines 5 distinct merchant profiles with realistic ticket size distributions and payment method preferences:

| Merchant Profile | Typical Sector | Amount Range (INR) | Primary Methods | Default Method Weighting |
|:---|:---|:---|:---|:---|
| `ECOMMERCE` | Online Retail & Marketplaces | ₹200.00 – ₹15,000.00 | UPI, CARD | UPI (50%), CARD (35%), WALLET (10%), NB (5%) |
| `SAAS_RECURRING` | Cloud Software & Subscriptions | ₹500.00 – ₹50,000.00 | CARD, NETBANKING | CARD (75%), NETBANKING (20%), UPI (5%) |
| `FOOD_DELIVERY` | Quick-Commerce & Delivery | ₹100.00 – ₹2,500.00 | UPI, WALLET | UPI (70%), WALLET (20%), CARD (10%) |
| `UTILITIES` | Bill Pay & Telecom Services | ₹150.00 – ₹8,000.00 | UPI, NETBANKING | UPI (60%), NETBANKING (30%), CARD (10%) |
| `CROSS_BORDER` | International Digital Services | ₹1,000.00 – ₹100,000.00 | CARD | CARD (90%), NETBANKING (10%) |

All monetary amounts are represented using the frozen `Money` value object (`amount_minor` in paise, `currency = Currency.INR`).

---

## 8. Multi-Attempt Ground Truth Architecture

Certain scenarios involve multiple sequential payment attempts on a single order (e.g., `S16` multiple transient failures, or `S03` where attempt 1 fails for insufficient funds and attempt 2 succeeds).

To represent this without ambiguity, `GroundTruth` encapsulates both journey-level summary attributes and an explicit array of per-attempt ground truth records:

```json
{
  "journey_id": "syn_jrn_01955f2b8e3a7c64a3d4e689d0b81098",
  "scenario_id": "S16",
  "is_revenue_at_risk": true,
  "recoverability": "RECOVERABLE",
  "root_cause": "Transient network timeout on attempt 1, followed by temporary issuer decline on attempt 2.",
  "expected_recovery_strategy_class": "RETRY_SAME_METHOD",
  "expected_eventual_recovery": true,
  "expected_recovered_amount": 450000,
  "attempt_truths": [
    {
      "payment_id": "syn_pay_01955f2b8e3a7c64a3d4e689d0b81099",
      "attempt_number": 1,
      "expected_final_state": "FAILED",
      "failure_category": "NETWORK_TIMEOUT",
      "failure_code": "SYN_ERR_TIMEOUT",
      "root_cause": "Issuer connection timed out.",
      "is_retryable": true,
      "recoverability": "RECOVERABLE"
    },
    {
      "payment_id": "syn_pay_01955f2b8e3a7c64a3d4e689d0b8109a",
      "attempt_number": 2,
      "expected_final_state": "CAPTURED",
      "failure_category": "NONE",
      "failure_code": null,
      "root_cause": "Successful payment on retry.",
      "is_retryable": false,
      "recoverability": "NOT_APPLICABLE"
    }
  ]
}
```

---

## 9. Reproducibility & Determinism Guarantees

The Synthetic Payment Laboratory guarantees **bit-for-bit SHA-256 reproducibility** across any machine or operating system:
1. **Isolated PRNG**: Each generator run instantiates an isolated `random.Random(seed)` instance. Global `random` state is never touched or polluted.
2. **Deterministic ID Generation**: All UUIDs and synthetic reference strings are derived via `uuid.uuid5(UUID_NAMESPACE, f"{seed}:{counter}:{entity_type}")`.
3. **Fixed Anchor Timestamp**: All timestamps are computed deterministically starting from `2026-01-01T00:00:00Z` plus discrete microsecond offsets.
4. **Zero Wall-Clock Metadata**: Output files (`observed_events.jsonl`, `journeys.jsonl`, `ground_truth.jsonl`, `summary.json`) contain zero wall-clock execution timestamps or machine-dependent paths.
5. **Canonical JSON Serialization**: All records are serialized with sorted keys, no trailing whitespace, and fixed separators (`separators=(',', ':')`).

---

## 10. Dataset Structure & Manifest Checksums

Every generated dataset resides in a dedicated directory:
```
artifacts/synthetic/ds_syn_default_s42_n10000/
├── manifest.json            # SHA-256 hashes of the 4 data files + config
├── summary.json             # Aggregated distributions & counts
├── observed_events.jsonl    # Public payment event lifecycle stream
├── journeys.jsonl           # Public payment journey summaries
└── ground_truth.jsonl       # Hidden evaluation oracle labels
```

### Non-Circular Manifest Hashing
`manifest.json` contains the exact SHA-256 digests of the four output files:
```json
{
  "dataset_id": "ds_syn_default_s42_n10000",
  "lab_version": "1.0.0",
  "schema_version": "1.0.0",
  "files": {
    "observed_events.jsonl": {
      "sha256": "4b61b9...",
      "records": 46329,
      "bytes": 18241032
    },
    "journeys.jsonl": {
      "sha256": "8f1a23...",
      "records": 10000,
      "bytes": 2841021
    },
    "ground_truth.jsonl": {
      "sha256": "3e9b1c...",
      "records": 10000,
      "bytes": 13204910
    },
    "summary.json": {
      "sha256": "a4d70e...",
      "bytes": 4821
    }
  }
}
```

---

## 11. Independent Dataset Validator

The validator (`SyntheticDatasetValidator`) inspects a generated dataset without trusting the generator:
- **Checksum Verification**: Recomputes SHA-256 of all files and verifies against `manifest.json`.
- **Schema & Purity Checks**: Enforces allowed schemas on `observed_events.jsonl` and `journeys.jsonl`, rejecting unknown keys.
- **Leakage Detection**: Deep-scans every observed record for prohibited ground truth keywords.
- **Tenant Isolation**: Verifies that orders, payments, and events within a journey all belong to the identical `merchant_id`.
- **Financial Conservation**: Verifies that payment amounts never exceed authorized order amounts, amounts are non-negative, and currency remains consistent.
- **State Machine Integrity**: Validates that payment transitions match the frozen domain state machine (`CREATED` -> `AUTHORIZED` -> `CAPTURED` or `FAILED`).

---

## 12. Database Persistence Mode & Safety Guardrails

The laboratory includes an optional persistence mode to seed synthetic orders and payments into a local test database:

```bash
uv run python -m app.lab generate --persist --journeys 100
```

### Safety Rules:
1. **Production & Staging Lockout**: `app.lab.persistence` explicitly inspects `APP_ENV` and database connection strings. Execution is immediately aborted if `APP_ENV` is `production` or `staging`, or if the database host contains production indicators.
2. **Domain Aggregates Only**: Seeding persists pure domain `Merchant`, `Order`, and `Payment` records via the repository layer and `UnitOfWork`.
3. **No Event Contamination**: Synthetic observed events are **NEVER** written to the internal `domain_events` or `outbox_messages` tables.

---

## 13. Developer CLI Usage

The laboratory CLI is accessible via `python -m app.lab`:

### Generating a Dataset
```bash
# Generate 10,000 journeys with seed 42 (default output dir: artifacts/synthetic/)
uv run python -m app.lab generate --seed 42 --journeys 10000 --merchants 50

# Dry-run generation without writing to disk
uv run python -m app.lab generate --seed 42 --journeys 1000 --dry-run

# Custom output directory
uv run python -m app.lab generate --seed 1337 --journeys 5000 --output ./my_dataset
```

### Validating a Dataset
```bash
# Validate dataset against manifest, purity rules, and domain invariants
uv run python -m app.lab validate ./artifacts/synthetic/ds_syn_default_s42_n10000
```

---

## 14. Versioning Policy

- **`LAB_VERSION = "1.0.0"`**: Version of the generator engine, CLI, and algorithms.
- **`SCHEMA_VERSION = "1.0.0"`**: Version of the JSONL data formats and manifest schema.
- **`SCENARIO_CATALOG_VERSION = "1.0.0"`**: Version of the scenario catalog definitions (`S01`–`S22`) and default weights.

Any breaking schema changes or scenario catalog additions will result in a semver bump.

---

## 15. Known Limitations

1. **Synthetic Heuristics**: While realistic, synthetic failure codes and latency profiles are derived from probabilistic models rather than real-time bank infrastructure telemetry.
2. **Proprietary Bank Errors**: Bank-specific internal server error pages (e.g., custom HTML frames from issuer ACS pages) are simulated as structured error responses rather than raw HTML scraping artifacts.
3. **Offline Settlement Delays**: Real-world netbanking batches sometimes settle days later via NEFT/RTGS; simulated timelines use a maximum 72-hour window.

---

## 16. Disclaimer: No Claim of Real Razorpay Distributions

> **Notice**: The Synthetic Payment Laboratory generates synthetic data designed exclusively for algorithm development, policy testing, and automated evaluation within RecoveryOS.
> 
> The scenario weights, failure percentages, and merchant profile distributions represent reasonable engineering models for evaluation benchmarks. They **do not** claim to represent actual proprietary Razorpay production volume, conversion rates, internal failure statistics, or commercial gateway telemetry.
