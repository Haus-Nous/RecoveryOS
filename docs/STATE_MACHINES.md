# RecoveryOS State Machines

All domain aggregates enforce deterministic state transition matrices. Attempting an unregistered transition raises `InvalidStateTransitionError`, and attempting mutation from a terminal state raises `TerminalStateError`.

---

## 1. Order State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> OPEN : mark_open()
    CREATED --> CANCELLED : cancel()
    OPEN --> PAID : mark_paid() [Terminal]
    OPEN --> CANCELLED : cancel() [Terminal]
```

### Order Transition Matrix (4 states, 16 pairs)
| From State | Allowed Target States | Terminal? |
| :--- | :--- | :---: |
| `CREATED` | `OPEN`, `CANCELLED` | No |
| `OPEN` | `PAID`, `CANCELLED` | No |
| `PAID` | *(None)* | **Yes** |
| `CANCELLED` | *(None)* | **Yes** |

---

## 2. Payment State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> PENDING : mark_pending()
    CREATED --> AUTHORIZED : mark_authorized()
    CREATED --> CAPTURED : capture()
    CREATED --> FAILED : fail(failure) [Terminal]
    CREATED --> CANCELLED : cancel() [Terminal]

    PENDING --> AUTHORIZED : mark_authorized()
    PENDING --> CAPTURED : capture()
    PENDING --> FAILED : fail(failure) [Terminal]
    PENDING --> CANCELLED : cancel() [Terminal]

    AUTHORIZED --> CAPTURED : capture()
    AUTHORIZED --> FAILED : fail(failure) [Terminal]
    AUTHORIZED --> CANCELLED : cancel() [Terminal]

    CAPTURED --> PARTIALLY_REFUNDED : refund(is_partial=True)
    CAPTURED --> REFUNDED : refund(is_partial=False) [Terminal]

    PARTIALLY_REFUNDED --> PARTIALLY_REFUNDED : refund(is_partial=True)
    PARTIALLY_REFUNDED --> REFUNDED : refund(is_partial=False) [Terminal]
```

### Payment Transition Matrix (8 states, 64 pairs)
- Terminal states: `FAILED`, `CANCELLED`, `REFUNDED`.
- Invariants: `CAPTURED` clears active failure context; transition to `FAILED` attaches `PaymentFailure`.

---

## 3. RecoveryCase State Machine & Verification Lifecycle

```mermaid
stateDiagram-v2
    [*] --> OPEN
    OPEN --> DIAGNOSING : start diagnosis
    OPEN --> CANCELLED : cancel() [Terminal]

    DIAGNOSING --> PLANNED : proposal generated
    DIAGNOSING --> EXHAUSTED : unrecoverable [Terminal]
    DIAGNOSING --> CANCELLED : cancel() [Terminal]

    PLANNED --> AWAITING_REVIEW : policy escalation
    PLANNED --> APPROVED : policy authorized
    PLANNED --> EXHAUSTED : retry budget exhausted [Terminal]
    PLANNED --> CANCELLED : cancel() [Terminal]

    AWAITING_REVIEW --> APPROVED : operator approves
    AWAITING_REVIEW --> EXHAUSTED : operator rejects [Terminal]
    AWAITING_REVIEW --> CANCELLED : operator cancels [Terminal]

    APPROVED --> EXECUTING : execute action
    APPROVED --> CANCELLED : cancel() [Terminal]

    EXECUTING --> RECOVERY_OBSERVED : payment recaptured
    EXECUTING --> DIAGNOSING : retry failed / re-diagnose
    EXECUTING --> PLANNED : re-plan strategy
    EXECUTING --> EXHAUSTED : attempts exhausted [Terminal]
    EXECUTING --> ESCALATED : technical escalation

    RECOVERY_OBSERVED --> AWAITING_VERIFICATION : queue settlement check
    RECOVERY_OBSERVED --> VERIFIED_RECOVERED : immediate ledger proof [Terminal]
    RECOVERY_OBSERVED --> VERIFICATION_FAILED : settlement discrepancy
    RECOVERY_OBSERVED --> CANCELLED : cancelled [Terminal]

    AWAITING_VERIFICATION --> VERIFIED_RECOVERED : settlement verified [Terminal]
    AWAITING_VERIFICATION --> VERIFICATION_FAILED : settlement rejected / chargeback
    AWAITING_VERIFICATION --> CANCELLED : cancelled [Terminal]

    VERIFICATION_FAILED --> ESCALATED : escalate for investigation
    VERIFICATION_FAILED --> DIAGNOSING : re-diagnose alternative recovery
    VERIFICATION_FAILED --> PLANNED : re-plan alternative action
    VERIFICATION_FAILED --> EXHAUSTED : write off [Terminal]
    VERIFICATION_FAILED --> CANCELLED : cancel [Terminal]

    ESCALATED --> PLANNED : manual plan approved
    ESCALATED --> DIAGNOSING : manual diagnosis
    ESCALATED --> EXHAUSTED : operator closed unrecovered [Terminal]
    ESCALATED --> CANCELLED : cancelled [Terminal]
```

### RecoveryCase Transition Matrix (13 states, 169 pairs)
- Terminal states: `VERIFIED_RECOVERED`, `EXHAUSTED`, `CANCELLED`.
- Verification failure handling: `VERIFICATION_FAILED` allows re-diagnosing, planning alternative strategies, escalating to operators, or marking exhausted.

---

## 4. RecoveryAction State Machine & Authorization Guardrail

```mermaid
stateDiagram-v2
    [*] --> PROPOSED
    PROPOSED --> AWAITING_AUTHORIZATION : requires review
    PROPOSED --> AUTHORIZED : policy ALLOW
    PROPOSED --> DENIED : policy DENY [Terminal]
    PROPOSED --> CANCELLED : cancel() [Terminal]

    AWAITING_AUTHORIZATION --> AUTHORIZED : human approves
    AWAITING_AUTHORIZATION --> DENIED : human rejects [Terminal]
    AWAITING_AUTHORIZATION --> CANCELLED : cancel() [Terminal]

    AUTHORIZED --> QUEUED : enqueue worker
    AUTHORIZED --> EXECUTING : execute directly
    AUTHORIZED --> CANCELLED : cancel() [Terminal]

    QUEUED --> EXECUTING : worker pick up
    QUEUED --> CANCELLED : cancel() [Terminal]

    EXECUTING --> SUCCEEDED : action success [Terminal]
    EXECUTING --> FAILED : execution error [Terminal]
    EXECUTING --> CANCELLED : cancelled [Terminal]
```

### RecoveryAction Transition Matrix (9 states, 81 pairs)
- Terminal states: `DENIED`, `SUCCEEDED`, `FAILED`, `CANCELLED`.
- **Authorization Guardrail Invariant**: An action **cannot** be initialized in or transition to `QUEUED` or `EXECUTING` without explicit authorization (`authorization_decision == PolicyDecision.ALLOW`). Attempting to bypass authorization raises `UnauthorizedActionTransitionError`.
