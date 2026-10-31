#!/usr/bin/env bash
# ==============================================================================
# Agentic Brand Marketing OS — Unified Launch & Lifecycle Orchestrator
# Starts backing infrastructure (PostgreSQL, Redis, MinIO, Qdrant, Ollama,
# Langfuse, OTel), runs migrations, awakens local Qwen models, seeds demo
# brand guidelines, and launches Backend API, Celery Workers, and Next.js UI.
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Ensure directories for logs and PIDs exist
mkdir -p "$REPO_ROOT/logs" "$REPO_ROOT/.pids"

# Color formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
MAGENTA="\033[0;35m"
RESET="\033[0m"

log_info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
log_step()    { echo -e "\n${BOLD}${BLUE}==>${RESET} ${BOLD}$*${RESET}"; }
log_success() { echo -e "${GREEN}[SUCCESS]${RESET} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*"; }

# ------------------------------------------------------------------------------
# 1. Environment & Tool Discovery
# ------------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"

detect_docker_compose() {
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
    else
        log_error "Neither 'docker compose' nor 'docker-compose' found. Please install Docker."
        exit 1
    fi
}
DOCKER_COMPOSE=$(detect_docker_compose)

detect_python_runner() {
    if command -v uv >/dev/null 2>&1; then
        echo "uv run"
    elif command -v conda >/dev/null 2>&1 && conda info --envs 2>/dev/null | grep -q "brand-marketing-platform"; then
        echo "conda run -n brand-marketing-platform"
    elif [ -f "$REPO_ROOT/.venv/bin/python" ]; then
        echo "$REPO_ROOT/.venv/bin/python"
    else
        echo "python3"
    fi
}
PY_RUN=$(detect_python_runner)

check_port() {
    local host="$1"
    local port="$2"
    python3 -c "
import socket, sys
try:
    with socket.create_connection(('$host', $port), timeout=1.5):
        sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

wait_for_port() {
    local name="$1"
    local host="$2"
    local port="$3"
    local max_wait="${4:-45}"
    local count=0

    printf "  ⏳ Waiting for %-22s (%s:%s)... " "$name" "$host" "$port"
    while ! check_port "$host" "$port"; do
        sleep 1
        count=$((count + 1))
        if [ "$count" -ge "$max_wait" ]; then
            echo -e "${RED}TIMEOUT${RESET}"
            log_error "$name failed to become ready on $host:$port within ${max_wait}s."
            return 1
        fi
    done
    echo -e "${GREEN}ONLINE${RESET}"
    return 0
}

kill_pid_file() {
    local pid_file="$1"
    local name="$2"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping $name (PID $pid)..."
            kill "$pid" 2>/dev/null || true
            for _ in {1..10}; do
                if ! kill -0 "$pid" 2>/dev/null; then break; fi
                sleep 0.5
            done
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

kill_port_owner() {
    local port="$1"
    local name="$2"
    local pids
    pids=$(ss -tulpn "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u || true)
    if [ -z "$pids" ]; then
        pids=$(lsof -ti :"$port" 2>/dev/null || true)
    fi
    if [ -n "$pids" ]; then
        log_warn "Terminating process on port $port ($name): $pids"
        for p in $pids; do
            kill -9 "$p" 2>/dev/null || true
        done
        sleep 0.5
    fi
}

# ------------------------------------------------------------------------------
# 2. Lifecycle Commands
# ------------------------------------------------------------------------------
stop_services() {
    local stop_infra="${1:-false}"
    log_step "Stopping Agentic Marketing OS Services..."

    kill_pid_file "$REPO_ROOT/.pids/frontend.pid" "Frontend (Next.js)"
    kill_pid_file "$REPO_ROOT/.pids/backend.pid"  "Backend API (FastAPI)"
    kill_pid_file "$REPO_ROOT/.pids/worker.pid"   "Celery Async Worker"
    kill_pid_file "$REPO_ROOT/.pids/beat.pid"     "Celery Beat Scheduler"

    # Terminate any dangling worker, backend, or frontend processes
    pkill -f "next-server" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    pkill -f "celery -A app.tasks.celery_app" 2>/dev/null || true

    # Ensure ports are freed
    kill_port_owner 8000 "FastAPI"
    kill_port_owner 3000 "Next.js"

    log_success "All application services stopped cleanly."

    if [ "$stop_infra" = "true" ]; then
        log_step "Tearing down Docker backing infrastructure..."
        $DOCKER_COMPOSE down
        log_success "Backing infrastructure stopped."
    else
        log_info "Backing containers kept online (use './start.sh --stop-all' to stop Docker containers)."
    fi
}

print_status() {
    echo -e "\n=================================================================="
    echo -e "${BOLD}${CYAN}   🚀 AGENTIC BRAND MARKETING OS — LIVE STATUS DASHBOARD${RESET}"
    echo -e "=================================================================="

    echo -e "\n${BOLD}[1] Backing Infrastructure (Docker Containers):${RESET}"
    local svcs=("postgres:5432" "redis:6379" "minio:9000" "qdrant:6333" "ollama:11434" "langfuse:3001" "otel-collector:4318")
    for item in "${svcs[@]}"; do
        local name="${item%%:*}"
        local port="${item##*:}"
        if check_port "127.0.0.1" "$port"; then
            printf "  • %-16s (Port %-5s): ${GREEN}🟢 HEALTHY / ONLINE${RESET}\n" "$name" "$port"
        else
            printf "  • %-16s (Port %-5s): ${RED}🔴 OFFLINE${RESET}\n" "$name" "$port"
        fi
    done

    echo -e "\n${BOLD}[2] Application Services:${RESET}"
    if check_port "127.0.0.1" 8000; then
        local b_pid
        b_pid=$(lsof -ti :8000 2>/dev/null | head -n1 || cat "$REPO_ROOT/.pids/backend.pid" 2>/dev/null || echo "active")
        printf "  • %-16s (PID %-7s): ${GREEN}🟢 RUNNING (http://localhost:8000)${RESET}\n" "FastAPI Backend" "$b_pid"
    else
        printf "  • %-16s : ${RED}🔴 STOPPED${RESET}\n" "FastAPI Backend"
    fi

    if pgrep -f "celery.*orchestrator_queue" >/dev/null 2>&1 || ([ -f "$REPO_ROOT/.pids/worker.pid" ] && kill -0 "$(cat "$REPO_ROOT/.pids/worker.pid")" 2>/dev/null); then
        local w_pid
        w_pid=$(pgrep -f "celery.*orchestrator_queue" 2>/dev/null | head -n1 || cat "$REPO_ROOT/.pids/worker.pid" 2>/dev/null)
        printf "  • %-16s (PID %-7s): ${GREEN}🟢 RUNNING (Queues: orchestrator, publishing, media, analytics)${RESET}\n" "Celery Worker" "$w_pid"
    else
        printf "  • %-16s : ${RED}🔴 STOPPED${RESET}\n" "Celery Worker"
    fi

    if pgrep -f "celery.*beat" >/dev/null 2>&1 || ([ -f "$REPO_ROOT/.pids/beat.pid" ] && kill -0 "$(cat "$REPO_ROOT/.pids/beat.pid")" 2>/dev/null); then
        local bt_pid
        bt_pid=$(pgrep -f "celery.*beat" 2>/dev/null | head -n1 || cat "$REPO_ROOT/.pids/beat.pid" 2>/dev/null)
        printf "  • %-16s (PID %-7s): ${GREEN}🟢 RUNNING (Periodic Tasks)${RESET}\n" "Celery Beat" "$bt_pid"
    else
        printf "  • %-16s : ${YELLOW}⚪ INACTIVE${RESET}\n" "Celery Beat"
    fi

    if check_port "127.0.0.1" 3000; then
        local f_pid
        f_pid=$(lsof -ti :3000 2>/dev/null | head -n1 || cat "$REPO_ROOT/.pids/frontend.pid" 2>/dev/null || echo "active")
        printf "  • %-16s (PID %-7s): ${GREEN}🟢 RUNNING (http://localhost:3000)${RESET}\n" "Next.js UI" "$f_pid"
    else
        printf "  • %-16s : ${RED}🔴 STOPPED${RESET}\n" "Next.js UI"
    fi

    echo -e "\n${BOLD}[3] Local Ollama / Qwen Models Configuration:${RESET}"
    if check_port "127.0.0.1" 11434; then
        local models
        models=$(curl -s http://localhost:11434/api/tags 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')
        echo -e "  • Available Models: ${CYAN}${models:-None}${RESET}"
    else
        echo -e "  • Ollama service unavailable."
    fi

    echo -e "==================================================================\n"
}

start_all() {
    local detach="${1:-false}"

    echo -e "\n${BOLD}${CYAN}==================================================================${RESET}"
    echo -e "${BOLD}${CYAN}   🚀 AGENTIC BRAND MARKETING OS — STARTUP SEQUENCE${RESET}"
    echo -e "${BOLD}${CYAN}==================================================================${RESET}"

    # 1. Environment Verification
    log_step "[1/6] Verifying Environment & Backing Files..."
    if [ ! -f "$REPO_ROOT/.env" ]; then
        if [ -f "$REPO_ROOT/.env.example" ]; then
            log_warn ".env not found. Creating from .env.example..."
            cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
        else
            touch "$REPO_ROOT/.env"
        fi
    fi
    log_info "Python runner selected: ${GREEN}$PY_RUN${RESET}"
    log_info "Docker Compose runner : ${GREEN}$DOCKER_COMPOSE${RESET}"

    # 2. Launch Infrastructure Containers
    log_step "[2/6] Launching Backing Infrastructure Containers..."
    $DOCKER_COMPOSE up -d postgres redis minio qdrant ollama langfuse otel-collector

    # Wait for ports
    log_step "[3/6] Awaiting Container Health & Network Availability..."
    wait_for_port "PostgreSQL"    "127.0.0.1" 5432  60
    wait_for_port "Redis"         "127.0.0.1" 6379  30
    wait_for_port "MinIO Storage" "127.0.0.1" 9000  30
    wait_for_port "Qdrant Vector" "127.0.0.1" 6333  30
    wait_for_port "Ollama Local"  "127.0.0.1" 11434 45
    wait_for_port "Langfuse OTLP" "127.0.0.1" 3001  60

    # 3. Database Migrations
    log_step "[4/6] Executing Database Migrations..."
    (cd "$REPO_ROOT/backend" && $PY_RUN alembic upgrade head)
    log_success "Database schema migrations applied."

    # 4. Infrastructure Awakening & Model Provisioning
    log_step "[5/6] Awakening Infrastructure & Provisioning Qwen Models..."
    $PY_RUN python "$REPO_ROOT/backend/scripts/awaken_infrastructure.py"

    # 5. Launch Application Services
    log_step "[6/6] Launching Application Control Plane Services..."

    # Ensure stale ports are clear
    kill_port_owner 8000 "FastAPI"
    kill_port_owner 3000 "Next.js"

    # Start Celery Worker
    log_info "Starting Celery Async Task Worker..."
    setsid $PY_RUN celery -A app.tasks.celery_app --workdir "$REPO_ROOT/backend" \
        worker --loglevel=info \
        -Q orchestrator_queue,publishing_queue,media_queue,analytics_queue \
        </dev/null > "$REPO_ROOT/logs/worker.log" 2>&1 &
    echo $! > "$REPO_ROOT/.pids/worker.pid"
    log_success "Celery Worker started (PID $(cat "$REPO_ROOT/.pids/worker.pid"), log: logs/worker.log)"

    # Start Celery Beat
    log_info "Starting Celery Beat Periodic Scheduler..."
    setsid $PY_RUN celery -A app.tasks.celery_app --workdir "$REPO_ROOT/backend" \
        beat --loglevel=info \
        </dev/null > "$REPO_ROOT/logs/beat.log" 2>&1 &
    echo $! > "$REPO_ROOT/.pids/beat.pid"
    log_success "Celery Beat started (PID $(cat "$REPO_ROOT/.pids/beat.pid"), log: logs/beat.log)"

    # Start FastAPI Backend
    log_info "Starting FastAPI Backend API on http://0.0.0.0:8000..."
    setsid $PY_RUN uvicorn app.main:app --app-dir "$REPO_ROOT/backend" --host 0.0.0.0 --port 8000 --reload \
        </dev/null > "$REPO_ROOT/logs/backend.log" 2>&1 &
    echo $! > "$REPO_ROOT/.pids/backend.pid"

    wait_for_port "FastAPI Backend" "127.0.0.1" 8000 30
    log_success "FastAPI Backend online (PID $(cat "$REPO_ROOT/.pids/backend.pid"), log: logs/backend.log)"

    # Start Next.js Frontend
    log_info "Starting Next.js Management UI on http://localhost:3000..."
    # Clear dev cache to avoid webpack chunk collision
    rm -rf "$REPO_ROOT/frontend/.next"
    (cd "$REPO_ROOT/frontend" && setsid npm run dev </dev/null > "$REPO_ROOT/logs/frontend.log" 2>&1 & echo $! > "$REPO_ROOT/.pids/frontend.pid")

    wait_for_port "Next.js Management UI" "127.0.0.1" 3000 45
    log_success "Next.js UI online (PID $(cat "$REPO_ROOT/.pids/frontend.pid"), log: logs/frontend.log)"

    # Print summary
    echo -e "\n=================================================================="
    echo -e "${BOLD}${GREEN}   ✨ ALL AGENTIC SYSTEM COMPONENTS ARE UP AND RUNNING!${RESET}"
    echo -e "=================================================================="
    echo -e "  • ${BOLD}Next.js Management UI :${RESET} ${CYAN}http://localhost:3000${RESET}"
    echo -e "  • ${BOLD}Orchestrator Chat UI   :${RESET} ${CYAN}http://localhost:3000/chat${RESET}"
    echo -e "  • ${BOLD}Backend API Docs (OpenAPI):${RESET} ${CYAN}http://localhost:8000/docs${RESET}"
    echo -e "  • ${BOLD}Backend Health Probe   :${RESET} ${CYAN}http://localhost:8000/health${RESET}"
    echo -e "  • ${BOLD}Langfuse Tracing Dashboard:${RESET} ${CYAN}http://localhost:3001${RESET}"
    echo -e "  • ${BOLD}MinIO Object Storage UI :${RESET} ${CYAN}http://localhost:9001${RESET} (Credentials in environment/.env)"
    echo -e "  • ${BOLD}Qdrant Vector DB REST  :${RESET} ${CYAN}http://localhost:6333/dashboard${RESET}"
    echo -e "  • ${BOLD}Local Ollama Endpoint  :${RESET} ${CYAN}http://localhost:11434${RESET}"
    echo -e "------------------------------------------------------------------"
    echo -e "  • ${BOLD}Authentication         :${RESET} Control Plane JWT (Set via DEFAULT_ADMIN_EMAIL / .env)"
    echo -e "=================================================================="
    echo -e "\nUseful Commands:"
    echo -e "  • Check Status : ${YELLOW}./start.sh --status${RESET}"
    echo -e "  • Stop System  : ${YELLOW}./start.sh --stop${RESET}"
    echo -e "  • View Logs    : ${YELLOW}./start.sh --logs [backend|worker|frontend|beat]${RESET}"
    echo -e "==================================================================\n"

    if [ "$detach" = "true" ]; then
        log_info "Running in detached mode. Services will continue running in the background."
        return 0
    fi

    # Interactive foreground mode: trap interrupts
    trap 'echo -e "\nCaught shutdown signal..."; stop_services false; exit 0' INT TERM
    echo -e "${YELLOW}Press Ctrl+C to stop all application services (backing containers remain up).${RESET}\n"
    # Keep script open and periodically check health
    while true; do
        sleep 5
        # If backend or frontend died, report it
        if [ -f "$REPO_ROOT/.pids/backend.pid" ] && ! kill -0 "$(cat "$REPO_ROOT/.pids/backend.pid")" 2>/dev/null; then
            log_error "FastAPI Backend stopped unexpectedly. Check logs/backend.log"
            break
        fi
        if [ -f "$REPO_ROOT/.pids/frontend.pid" ] && ! kill -0 "$(cat "$REPO_ROOT/.pids/frontend.pid")" 2>/dev/null; then
            log_error "Next.js UI stopped unexpectedly. Check logs/frontend.log"
            break
        fi
    done
}

tail_logs() {
    local target="${1:-all}"
    case "$target" in
        backend)  tail -f "$REPO_ROOT/logs/backend.log" ;;
        worker)   tail -f "$REPO_ROOT/logs/worker.log" ;;
        beat)     tail -f "$REPO_ROOT/logs/beat.log" ;;
        frontend) tail -f "$REPO_ROOT/logs/frontend.log" ;;
        all|*)    tail -f "$REPO_ROOT/logs/"*.log ;;
    esac
}

# ------------------------------------------------------------------------------
# 3. CLI Argument Parsing
# ------------------------------------------------------------------------------
case "${1:-}" in
    --detach|-d)
        start_all true
        ;;
    --status|-s|status)
        print_status
        ;;
    --stop|stop)
        stop_services false
        ;;
    --stop-all|stop-all)
        stop_services true
        ;;
    --restart|restart)
        stop_services false
        sleep 2
        start_all true
        ;;
    --logs|logs)
        tail_logs "${2:-all}"
        ;;
    --help|-h|help)
        echo "Agentic Brand Marketing OS — Startup Script"
        echo ""
        echo "Usage: ./start.sh [command|flag]"
        echo ""
        echo "Commands & Flags:"
        echo "  (none)        Start all services interactively (Ctrl+C gracefully stops app)"
        echo "  -d, --detach  Start all services in background and exit"
        echo "  --status      Show live health and status of containers, ports, and processes"
        echo "  --stop        Stop application services (Backend, Worker, Beat, Frontend)"
        echo "  --stop-all    Stop application services AND tear down Docker backing containers"
        echo "  --restart     Restart application services"
        echo "  --logs [svc]  Tail logs (svc: backend, worker, beat, frontend, or all)"
        echo "  --help        Show this help message"
        ;;
    *)
        start_all false
        ;;
esac
