.PHONY: help setup infra-up infra-down backend-dev worker beat frontend-dev migrate seed test lint skills-validate dev dev-backend dev-worker dev-beat dev-frontend validate-skills

help:
	@echo "Agentic Brand Marketing OS - Command Suite"
	@echo "-------------------------------------------"
	@echo "setup            Initialize uv workspace and install dependencies"
	@echo "infra-up         Start PostgreSQL, Redis, MinIO, Qdrant, Ollama, Langfuse, and OTel Collector"
	@echo "infra-down       Tear down backing infrastructure containers"
	@echo "backend-dev      Run FastAPI development server with reload"
	@echo "worker           Run Celery asynchronous task worker"
	@echo "beat             Run Celery Beat periodic scheduler"
	@echo "frontend-dev     Run Next.js management UI in development mode"
	@echo "migrate          Execute Alembic database migrations"
	@echo "seed             Seed initial demo brand, guidelines, and admin user"
	@echo "test             Execute test suites"
	@echo "lint             Run ruff and frontend code checks"
	@echo "skills-validate  Validate SKILL.md packages against progressive-disclosure rubric"

setup:
	export PATH="$$HOME/.local/bin:$$PATH" && uv sync
	cd frontend && npm install
	cd packages/contracts && npm install

infra-up:
	docker compose up -d postgres redis minio qdrant ollama langfuse otel-collector

infra-down:
	docker compose down

backend-dev:
	export PATH="$$HOME/.local/bin:$$PATH" && uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload

worker:
	export PATH="$$HOME/.local/bin:$$PATH" && uv run celery -A app.tasks.celery_app --workdir backend worker --loglevel=info -Q orchestrator_queue,publishing_queue,media_queue,analytics_queue

beat:
	export PATH="$$HOME/.local/bin:$$PATH" && uv run celery -A app.tasks.celery_app --workdir backend beat --loglevel=info

frontend-dev:
	cd frontend && npm run dev

migrate:
	cd backend && export PATH="$$HOME/.local/bin:$$PATH" && uv run alembic upgrade head

seed:
	cd backend && export PATH="$$HOME/.local/bin:$$PATH" && uv run python scripts/seed_db.py

skills-validate:
	export PATH="$$HOME/.local/bin:$$PATH" && uv run python backend/scripts/validate_skills.py

test:
	export PATH="$$HOME/.local/bin:$$PATH" && uv run pytest backend/tests/
	cd frontend && npm run test

lint:
	export PATH="$$HOME/.local/bin:$$PATH" && uv run ruff check backend
	cd frontend && npm run lint

# Convenience aliases matching legacy naming
dev-backend: backend-dev
dev-worker: worker
dev-beat: beat
dev-frontend: frontend-dev
validate-skills: skills-validate
