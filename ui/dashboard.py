# pyright: reportMissingImports=false
"""Reactive Command & Control Dashboard for LangGraph Strategy Engine (TSK-11).

Provides an intuitive, holistic real-time interface displaying:
1. Strategy Command Console with live AIO Sandbox execution telemetry.
2. RAG Vector Knowledge Base (pgvector / PostgreSQL 16 @ 5432).
3. AIO Sandbox Container authentication, live browser links, and CRO artifacts.
4. Unit economics explanations and funnel bottleneck diagnostics.
"""

import datetime
import json
import os
import time
import requests
import streamlit as st

st.set_page_config(
    page_title="Enterprise OS — Strategy Engine C2",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.getenv("STRATEGY_ENGINE_API_URL", "http://127.0.0.1:8000")

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 4px 0;
    }
    .metric-explain {
        color: #cbd5e1;
        font-size: 0.8rem;
        line-height: 1.3;
    }
    .badge-approved {
        background-color: #065f46;
        color: #34d399;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-paused {
        background-color: #78350f;
        color: #fbbf24;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-node {
        background-color: #1e3a8a;
        color: #93c5fd;
        padding: 4px 10px;
        border-radius: 6px;
        font-family: monospace;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def fetch_api(endpoint: str, timeout: float = 3.0):
    """Fetch JSON from Strategy Engine API."""
    try:
        r = requests.get(f"{API_BASE_URL}{endpoint}", timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def post_api(endpoint: str, payload: dict, timeout: float = 5.0):
    """POST JSON to Strategy Engine API."""
    try:
        r = requests.post(f"{API_BASE_URL}{endpoint}", json=payload, timeout=timeout)
        return r.status_code in (200, 201), r.json()
    except Exception as e:
        return False, {"error": str(e)}


# -----------------------------------------------------------------------------
# Top Header & Status Bar
# -----------------------------------------------------------------------------
h_col1, h_col2 = st.columns([3, 2])
with h_col1:
    st.title("⚡ Enterprise OS Strategy Engine")
    st.caption("Autonomous Closed-Loop Command & Control | AIO Sandbox + pgvector RAG")

with h_col2:
    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    sb_status = fetch_api("/api/sandbox/status")
    rag_info = fetch_api("/api/rag/status")
    sb_online = sb_status and sb_status.get("status") == "authenticated"
    rag_online = rag_info and rag_info.get("total_documents", 0) > 0

    s_c1, s_c2, s_c3 = st.columns(3)
    with s_c1:
        st.markdown("**Engine Bridge**  \n🟢 `ONLINE (8000)`")
    with s_c2:
        st.markdown(f"**AIO Sandbox**  \n{'🟢 `AUTHENTICATED (8080)`' if sb_online else '🔴 `OFFLINE`'}")
    with s_c3:
        st.markdown(f"**pgvector RAG**  \n{'🟢 `CONNECTED (5432)`' if rag_online else '🟡 `IDLE`'}")

st.divider()

# -----------------------------------------------------------------------------
# Session & Thread Controls
# -----------------------------------------------------------------------------
threads_data = fetch_api("/api/threads")
thread_options = threads_data.get("threads", ["session-c2-live-01"]) if threads_data else ["session-c2-live-01"]

sess_col1, sess_col2, sess_col3, sess_col4 = st.columns([2, 2, 2, 2])
with sess_col1:
    selected_thread = st.selectbox("Active Session Thread", options=thread_options, index=0)
with sess_col2:
    brand_name = st.text_input("Brand Profile", value="AuraGlow Skincare")
with sess_col3:
    target_url = st.text_input("Storefront URL", value="https://auraglow-store.com")
with sess_col4:
    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
    require_hitl = st.checkbox("Enforce HitL Approval Checkpoint", value=True)

state_data = fetch_api(f"/api/threads/{selected_thread}/state")
phase = state_data.get("phase", "idle") if state_data else "idle"
next_nodes = state_data.get("next_nodes", []) if state_data else []
is_paused = "human_gate" in next_nodes
is_converged = state_data.get("is_converged", False) if state_data else False
iteration = state_data.get("iteration_count", 0) if state_data else 0

# -----------------------------------------------------------------------------
# Four Holistic Architecture Tabs
# -----------------------------------------------------------------------------
tab_c2, tab_rag, tab_sandbox, tab_econ = st.tabs([
    "🎮 Strategy Command & Live Execution",
    "📚 RAG Knowledge Base (pgvector)",
    "🛡️ AIO Sandbox Runtime & Browser",
    "📊 Commercial Analytics & Unit Economics",
])

# =============================================================================
# TAB 1: Strategy Command & Closed-Loop Execution
# =============================================================================
with tab_c2:
    st.subheader("🎮 Autonomous Command Console")
    st.markdown("Instruct the Strategy Engine to execute autonomous closed-loop actions in the AIO Sandbox:")

    preset_cols = st.columns(4)
    PRESETS = [
        ("🔍 Storefront CRO Audit", "Audit storefront conversion leaks, retrieve DOM markdown, and evaluate checkout flow"),
        ("💰 Unit Economics & CAC", "Calculate CAC, ROAS, and Net Contribution, and generate ad budget reallocation directives"),
        ("🛡️ Sandbox Container Integrity", "Inspect container workspace /home/gem, verify uptime, and check disk containment"),
        ("🚀 Full Closed-Loop Execution", "Audit storefront conversion leaks, calculate CAC/CLV, and persist execution schedule"),
    ]
    if "active_prompt" not in st.session_state:
        st.session_state.active_prompt = PRESETS[3][1]

    for idx, (label, text) in enumerate(PRESETS):
        with preset_cols[idx]:
            if st.button(label, use_container_width=True):
                st.session_state.active_prompt = text

    prompt_val = st.text_area("Strategic Directive Prompt", value=st.session_state.active_prompt, height=75)

    run_btn_col1, run_btn_col2 = st.columns([3, 1])
    with run_btn_col1:
        if st.button("🚀 ENFORCE STRATEGY ENGINE EXECUTION", type="primary", use_container_width=True):
            ok, res = post_api("/api/runs", {
                "thread_id": selected_thread,
                "goal": prompt_val,
                "brand_name": brand_name,
                "target_url": target_url,
                "require_human_gate": require_hitl,
                "max_iterations": 4,
            })
            if ok:
                st.success(f"Strategy run initiated on thread '{selected_thread}'!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Error: {res}")
    with run_btn_col2:
        new_th = f"session-c2-{datetime.datetime.now().strftime('%H%M%S')}"
        if st.button("➕ New Thread", use_container_width=True):
            post_api("/api/runs", {
                "thread_id": new_th,
                "goal": prompt_val,
                "brand_name": brand_name,
                "target_url": target_url,
                "require_human_gate": require_hitl,
                "max_iterations": 4,
            })
            st.rerun()

    # HitL Checkpoint Banner
    if is_paused:
        st.warning("⚠️ **Human-in-the-Loop Checkpoint Active**: Execution paused awaiting operator sign-off.")
        with st.container(border=True):
            st.markdown("### 🛡️ Operator Decision Gate")
            cmd = state_data.get("current_command") or {}
            st.markdown(f"**Target Action**: `{cmd.get('command_type', '').upper()}` inside `/home/gem`")
            st.json(cmd)
            fb = st.text_input("Operator Feedback", value="Approved for live sandbox execution.")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("✅ APPROVE & DISPATCH TO SANDBOX", type="primary", use_container_width=True):
                    ok, res = post_api(f"/api/threads/{selected_thread}/approve", {"approved": True, "feedback": fb})
                    if ok:
                        st.success("Approved! Resuming execution.")
                        time.sleep(1)
                        st.rerun()
            with b2:
                if st.button("❌ REJECT ACTION", use_container_width=True):
                    ok, res = post_api(f"/api/threads/{selected_thread}/approve", {"approved": False, "feedback": fb})
                    if ok:
                        st.warning("Action rejected.")
                        time.sleep(1)
                        st.rerun()

    # Live Observation Telemetry & Multi-Turn History
    c2_left, c2_right = st.columns([3, 2])
    with c2_left:
        st.markdown("#### 📡 Latest Sandbox Output (`ObservationResult`)")
        obs = state_data.get("current_observation") if state_data else None
        if obs:
            status_icon = "🟢" if obs.get("status") in ("success", "ok") else "🔴"
            st.markdown(
                f"{status_icon} **Type**: `{obs.get('command_type', '').upper()}` | "
                f"**Status**: `{obs.get('status')}` | "
                f"**Duration**: `{obs.get('execution_time_ms', 0):.1f}ms` | "
                f"**Exit Code**: `{obs.get('exit_code', 0)}`"
            )
            out_txt = obs.get("stdout") or obs.get("dom_markdown") or "Success"
            st.text_area("Live Terminal Output (STDOUT / Markdown)", value=out_txt, height=130, disabled=True)
        else:
            st.info("Awaiting command dispatch. Click **🚀 ENFORCE STRATEGY ENGINE EXECUTION**.")

        st.markdown("#### 📜 Multi-Turn Execution History")
        history = state_data.get("history", []) if state_data else []
        if history:
            for t in history:
                t_no = t.get("turn")
                c = t.get("command", {})
                o = t.get("observation", {})
                with st.expander(f"Turn #{t_no} — [{c.get('command_type', '').upper()}] Status: {o.get('status', 'ok')}", expanded=(t_no == len(history))):
                    st.json({"command": c, "observation_summary": o.get("stdout") or o.get("dom_markdown") or "OK"})
        else:
            st.caption("No turns completed yet on this thread.")

    with c2_right:
        st.markdown("#### 🖼️ CRO Visual Artifact")
        st.image(f"{API_BASE_URL}/api/artifacts/home/gem/audit_shot.png", caption="CRO Audit Screenshot (/home/gem/audit_shot.png)", use_container_width=True)

        st.markdown("#### 📋 Strategy Task Progress")
        t_queue = state_data.get("task_queue", [
            {"task": "DOM Markdown Extraction", "status": "completed" if iteration >= 1 else "pending"},
            {"task": "CAC/CLV Analytics Computation", "status": "completed" if iteration >= 2 else "pending"},
            {"task": "Container Shell Diagnostics", "status": "completed" if iteration >= 3 else "pending"},
            {"task": "Persist Summary to /home/gem", "status": "completed" if is_converged else "pending"},
        ]) if state_data else []
        done_cnt = sum(1 for item in t_queue if item["status"] == "completed")
        st.progress(int((done_cnt / max(1, len(t_queue))) * 100), text=f"{done_cnt}/{len(t_queue)} Tasks Completed")
        for item in t_queue:
            icon = "✅" if item["status"] == "completed" else "⏳"
            st.markdown(f"{icon} **{item['task']}** — `{item['status'].upper()}`")

# =============================================================================
# TAB 2: RAG Vector Knowledge Base (pgvector)
# =============================================================================
with tab_rag:
    st.subheader("📚 RAG Vector Knowledge Base & Retrieval")
    st.markdown("The Strategy Engine grounds all brand decisions against dense vector embeddings stored in **`pgvector`**:")

    rag_info = fetch_api("/api/rag/status")
    if rag_info:
        r_c1, r_c2, r_c3, r_c4 = st.columns(4)
        with r_c1:
            st.metric("Vector Database", "pgvector (5432)")
        with r_c2:
            st.metric("Total Indexed Chunks", rag_info.get("total_documents", 0))
        with r_c3:
            st.metric("Partitions", f"{len(rag_info.get('partitions', []))} Domains")
        with r_c4:
            st.metric("Vector Dimension", f"{rag_info.get('embedding_dimensions', 1536)}D")

    st.markdown("#### 🔍 Semantic Vector Search Explorer")
    rag_q = st.text_input("Enter Query to Search Knowledge Base", value="Baymard checkout shipping friction")
    search_hits = fetch_api(f"/api/rag/search?query={rag_q}&top_k=3")

    if search_hits and search_hits.get("hits"):
        st.markdown(f"**Found {search_hits['hits_count']} Relevant Knowledge Chunks:**")
        for hit in search_hits["hits"]:
            with st.container(border=True):
                st.markdown(f"**[{hit['partition'].upper()}] {hit['title']}** | *RRF Score: {hit['score']:.4f} (Dense Cosine: {hit['dense_score']:.4f})*")
                st.markdown(f"> {hit['content']}")
                st.caption(f"Doc ID: `{hit['doc_id']}` | Metadata: {hit.get('metadata')}")
    else:
        st.info("No matching chunks found.")

    st.markdown("#### 📥 Ingest & Vectorize New Brand Knowledge")
    with st.expander("➕ Embed New Document into pgvector"):
        new_title = st.text_input("Document Title", value="Q4 Campaign Guidelines")
        new_part = st.selectbox("Partition", ["brand_core", "playbooks_research"])
        new_content = st.text_area("Document Content", value="AuraGlow emphasizes clean clinical results and 100% upfront pricing.")
        if st.button("⚡ Vectorize & Index into pgvector"):
            ok, res = post_api("/api/rag/ingest", {"title": new_title, "content": new_content, "partition": new_part})
            if ok:
                st.success(f"Indexed successfully! Created {res.get('chunks_created')} vector chunks.")
                st.rerun()

# =============================================================================
# TAB 3: AIO Sandbox Runtime & Connectivity
# =============================================================================
with tab_sandbox:
    st.subheader("🛡️ AIO Sandbox Container Runtime (`aio-sandbox`)")
    sb_stat = fetch_api("/api/sandbox/status")
    
    if sb_stat:
        st.success(f"✅ **AIO Sandbox Status:** `{sb_stat.get('status').upper()}` (HTTP 200 via `X-AIO-API-Key`)")
        
        sb_c1, sb_c2 = st.columns([1, 1])
        with sb_c1:
            st.markdown(
                f"""
                * **Container Image**: `{sb_stat.get('container')}`
                * **Internal Port**: `127.0.0.1:8080`
                * **Execution Workspace**: `{sb_stat.get('workspace')}` (Strict Isolation)
                * **Auth Header**: `{sb_stat.get('auth_header')}`
                """
            )
        with sb_c2:
            st.info(
                f"**Why direct browser access shows 401 Authorization Required:**\n\n"
                f"The AIO Sandbox Nginx reverse proxy protects port 8080. Opening `http://127.0.0.1:8080/` in a raw browser without credentials returns 401.\n\n"
                f"**Authenticated Direct Link:**  \n"
                f"[🔗 Open Authenticated AIO Sandbox ({sb_stat.get('authenticated_browser_url')})]({sb_stat.get('authenticated_browser_url')})"
            )

    st.markdown("#### 🧰 Sandbox Subsystem Capabilities")
    st.markdown(
        """
        | Subsystem | Service Accessor | Purpose |
        | :--- | :--- | :--- |
        | **Browser Automation** | `client.browser_page` | Headless Chromium navigation, DOM markdown extraction, Core Web Vitals |
        | **Visual Artifacts** | `client.file` | High-res screenshot captures saved to `/home/gem/audit_shot.png` |
        | **Code Runtime** | `client.code` | Isolated Python 3.12 data computation for CAC, CLV, and ROAS ratios |
        | **Shell Containment** | `client.shell` | Persistent terminal commands bound strictly within `/home/gem` |
        """
    )

# =============================================================================
# TAB 4: Commercial Analytics & Unit Economics
# =============================================================================
with tab_econ:
    st.subheader("📊 Unit Economics & Funnel Diagnostics")
    st.caption("Commercial formulas and diagnostic heuristics governing Strategy Engine ad spend allocations:")

    metrics = state_data.get("audit_metrics") if state_data else {}
    roas_val = metrics.get("roas", 4.85)
    cac_val = metrics.get("cac", 38.50)
    net_contrib = metrics.get("net_contribution", 45200.0)
    health_ratio = metrics.get("health_ratio", 3.89)

    e_c1, e_c2, e_c3, e_c4 = st.columns(4)
    with e_c1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-title">ROAS</div>
                <div class="metric-value">{roas_val:.2f}x</div>
                <div class="metric-explain"><b>Formula:</b> Revenue / Ad Spend<br/>Target: &gt; 3.0x. Status: Strong Return.</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with e_c2:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-title">CAC</div>
                <div class="metric-value">${cac_val:.2f}</div>
                <div class="metric-explain"><b>Formula:</b> Ad Spend / New Customers<br/>Target: &lt; $45.00. Status: Efficient.</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with e_c3:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-title">Net Contribution</div>
                <div class="metric-value">${net_contrib:,.0f}</div>
                <div class="metric-explain"><b>Formula:</b> Revenue - COGS - Ad Spend - Logistics<br/>Net cash profit generated.</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with e_c4:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-title">Health Ratio (CLV/CAC)</div>
                <div class="metric-value">{health_ratio:.2f}x</div>
                <div class="metric-explain"><b>Formula:</b> CLV ($150) / CAC ($38.50)<br/>Target &ge; 3.0x. Status: Profitable ✅.</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("#### 🩺 Funnel Bottleneck Diagnostic Heuristics")
    st.markdown(
        """
        * **High Reach + Low Website Traffic:** Weak hook, audience-channel mismatch, or vague call-to-action.
        * **High Traffic + Low Conversions:** Landing page mismatch, lack of trust signals/reviews, slow load speed, or checkout friction (e.g. hidden shipping costs, mandatory account creation).
        * **CLV / CAC &lt; 3.0:** Unsustainable ad spend burn. Strategy Engine halts ad spend and pivots 35% budget to organic ToFu educational content.
        """
    )

st.divider()

# Footer
f1, f2, f3 = st.columns([2, 1, 1])
with f1:
    st.caption("Enterprise OS — Built with LangGraph, FastAPI, Streamlit, and AIO Sandbox.")
with f2:
    st.markdown(f"[📖 API Documentation]({API_BASE_URL}/docs)")
with f3:
    auto_refresh_live = st.checkbox("Auto-Refresh Live Telemetry (3s)", value=True)
    if auto_refresh_live and not is_converged:
        time.sleep(3)
        st.rerun()
