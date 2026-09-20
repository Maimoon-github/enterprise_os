# Creative Engine (`W_CREAT`) — Validated Architecture and Minimal Implementation Delta

**Research/validation date:** September 20, 2026

## 1. Research synthesis

### Agent workflow architecture

The proposed fixed workflow is appropriate:

```text
W_CREAT plan
   ↓
RESEARCH
   ↓
CONCEPT
   ↓
COPY ─────┐
          ├─ parallel
VISUAL ───┘
   ↓
ADAPT
   ↓
QA
   ↓
W_CREAT synthesis
   ↓
IE
```

Anthropic distinguishes sequential chaining, parallelization, and evaluator-optimizer workflows, recommending parallel execution when subtasks are independent and separate evaluation when clear quality criteria exist. That directly supports parallel `COPY || VISUAL` and an independent `QA` stage.

OpenAI similarly recommends avoiding multi-agent complexity unless prompt/tool boundaries justify it, while emphasizing explicit tools, instructions, guardrails, tracing, and human intervention.

**Conclusion:** research does not independently prescribe “six agents.” The six-agent design is justified because Enterprise OS already requires independent purpose-scoped LLM identities, and these six responsibilities have materially different contexts, outputs, tool surfaces, trust boundaries, or evaluator roles. No seventh agent is justified.

### Creative diversity

Google Ads recommends unique rather than repetitive responsive-search assets and currently supports up to 15 headlines and four descriptions per RSA.

Therefore:

* variants must differ by angle, benefit, tension, proof framing, narrative, or CTA—not just synonyms;
* deterministic deduplication belongs in a microtool;
* semantic/conceptual distinctness belongs in Creative QA.

### Platform-native adaptation

Platform rules materially differ, which strongly justifies `CREAT-ADAPT`.

TikTok's current guidance favors vertical 9:16 creative, preserving UI-safe areas and using a hook → body → close structure. Its June 2026 in-feed specification also makes dimensions and safe-zone behavior format-dependent.

Meta recommends native Reels creative using 9:16 video, audio, and important elements inside safe zones.

YouTube recommends vertical 9:16 assets for Shorts, while its ad specifications define format-specific resolutions, safe zones, CTA behavior, and text requirements.

LinkedIn has its own image ratios and text limits; for example, its current single-image guidance recommends 4:5 for vertical assets and provides separate introductory-text, headline, and description limits.

**Conclusion:** CONCEPT/COPY/VISUAL should not hard-code every final platform treatment. `CREAT-ADAPT` should consume a frozen, cited platform-spec snapshot and produce channel-native variants.

### Editorial/web quality

Google continues to emphasize original, useful, people-first material rather than mass-produced commodity content. Its generative-AI guidance warns that scaled generation without added user value can violate scaled-content-abuse policies.

Its newer generative-search guidance specifically emphasizes unique viewpoints and non-commodity content rather than simply recycling material already available online.

Therefore web-content QA should evaluate:

* substantive value;
* originality against supplied/reference material;
* evidence and factual accuracy;
* audience usefulness;
* excessive templating or near-duplicate generation.

It should **not** optimize for arbitrary word counts or generate pages merely to cover query permutations.

### Evaluation

OpenAI's current agent-evaluation guidance recommends traces for finding workflow-level failures—including bad tool selection, incorrect handoffs, instruction violations, and regressions—and repeatable datasets/evals once desired behavior is defined.

Model graders are explicitly separate evaluators, and their quality should itself be tested against trusted human judgments.

This supports `CREAT-QA` as a separate LLM identity rather than asking COPY/VISUAL to approve their own work.

### Sandboxed execution

AIO Sandbox exposes browser, shell, file, Jupyter, VS Code, and MCP capabilities, but its published quick start still demonstrates `seccomp=unconfined`.

Docker's current security guidance describes seccomp as an important least-privilege layer and specifically recommends against disabling the default seccomp profile. Namespaces, cgroups, reduced capabilities, and external network controls remain separate security mechanisms.

**Conclusion:** your constraint is correct:

> AIO Sandbox is the execution payload, not the Enterprise OS security boundary.

The existing hardened container/micro-virtualization, seccomp, capabilities, namespaces, egress proxy, cleanup, audit and interception layers remain authoritative.

### Provenance

W3C PROV defines `Entity`, `Activity`, and `Agent` as its core provenance concepts and supports describing generation, derivation, use, and responsibility.

Existing Enterprise OS provenance infrastructure should therefore record Creative lineage without introducing a Creative-specific ledger.

---

## 2. Decision classification

| Decision                                                                  | Classification                      | Result                               |
| ------------------------------------------------------------------------- | ----------------------------------- | ------------------------------------ |
| Strategy authority remains with `W_STRAT` / IE                            | **Project-defined**                 | Preserve                             |
| Model A: IE exclusively brokers enterprise/RAG data                       | **Project-defined**                 | Preserve                             |
| `W_CREAT` has its own LLM                                                 | **Project-defined**                 | Required                             |
| `W_CREAT` has zero AIO capability                                         | **Project-defined**                 | Required                             |
| Every Creative specialist has an independent LLM identity/context         | **Project-defined**                 | Required                             |
| Every specialist tool executes in a fresh task/attempt-scoped AIO sandbox | **Project-defined**                 | Required                             |
| Fixed workflow rather than model-selected routing                         | **Project + research-backed**       | Required                             |
| COPY and VISUAL may execute concurrently                                  | **Research-backed**                 | Valid                                |
| Independent QA rather than self-evaluation                                | **Research-backed**                 | Required                             |
| Dedicated ADAPT stage                                                     | **Research-backed**                 | Required                             |
| Six specialists                                                           | **Validated architecture decision** | Keep all six                         |
| Seventh specialist                                                        | **Not justified**                   | Do not add                           |
| Character/spec/schema/dedup checks as agents                              | **Not justified**                   | Keep as microtools                   |
| Separate claims/regulatory Creative agent                                 | **Wrong ownership**                 | `W_PROD/S_VAL` remains authoritative |
| Separate competitor/customer research Creative agents                     | **Wrong ownership**                 | `W_COMP/W_VOICE` via IE              |
| Creative-specific DB/RAG/MCP/persistence                                  | **Prohibited/unnecessary**          | Do not add                           |

---

# 3. Final responsibility and access matrix

| Component          | LLM responsibility                                                                                        | Inputs                                                                                                            | Outputs                                                        | Sandbox/tool boundary                                                               | Network                  |
| ------------------ | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------ |
| **W_CREAT**        | Validate Creative scope, produce bounded CreativePlan, coordinate fixed workflow, package approved output | Tenant-scoped TaskGrant, approved W_STRAT strategy, brand persona, product/customer/competitor evidence, policies | `CreativePlan`, final immutable `CreativePackage`              | **No SandboxClient injected. No AIO capability.** IE context-request interface only | None                     |
| **CREAT-RESEARCH** | Define public research questions; synthesize platform/creative references                                 | Approved platforms/channels, objective, research constraints                                                      | `ResearchBrief`, `PlatformSpecSnapshot`                        | Fresh AIO; browser/fetch, citation extraction, source hashing/schema validation     | **ALLOWLIST_PROXY only** |
| **CREAT-CONCEPT**  | Develop message territories, campaign concepts, angles and narrative architecture                         | Strategy + ResearchBrief + brand/evidence bundle                                                                  | `ConceptPack`                                                  | Fresh AIO; schema, claim-ref and variant-dedup utilities                            | `DENY_ALL`               |
| **CREAT-COPY**     | Produce genuinely distinct hooks, headlines, body, captions and CTAs                                      | Approved ConceptPack, voice, evidence/claims                                                                      | `CopyPack`                                                     | Fresh AIO; char-limit, claim-ref, prohibited-term, schema and dedup checks          | `DENY_ALL`               |
| **CREAT-VISUAL**   | Produce art direction, storyboards, shot lists and generation/production briefs                           | ConceptPack, brand tokens, allowed product evidence                                                               | `VisualPack`                                                   | Fresh AIO; format/aspect/safe-zone-metadata/schema validators                       | `DENY_ALL`               |
| **CREAT-ADAPT**    | Recompose approved creative for each authorized placement/channel                                         | CopyPack + VisualPack + frozen PlatformSpecSnapshot                                                               | `AdaptedCreativePack`, asset matrix, content-calendar proposal | Fresh AIO; channel/spec/format/text validators                                      | `DENY_ALL`               |
| **CREAT-QA**       | Independently evaluate; never rewrite                                                                     | Candidate package, strategy, evidence, policies, brand rules, platform specs                                      | `QAReport {PASS\|REVISE\|BLOCK}`                               | Fresh **read-oriented** AIO; validators only                                        | `DENY_ALL`               |

### Important ownership boundaries

`CREAT-RESEARCH` may retrieve:

* official platform documentation;
* generic public creative/editorial research;
* public format/trend/reference material explicitly allowed by policy.

It must **not** independently retrieve:

* named competitor intelligence;
* customer evidence;
* product substantiation;
* internal campaign telemetry;
* tenant/customer information.

Those remain IE-mediated.

Likewise, `CREAT-QA` verifies that a factual claim has an approved evidence reference. It does **not** decide that an unsupported medical/product/regulatory claim is valid. That authority remains upstream.

---

# 4. Typed handoff contract

Every artifact should carry the same immutable envelope:

```text
tenant_id
task_id
run_id
stage_attempt_id
strategy_version/hash
policy_version/hash
brand_persona_version/hash
approved_channel_ids
evidence_refs[]
input_artifact_hashes[]
producing_agent_id
model_identity/model_version
tool_invocation_refs[]
created_at
artifact_hash
```

Stage-specific contracts:

```text
CreativePlan
  approved objectives
  approved channels
  required deliverables
  evidence manifest
  prohibited scope
  expected artifact types

ResearchBrief
  source URL/domain
  publisher
  retrieved_at
  source/content hash
  extracted finding
  citation
  confidence
  unresolved question

PlatformSpecSnapshot
  platform
  placement
  retrieved_at
  source refs
  dimensions
  ratios
  text limits
  safe-zone requirements
  other deterministic constraints

ConceptPack
  concept_id
  territory
  audience tension
  message angle
  narrative architecture
  approved evidence refs
  prohibited claims

CopyPack
  copy_variant_id
  concept_ref
  variant purpose/angle
  copy fields
  factual claim refs
  non-factual classification where applicable

VisualPack
  visual_variant_id
  concept_ref
  visual territory
  composition
  storyboard
  shot list
  production/generation brief
  product/brand refs

AdaptedCreativePack
  source copy/visual refs
  channel
  placement
  format
  adaptation
  asset matrix
  calendar proposal
  platform_spec_version

QAReport
  artifact_hash
  PASS | REVISE | BLOCK
  findings[]
  severity
  reason_code
  evidence refs
  failed deterministic checks
```

A factual statement without an authorized `evidence_ref` fails closed. Research findings about advertising practice cannot be reused as product substantiation.

---

# 5. Deterministic execution flow

```text
W_STRAT
   │ approved strategy
   ▼
IE
   │ tenant-scoped CreativeTaskGrant
   │ approved strategy + brand persona
   │ product/customer/competitor evidence
   │ policies + approved channels
   ▼
W_CREAT
   │
   ├─ deterministic scope validation
   ├─ W_CREAT LLM → CreativePlan
   └─ deterministic post-plan scope validation
        │
        ▼
CREAT-RESEARCH
 own LLM → fresh AIO → allowlisted browser
        │
        ▼
CREAT-CONCEPT
 own LLM → fresh AIO → DENY_ALL
        │
        ├────────────────┐
        ▼                ▼
 CREAT-COPY         CREAT-VISUAL
 own LLM            own LLM
 fresh AIO          fresh AIO
 DENY_ALL           DENY_ALL
        │                │
        └────── join ────┘
                 │
                 ▼
           CREAT-ADAPT
       own LLM + fresh AIO
             DENY_ALL
                 │
                 ▼
             CREAT-QA
       own independent LLM
       fresh read-only AIO
                 │
      ┌──────────┼──────────┐
      ▼          ▼          ▼
     PASS      REVISE      BLOCK
      │          │          │
      │      static route    └──→ W_CREAT → IE
      │          │
      └──────────┴─→ W_CREAT package
                       │
                       ▼
                      IE
                       │
                      HITL
                       │
               signed authorization
                       ▼
                 Outbound MCP
```

### Static revision table

QA may choose only an enumerated reason code; the backend owns the transition:

| QA reason          | Deterministic route                             |
| ------------------ | ----------------------------------------------- |
| `RESEARCH`         | RESEARCH → CONCEPT → COPY ∥ VISUAL → ADAPT → QA |
| `CONCEPT`          | CONCEPT → COPY ∥ VISUAL → ADAPT → QA            |
| `COPY`             | COPY → ADAPT → QA                               |
| `VISUAL`           | VISUAL → ADAPT → QA                             |
| `ADAPT`            | ADAPT → QA                                      |
| `EVIDENCE_MISSING` | W_CREAT → IE; no Creative retry                 |
| `SCOPE_VIOLATION`  | BLOCK → IE                                      |
| `POLICY_BLOCK`     | BLOCK → IE                                      |

`max_revision_attempts` must be a policy/grant value rather than something an LLM controls.

### Critical synthesis rule

After QA returns `PASS`, **W_CREAT must not rewrite creative content**.

Its final synthesis may:

* package artifacts;
* select from explicitly passed variants;
* attach rationale;
* attach lineage;
* summarize deliverables.

Any textual or visual mutation after QA invalidates the QA hash and must re-enter QA.

---

# 6. LLM and sandbox boundary

```text
                     HOST / CONTROL PLANE

 Purpose-scoped LLM identity
           │
           │ provider-neutral LLM gateway
           │ provider credentials remain here
           ▼
 Creative specialist
           │
           │ typed capability mandate
           ▼
 ┌──────────────────────────────────┐
 │ Fresh task/attempt AIO Sandbox   │
 │                                  │
 │ deterministic microtools         │
 │ ephemeral input/output workspace │
 │ no LLM/provider credentials      │
 │ no enterprise credentials        │
 │ no sibling access                │
 └──────────────────────────────────┘
```

“Independent LLM” should mean at minimum:

```text
separate specialist identity
+ separate system contract
+ separate context window/history
+ separate LlmClient/run instance
+ separate token/budget policy
+ separate provenance identity
```

It does **not** necessarily require seven different physical foundation models. The same provider/model can initially back several specialists while their identities and contexts remain isolated.

### Fresh sandbox semantics

Provision per:

```text
(task_id, specialist_id, stage_attempt_id)
```

Lifecycle:

```text
authorize
→ provision fresh sandbox
→ mount sealed/read-only inputs
→ execute approved tools
→ validate output schema
→ seal output/hash
→ collect sanitized audit record
→ destroy sandbox
→ revoke capability/egress token
```

There must be no production fallback such as:

```text
AIO unavailable
→ run Creative microtool directly in backend process
```

Correct behavior is:

```text
AIO unavailable
→ fail stage closed
```

### Network policy

Default:

```text
CREAT-CONCEPT  DENY_ALL
CREAT-COPY     DENY_ALL
CREAT-VISUAL   DENY_ALL
CREAT-ADAPT    DENY_ALL
CREAT-QA       DENY_ALL
```

Research:

```text
CREAT-RESEARCH
   ↓
hardened egress proxy
   ↓
explicit domain/search-provider allowlist
```

Also deny:

```text
localhost / host network
private RFC1918 ranges
link-local addresses
cloud metadata endpoints
raw IP bypass
internal enterprise domains
DB / RAG / CMS / MCP endpoints
provider LLM endpoints
outbound publishing APIs
```

The uploaded sandbox tree already contains useful primitives to reuse:

```text
docker/hardened/
├── egress-proxy/
│   ├── allowed-domains.txt
│   └── tinyproxy-allowlist.conf
├── seccomp/
│   ├── chromium-seccomp.json
│   └── worker-seccomp.json
└── skills/s-copy/
```

No Creative-specific gateway is required.

---

# 7. Deterministic Creative microtools

Keep these as tools, not agents:

```text
validate_output_schema
validate_channel_scope
validate_character_limits
validate_required_fields
validate_claim_references
screen_prohibited_terms
validate_aspect_ratio
validate_safe_zone_metadata
validate_platform_format
deduplicate_exact
deduplicate_normalized
deduplicate_ngram_similarity
validate_citation_manifest
hash_artifact
```

Semantic judgments such as:

```text
"Are these concepts genuinely different?"
"Does this sound like the brand?"
"Is the page actually useful?"
"Is this narrative compelling?"
```

belong to the relevant LLM/QA evaluator, not to pretend-deterministic code.

---

# 8. Minimal repository delta

The uploaded backend tree shows that Development and Strategy already use `subagents/`, while Creative currently contains only `creative_content.py`. It also already contains the shared sandbox, LLM, provenance, orchestration, test and hardened-sandbox layers needed for this implementation.

```text
backend/app/
├── agents/
│   ├── base.py                                      [MODIFY - MINIMAL]
│   ├── creative_content.py                          [REUSE compatibility wrapper]
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
│   └── creative_content_workflow.py                 [ADD]
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
├── schemas/
│   ├── agent_contracts.py                           [MODIFY - ADDITIVE]
│   └── sandbox.py                                   [REUSE / MINIMAL MODIFY]
│
└── main.py                                          [MODIFY]

sandbox/docker/hardened/
└── skills/
    └── s-copy/
        ├── SKILL.md                                 [MODIFY]
        └── scripts/run.py                           [MODIFY]

tests/
├── unit/
│   ├── test_creative_content_verification.py        [EXTEND]
│   ├── test_llm_wiring_verification.py              [EXTEND]
│   └── test_creative_workflow.py                    [ADD]
└── integration/
    ├── test_creative_integration.py                  [MODIFY]
    ├── test_model_a_data_access.py                  [EXTEND]
    ├── test_worker_sandbox_boundary.py               [MODIFY]
    └── test_creative_sandbox_boundaries.py          [ADD]
```

No Creative-specific:

```text
database
repository
RAG controller
MCP gateway
artifact store
provenance store
state machine
```

should be added.

`creative_content_workflow.py` should be a small fixed-DAG executor, **not another enterprise task-state machine**.

---

# 9. Exact necessary changes

## `agents/base.py` — MODIFY minimally

The prior repository analysis supplied with the project reports that the worker base assumes a sandbox capability.

Allow:

```python
capability: SandboxCapability | None
```

A direct sandbox execution method must reject `None`.

Do not redesign the other worker classes.

---

## `creative_content_engine/creative_content.py` — MODIFY

Remove direct Creative sandbox ownership.

Obsolete shape:

```text
W_CREAT
  capability = S_COPY
  → SandboxClient.invoke(...)
```

New shape:

```text
validate TaskGrant
validate tenant
validate strategy hash
validate approved channels
validate evidence manifest

W_CREAT LLM → CreativePlan
validate CreativePlan remains inside grant

CreativeContentWorkflow.run(...)

require QA PASS on exact final artifact hashes

package unchanged approved artifacts
return CreativePackage/EvidenceEnvelope
```

`CreativeContentAgent` itself should receive **no SandboxClient**.

---

## `creative_content_engine/subagents/*.py` — ADD

Each specialist should own:

```text
SPECIALIST_ID
purpose-scoped LlmClient
SandboxClient / sandbox provisioner
typed input contract
typed output contract
fixed tool allowlist
fixed network policy
```

Typical interface:

```python
async def run(
    grant: CreativeTaskGrant,
    input_artifact: TypedArtifact,
) -> TypedStageResult:
    ...
```

LLM-generated tool names or arbitrary shell commands must never expand the allowlist.

---

## `creative_content_workflow.py` — ADD

Hard-code:

```text
RESEARCH
→ CONCEPT
→ COPY || VISUAL
→ ADAPT
→ QA
```

Only COPY and VISUAL may use predefined parallel execution such as `asyncio.gather()`.

Workflow structure must not come from W_CREAT's LLM output.

Implement the static revision table described above and a bounded revision count.

---

## `integrations/llm/client.py` — REUSE

Keep the provider-neutral host boundary.

Instantiate distinct clients/run identities in composition:

```text
w_creat_llm
research_llm
concept_llm
copy_llm
visual_llm
adapt_llm
qa_llm
```

Do not place API keys or provider credentials in sandbox environment variables.

Modify this client only if it currently cannot attach:

```text
agent_identity
model_identity
task/run provenance metadata
```

to calls.

---

## `sandbox/capabilities.py` — MODIFY

Current architectural model:

```text
W_CREAT → S_COPY
```

must become:

```text
W_CREAT itself      → DENY

CREAT-RESEARCH      → scoped Creative capability
CREAT-CONCEPT       → scoped Creative capability
CREAT-COPY          → scoped Creative capability
CREAT-VISUAL        → scoped Creative capability
CREAT-ADAPT         → scoped Creative capability
CREAT-QA            → scoped Creative capability
```

For the smallest delta, the existing `S_COPY` capability identifier can remain internally as a legacy Creative-utility envelope **provided that authorization additionally requires an approved `specialist_id`.**

Therefore:

```text
parent_worker = W_CREAT
specialist_id = null
→ DENY

parent_worker = W_CREAT
specialist_id = CREAT-COPY
operation = validate_copy
→ potentially ALLOW
```

This avoids creating six new global sandbox capability enums.

---

## `sandbox/client.py` — MODIFY

Creative execution must use actual AIO provisioning.

Required lifecycle:

```text
SandboxIdentity
→ provision fresh runtime
→ apply specialist policy
→ execute
→ seal output
→ collect logs
→ destroy
```

Do not keep any backend-process Creative fallback.

If the existing client caches an AIO session, that cache cannot cause two specialist attempts to share a runtime.

---

## `sandbox_policy.py` — MODIFY

Generalize identity from worker-only validation to:

```text
engine/parent_worker
specialist_id
task_id
attempt_id
tenant_id
```

Preserve existing hardened controls:

```text
non-root
capability drop
no-new-privileges
seccomp
namespaces
cgroups
ephemeral filesystem
credential stripping
action interception
audit logging
anti-SSRF
```

Research gets the only Creative egress exception.

---

## `schemas/agent_contracts.py` — MODIFY additively

Reuse existing Creative package structures wherever possible.

Add only missing traceability fields such as:

```text
research_references
concept_refs
platform_spec_refs
claim_evidence_refs
qa_status
qa_findings
artifact_hashes
```

Do not create a Creative persistence model.

---

## `schemas/sandbox.py` — REUSE / MINIMAL MODIFY

The supplied prior analysis indicates the schema already has concepts such as:

```text
specialist_id
subagent_id
allowed_tools
allowed_operations
network policy
expected_output_schema
```

If that remains true, reuse them.

One required authorization property is:

> Research egress authority must be bound to the exact `specialist_id + task_id + attempt_id`, not merely to `W_CREAT`.

---

## `micro_tools.py` — MODIFY

Move/refactor deterministic Creative checks here or expose the equivalent existing implementations.

No creative ideation should live here.

---

## `s-copy/SKILL.md` + `scripts/run.py` — MODIFY heavily

`S_COPY` should cease to mean “generate the entire Creative package.”

Retain only deterministic utility operations.

Target behavior:

```text
S_COPY / Creative utilities
├── validate_copy
├── validate_claim_refs
├── validate_platform_format
├── validate_aspect_ratio
├── validate_safe_zone_metadata
├── validate_schema
├── prohibited_term_check
└── deduplicate_variants
```

Generation belongs to the purpose-scoped LLM specialists.

A later rename from `S_COPY` to `S_CREATIVE_UTILS` would improve semantics, but it is **not necessary for this minimal implementation**.

---

## `main.py` — MODIFY

Compose:

```text
W_CREAT LLM
Research LLM
Concept LLM
Copy LLM
Visual LLM
Adapt LLM
QA LLM

six specialist objects
CreativeContentWorkflow
W_CREAT coordinator
```

Do not inject `SandboxClient` into W_CREAT.

A generic startup assertion that assumes every Layer-5 worker has a sandbox capability must be changed to recognize:

```text
W_CREAT      → zero sandbox capability
CREAT-*      → sandbox capability required
other workers→ existing behavior unchanged
```

---

# 10. Obsolete behavior to remove

The supplied prior Creative repository-analysis file reports four concrete behaviors that are incompatible with the accepted design.

### 1. Direct `W_CREAT → S_COPY`

Remove any equivalent of:

```python
class CreativeContentAgent(...):
    capability = SandboxCapability.COPY
```

`W_CREAT` must have zero sandbox authority.

### 2. Fabricated evidence fallback

Remove fallback claims such as:

```text
"Validated enterprise performance backed by benchmark testing."
```

No synthetic evidence placeholders are acceptable.

Missing evidence becomes:

```text
MISSING_EVIDENCE
→ fail closed / return to IE
```

### 3. Fabricated strategy/channel defaults

Never silently manufacture:

```text
Meta
Google
TikTok
LinkedIn
email
generic target audiences
generic objectives
```

because strategy context is incomplete.

Only channels explicitly present in the IE grant may appear downstream.

### 4. Monolithic S_COPY generation

Remove S_COPY responsibility for combinations such as:

```text
claim inference
+ hook ideation
+ copy generation
+ visual briefs
+ social variants
+ scheduling
+ compliance judgment
+ final package assembly
```

Those responsibilities now belong to separate LLM specialists or deterministic microtools.

---

# 11. QA semantics

`CREAT-QA` should evaluate five distinct layers.

| Layer            | Evaluation                                                                        |
| ---------------- | --------------------------------------------------------------------------------- |
| **Grounding**    | Every factual/product claim maps to approved evidence                             |
| **Brand**        | Voice, message architecture and brand constraints are respected                   |
| **Originality**  | Variants are materially different and not obvious rewrites of supplied references |
| **Platform**     | Format/spec/safe-zone/text/channel requirements pass                              |
| **Policy/scope** | No disallowed claim, channel, objective or campaign expansion                     |

Hard deterministic failures should be supplied to QA as tool evidence.

Example:

```text
character limit exceeded
unsupported evidence ID
unapproved channel
invalid schema
prohibited term
```

QA must report them, not repair them.

`QAReport` should always contain:

```text
status
evaluated_artifact_hash
finding code
severity
affected artifact IDs
evidence
recommended responsible stage
```

---

# 12. Provenance model

Reuse the existing provenance service.

Map:

```text
PROV Agent
  W_CREAT
  CREAT-COPY
  CREAT-QA
  model identity
  HITL approver

PROV Activity
  Creative planning
  specialist attempt
  browser/tool invocation
  adaptation
  QA evaluation
  final packaging

PROV Entity
  TaskGrant
  strategy snapshot
  brand persona snapshot
  evidence item
  platform spec snapshot
  ConceptPack
  CopyPack
  VisualPack
  AdaptedCreativePack
  QAReport
  CreativePackage
```

Record at least:

```text
used
wasGeneratedBy
wasAssociatedWith
wasDerivedFrom
wasInformedBy
```

The exact artifact hashes are important because QA approval must apply to the same immutable artifact later presented to IE/HITL.

---

# 13. Required acceptance tests

| Test                                                     | Expected                   |
| -------------------------------------------------------- | -------------------------- |
| W_CREAT directly requests sandbox                        | **DENY**                   |
| W_CREAT receives `SandboxClient`                         | test fails                 |
| Creative specialist has no specialist identity           | **DENY**                   |
| Unknown Creative specialist ID                           | **DENY**                   |
| Research accesses allowlisted public domain              | ALLOW                      |
| Research accesses internal/private address               | **DENY**                   |
| COPY requests internet                                   | **DENY**                   |
| VISUAL requests internet                                 | **DENY**                   |
| ADAPT requests internet                                  | **DENY**                   |
| QA requests internet                                     | **DENY**                   |
| Research egress token reused by COPY                     | **DENY**                   |
| Specialists share one conversation/context instance      | test fails                 |
| Independent specialist LLM identities                    | PASS                       |
| Missing approved strategy                                | **FAIL CLOSED**            |
| Missing evidence for factual claim                       | **BLOCK/MISSING_EVIDENCE** |
| Unsupported channel generated                            | **BLOCK**                  |
| COPY executes before CONCEPT completes                   | test fails                 |
| COPY and VISUAL overlap after CONCEPT                    | PASS                       |
| ADAPT begins before both branches complete               | test fails                 |
| QA rewrites candidate                                    | test fails                 |
| QA returns status without evidence/findings              | test fails                 |
| Specialist imports/uses DB/RAG/CMS directly              | test fails                 |
| Creative AIO unavailable and backend fallback runs       | test fails                 |
| AIO unavailable and stage fails closed                   | PASS                       |
| W_CREAT mutates artifact after QA hash                   | test fails                 |
| External publish without IE/HITL authorization           | **DENY**                   |
| Provenance omits specialist/model/tool/artifact identity | test fails                 |

Update the existing generic worker/sandbox test from:

```text
all workers → must have sandbox
```

to:

```text
W_CREAT        → MUST NOT have sandbox
CREAT-*        → MUST use sandbox
other workers  → preserve existing policy
```

---

# 14. Remaining evidence gaps / TBDs

1. **Actual source-code verification.** The current uploads provide repository trees and architecture documents, not the underlying current `.py` sources. The concrete `capability = COPY`, fallback-evidence and local-fallback findings above come from the supplied prior Creative refinement/repository-analysis material; they should be rechecked against the live source before applying a line-level patch.

2. **Fresh AIO provisioning.** The tree shows hardened sandbox infrastructure, but a file tree alone cannot prove that each Creative specialist attempt receives a newly provisioned runtime rather than a reused client/container.

3. **Research egress domains.** Ownership and versioning of the Research allowlist still need to be defined. Avoid wildcard internet access.

4. **Actual model mapping.** Separate LLM identities are required. Whether COPY, VISUAL, QA, etc. use different physical models/providers remains configuration policy.

5. **Revision ceiling.** Define `max_revision_attempts` centrally.

6. **Platform-spec freshness.** Specifications change frequently. Store dated/source-hashed spec snapshots and define a policy-level freshness requirement rather than permanently hard-coding today's dimensions.

7. **Visual asset generation.** With the supplied architecture, `CREAT-VISUAL` should produce art direction, storyboards, shot lists and generation/production prompts. Actual image/video generation should not be silently introduced unless a governed generation capability is separately approved.

8. **Global originality.** With QA network-disabled, QA can verify uniqueness against the candidate set, Research snapshot and IE-provided reference corpus. It cannot honestly guarantee uniqueness against the entire public internet.

9. **Architecture-document drift.** The supplied `Final-Level Full Architecture.md` still describes W_CREAT as directly executing S_COPY. That documentation is superseded by this design for W_CREAT and should eventually be updated, though it is not required to implement the code path itself.

---

# Final validated architecture

```text
KEEP
  CREAT-RESEARCH
  CREAT-CONCEPT
  CREAT-COPY
  CREAT-VISUAL
  CREAT-ADAPT
  CREAT-QA

ADD
  no seventh Creative specialist
  fixed Creative workflow executor
  six specialist implementations
  only necessary tests

W_CREAT
  own purpose-scoped LLM       = YES
  AIO-Sandbox capability       = NO
  enterprise/RAG direct access = NO
  strategy mutation            = NO
  publishing                   = NO
  final content rewriting
    after QA                    = NO

CREAT-*
  independent LLM identity     = YES
  fresh AIO per attempt        = YES
  enterprise direct access     = NO
  outbound credentials         = NO
  arbitrary workflow redesign  = NO

NETWORK
  RESEARCH = explicit allowlist through hardened proxy
  all other Creative specialists = DENY_ALL

S_COPY
  monolithic creative generator = REMOVE
  deterministic utility layer   = RETAIN/REFACTOR

DATA
  IE remains exclusive enterprise evidence/RAG broker

OUTPUT
  QA-passed immutable CreativePackage
      → IE
      → HITL
      → Outbound MCP
```

This gives Enterprise OS the required separation: **strategy remains authoritative upstream; `W_CREAT` coordinates but cannot execute; specialists reason independently with attenuated sandbox permissions; deterministic rules remain tools; QA is independent; evidence fails closed; and no generated artifact can reach an external system without IE/HITL authorization.**
