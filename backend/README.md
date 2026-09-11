# Governed Multi-Agent Marketing Intelligence Backend

Model-A governance architecture:

    directive -> policy envelope -> DAG scheduling -> bounded workers
    -> evidence synthesis -> HITL preview -> signed dispatch -> telemetry
    -> validated learning promotion

## Layout

| Path                  | Purpose                                                   |
|-----------------------|-----------------------------------------------------------|
| `app/api`             | Transport/API boundary only                               |
| `app/core`            | Runtime settings and logging                              |
| `app/schemas`         | Cross-layer Pydantic contracts                            |
| `app/orchestration`   | Transport-independent Intelligence Engine logic           |
| `app/agents`          | Seven bounded workers (W_DEV..W_LEARN)                    |
| `app/services`        | Application services (policy, HITL, RAG, telemetry)       |
| `app/security`        | Authorization, scope, and signature enforcement           |
| `app/mcp`             | MCP host, data gateway, outbound gateway                  |
| `app/integrations`    | LLM, sandbox, CMS, ads, social adapters                   |
| `app/persistence`     | PostgreSQL/pgvector/TimescaleDB repositories              |
| `scripts`             | Developer Bash entrypoints (dev/test/lint)                |
| `tests`               | Unit, integration, acceptance suites                      |
| `var`                 | Runtime data (gitignored)                                 |

## Quick start

    cp .env.example .env
    make install
    make test
    make dev

## Environment

Configuration is read from environment variables prefixed with `BACKEND_`
(see `app/core/settings.py`). Secrets must never be committed; use `.env`
locally and a secret manager in deployment.


# Governed Backend

A governed multi-agent marketing orchestration backend: a central
Intelligence Engine coordinates seven bounded worker agents, brokers all
retrieval through governed Agentic RAG, requires mandatory human review
before any spend/claim/code/dispatch action, and records every control-plane
step in a tamper-evident audit chain.

See `docs/ASSUMPTIONS.md` for every place the source architecture left a
technology choice unspecified and the concrete decision made here.

## Layout

```text
backend/
├── pyproject.toml          — Python project metadata and dependencies
├── .env.example             — every supported environment variable
├── app/                     — the application package (see below)
├── tests/                   — unit, integration, and acceptance suites
├── docs/                    — architecture notes and assumptions
└── scripts/                 — bash entrypoints and utilities for local dev
```

`app/` mirrors the layered architecture directly: `api/` is the transport
boundary, `orchestration/` is the transport-independent Intelligence Engine,
`agents/` are the seven bounded workers, `services/` are supporting
application services (including governed RAG), `security/` and `mcp/` are
the authorization and actuation boundaries, `integrations/` are the vendor
adapters, and `persistence/` is the system-of-record boundary.

## Quickstart

```bash
./scripts/bootstrap.sh        # create a venv and install dependencies
cp .env.example .env          # fill in real values as needed
./scripts/run_tests.sh        # run the full test suite
./scripts/lint.sh             # run ruff, mypy, and shellcheck
./scripts/run_dev_server.sh   # start the API with uvicorn --reload
```

All four scripts are self-contained, idempotent, and safe to re-run. Run
them from the repository root, or from anywhere — each resolves its own
paths relative to its own location, not the caller's working directory.

## Running tests directly

```bash
pip install -e ".[dev]"
pytest
```

The suite requires no external services: every test exercises the real
domain logic (policy evaluation, task-state transitions, HITL gating,
provenance hash-chaining, RAG governance, the full end-to-end flow) against
in-memory fakes for the sandbox, vector store, and persistence layer.

## API surface

- `POST /directives` — accept an owner-issued objective/scope/budget/risk directive
- `GET /directives/{directive_id}` — retrieve a directive
- `GET /tasks/{task_id}` — retrieve canonical task state
- `GET /tasks/directive/{directive_id}` — list tasks for a directive
- `POST /approvals/{preview_id}/decide` — record a human approval/rejection
- `POST /telemetry` — ingest a normalized telemetry event
- `GET /healthz` — liveness check