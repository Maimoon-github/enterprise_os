.PHONY: help setup dev infra-up infra-down migrate seed test lint build

help:
	@echo "Agentic Brand Marketing OS - Command Suite"
	@echo "-------------------------------------------"
	@echo "setup         Initialize Python virtual environments and install frontend packages"
	@echo "infra-up      Start PostgreSQL, Redis, MinIO, Qdrant, Langfuse, and Ollama"
	@echo "infra-down    Tear down backing infrastructure containers"
	@echo "migrate       Execute Alembic database migrations"
	@echo "seed          Seed initial demo brand, guidelines, and admin user"
	@echo "dev-backend   Run FastAPI development server with reload"
	@echo "dev-worker    Run Celery asynchronous task worker"
	@echo "dev-beat      Run Celery Beat periodic scheduler"
	@echo "dev-frontend  Run Next.js management UI in development mode"
	@echo "dev           Run all services locally using Overmind/tmux or concurrently"
	@echo "validate-skills Run skills-ref validation suite against backend/skills/"
	@echo "test          Execute backend and frontend test suites"
	@echo "lint          Run ruff and eslint code formatting checks"

setup:
	cd backend && uv venv && uv sync
	cd frontend && npm install
	cd packages/contracts && npm install

infra-up:
	docker compose up -d postgres redis minio qdrant langfuse otel-collector

infra-down:
	docker compose down

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python scripts/seed_db.py

validate-skills:
	cd backend && uv run python scripts/validate_skills.py

dev-backend:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-worker:
	cd backend && uv run celery -A app.tasks.celery_app worker --loglevel=info -Q orchestrator_queue,publishing_queue,media_queue,analytics_queue

dev-beat:
	cd backend && uv run celery -A app.tasks.celery_app beat --loglevel=info

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest tests/
	cd frontend && npm run test

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint
