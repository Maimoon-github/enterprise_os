# Observability, OpenInference Conventions, and Evaluation Framework

## Distributed Tracing with OpenTelemetry & Langfuse

1. **Instrumentation Layer:** All services initialize OpenTelemetry SDK tracers (`opentelemetry-sdk`). Spans are tagged with standard **OpenInference** semantic attributes:
   - `openinference.span.kind`: `AGENT`, `CHAIN`, `LLM`, `TOOL`, `RETRIEVER`, `RERANKER`, `GUARDRAIL`, `EVALUATOR`, `DECISION`.
   - `graph.node.id`, `graph.node.parent_id`, `agent.name`, `session.id`.
   - Tool arguments, latency, exceptions, and token velocity metrics.
2. **Export Target:** Spans export via OTLP (`/v1/traces`) directly to self-hosted **Langfuse**.
3. **Optional Local Debugging:** Arize Phoenix can run concurrently as an optional OTLP receiver for local evaluation testing without modifying application code.

## Evaluation Pipeline
- **Layer 1: Deterministic Schema & Rule Checks (Code):** Pydantic validators assert character limits (X $\le$ 280, Threads $\le$ 500, LinkedIn $\le$ 3,000) and aspect ratios.
- **Layer 2: Trajectory & Tool-Order Gate:** Asserts that retrieval operations strictly precede drafting, and human approval interrupts precede platform publishing.
- **Layer 3: Isolated LLM-as-a-Judge Rubric:** Evaluates Brand Voice Fidelity ($\ge 0.85$), Groundedness ($\ge 0.90$), and Platform Engagement ($\ge 0.80$).
- **Layer 4: Offline CI/CD Golden Suite:** Tests 50+ benchmark scenarios using Pydantic `TestModel` burning zero LLM tokens.
