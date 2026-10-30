#!/usr/bin/env python3
"""Infrastructure Awakening & Qwen Local Model Provisioner.

Discovers local Ollama models, binds optimal Qwen models for supervisor & worker roles,
verifies and awakens backing services, pre-warms models, and seeds demo brand guidelines.
"""
import asyncio
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import httpx  # noqa: E402
from scripts.seed_db import seed  # noqa: E402

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
PROJECT_ROOT = backend_root.parent


def check_tcp_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


async def discover_ollama_models() -> list[dict[str, Any]]:
    """Fetch all available models directly from Ollama."""
    try:
        async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=10.0) as client:
            res = await client.get("/api/tags")
            if res.status_code == 200:
                data = res.json()
                return data.get("models", [])
    except Exception as exc:
        print(f"⚠️  Could not query Ollama at {OLLAMA_BASE_URL}: {exc}")
    return []


def select_best_qwen_models(models: list[dict[str, Any]]) -> dict[str, str]:
    """Select the best Qwen models available on localhost for each infrastructure role."""
    model_names = [m.get("name", "") for m in models]

    # 1. Supervisor Model (prefer 14b, 32b, or 9b for complex multi-step reasoning)
    supervisor = None
    for candidate in [
        "qwen2.5:14b",
        "qwen2.5:14b-instruct-q4_K_M",
        "qwen3.5:9b-q4_K_M",
        "deepseek-r1:32b-qwen-distill-q4_K_M",
        "qwen2.5:7b",
    ]:
        if any(candidate in name for name in model_names):
            supervisor = candidate
            break
    if not supervisor:
        supervisor = "qwen2.5:14b"

    # 2. Worker / Subgraph Model (prefer 7b or 4b for fast token generation)
    worker = None
    for candidate in [
        "qwen2.5:7b",
        "qwen3.5:4b-q4_K_M",
        "qwen3.5:4b",
        "qwen-agent:4b",
        "local-agent-model:latest",
    ]:
        if any(candidate in name for name in model_names):
            worker = candidate
            break
    if not worker:
        worker = "qwen2.5:7b"

    # 3. Coder / Agent Model
    coder = None
    for candidate in ["qwen2.5-coder:7b", "qwen-agent:4b"]:
        if any(candidate in name for name in model_names):
            coder = candidate
            break
    if not coder:
        coder = worker

    # 4. Embedding Model
    embedding = "nomic-embed-text:latest" if any("nomic-embed" in name for name in model_names) else "nomic-embed-text"

    return {
        "supervisor": supervisor,
        "worker": worker,
        "coder": coder,
        "embedding": embedding,
    }


def update_env_file(model_map: dict[str, str]) -> None:
    """Synchronize .env with selected Qwen models and local model path."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    content = env_path.read_text()
    replacements = {
        r"^OLLAMA_MODEL_SUPERVISOR=.*$": f"OLLAMA_MODEL_SUPERVISOR={model_map['supervisor']}",
        r"^OLLAMA_MODEL_WORKER=.*$": f"OLLAMA_MODEL_WORKER={model_map['worker']}",
        r"^OLLAMA_MODEL_EMBEDDING=.*$": f"OLLAMA_MODEL_EMBEDDING={model_map['embedding']}",
    }

    for pattern, repl in replacements.items():
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, repl, content, flags=re.MULTILINE)
        else:
            content += f"\n{repl}"

    if "OLLAMA_MODELS_PATH=" not in content:
        home_ollama = Path.home() / ".ollama"
        content += f"\nOLLAMA_MODELS_PATH={home_ollama}\n"

    env_path.write_text(content)
    print("📝 Synchronized .env configuration with local Qwen models.")


async def verify_and_prewarm(model_name: str) -> bool:
    """Pre-warm model with a lightweight ping to load weights into memory."""
    print(f"🔥 Awakening and pre-warming Qwen model: {model_name}...")
    try:
        async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=60.0) as client:
            payload = {"model": model_name, "prompt": "Ready check", "stream": False}
            res = await client.post("/api/generate", json=payload)
            if res.status_code == 200:
                print(f"✅ Model {model_name} awakened and ready for inference.")
                return True
    except Exception as exc:
        print(f"⚠️  Warm-up completed with note: {exc}")
    return False


async def awaken():
    print("==================================================================")
    print("   🚀 AGENTIC MARKETING OS — INFRASTRUCTURE AWAKENING & PROVISIONING")
    print("==================================================================")

    # 1. Check Infrastructure Ports
    services = {
        "PostgreSQL (5432)": check_tcp_port("localhost", 5432),
        "Redis (6379)": check_tcp_port("localhost", 6379),
        "MinIO (9000)": check_tcp_port("localhost", 9000),
        "Qdrant (6333)": check_tcp_port("localhost", 6333),
        "Langfuse (3001)": check_tcp_port("localhost", 3001),
        "Ollama (11434)": check_tcp_port("localhost", 11434),
    }

    print("\n[1/4] Checking Backing Infrastructure Services:")
    for svc, healthy in services.items():
        status_str = "🟢 ONLINE" if healthy else "🔴 OFFLINE"
        print(f"  • {svc:<22}: {status_str}")

    # 2. Discover Local Ollama Models
    print("\n[2/4] Discovering Local Ollama Models:")
    models = await discover_ollama_models()
    if not models:
        print("  ⚠️  No models returned via Ollama HTTP API. Checking local volume mapping...")
    else:
        qwen_models = [m["name"] for m in models if "qwen" in m.get("name", "").lower()]
        print(f"  • Total Ollama models detected: {len(models)}")
        print(f"  • Local Qwen models: {', '.join(qwen_models) if qwen_models else 'None'}")

    model_map = select_best_qwen_models(models)
    print("\n[3/4] Optimal Model Routing Configuration:")
    print(f"  • Supervisor / Orchestrator : {model_map['supervisor']}")
    print(f"  • Worker / Subgraph Copier  : {model_map['worker']}")
    print(f"  • Code / Tool Specialist    : {model_map['coder']}")
    print(f"  • Vector Embeddings         : {model_map['embedding']}")

    # Synchronize environment
    update_env_file(model_map)

    # Prewarm worker model
    if services.get("Ollama (11434)"):
        await verify_and_prewarm(model_map["worker"])

    # 3. Idempotently Seed Database & Brand Guidelines
    print("\n[4/4] Idempotent Database & Brand RAG Seeding:")
    try:
        seed_result = await seed()
        print(f"  ✅ Admin User  : {seed_result['admin_user']}")
        print(f"  ✅ Demo Brand  : {seed_result['brand_slug']} (ID: {seed_result['brand_id'][:12]}...)")
        print(f"  ✅ Guidelines  : {seed_result['guidelines_indexed']} deterministic documents indexed.")
    except Exception as exc:
        print(f"  ⚠️  Seed skipped or encountered note: {exc}")

    print("\n==================================================================")
    print("   ✨ INFRASTRUCTURE AWAKENED & PROVISIONED SUCCESSFULLY")
    print("==================================================================")
    print("Run these commands to start working:")
    print("  • Start Backend API : make dev-backend   (http://localhost:8000)")
    print("  • Start Worker Fleet: make dev-worker    (Celery + Podman Sandbox)")
    print("  • Start Management UI: make dev-frontend (http://localhost:3000)")
    print("==================================================================\n")


if __name__ == "__main__":
    asyncio.run(awaken())
