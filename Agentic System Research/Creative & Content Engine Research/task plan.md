Based on the Strategy Engine architecture in the provided project materials, the essential implementation plan can be reduced to **7 sequential tasks**. The core runtime remains:

`IE → W_STRAT → S_ALLOC → W_STRAT → IE → downstream W_CREAT / HITL as required`

| Task ID      | Phase                      | Task Name                                            | Description                                                                                                                                                                                                                                                                                                                                                                                                                | Predecessor | Milestone                                                  | Resource / Owner               |
| ------------ | -------------------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------- | ------------------------------ |
| **CREAT-01** | Foundation                 | **Define Strategy Engine Contracts & Boundaries**    | Establish `W_STRAT` as the bounded Layer-5 Strategy worker. Define TaskGrant inputs, tenant scope, strategy outputs, Model-A restrictions, and the `W_STRAT ↔ S_ALLOC` boundary. **Sub-tasks:** validate T16 Product Evidence, T17 Customer Voice, T18 Competitor Intelligence dependencies; define allowed channels, budget ceiling, objectives, time horizon, constraints, and fail-closed behavior.                     | —           | **M1 — Strategy contracts frozen**                         | Architecture / `W_STRAT`       |
| **CREAT-02** | Reasoning                  | **Implement W_STRAT Strategic Reasoning**            | Give `W_STRAT` its own purpose-scoped LLM for qualitative strategy synthesis. It interprets IE-supplied evidence, campaign objectives, funnel roles, channel roles, KPIs, constraints, and planning assumptions without calculating or mutating budgets itself. **Sub-tasks:** dependency normalization, tenant isolation, channel-scope enforcement, strategy brief creation, risk/assumption identification.             | STRAT-01    | **M2 — W_STRAT reasoning operational**                     | `W_STRAT` / LLM Integration    |
| **CREAT-03** | Specialist                 | **Implement S_ALLOC Reasoning Sub-Agent**            | Create/validate the purpose-scoped `StrategyAllocationAgent` (`S_ALLOC`). Its independent LLM interprets KPI priorities, scenario emphasis, modeling assumptions, and risks. It cannot access RAG, DB, IE internals, outbound systems, or expand budget/channel scope. **Sub-tasks:** structured reasoning schema, independent LLM context, scope checks, model metadata/provenance.                                       | STRAT-02    | **M3 — S_ALLOC reasoning isolated**                        | `S_ALLOC` / AI-ML              |
| **CREAT-04** | Sandbox Execution          | **Build Deterministic Allocation & Funnel Modeling** | Execute quantitative work through fresh task-scoped AIO-Sandbox capability `S_ALLOC`. **Sub-tasks:** media-mix modeling, budget optimization, funnel simulation, ROAS/scenario calculations, diminishing-return constraints, resource limits, deny-all network policy, output sanitization, sandbox teardown. Numerical allocation remains deterministic rather than LLM-generated.                                        | STRAT-03    | **M4 — Sandboxed allocation engine validated**             | `S_ALLOC` / Sandbox & Security |
| **CREAT-05** | Synthesis                  | **Assemble Holistic Omnichannel Strategy**           | `W_STRAT` combines its strategic reasoning with sanitized S_ALLOC results into the canonical `OmnichannelStrategyPlan`. **Sub-tasks:** channel allocations, funnel-stage allocations, channel roles, media mix, campaign proposals, budget distribution, scenario comparison, KPI targets, assumptions, evidence references, caveats and confidence. Ensure total allocation cannot exceed the IE-approved budget ceiling. | STRAT-04    | **M5 — Complete strategy package produced**                | `W_STRAT`                      |
| **CREAT-06** | Governance                 | **Validate Scope, Provenance & IE Handoff**          | Validate the final strategy before returning it to IE. **Sub-tasks:** tenant/channel/budget checks, evidence-reference verification, unsupported-estimate marking, W3C PROV lineage, LLM/model metadata, sandbox execution references, artifact hashing and EvidenceEnvelope creation. IE remains the authority for downstream routing; external spend or mutation still requires governed HITL/outbound flow.             | STRAT-05    | **M6 — Governed Strategy EvidenceEnvelope accepted by IE** | `W_STRAT` + IE / Governance    |
| **CREAT-07** | Integration & Verification | **Integrate, Test & Enable Creative Handoff**        | Wire the completed Strategy Engine into Enterprise OS and prove architectural boundaries. **Sub-tasks:** register `W_STRAT` and `S_ALLOC` LLMs, sandbox capability wiring, update composition root, test Model-A isolation, cross-tenant denial, budget/channel enforcement, missing-evidence failure, sandbox isolation, provenance persistence, and final `IE → W_CREAT` strategy handoff.                               | STRAT-06    | **M7 — Strategy Engine production-ready**                  | Backend / QA / Security / IE   |

### Essential task dependency chain

```text
CREAT-01
Contracts & Boundaries
    ↓
CREAT-02
W_STRAT Reasoning
    ↓
CREAT-03
S_ALLOC Reasoning
    ↓
CREAT-04
Sandboxed Quantitative Modeling
    ↓
CREAT-05
Holistic Strategy Synthesis
    ↓
CREAT-06
Governance + IE Handoff
    ↓
CREAT-07
Integration + Verification + W_CREAT Handoff
```

The most important separation to preserve is:

**`W_STRAT` = qualitative strategic authority and synthesis**
**`S_ALLOC` = bounded allocation reasoning + deterministic quantitative execution**
**`IE` = enterprise-data authority, orchestration authority, and downstream handoff authority**

No additional Strategy sub-agent appears essential from the supplied architecture; **`S_ALLOC` remains the single justified Strategy specialist**.

Some earlier uploaded attachments are no longer directly loadable in this session. I used the Strategy Engine architecture already established from those materials in this project; if you want this plan cross-checked line-by-line against those exact files again, re-upload them.
