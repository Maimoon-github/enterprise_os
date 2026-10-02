# Strategy Engine validated change package

This package is based on the live `Maimoon-github/enterprise_os` repository plus the supplied hierarchy/architecture files and current primary-source research.

## Write limitation

The connected GitHub App allowed repository reads but rejected branch creation with HTTP 403 (`Resource not accessible by integration`). Therefore these changes were validated locally but were not pushed to GitHub.

## Validated architecture decision

Keep one Strategy specialist only:

- `W_STRAT`: Layer-5 strategy/orchestration worker with its own purpose-scoped LLM.
- `S_ALLOC`: Layer-6 media/budget specialist with a separate purpose-scoped reasoning LLM plus deterministic sandbox tools.
- Do **not** add separate MMM, funnel, campaign, or verifier agents yet. Those are tools/functions inside `S_ALLOC` until evidence shows they need independent agent lifecycles.

The LLM is advisory. Numerical allocation, budget caps, constraints, response curves, and model diagnostics remain deterministic sandbox behavior.

## Required repository edits

### Add

1. `backend/app/agents/strategy_engine/subagents/__init__.py`
2. `backend/app/agents/strategy_engine/subagents/allocation.py`
3. Strategy-specific tests for separate S_ALLOC reasoning and no reverse dependency.

### Modify

1. `backend/app/agents/strategy_engine/strategy.py`
   - Keep `W_STRAT` as the parent strategy/synthesis worker.
   - Delegate S_ALLOC work only through the existing typed sandbox/specialist mandate interface; do not give S_ALLOC a reference to `StrategyAgent`.
   - Add only bounded S_ALLOC conclusions (`scenario_emphasis`, KPI priorities, assumptions, risks) to the returned specialist result/evidence.
   - Preserve separate LLM provenance.
   - Remove fabricated fallback product claims, customer objections, and competitor evidence.
   - Intersect requested channels with `TenantScope.allowed_channels`; never broaden scope from context.
   - Pass optional `kpi_name`, `performance_telemetry`, `media_history`, `control_variables`,
     `incrementality_evidence`, and `channel_constraints`.
   - Clamp requested spend to the IE-authorized budget cap.

2. `backend/app/integrations/sandbox/capabilities.py`
   - Keep `W_STRAT -> S_ALLOC`.
   - Add operations: `model_media_mix`, `simulate_funnel`.
   - Add tools: `media_mix_modeler`, `budget_allocator_tool`, `funnel_simulator`,
     `optimization_modeler`.
   - Keep existing aliases for backward compatibility.
   - Keep `NetworkPolicy.DISABLED`.

3. `backend/app/integrations/sandbox/micro_tools.py`
   - Replace ROAS-only proportional allocation with a deterministic, constrained,
     diminishing-returns planning model.
   - Parse optional media history, uncertainty, saturation, incrementality calibration,
     and channel bounds.
   - Allocate against current marginal return instead of historical ROAS alone.
   - Emit `marginal_roas`, `response_curves`, `model_diagnostics`, scenario assumptions,
     and unallocated contingency.
   - Explicitly label the current model as a planning proxy, not a fitted causal MMM.

4. `sandbox/docker/hardened/skills/s-alloc/scripts/run.py`
   - Mirror the same deterministic S_ALLOC behavior for the actual isolated runtime.

5. `backend/app/integrations/sandbox/client.py`
   - When a sandbox endpoint is configured, execute `S_ALLOC` through the remote AIO shell using the mounted `/home/gem/skills/s-alloc/scripts/run.py` skill.
   - Do not silently fall back to in-process execution after a configured remote sandbox fails; fail closed.
   - Permit the existing local micro-tool fallback only when no sandbox endpoint/client is configured (tests/development compatibility).

6. `sandbox/docker/hardened/skills/s-alloc/SKILL.md`
   - Use the contract included in this package.

7. `backend/app/main.py`
   - Create an independent LLM client instance for W_STRAT reasoning.
   - Do not pass the S_ALLOC LLM object into `W_STRAT`; register/inject it at the specialist-dispatch boundary so S_ALLOC remains interface-isolated from its parent.
   - Reuse the existing provider-neutral settings; do not add provider dependencies yet.
   - Close each client at shutdown.
   - The default may use the same configured model/provider; the isolation requirement is a distinct purpose-scoped client/context. Per-agent model selection can be added later only if required.

8. Tests
   - Extend `test_strategy_allocation_verification.py` with saturation/mROI/constraint/
     diagnostics/no-fabrication cases.
   - Extend `test_worker_sandbox_boundary.py` / negative security tests to assert:
       * `S_ALLOC` network disabled;
       * no direct RAG/persistence/IE access;
       * no import/dependency on `W_STRAT`;
       * allowed channels cannot exceed tenant scope.
   - Add a unit test confirming W_STRAT and S_ALLOC use distinct injected LLM client objects.

## S_ALLOC algorithm supplied here

`/s_alloc_core.py` is the tested reference implementation for replacing the current
`execute_s_alloc` core and mirroring into sandbox `run.py`.

It uses:
- a saturating response proxy;
- marginal return for iterative budget placement;
- uncertainty penalty;
- explicit min/max channel constraints;
- response-curve samples;
- model-health diagnostics;
- scenario selection from bounded objective/S_ALLOC reasoning;
- no fabricated evidence.

This is intentionally **not** a full causal MMM implementation and adds no Meridian/Robyn dependency.

## Local validation performed

`pytest -q test_s_alloc_core.py`

Result: **5 passed**

Covered:
1. authorized budget ceiling and channel constraints;
2. saturation causing budget to move away from an otherwise higher historical-ROAS channel;
3. explicit `REVIEW` diagnostics and `causal_mmm=false`;
4. bounded S_ALLOC LLM scenario emphasis without budget-cap override;
5. no fabricated product/competitor evidence.

`python -m py_compile` also passed for:
- `subagents/allocation.py`
- `s_alloc_core.py`

Full repository test execution was not possible because the GitHub integration exposes repository content through API tools rather than a writable/cloneable local checkout, and repository branch creation was denied by the connected GitHub App.
