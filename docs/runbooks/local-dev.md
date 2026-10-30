# Runbook: Local Development

## 1. Initial Setup
```bash
cp .env.example .env
make setup
```

## 2. Start Backing Infrastructure
```bash
make infra-up
```
Verify the following services are running:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- MinIO on `localhost:9000` (Console on `localhost:9001`)
- Qdrant on `localhost:6333`
- Langfuse on `localhost:3001`

## 3. Pull Ollama Models
Ensure Ollama is running and pull the core models:
```bash
ollama pull llama3.3:70b
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

## 4. Run Migrations & Seed Data
```bash
make migrate
make seed
```

## 5. Start Development Servers
In separate terminal panes or via process manager:
```bash
make dev-backend   # FastAPI on localhost:8000
make dev-worker    # Celery async worker
make dev-beat      # Celery Beat scheduler
make dev-frontend  # Next.js on localhost:3000
```
