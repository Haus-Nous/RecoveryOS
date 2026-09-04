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

### Order Transition Matrix
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

---

## 3. RecoveryCase State Machine

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

    EXECUTING --> RECOVERED : funds recaptured [Terminal]
    EXECUTING --> DIAGNOSING : retry attempt failed
    EXECUTING --> PLANNED : re-plan strategy
    EXECUTING --> EXHAUSTED : attempts exhausted [Terminal]
    EXECUTING --> ESCALATED : technical escalation

    ESCALATED --> PLANNED : manual remediation
    ESCALATED --> EXHAUSTED : closed unrecovered [Terminal]
    ESCALATED --> CANCELLED : cancelled [Terminal]
```

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

### Authorization Invariant
An action **cannot** transition to `QUEUED` or `EXECUTING` without explicit authorization (`authorization_decision == PolicyDecision.ALLOW`). Attempting to bypass authorization raises `UnauthorizedActionTransitionError`.
