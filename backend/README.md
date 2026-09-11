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
