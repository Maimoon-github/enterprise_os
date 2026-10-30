# Runbook: Local Development & E2E Verification

## 1. Initial Setup
```bash
cp .env.example .env
make setup
```

## 2. Start Backing Infrastructure
```bash
make infra-up
```
Verify the following services are healthy and running:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- MinIO on `localhost:9000` (Console on `localhost:9001`)
- Qdrant on `localhost:6333`
- Langfuse on `localhost:3001`
- OpenTelemetry Collector on `localhost:4317` (gRPC) / `localhost:4318` (HTTP)

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
The seed script (`backend/scripts/seed_db.py`) is strictly idempotent and establishes:
- **Default Admin User:** `admin@marketing-os.local` / `admin123` (role: `admin`)
- **Demo Brand:** `Apex Horizon` (slug: `apex-horizon`)
- **Pre-Indexed Guidelines:** Deterministic Brand RAG knowledge documents with pillars, prohibited buzzwords, and platform copy constraints.

## 5. Start Development Servers
In separate terminal panes or via process manager:
```bash
make dev-backend   # FastAPI BFF on localhost:8000
make dev-worker    # Celery async worker (queues: orchestrator, publishing, media, analytics)
make dev-beat      # Celery Beat periodic scheduler
make dev-frontend  # Next.js management UI on localhost:3000
```

## 6. Pre-Indexed Brand Guidelines & RAG Verification
Verify Brand RAG resources and knowledge retrieval:
```bash
# Verify FastMCP Brand RAG resource exposure
python -c "from mcp_servers.brand_rag_server.resources import get_brand_voice_guidelines; print(get_brand_voice_guidelines('apex-horizon'))"

# Verify hybrid retrieval over seeded documents
python -c "from mcp_servers.brand_rag_server.tools import search_brand_knowledge; print(search_brand_knowledge('deterministic governance', limit=2))"
```

## 7. Offline Golden-Suite Regression Suite
Execute the 4-layer evaluation regression suite without external LLM token consumption:
```bash
# Run programmatic CLI regression
cd backend && python -m app.observability.evals.golden_suite

# Run pytest evaluation suites
pytest backend/tests/evals/test_trajectory.py
```
**Expected Pass Criteria:**
- 100% scenario pass rate across Golden Test Scenarios.
- Zero external LLM token expenditure (uses deterministic heuristic/rubric checkers and mock client fallback).
- Strictly ascending milestone order: `BrandRAG ≺ DraftCopy ≺ ApprovalGate ≺ Publish`.

## 8. End-to-End (E2E) Verification Flow
1. **Login:** Navigate to `http://localhost:3000/login` and authenticate with `admin@marketing-os.local` / `admin123`.
2. **Synthesize Campaign:** Go to `/campaigns/new`, select brand `Apex Horizon`, target platforms (LinkedIn, X, Threads, YouTube), enter strategic directives, and click "Synthesize Campaign Blueprint".
3. **Inspect Live DAG:** Navigate to `/runs/{runId}` to monitor live SSE events (`node_start`, `node_transition`, `tool_call`, `interrupt`).
4. **Human Approval Gate:** Confirm execution halts at super-step `human_approval_gate_node`.
5. **Resume & Fan-out:** Open `/approvals`, review blueprint diff, and click "Approve & Publish" (or "Request Revision").
6. **Closed-Loop Loop:** Observe post-approval fan-out and Polars z-score analytics evaluation at `/analytics`.

## 9. Failure Triage & Diagnostic Pointers
- **Duplicate Key Error on Seeding:** Ensure `seed_db.py` uses `select()` checks before inserts. The script is designed to update existing records rather than inserting blindly.
- **Trajectory Ordering Inversion (`violations` array not empty):** Check that nodes follow canonical DAG order. Specifically, verify that `prepare_publish_payload_node` is not aliased as an outbound publish milestone before `human_approval_gate_node`.
- **Buzzword Penalty in Rubric Judge:** Confirm generated copy does not contain prohibited vocabulary (`game-changer`, `synergy`, `paradigm shift`, `disruptive`, `revolutionary`, `deep dive`).
- **PostgresSaver Interrupt Recovery:** If graph resumes fail, inspect PostgreSQL `checkpoints` table for valid thread snapshot.
