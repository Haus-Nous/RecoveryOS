# RecoveryOS — Local Development Guide

## Prerequisites
- **macOS** (Apple Silicon arm64 recommended) or Linux
- **Node.js** 20+ / 22+ & **pnpm** (via `corepack enable` or `npm install -g pnpm`)
- **Python** 3.12+ & **uv** (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Docker Desktop** or Docker daemon with Docker Compose support

---

## Initial Setup

1. **Clone & Enter Repository**:
   ```bash
   git clone https://github.com/Haus-Nous/RecoveryOS.git
   cd RecoveryOS
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```

3. **Start Infrastructure**:
   ```bash
   make infra-up
   # Starts PostgreSQL 16 (port 5432) and Redis 7 (port 6379)
   ```

4. **Install Dependencies**:
   ```bash
   # Backend
   cd apps/api && uv venv && source .venv/bin/activate && uv pip install -e ".[dev]" && cd ../..

   # Frontend
   pnpm install
   ```

5. **Run Migrations**:
   ```bash
   make db-migrate
   ```

---

## Running Applications Locally

- **Run Both Frontend & Backend Concurrently**:
  ```bash
  make dev
  ```
- **Backend API**: `http://localhost:8000` (Docs: `http://localhost:8000/docs`)
- **Frontend Console**: `http://localhost:3000`

---

## Quality & Testing Commands

| Command | Action |
| :--- | :--- |
| `make lint` | Run Ruff on backend and ESLint on frontend |
| `make format-check` | Check backend formatting with Ruff |
| `make format` | Auto-format backend code with Ruff |
| `make typecheck` | Run static type checks (`mypy` on API, `tsc` on Web) |
| `make test` | Run complete backend and frontend test suites |
| `make build` | Run Next.js production build |
