.PHONY: help dev dev-web dev-api infra-up infra-down infra-restart infra-logs lint format-check format typecheck test test-backend test-frontend build clean db-migrate

ROOT_DIR := $(shell pwd)
API_DIR := $(ROOT_DIR)/apps/api
WEB_DIR := $(ROOT_DIR)/apps/web

PYTHON := $(API_DIR)/.venv/bin/python
UVICORN := $(API_DIR)/.venv/bin/uvicorn
RUFF := $(API_DIR)/.venv/bin/ruff
MYPY := $(API_DIR)/.venv/bin/mypy
PYTEST := $(API_DIR)/.venv/bin/pytest
ALEMBIC := $(API_DIR)/.venv/bin/alembic

help:
	@echo "RecoveryOS — Root Developer Commands"
	@echo "=================================================="
	@echo "make infra-up       - Start PostgreSQL and Redis via Docker Compose"
	@echo "make infra-down     - Stop Docker Compose services"
	@echo "make infra-restart  - Restart Docker Compose services"
	@echo "make infra-logs     - Tail Docker Compose logs"
	@echo "make dev            - Run both backend and frontend concurrently"
	@echo "make dev-api        - Run FastAPI backend development server"
	@echo "make dev-web        - Run Next.js frontend development server"
	@echo "make lint           - Run linter across backend (ruff) and frontend (eslint)"
	@echo "make format-check   - Check code formatting (ruff format)"
	@echo "make format         - Auto-format backend code (ruff format)"
	@echo "make typecheck      - Run static type checking (mypy + tsc)"
	@echo "make test           - Run full test suite (pytest + vitest)"
	@echo "make test-backend   - Run backend tests (pytest)"
	@echo "make test-frontend  - Run frontend tests (vitest)"
	@echo "make build          - Build production assets (Next.js build)"
	@echo "make db-migrate     - Run Alembic database migrations to head"
	@echo "make clean          - Remove temporary caches and build artifacts"

infra-up:
	docker compose up -d

infra-down:
	docker compose down

infra-restart:
	docker compose restart

infra-logs:
	docker compose logs -f

dev-api:
	cd $(API_DIR) && $(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

dev-web:
	pnpm --filter @recoveryos/web dev

dev:
	@echo "Starting RecoveryOS development environment..."
	@make -j 2 dev-api dev-web

lint:
	cd $(API_DIR) && $(RUFF) check .
	pnpm --filter @recoveryos/web lint

format-check:
	cd $(API_DIR) && $(RUFF) format --check .

format:
	cd $(API_DIR) && $(RUFF) format .

typecheck:
	cd $(API_DIR) && $(MYPY) .
	pnpm --filter @recoveryos/web typecheck

test-backend:
	cd $(API_DIR) && $(PYTEST) -v

test-frontend:
	pnpm --filter @recoveryos/web test

test:
	@echo "--- Running Backend Tests (pytest) ---"
	@make test-backend
	@echo "--- Running Frontend Tests (vitest) ---"
	@make test-frontend

build:
	pnpm --filter @recoveryos/web build

db-migrate:
	cd $(API_DIR) && $(ALEMBIC) upgrade head

clean:
	rm -rf $(WEB_DIR)/.next $(WEB_DIR)/out $(API_DIR)/.pytest_cache $(API_DIR)/.mypy_cache $(API_DIR)/.ruff_cache
