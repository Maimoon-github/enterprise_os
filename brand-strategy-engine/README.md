# Universal AI Brand Strategy Engine

Production-grade multi-agent autonomous system for empirical website reconnaissance, commercial diagnostic audits, and adversarial strategy verification. Powered by the **Google Antigravity SDK** and local **Ollama** inference models across Mode A (Personal Branding), Mode B (eCommerce Growth), and Mode C (Shared Core).

---

## 1. System Architecture & Topology

```
                           ┌─────────────────────────────────────────────────────────────┐
                           │          Brand Strategy Orchestrator (Agent 0)              │
                           │     [Google Antigravity SDK Supervisor | Qwen 2.5 72B]      │
                           └──────┬───────────────────────────────┬────────────────▲─────┘
                                  │ (Task Delegation Slice)       │                │
            ┌─────────────────────▼────────┐             ┌────────▼────────┐       │ (Adversarial
            │  1. Website & Social Analyst │             │  2. Audience    │       │  Revisions
            │     [Llama 3.2 Vision 11B]   │             │     Strategist  │       │  Max 3 Loops)
            └──────────────┬───────────────┘             │  [Qwen 2.5 32B] │       │
                           │                             └────────┬────────┘       │
                           └───────────────┬──────────────────────┘                │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │    3. Brand Strategist      │                        │
                            │       [Qwen 2.5 32B]        │                        │
                            └──────────────┬──────────────┘                        │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │ 4. SEO & Content Strategist │                        │
                            │       [Qwen 2.5 32B]        │                        │
                            └──────────────┬──────────────┘                        │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │    5. Growth Strategist     │                        │
                            │    [Llama 3.3 70B Inst.]    │                        │
                            └──────────────┬──────────────┘                        │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │    6. Strategy Validator    ├────────────────────────┘
                            │    [DeepSeek-R1 Distill 70B]│
                            └──────────────┬──────────────┘
                                           │ (Approval Certificate)
                                           ▼
                            ┌─────────────────────────────┐
                            │   Validated Growth Plan     │
                            └─────────────────────────────┘
```

---

## 2. Directory Tree

```
brand-strategy-engine/
├── .config/
│   ├── config.toml                     # Global runtime, Ollama routing, VNC settings
│   └── settings.json                   # IDE and runtime workspace settings
├── docker/
│   ├── Dockerfile.engine               # Core Antigravity SDK & agent runtime container
│   ├── Dockerfile.vnc_sandbox          # Internalized headless VNC browser container
│   └── docker-compose.yml              # Multi-container isolated bridge topology
├── internal_sandbox/                   # PRIVATE: Sandboxed VNC Display Subsystem
│   ├── config/tint2/tint2rc            # Desktop panel configuration
│   ├── entrypoint.sh                   # Display initialization supervisor
│   ├── scripts/                        # Startup scripts (xvfb, tint2, mutter, x11vnc, noVNC)
│   └── tools/                          # Low-level computer use scripts (base, bash, computer, edit, vnc_client)
├── src/
│   ├── schemas/                        # Pydantic v2 master contracts (evidence, initiative, state, validation)
│   ├── tools/                          # Public tool bridges (browser_bridge, dom_parser, metric_validator, rag_search)
│   ├── memory/                         # Dual-tier memory (short_term, long_term, summarizer)
│   ├── rag/                            # Grounded document ingestion (parser, chunker, embedder, store)
│   ├── agents/                         # Domain specialist agents (analyst, audience, brand, seo, growth, validator)
│   ├── orchestrator/                   # Central supervisor (manager, state_machine, context_isolator)
│   └── runtime/                        # Execution entrypoints (api, cli)
├── tests/                              # Comprehensive test suite (pytest)
├── pyproject.toml                      # Build and dependency configuration
└── README.md
```

---

## 3. Operational Modalities

- **Mode A (Personal Branding & Portfolio Strategy)**: Tailored for software engineers, consultants, data scientists, and creators. Audits hero positioning, proof-of-work discoverability, technical stack authority, case study conversion architecture, and social validation footprints.
- **Mode B (eCommerce Growth Strategy)**: Tailored for DTC brands and digital merchants. Evaluates collection navigation, cart abandonment triggers, product detail page (PDP) conversion barriers, shipping/return policy transparency, and unit-economic growth loops.
- **Mode C (Shared Strategic Intelligence Core)**: Common multi-agent fabric providing headless VNC exploration, deterministic evidence indexing, context-isolated state transitions, and adversarial validation.

---

## 4. Local Execution & Testing

### Run All Unit and Integration Tests

```bash
cd brand-strategy-engine
conda run -n strategy_engine pytest -v
```

### Run Audit via CLI

```bash
conda run -n strategy_engine python -m src.runtime.cli \
  --mode Mode_A_Personal \
  --url "https://alexchen.dev"
```

### Run FastAPI REST Server

```bash
conda run -n strategy_engine uvicorn src.runtime.api:app --host 0.0.0.0 --port 8000
```
