# RecoveryOS

> **Payment Reliability & Revenue Recovery Control Plane**  
> Built for the **Razorpay AI Buildathon** under the **AI Revenue Recovery** track.

---

## Architectural Invariant

RecoveryOS enforces a strict, non-negotiable architectural invariant:

```
AI PROPOSES.
POLICY AUTHORIZES.
INFRASTRUCTURE EXECUTES.
LEDGER VERIFIES.
```

1. **AI Proposes**: Diagnostic models and heuristic engines inspect payment failure events and formulate structured recovery action plans (`RecoveryProposal`).
2. **Policy Authorizes**: Deterministic merchant-configured policy rules evaluate proposed plans and strictly allow (`PolicyDecision.ALLOW`), escalate for review (`REVIEW`), or deny execution (`DENY`).
3. **Infrastructure Executes**: High-reliability executors dispatch authorized recovery actions (`RecoveryAction`) with idempotency guarantees.
4. **Ledger Verifies**: Double-entry financial reconciliation records every event, verifying settled revenue (`RecoveryOutcome.VERIFIED`) before reporting recovered capital.

---

## Status & Current Phase

- **Completed Phases**:
  - **Phase 0 — Foundation, Architecture & Verified Development Environment** (COMPLETE)
  - **Phase 1 / 1R — Domain Model & Financial State Machines** (COMPLETE & FROZEN)
  - **Phase 2 / 2R / 2RR — Database, Persistence & Transactional Foundation** (COMPLETE & SEALED)
  - **Phase 3 — Authentication, RBAC & Multi-Tenant Authorization** (COMPLETE & VERIFIED)
- **Roadmap**: See [docs/PHASES.md](docs/PHASES.md) for the complete 21-phase plan.

---

## Technology Stack

- **Monorepo**: Lightweight workspace managed by `pnpm`
- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons, Vitest, React Testing Library
- **Backend API**: Python 3.12+, FastAPI, Pydantic v2, Pydantic Settings, SQLAlchemy 2.x (Async), Alembic, Pytest, Ruff, Mypy
- **Infrastructure**: Docker Compose, PostgreSQL 16 Alpine, Redis 7 Alpine
- **CI / Quality**: GitHub Actions, strict static analysis, and automated unit/integration test suites

---

## Repository Layout

```
RecoveryOS/
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI workflow
├── apps/
│   ├── api/                     # FastAPI Backend Application
│   │   ├── alembic/             # Database migrations
│   │   ├── app/
│   │   │   ├── api/             # Routes and endpoints (/health, /ready)
│   │   │   ├── core/            # Config, logging, middleware
│   │   │   ├── domain/          # Pure Domain Model & Financial State Machines
│   │   │   │   ├── entities/    # Order, Payment, RecoveryCase, Proposal, Policy, Action, Outcome
│   │   │   │   ├── events/      # Immutable Domain Events
│   │   │   │   ├── services/    # Pure domain services
│   │   │   │   └── values/      # Money (minor units), Currency, Confidence, Failure taxonomy
│   │   │   └── infrastructure/  # SQLAlchemy and Redis async clients
│   │   ├── tests/               # Pytest suite (318+ tests)
│   │   └── pyproject.toml       # Backend dependencies & tool configs
│   └── web/                     # Next.js Frontend Application
│       ├── src/
│       │   ├── app/             # Next.js App Router pages
│       │   ├── components/      # Operations console shell & live system status
│       │   ├── lib/             # Typed API client
│       │   └── test/            # Vitest suite
│       ├── package.json
│       └── tsconfig.json
├── docs/
│   ├── ARCHITECTURE.md          # Architecture specifications & diagrams
│   ├── DEVELOPMENT.md           # Local setup and workflow guide
│   ├── DOMAIN_MODEL.md          # Domain model specifications & invariants
│   ├── PHASES.md                # 21-phase roadmap
│   ├── PRODUCT.md               # Product requirements and non-goals
│   ├── SECURITY_PRINCIPLES.md   # Security policies & guardrails
│   └── STATE_MACHINES.md        # State machine transition charts & matrices
├── .env.example                 # Configuration template
├── .gitignore                   # Comprehensive gitignore
├── docker-compose.yml           # PostgreSQL 16 + Redis 7 services
├── Makefile                     # Root developer task runner
├── package.json                 # Monorepo root manifest
├── pnpm-workspace.yaml          # Monorepo workspace configuration
└── README.md
```

---

## Quickstart & Local Setup

### 1. Prerequisites
- **Node.js** 20+ / 22+ & **pnpm**
- **Python** 3.12+ & **uv**
- **Docker Desktop**

### 2. Environment Configuration
```bash
cp .env.example .env
```

### 3. Start Backing Infrastructure
```bash
make infra-up
```
Starts PostgreSQL 16 on port `5432` and Redis 7 on port `6379`.

### 4. Install Dependencies
```bash
# Backend
cd apps/api && uv venv && source .venv/bin/activate && uv pip install -e ".[dev]" && cd ../..

# Frontend
pnpm install
```

### 5. Run Database Migrations
```bash
make db-migrate
```

### 6. Start Development Servers
```bash
make dev
```
- **Web Console**: `http://localhost:3000`
- **FastAPI API**: `http://localhost:8000`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`

---

## Developer Commands

| Command | Action |
| :--- | :--- |
| `make dev` | Start backend (`8000`) and frontend (`3000`) concurrently |
| `make infra-up` | Start PostgreSQL and Redis Docker containers |
| `make infra-down` | Stop Docker containers |
| `make lint` | Run Ruff linter on API and ESLint on Web |
| `make format-check` | Check code formatting via Ruff |
| `make format` | Auto-format backend code via Ruff |
| `make typecheck` | Run static type checks (`mypy` + `tsc`) |
| `make test` | Run all unit & integration tests (`pytest` + `vitest`) |
| `make build` | Run Next.js production build |
| `make db-migrate` | Apply Alembic migrations |

---

## Security & Compliance Notice

- **No Cardholder Data**: RecoveryOS does not store or process PAN, CVV, or card credentials.
- **Untrusted External Data**: All webhooks, provider payloads, and AI outputs are treated as untrusted and validated against strict schemas.
- **Production-Oriented**: Designed toward production-grade financial security practices.

---

## Documentation Links

- [Product Specification](docs/PRODUCT.md)
- [Architecture & Diagrams](docs/ARCHITECTURE.md)
- [Domain Model Specification](docs/DOMAIN_MODEL.md)
- [State Machine Transitions](docs/STATE_MACHINES.md)
- [Security Principles](docs/SECURITY_PRINCIPLES.md)
- [Local Development Guide](docs/DEVELOPMENT.md)
- [Phase Roadmap (0–20)](docs/PHASES.md)
