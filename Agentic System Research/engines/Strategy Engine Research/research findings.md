## 1. Research synthesis

The supplied architecture fixes the core boundary: `W_STRAT` is a Layer-5 Marketing Worker using `media_mix_modeler`, `budget_allocator_tool`, `funnel_simulator`, and `system:marketing-strategy`; its data access is read-only through IE and its sandbox capability is `S_ALLOC`.  Model A further requires workers/sub-agents to obtain enterprise data through IE rather than directly querying RAG, databases, CMS, or memory. 

Current MMM research supports changing the existing ROAS-weighted allocation logic. Google Meridian distinguishes **ROI** from **marginal ROI**, with mROI specifically useful for deciding where the next unit of budget should go; its optimizer uses channel constraints, scenarios, response curves, and target ROI/mROI rather than simple historical-ROAS ranking. ([Google for Developers][1])

A model should also expose diagnostics before its output is treated as causal. Meridian explicitly requires post-fit health checks and distinguishes `PASS`, `REVIEW`, and `FAIL`; the present Enterprise OS `S_ALLOC` implementation is not a fitted causal MMM, so it should identify itself as a planning/response-curve proxy rather than imply causal certainty. ([Google for Developers][2])

For brand development, upper-funnel activity should not be evaluated only as immediate conversion media. Meridian's full-funnel approach explicitly models brand marketing → brand equity → final KPI, supporting separate brand-building and lower-funnel objectives inside Strategy planning. ([Google for Developers][3])

The research does **not** justify creating multiple new Strategy agents. Both Anthropic and OpenAI recommend adding multi-agent complexity only where separate autonomous reasoning materially improves outcomes; predictable numerical work is better retained as deterministic tooling. ([Anthropic][4])

AIO Sandbox supplies browser, shell, file and shared-workspace capabilities, but capability availability does not mean every specialist should receive all of them. `S_ALLOC` requires computation/filesystem execution, not web browsing, so its network policy should remain disabled. ([GitHub][5])

---

# 2. Verified vs. inferred decisions

| Decision                                           | Status                                         | Conclusion                |
| -------------------------------------------------- | ---------------------------------------------- | ------------------------- |
| `W_STRAT` is Layer-5 Marketing Worker              | **Project-defined**                            | Preserve                  |
| IE-only read access                                | **Project-defined**                            | Preserve Model A          |
| `W_STRAT → S_ALLOC`                                | **Project-defined**                            | Preserve                  |
| `S_ALLOC` executes in sandbox                      | **Project-defined**                            | Enforce in actual runtime |
| Separate purpose-scoped LLM for `W_STRAT`          | **User requirement + existing worker pattern** | Required                  |
| Separate purpose-scoped LLM for `S_ALLOC`          | **User requirement + validated design**        | Required                  |
| Additional Strategy agents                         | **Not supported**                              | Do not add                |
| MMM/funnel/budget functions as deterministic tools | **Research-backed inference**                  | Keep under `S_ALLOC`      |
| mROI/response curves/channel constraints           | **Research-backed**                            | Add                       |
| Causal MMM claim                                   | **Not supported by current code**              | Explicitly avoid          |
| Strategy browser access                            | **Not required**                               | Keep disabled             |
| Direct `S_ALLOC → W_STRAT` access                  | **Explicitly prohibited**                      | Enforce                   |

The project already describes worker → sandbox mandates and sandbox → worker sanitized results. 

---

# 3. Final Strategy Engine / sub-agent map

### `W_STRAT — Strategy Engine`

Owns:

* strategic objective and KPI interpretation;
* brand and funnel strategy;
* channel-role definition;
* campaign architecture;
* scenario framing;
* synthesis of modeled evidence;
* media/budget-plan proposal;
* assumptions, risks and confidence;
* creation of the final `EvidenceEnvelope`.

It does **not** own competitor scraping, customer-feedback parsing, claim validation, creative generation, attribution learning, persistence, campaign deployment, or external writes. Those responsibilities already belong to other workers or IE-controlled boundaries. 

### `S_ALLOC — Media & Budget Allocation Specialist`

This is the **only additional Strategy sub-agent currently justified**.

Its purpose-scoped LLM handles:

* interpreting the media-planning subtask;
* KPI prioritization;
* scenario emphasis;
* modeling assumptions;
* risk identification;
* interpreting deterministic model outputs.

Its LLM must **not**:

* calculate or authorize final spend;
* increase budget ceilings;
* expand allowed channels;
* grant itself tools;
* access RAG/database/IE internals;
* call `W_STRAT`;
* execute campaign changes.

Its deterministic tools handle:

* `media_mix_modeler`;
* `budget_allocator_tool`;
* `funnel_simulator`;
* `optimization_modeler`;
* response-curve calculation;
* marginal-return calculation;
* constraint enforcement.

---

# 4. Tools / LLM / I/O / access matrix

| Component               | Reasoning                   | Main inputs                                                                     | Tools                           | Outputs                                                                 | Enterprise data  | Sandbox               |
| ----------------------- | --------------------------- | ------------------------------------------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------- | ---------------- | --------------------- |
| `W_STRAT`               | Own purpose-scoped LLM      | IE grant, brand context, validated market/customer/product/performance evidence | `system:marketing-strategy`     | strategy brief, campaign architecture, strategy plan, evidence envelope | Read-only via IE | Can request `S_ALLOC` |
| `S_ALLOC`               | Separate purpose-scoped LLM | Serialized bounded strategy mandate                                             | MMM/funnel/allocation tools     | assumptions, model request, interpreted model results                   | None directly    | Yes                   |
| `media_mix_modeler`     | None                        | KPI, media history, spend, controls, priors                                     | deterministic/statistical model | response estimates, uncertainty, diagnostics                            | None             | Yes                   |
| `budget_allocator_tool` | None                        | response curves, mROI, bounds, total budget                                     | constrained optimization        | proposed allocation                                                     | None             | Yes                   |
| `funnel_simulator`      | None                        | funnel assumptions, channel roles, conversion inputs                            | deterministic simulation        | funnel scenarios                                                        | None             | Yes                   |
| `optimization_modeler`  | None                        | mathematical objective + constraints                                            | solver/model                    | numeric solution/diagnostics                                            | None             | Yes                   |

A W3C PROV representation naturally maps task/context/model artifacts to `Entity`, model and sandbox runs to `Activity`, and IE/W_STRAT/S_ALLOC/reviewer to `Agent`. ([W3C][6])

---

# 5. Logical and execution flow

```text
Brand / Business Objective
          │
          ▼
Intelligence Engine
  policy + CTS + RAG + brand context
          │
          │ Bounded TaskGrant
          ▼
W_STRAT
  own LLM:
  strategy interpretation
  KPI / funnel / channel reasoning
          │
          │ typed specialist mandate
          ▼
Sandbox / Specialist Dispatch Boundary
          │
          ▼
S_ALLOC
  own purpose-scoped LLM
  assumptions / KPI priorities / scenario intent
          │
          ▼
aio-sandbox
  ├─ media_mix_modeler
  ├─ response/mROI model
  ├─ funnel_simulator
  ├─ budget_allocator_tool
  └─ optimization_modeler
          │
          ▼
Sanitized modeled result
  + diagnostics
  + assumptions
  + uncertainty
  + constraints
          │
          ▼
W_STRAT strategic synthesis
          │
          ▼
EvidenceEnvelope
          │
          ▼
IE
  provenance / state / HITL
          │
          ▼
HITL approval for spend/action
          │
          ▼
Outbound MCP
```

There is no `S_ALLOC → W_STRAT` API/import/callback path. Communication is through bounded serialized mandates/results.

---

# 6. Sandbox/security boundary

The existing project already specifies ephemeral isolation, deny-by-default egress and sandbox execution for specialist tools.  The repository tree also already contains hardened seccomp/egress infrastructure and an `s-alloc` skill. 

For `S_ALLOC`:

```text
Allowed
✓ task-scoped Python computation
✓ approved S_ALLOC scripts
✓ task-scoped /workspace files
✓ deterministic modeling
✓ structured sanitized output

Denied
✗ enterprise DB
✗ Agentic RAG
✗ IE internal API
✗ W_STRAT module/API
✗ ad/social platform credentials
✗ backend source filesystem
✗ sibling sandbox workspaces
✗ arbitrary network access
✗ browser/CDP/VNC by default
```

One important live-code issue was found: the current `SandboxClient` uses remote AIO interfaces for some capabilities but computational specialists including `S_ALLOC` ultimately fall back to the in-process `dispatch_micro_tool`. That does not fully satisfy the stated architecture.

**Required correction:** when `SANDBOX_ENDPOINT` is configured, `S_ALLOC` should run the mounted:

```text
/home/gem/skills/s-alloc/scripts/run.py
```

through the AIO shell using task-scoped `/workspace` input/output. A configured sandbox failure should fail closed. Local in-process execution should remain only as test/development fallback when no sandbox endpoint is configured.

---

# 7. Final minimal hierarchy

```text
backend/
├── app/
│   ├── agents/
│   │   └── strategy_engine/
│   │       ├── __init__.py
│   │       ├── strategy.py                         [MODIFY]
│   │       └── subagents/
│   │           ├── __init__.py                     [ADD]
│   │           └── allocation.py                   [ADD]
│   │
│   ├── integrations/
│   │   └── sandbox/
│   │       ├── capabilities.py                     [MODIFY]
│   │       ├── client.py                           [MODIFY]
│   │       ├── micro_tools.py                      [MODIFY]
│   │       └── sandbox_policy.py                   [REUSE]
│   │
│   ├── schemas/
│   │   ├── agent_contracts.py                      [REUSE]
│   │   └── sandbox.py                              [REUSE]
│   │
│   ├── orchestration/
│   │   ├── intelligence_engine.py                  [REUSE]
│   │   ├── context_assembly.py                     [REUSE]
│   │   └── hitl_preview_generator.py               [REUSE]
│   │
│   └── main.py                                     [MODIFY]
│
└── tests/
    ├── unit/
    │   ├── test_strategy_allocation_verification.py [EXTEND]
    │   ├── test_specialist_micro_tools.py            [EXTEND]
    │   └── test_strategy_subagent_reasoning.py       [ADD]
    └── integration/
        ├── test_strategy_integration.py              [EXTEND]
        ├── test_worker_sandbox_boundary.py           [EXTEND]
        ├── test_model_a_data_access.py               [EXTEND]
        └── test_security_boundaries_negative.py      [EXTEND]

sandbox/
└── docker/
    └── hardened/
        └── skills/
            └── s-alloc/
                ├── SKILL.md                          [MODIFY]
                └── scripts/
                    └── run.py                        [MODIFY]
```

This extends the repository's existing `strategy_engine/strategy.py` structure without adding parallel Strategy services, repositories or state machines. 

---

# 8. Exact minimum code changes

**`strategy.py`**

* remove fabricated fallback clinical claims, objections and competitor records;
* fail closed or explicitly mark missing evidence instead;
* prevent `context["channels"]` from expanding `TenantScope.allowed_channels`;
* cap requested spend against IE-authorized budget;
* pass KPI, media history/performance telemetry, controls, incrementality evidence and channel constraints where available;
* keep strategic synthesis in `W_STRAT`.

**`subagents/allocation.py`**

* introduce the independently scoped `S_ALLOC` reasoning contract;
* no import/reference to `StrategyAgent`;
* output only KPI priorities, scenario emphasis, assumptions, risks and confidence.

**`capabilities.py`**

* retain `W_STRAT → S_ALLOC`;
* add canonical operations such as `model_media_mix` and `simulate_funnel`;
* authorize the already specified project tools;
* retain old aliases for compatibility;
* keep network `DISABLED`.

**`micro_tools.py` and `s-alloc/scripts/run.py`**

* replace naive proportional ROAS allocation with constrained diminishing-return/mROI allocation;
* support channel lower/upper bounds;
* expose response curves and marginal returns;
* propagate uncertainty;
* emit health/model diagnostics;
* label output a planning proxy when no fitted causal MMM exists.

**`sandbox/client.py`**

* execute configured `S_ALLOC` jobs inside AIO Sandbox instead of silently running them in the backend process.

**`main.py`**

* use distinct purpose-scoped LLM client instances for W_STRAT and S_ALLOC;
* register/inject the S_ALLOC LLM at the specialist-dispatch boundary, not as a reverse dependency on `W_STRAT`;
* no new LLM provider dependency is required.

No Strategy-specific database, RAG controller, MCP gateway, persistence service, browser service, repository, or state machine should be added.

---

# 9. Implementation and test results

I prepared a local validated implementation package against the live `Maimoon-github/enterprise_os` code.

Implemented in the patch package:

* `S_ALLOC` purpose-scoped LLM reasoning contract;
* no `StrategyAgent` dependency;
* deterministic response-curve/mROI allocation reference implementation;
* budget and channel constraints;
* saturation handling;
* model diagnostics;
* explicit non-causal-model labeling;
* no fabricated claims/competitor evidence;
* updated `S_ALLOC` skill contract;
* AIO remote-execution integration guidance.

Focused tests executed locally:

```text
pytest -q test_s_alloc_core.py
5 passed
```

The tests covered:

1. authorized budget ceiling and channel constraints;
2. saturation causing allocation to move away from an otherwise higher historical-ROAS channel;
3. explicit model-health `REVIEW` status and `causal_mmm = false`;
4. S_ALLOC LLM scenario advice being unable to override budget authority;
5. absence of fabricated product/competitor evidence.

Python compilation checks also passed for the new sub-agent reasoning module and deterministic S_ALLOC reference implementation.

**Repository push status:** no repository files were committed. I attempted to create a dedicated GitHub branch, but the connected GitHub App returned HTTP `403 Resource not accessible by integration`. Therefore I did not mutate `main`.

[Download the validated Strategy Engine patch bundle](sandbox:/mnt/data/strategy_engine_validated_patch.zip)

---

# 10. Remaining evidence gaps

1. **Per-agent model selection:** the repository currently has one shared `LlmSettings`. Separate LLM *instances/context boundaries* can be introduced without new configuration. Separate providers/models per agent should only be added if that becomes an explicit deployment requirement.

2. **True causal MMM:** it is not currently implemented. The proposed improvement is deliberately a constrained response-curve planning model. A genuine causal MMM requires sufficient longitudinal media/KPI/control data, model fitting, calibration and health diagnostics; Meridian/Robyn should remain references rather than dependencies.

3. **Incrementality evidence:** when experiments are available, they should become IE-mediated calibration evidence rather than being independently fetched by `S_ALLOC`.

4. **AIO SDK runtime verification:** the repository pins AIO Sandbox and exposes shell/file interfaces, but the proposed remote `S_ALLOC` dispatch must still be exercised against the actual deployed SDK/container before merge.

5. **Full regression suite:** it could not be executed because the connected GitHub integration exposes repository contents but did not permit creation of a writable branch/local checkout. The focused local Strategy tests passed; full repository/CI validation remains required before merge.

[1]: https://developers.google.com/meridian/docs/advanced-modeling/how-to-choose-treatment-prior-types "https://developers.google.com/meridian/docs/advanced-modeling/how-to-choose-treatment-prior-types"
[2]: https://developers.google.com/meridian/docs/post-modeling/health-checks "https://developers.google.com/meridian/docs/post-modeling/health-checks"
[3]: https://developers.google.com/meridian/docs/advanced-modeling/full-funnel?authuser=00 "https://developers.google.com/meridian/docs/advanced-modeling/full-funnel?authuser=00"
[4]: https://www.anthropic.com/engineering/building-effective-agents "https://www.anthropic.com/engineering/building-effective-agents"
[5]: https://github.com/agent-infra/sandbox "https://github.com/agent-infra/sandbox"
[6]: https://www.w3.org/TR/prov-o/ "https://www.w3.org/TR/prov-o/"
