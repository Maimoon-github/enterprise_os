#!/usr/bin/env bash
# create-business-os.sh — scaffold the business-os repository structure
set -euo pipefail

ROOT="${1:-business-os}"

mkdir -p "$ROOT"
cd "$ROOT"

# ------------------------------------------------------------------
# 1. Top-level directories
# ------------------------------------------------------------------
mkdir -p chief-of-staff dashboard infrastructure

# ------------------------------------------------------------------
# 2. Agent directories (one isolated environment per agent)
# ------------------------------------------------------------------
AGENTS=(marketing sales support receptionist inbox finance research reputation)
mkdir -p agents
for a in "${AGENTS[@]}"; do
  mkdir -p "agents/$a"
done

# ------------------------------------------------------------------
# 3. Shared services
# ------------------------------------------------------------------
mkdir -p shared/knowledge shared/events shared/integrations

# ------------------------------------------------------------------
# 4. Placeholder files so empty dirs are tracked by git
# ------------------------------------------------------------------
for a in "${AGENTS[@]}"; do
  touch "agents/$a/.gitkeep"
  cat > "agents/$a/README.md" <<EOF
# $a agent

Independent environment for the **$a** business agent.
Exposes capabilities only via API / MCP / webhook / adapter.
Orchestrated exclusively by \`chief-of-staff/\`.
EOF
done

touch chief-of-staff/.gitkeep dashboard/.gitkeep infrastructure/.gitkeep
touch shared/knowledge/.gitkeep shared/events/.gitkeep shared/integrations/.gitkeep

# ------------------------------------------------------------------
# 5. Root files
# ------------------------------------------------------------------
cat > docker-compose.yml <<'EOF'
# business-os — infrastructure entrypoint
# Services: chief-of-staff, agents/*, shared/{knowledge,events,integrations}, dashboard
version: "3.9"
services: {}
EOF

cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
.venv/
.env

# Node / Next.js
node_modules/
.next/
out/

# OS / editor
.DS_Store
.idea/
.vscode/

# Data / secrets
*.sqlite3
*.db
secrets/
EOF

cat > README.md <<'EOF'
# business-os

Self-hosted Brand Operations OS.

| Path | Responsibility |
|------|----------------|
| `chief-of-staff/` | Python + LangGraph + FastAPI orchestrator (command, delegate, monitor, report) |
| `agents/` | Eight isolated business agents, each with its own environment and internal orchestrator |
| `shared/` | Central knowledge (PostgreSQL + Qdrant), event bus (Redis), integrations (API / MCP / adapters) |
| `dashboard/` | Next.js + TypeScript control surface |
| `infrastructure/` | Docker Compose stack |
EOF

# ------------------------------------------------------------------
# 6. Optional git init
# ------------------------------------------------------------------
if [[ "${INIT_GIT:-0}" == "1" ]]; then
  git init -q
fi

# ------------------------------------------------------------------
# 7. Summary
# ------------------------------------------------------------------
echo "Created: $(pwd)"
echo
find . -maxdepth 2 -type d | sort