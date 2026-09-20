The design is valid with one important conclusion: **keep the six proposed Creative specialists and add no seventh agent at this stage**. The main implementation work is not adding more agents; it is removing the current `W_CREAT → S_COPY` monolith and changing sandbox authorization from worker-level to specialist-level.

## 1. Research synthesis

Checked against current primary guidance on September 20, 2026.

**Workflow architecture.** Anthropic’s agent guidance recommends fixed prompt-chaining for tasks that decompose cleanly, controlled parallelization where subtasks are independent, and evaluator-optimizer loops when clear evaluation criteria exist. That maps well to `RESEARCH → CONCEPT → [COPY || VISUAL] → ADAPT → QA`, with QA as an independent evaluator rather than a generator. ([Anthropic][1])

**Creative diversity.** Google Ads explicitly recommends numerous unique rather than repetitive headlines/descriptions; RSAs currently support up to 15 headlines and four descriptions. This supports producing genuinely different concepts/angles rather than superficial rewrites. ([Google Help][2])

**Platform-native execution.** TikTok currently recommends vertical 9:16, 720p-or-better footage, UI-safe composition, and a hook → body → close structure. Meta similarly emphasizes 9:16 Reels creative, audio, key messages in safe zones, and testing. These requirements justify separating creative generation from `CREAT-ADAPT` and deterministic platform validation. ([TikTok For Business][3])

**Web/editorial quality.** Google Search continues to prioritize original, useful, people-first material and specifically warns against commodity/scaled AI output without added value. Its newer generative-search guidance similarly emphasizes unique viewpoints and non-commodity content. ([Google for Developers][4])

**Sandboxing.** AIO Sandbox exposes shell, file, browser, Jupyter, VS Code and MCP capabilities, but its published quick start still launches with `seccomp=unconfined`. Therefore AIO Sandbox should remain the **execution payload inside your existing hardened isolation boundary**, not be treated as the complete Enterprise OS security boundary. ([GitHub][5])

### Decision classification

**Project-defined:** Model A, IE-only enterprise data access, no W_CREAT sandbox, individual Creative LLMs, fresh specialist sandboxes, tenant isolation, HITL before outbound mutation, W3C PROV lineage.

**Research-backed:** fixed workflow, parallel COPY/VISUAL only, independent QA evaluator, diversified variants, platform-native adaptation, people-first editorial requirements, outer hardening around AIO.

**Remaining assumptions:** separate LLMs may initially use the same provider/model configuration; image generation itself is outside this engine version; exact Research egress domains and QA retry count remain policy configuration.

---

# 2. Final responsibility/access matrix

| Component          | LLM responsibility                                                    | Main input                                                         | Output                                                          | Sandbox / tools                                                | Network            |
| ------------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------- | -------------------------------------------------------------- | ------------------ |
| **W_CREAT**        | Creative planning, stage orchestration, final synthesis               | IE TaskGrant, approved strategy, brand/persona, evidence envelopes | `CreativePlan`, final `CreativePackage` / EvidenceEnvelope      | **None**                                                       | None               |
| **CREAT-RESEARCH** | Select research questions, synthesize authoritative public references | Approved channels, objective, platform scope                       | `ResearchBrief` with citations/spec snapshots/patterns/unknowns | Fresh AIO; browser, citation extraction, source normalization  | **ALLOWLIST** only |
| **CREAT-CONCEPT**  | Message architecture, territories, angles, narrative                  | Strategy + ResearchBrief + brand/evidence                          | `ConceptPack`                                                   | Fresh AIO; schema/dedup/claim-ref checks                       | DENY_ALL           |
| **CREAT-COPY**     | Hooks, headlines, body, captions, CTA variants                        | Approved concepts + claims + voice                                 | `CopyPack`                                                      | Fresh AIO; character/spec/prohibited-term/claim-ref validators | DENY_ALL           |
| **CREAT-VISUAL**   | Art direction, storyboards, shot lists, visual prompts                | Concepts + brand tokens + evidence                                 | `VisualPack`                                                    | Fresh AIO; aspect-ratio/safe-zone/schema validators            | DENY_ALL           |
| **CREAT-ADAPT**    | Rewrite/recompose material natively for approved channels             | Copy + Visual + frozen platform specs                              | `AdaptedCreativePack`, asset matrix, calendar                   | Fresh AIO; channel-spec/format validators                      | DENY_ALL           |
| **CREAT-QA**       | Independent evaluation only                                           | Complete candidate + evidence + strategy + policies                | `QAReport: PASS/REVISE/BLOCK`                                   | Fresh read-only AIO; deterministic validators                  | DENY_ALL           |

### Specialist boundaries

`CREAT-RESEARCH` does **not** replace `W_COMP`, `W_VOICE`, or `W_PROD`.

It can research:

* official platform specifications;
* general creative-format guidance;
* public editorial/creative trends;
* non-enterprise references.

It cannot independently gather competitor intelligence, private customer evidence, product claims, tenant data, or campaign telemetry. Those arrive from IE as approved evidence.

`CREAT-QA` also does not become a regulatory claims engine. It checks whether copy references approved claims; `W_PROD/S_VAL` remains authoritative for whether a claim itself is valid.

---

# 3. Logical/execution flow

```text
W_STRAT
   │ approved holistic strategy
   ▼
Intelligence Engine
   │
   │ bounded Creative TaskGrant
   │ + strategy snapshot
   │ + brand persona
   │ + approved evidence
   │ + policy/channel scope
   ▼
W_CREAT ── own LLM
   │
   │ validate scope + create immutable CreativePlan
   ▼
CREAT-RESEARCH ── own LLM ── fresh AIO ── allowlisted web
   │
   ▼
CREAT-CONCEPT ── own LLM ── fresh AIO ── DENY_ALL
   │
   ├──────────── fork ────────────┐
   ▼                              ▼
CREAT-COPY                    CREAT-VISUAL
own LLM + fresh AIO           own LLM + fresh AIO
DENY_ALL                      DENY_ALL
   │                              │
   └──────────── join ────────────┘
                  │
                  ▼
            CREAT-ADAPT
        own LLM + fresh AIO
              DENY_ALL
                  │
                  ▼
              CREAT-QA
        own LLM + fresh AIO
       read-only / DENY_ALL
           │      │      │
        PASS   REVISE   BLOCK
           │      │      └──→ W_CREAT → IE blocker
           │      │
           │      └──→ predefined responsible stage only
           │           → ADAPT → QA
           ▼
        W_CREAT
     final synthesis
           │
           ▼
          IE
           │
          HITL
           │ signed clearance
           ▼
     Outbound MCP
```

A `REVISE` result should use **predefined reason codes**, for example `COPY`, `VISUAL`, `ADAPT`, or `EVIDENCE`. QA does not choose a new workflow. `EVIDENCE` returns upward to W_CREAT/IE rather than letting QA or Research invent or retrieve enterprise facts.

Set a deterministic retry limit, e.g. `max_revision_attempts` from the grant/policy.

---

# 4. LLM and sandbox boundary model

The important distinction is:

```text
Purpose-scoped LLM reasoning
        │
        │ host-side LlmClient
        │ credentials never leave backend
        ▼
Creative specialist
        │
        │ typed SandboxInvocationMandate
        ▼
Fresh AIO Sandbox
        │
        ├── deterministic tools
        ├── browser only for CREAT-RESEARCH
        └── ephemeral artifacts
```

The **LLM itself should not need provider credentials inside AIO Sandbox**. Each specialist owns an independent `LlmClient` instance/context at the backend boundary; only its tool execution goes into AIO.

That also means siblings never share conversation history. A stage receives only its explicitly typed predecessor artifacts.

Model/provider reuse is acceptable initially:

```text
CREAT-COPY LlmClient instance   ─┐
CREAT-VISUAL LlmClient instance ├─ same configured provider/model allowed
CREAT-QA LlmClient instance     ─┘
```

They remain logically independent by client instance, system identity, prompt contract, context, budget, and provenance identity.

If later you require different actual models per specialist, extend configuration then. It is not required for the first implementation.

---

# 5. Minimal codebase hierarchy

I would make two small additions to your proposed hierarchy because the current code requires them.

```text
backend/app/
├── agents/
│   ├── base.py                                      [MODIFY - MINIMAL]
│   ├── creative_content.py                          [REUSE wrapper]
│   └── creative_content_engine/
│       ├── __init__.py                              [MODIFY]
│       ├── creative_content.py                      [MODIFY]
│       └── subagents/                               [ADD]
│           ├── __init__.py                          [ADD]
│           ├── research.py                          [ADD]
│           ├── concept.py                           [ADD]
│           ├── copy.py                              [ADD]
│           ├── visual.py                            [ADD]
│           ├── adaptation.py                        [ADD]
│           └── quality.py                           [ADD]
│
├── orchestration/
│   ├── dag_scheduler.py                             [REUSE]
│   └── creative_content_workflow.py                 [ADD]
│
├── schemas/
│   ├── agent_contracts.py                           [MODIFY - ADDITIVE]
│   └── sandbox.py                                   [MODIFY - MINIMAL]
│
├── integrations/
│   ├── llm/
│   │   └── client.py                                [REUSE]
│   └── sandbox/
│       ├── capabilities.py                          [MODIFY]
│       ├── client.py                                [MODIFY]
│       ├── micro_tools.py                           [MODIFY]
│       └── sandbox_policy.py                        [MODIFY]
│
└── main.py                                          [MODIFY]

sandbox/docker/hardened/
└── skills/
    └── s-copy/
        ├── SKILL.md                                 [MODIFY]
        └── scripts/run.py                           [MODIFY]

tests/
├── unit/
│   ├── test_creative_content_verification.py        [MODIFY]
│   ├── test_llm_wiring_verification.py              [EXTEND]
│   └── test_creative_workflow.py                    [ADD]
└── integration/
    ├── test_creative_integration.py                 [MODIFY]
    ├── test_model_a_data_access.py                  [EXTEND]
    ├── test_worker_sandbox_boundary.py              [MODIFY]
    └── test_creative_sandbox_boundaries.py          [ADD]
```

`creative_content_workflow.py` is justified rather than extending the canonical `DagScheduler`: the existing scheduler operates on IE-level `CanonicalTaskState` records. Creating fake enterprise tasks for every internal Creative stage would couple internal creative execution to canonical state unnecessarily. The new module should therefore be a **small stateless fixed-DAG executor, not another state machine**.

---

# 6. Exact necessary changes

### `agents/base.py`

Current `BoundedWorkerAgent` assumes:

> every worker owns one sandbox capability and `run()` always invokes it.

That is incompatible with W_CREAT.

Minimal change:

```text
capability: SandboxCapability | None
```

and make the base sandbox-running implementation reject `None`.

`CreativeContentAgent` overrides `run()` with its orchestration path.

Do **not** redesign all worker interfaces.

---

### `creative_content_engine/creative_content.py`

Remove:

```python
capability = SandboxCapability.COPY
```

Remove the direct:

```text
build_payload()
    → operation=generate_variants
    → SandboxClient.invoke(S_COPY)
```

Replace it with:

```text
validate IE grant
validate strategy tenant/scope
freeze CreativeBrief
W_CREAT LLM planning
CreativeContentWorkflow.run(...)
W_CREAT LLM final synthesis
return EvidenceEnvelope
```

Delete all invented defaults, including:

```text
"Validated enterprise performance backed by benchmark testing."
```

and default fabricated strategy/audience/channel behavior.

An absent strategy must not become:

```text
meta, google, tiktok, linkedin, email
```

unless those values actually occur in the authorized grant.

---

### Six `subagents/*.py`

Each specialist gets:

```python
self._llm_client
self._sandbox_client
SPECIALIST_ID
```

and a narrow method such as:

```python
async def run(
    grant: TaskGrant,
    input_artifact: ...,
) -> TypedStageResult:
```

Every sandbox mandate includes:

```text
worker_role = W_CREAT
specialist_id = CREAT_...
task_id
tenant_id
operation
allowed_tools
network_policy
expected_output_schema
provenance_context
```

The sub-agent cannot accept arbitrary tools proposed by its LLM.

---

### `creative_content_workflow.py`

Hard-code the graph:

```text
RESEARCH
  ↓
CONCEPT
  ↓
COPY || VISUAL
  ↓ join
ADAPT
  ↓
QA
```

Only COPY and VISUAL use `asyncio.gather()`.

Models cannot add, skip, reorder, or invent stages.

Any revision path must exist in a static transition table.

---

### `schemas/agent_contracts.py`

Reuse the existing `CreativePackage`, `AdCopyVariant`, `VisualBrief`, `SocialPostVariant`, and `ContentScheduleItem`.

Add optional typed fields only where final traceability currently has no home, for example:

```text
research_references
concept_refs
qa_status
qa_findings
platform_spec_versions
```

Do not create a separate Creative persistence schema.

---

### `schemas/sandbox.py`

The existing structures are already close to what you need:

* `specialist_id`
* `SandboxIdentity`
* `SandboxCapabilityGrant.subagent_id`
* `allowed_tools`
* `allowed_operations`
* network policy
* expected output schema.

Reuse them.

One worthwhile hardening change: bind an egress grant to `specialist_id` as well as W_CREAT/task/capability. Otherwise a Research egress grant is insufficiently tied to the specialist that is allowed to use it.

---

### `sandbox/capabilities.py`

This needs the largest authorization-model adjustment.

Current model is effectively:

```text
W_CREAT → S_COPY
```

Replace Creative authorization with:

```text
W_CREAT itself → NO SANDBOX CAPABILITY

CREAT-RESEARCH → creative sandbox grant
CREAT-CONCEPT  → creative sandbox grant
CREAT-COPY     → creative sandbox grant
CREAT-VISUAL   → creative sandbox grant
CREAT-ADAPT    → creative sandbox grant
CREAT-QA       → creative sandbox grant
```

The existing coarse `S_COPY` capability can remain temporarily for compatibility, but access must additionally validate `specialist_id`.

That avoids creating six new global `SandboxCapability` enums.

For example:

```text
CREAT-RESEARCH
  allowed_operations = research_sources, validate_citations
  allowed_tools      = browser, citation_extractor
  network            = ALLOWLIST

CREAT-COPY
  allowed_operations = validate_copy, validate_claim_refs, dedupe
  allowed_tools      = text_validator, claim_ref_checker
  network            = DISABLED

CREAT-QA
  allowed_operations = validate_package
  allowed_tools      = format_validator, policy_linter, dedupe
  network            = DISABLED
```

A mandate with `W_CREAT + S_COPY` and no recognized specialist ID must be rejected.

---

### `sandbox/client.py`

Current live repository behavior has an important gap:

* remote AIO execution is explicitly implemented for `S_ALLOC`;
* there are special paths for `S_CODE` and `S_SCRAPE`;
* Creative `S_COPY` has no corresponding remote AIO implementation;
* if no remote endpoint exists, execution drops to local `dispatch_micro_tool()`.

That must change for Creative.

Add generic specialist execution using the AIO file/shell/browser interfaces instead of hard-coding each Creative operation.

For production Creative execution:

```text
no AIO endpoint
    → FAIL CLOSED
```

not:

```text
no AIO endpoint
    → execute Creative tool in backend process
```

The current client also caches `_sandbox`. A cached client plus a task workspace is **not evidence by itself that every specialist attempt has a fresh isolated AIO runtime**.

The final implementation must connect:

```text
SandboxIdentity
→ provision
→ execute
→ seal outputs
→ destroy
```

to the actual outer sandbox/container lifecycle.

---

### `sandbox_policy.py`

It currently describes itself mainly as a W_DEV control plane.

Generalize engine identity validation to support:

```text
engine_id = W_CREAT
step_id   = CREAT-COPY / CREAT-QA / ...
attempt_id
```

Keep:

* fresh workspace;
* non-root;
* cap drop;
* no-new-privileges;
* cgroups;
* seccomp;
* ephemeral storage;
* credential revocation;
* deny-all networking;
* anti-SSRF.

Only Research receives an allowlist policy.

---

### `s-copy/SKILL.md` and `run.py`

The current S_COPY implementation is obsolete as a Creative generator.

It currently combines:

```text
claim parsing
+ fallback evidence fabrication
+ hook generation
+ hook ranking
+ copy generation
+ channel adaptation
+ visual brief generation
+ social generation
+ schedule generation
+ compliance checking
+ package assembly
```

That duplicates almost the entire proposed Creative Engine.

Strip it down to deterministic utilities such as:

```text
validate_character_limits
validate_required_fields
validate_claim_references
screen_prohibited_terms
validate_aspect_ratio
validate_safe_zone_metadata
deduplicate_variants
validate_platform_format
validate_output_schema
```

Do **not** keep templates such as:

```text
"Why leading brands..."
"The proven approach to 3x..."
"The hidden secret to 3x..."
```

as generation logic.

Do not let the sandbox script choose funnel stages, invent schedules, choose claims, or produce art direction.

---

### `llm/client.py`

**REUSE as-is initially.**

It is already provider-neutral and keeps credentials host-side.

The required isolation comes from separate instances:

```text
w_creat_llm
research_llm
concept_llm
copy_llm
visual_llm
adapt_llm
qa_llm
```

They may use the same `LlmSettings` initially.

---

### `main.py`

Current composition shares the main `llm_client` broadly and only creates a separate S_ALLOC instance.

For Creative, construct seven independent clients and inject them explicitly.

Also remove the current assumption:

```python
assert get_capability_for_role(role) == agent_class.capability
```

for W_CREAT, because W_CREAT intentionally has no capability.

The six Creative specialists, workflow, and W_CREAT coordinator should be composed here.

---

# 7. Behaviors that must be removed

The repository inspection found four concrete incompatibilities.

### A. Direct W_CREAT sandbox coupling

Current:

```python
class CreativeContentAgent(BoundedWorkerAgent):
    capability = SandboxCapability.COPY
```

Remove it.

The uploaded architecture documents also still say W_CREAT directly executes S_COPY and that all seven workers have sandbox access. That is now superseded **for W_CREAT only** by your new project requirement.

### B. Fabricated product evidence

Both current `creative_content.py` and `s-copy/scripts/run.py` can invent:

```text
Validated enterprise performance backed by benchmark testing.
```

This must be deleted entirely.

### C. Fabricated strategy/scope defaults

Current Creative behavior can manufacture:

```text
channels = meta/google/tiktok/linkedin/email
target_audience = generic growth audience
```

when dependencies are absent.

Delete these fallbacks.

Scope must originate from IE/W_STRAT.

### D. Monolithic generative S_COPY

The existing S_COPY generates copy, hooks, visuals, social content and schedules itself.

After this redesign, **LLM specialists generate; S_COPY-style sandbox tools validate and transform deterministic properties**.

That is the central migration.

---

# 8. Required tests

At minimum, acceptance should prove:

| Test                                                      | Expected result                       |
| --------------------------------------------------------- | ------------------------------------- |
| W_CREAT tries `SandboxClient.invoke()`                    | **DENIED**                            |
| `get_capability_for_role(W_CREAT)`                        | no direct capability                  |
| Unknown Creative specialist invokes S_COPY                | **DENIED**                            |
| CREAT-RESEARCH uses approved domain                       | allowed                               |
| CREAT-RESEARCH uses unapproved/private/internal domain    | **DENIED**                            |
| COPY/VISUAL/ADAPT/QA request network                      | **DENIED**                            |
| Research egress grant reused by COPY                      | **DENIED**                            |
| Six specialists instantiated with same `LlmClient` object | test fails                            |
| Six separate LLM instances                                | passes                                |
| Strategy absent                                           | **fails closed**                      |
| Unsupported claim absent from evidence                    | excluded/BLOCKED, never invented      |
| Strategy allows only LinkedIn + Meta                      | no TikTok/Google/etc. output          |
| COPY starts before CONCEPT completes                      | test fails                            |
| COPY and VISUAL run after CONCEPT concurrently            | passes                                |
| ADAPT starts before both branches finish                  | test fails                            |
| QA modifies candidate artifact                            | test fails                            |
| QA returns PASS/REVISE/BLOCK + findings                   | passes                                |
| Creative specialist imports RAG/DB/MCP/CMS                | test fails                            |
| AIO unavailable in production Creative path               | **fails closed**                      |
| Final external publish without HITL signature             | existing outbound test remains denied |
| Provenance missing specialist/model/tool/artifact IDs     | test fails                            |

Do **not** change the generic worker-sandbox test merely to continue asserting that all seven top-level workers use the sandbox. That test now needs to distinguish:

```text
W_CREAT       → must NOT sandbox
CREAT-*       → must sandbox
other workers → existing policy unchanged
```

---

## Remaining evidence gaps / TBDs

1. **Fresh AIO runtime semantics.** The current repository proves task-scoped workspaces and exposes provisioning contracts, but I did not find evidence that generic `SandboxClient.invoke()` actually creates a new AIO container/micro-VM for every Creative attempt. This needs implementation/infrastructure verification before calling the acceptance criterion satisfied.

2. **Research egress allowlist.** Decide the permitted search/vendor domains and who versions that list. Avoid `*`.

3. **LLM model assignment.** Separate LLM instances are required; separate actual model/provider configurations are not yet specified. No additional configuration hierarchy is necessary until that decision is made.

4. **Visual generation.** `CREAT-VISUAL` should currently produce direction, storyboards, prompts and briefs. Actual image/video generation is not supported by the supplied architecture and should not be silently added.

5. **QA retry policy.** Define the maximum revision count and which QA finding codes route to COPY, VISUAL or ADAPT.

6. **Platform-spec freshness.** Dimensions, limits and placement rules change. Treat the Research output as a dated/versioned platform-spec snapshot rather than permanently hard-coding today's values.

7. **Architecture documentation.** `Final-Level Full Architecture.md`, `Backend Hierarchy.md`, and the flowchart still encode the older `W_CREAT → S_COPY` direct-sandbox model. Once this design is adopted, those diagrams/tables should be revised to show `W_CREAT → Creative specialists → sandbox`.

### Final architecture decision

```text
Keep:
  CREAT-RESEARCH
  CREAT-CONCEPT
  CREAT-COPY
  CREAT-VISUAL
  CREAT-ADAPT
  CREAT-QA

Add no additional Creative agent.

W_CREAT:
  own LLM = YES
  sandbox = NO
  enterprise data = IE-mediated only
  orchestration = deterministic
  publication = NO

Creative specialists:
  own LLM = YES, independently instantiated
  fresh AIO sandbox = YES
  direct enterprise access = NO
  outbound credentials = NO

S_COPY:
  monolithic generator = REMOVE
  deterministic creative utility boundary = RETAIN/REFACTOR
```

This preserves the Enterprise OS Model-A hierarchy while making the Creative Engine substantially cleaner: **strategy remains upstream, reasoning is purpose-separated, generation and evaluation are independent, execution authority monotonically decreases, and no Creative component can invent evidence or publish autonomously.**

[1]: https://www.anthropic.com/engineering/building-effective-agents?subjects=alignment&utm_source=chatgpt.com "Building Effective AI Agents \ Anthropic"
[2]: https://support.google.com/google-ads/answer/6167122?hl=en&utm_source=chatgpt.com "Best practices for creating effective responsive search ads - Google Ads Help"
[3]: https://ads.tiktok.com/business/en/creative-codes?utm_source=chatgpt.com "TikTok Creative Codes: 6 Principles for Creating Effective Ads"
[4]: https://developers.google.com/search/docs/fundamentals/creating-helpful-content?utm_source=chatgpt.com "Creating Helpful, Reliable, People-First Content | Google Search Central  |  Documentation  |  Google for Developers"
[5]: https://github.com/agent-infra/sandbox?utm_source=chatgpt.com "GitHub - agent-infra/sandbox: All-in-One Sandbox for AI Agents that combines Browser, Shell, File, MCP and VSCode Server in a single Docker container. · GitHub"
