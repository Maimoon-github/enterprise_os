# 1. Recommended Architecture

The recommended design is a **hierarchical, deterministic, sequential Development Engine** under the Intelligence Engine, with a fresh isolated sandbox execution context for each sub-agent step and a mandatory human gate between every two sub-agents.

Your existing architecture already provides the correct outer structure:

```text
Intelligence Engine / MCP Host
        │
        │ Signed bounded Development Task Grant
        ▼
Development Engine (W_DEV)
        │
        │ Deterministic internal state machine
        ▼
One Development Sub-Agent at a time
        │
        ▼
Ephemeral Agent Sandbox
        │
        ├── Tools
        ├── Microtools
        ├── Local source snapshot
        └── Local build/test environment
        │
        ▼
Sealed Candidate Result
        │
        ▼
Development Engine
        │
        ▼
HITL Approval Gateway
        │
   ┌────┴─────┐
 Approve     Reject
   │            │
   ▼            ▼
Checkpoint    Corrective route
   │            │
Next agent ◄────┘
        │
        ▼
Final Release Candidate
        │
        ▼
Intelligence Engine
        │
        ▼
Post-HITL Outbound MCP
        │
        ▼
CMS / Website / Deployment Target
```

The control-flow pattern should be a **deterministic sequential workflow with durable checkpoints and explicit HITL interrupts**, not manager-agent delegation, group chat, free-form handoffs, or agent-selected parallel execution. Current agent-framework guidance makes the same distinction: if the process order and approval points are known beforehand, they belong in workflow code rather than being chosen dynamically by an LLM. HITL workflows then pause, persist state, and resume after an external decision. ([Microsoft Learn][1])

A critical design principle is:

> **The Development Engine may reason about development work, but it must not be allowed to decide whether governance steps can be bypassed.**

Sequencing, locking, sandbox allocation, approval requirements, retries, provenance capture, and advancement to the next sub-agent must therefore be deterministic backend logic.

---

# 2. Sub-Agent Inventory and Responsibilities

I recommend **seven named Development Engine sub-agents**. This is enough separation to create meaningful responsibility and approval boundaries without turning every small capability into an agent.

| ID / Name                                            | Primary responsibility                                                                                                      | Skills / capabilities                                                                                                        | Permitted tools and microtools                                                                                                        | Inputs                                                              | Outputs                                                                                                            | Handoff condition                                               |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| **DEV-PLAN — Development Planning & Impact Agent**   | Convert the IE task grant into an implementation plan and determine which downstream sub-agents are needed                  | Architecture analysis, dependency analysis, change-impact analysis, repository understanding, acceptance-criteria definition | Read-only file index, symbol index, AST parser, dependency graph reader, schema introspector, manifest reader                         | Task grant, policy envelope, source-snapshot ref, approved context  | Ordered Development Execution Plan, affected-artifact list, risk class, required capabilities, acceptance criteria | Human approves exact plan hash                                  |
| **DEV-CMS — CMS Schema & Contract Agent**            | Create or modify CMS content models, schemas, API contracts, migrations, and generated type contracts                       | Schema evolution, JSON Schema, GraphQL/REST contracts, migrations, backward compatibility, CMS modeling                      | File patch tool, schema validator, migration generator, type generator, AST parser                                                    | Approved plan, prior approved snapshot, CMS/schema context          | Candidate schema diff, migration plan, compatibility report, generated contracts                                   | Human approves candidate schema checkpoint                      |
| **DEV-UI — UI Layout & Component Agent**             | Implement page layouts, component composition, templates, UI structure, styling and accessibility-related artifacts         | Component architecture, design systems, responsive layouts, accessibility, rendering                                         | File patcher, component-catalog inspector, AST parser, formatter, template compiler, local browser/render tool, accessibility checker | Approved plan/schema snapshot, UI requirements, component contracts | UI/component diff, render evidence, accessibility report                                                           | Human approves UI checkpoint                                    |
| **DEV-CODE — Application Code Implementation Agent** | Implement application logic and integration code required by the approved plan                                              | Application programming, refactoring, API integration, state management, error handling                                      | Patch/file tools, AST parser, compiler, formatter, package manager through allow-listed proxy, code generator                         | Latest approved snapshot, plan, schemas/contracts, UI artifacts     | Candidate source diff, implementation notes, dependency changes                                                    | Human approves implementation checkpoint                        |
| **DEV-VERIFY — Build & Verification Agent**          | Independently establish whether the candidate builds and meets technical acceptance criteria                                | Testing, type checking, lint interpretation, build diagnosis, coverage analysis                                              | Linter, compiler, type checker, unit/integration test runners, build system, coverage tool, AST parser                                | Approved candidate snapshot and acceptance criteria                 | Verification dossier, lint results, test results, build result, coverage evidence, pass/fail verdict               | Human accepts report **and** machine verification policy passes |
| **DEV-SEC — Secure Code & Static Review Agent**      | Independently inspect candidate artifacts for security, dangerous behavior and policy violations                            | Secure coding review, dependency risk, secret detection, permission analysis, tenant-boundary review                         | AST parser, SAST scanner, secret scanner, dependency scanner, policy rules, manifest analyzer                                         | Verified candidate snapshot, diff, policy envelope                  | Security findings, severity classification, policy verdict, remediation targets                                    | Human accepts report **and** no hard-block finding remains      |
| **DEV-REL — Release & Development Operations Agent** | Build the immutable release candidate and operational package; prepare but do not independently perform external deployment | Packaging, build/release engineering, migration ordering, rollback planning, SBOM/provenance preparation                     | Build packager, manifest generator, SBOM generator, migration dry-run, checksum generator, local deployment simulator                 | Security-approved snapshot, verification evidence, release policy   | Release bundle, deployment manifest, rollback manifest, digests, SBOM, release dossier                             | Final human approval; release bundle returns to IE              |

### Why these boundaries are justified

**DEV-PLAN is separate** because planning has a different lifecycle and privilege profile from mutation. It should normally receive read-only project access.

**DEV-CMS and DEV-UI are separate** because their artifact domains, validators, risks, and handoff criteria are meaningfully different. Not every task needs both.

**DEV-CODE is an author, not its own reviewer.** Letting the component coder declare its own output clean defeats the purpose of your approval and isolation model.

**DEV-VERIFY and DEV-SEC are independent reviewers.** Both should normally have a read-only project snapshot. They may create reports and temporary build outputs, but they must not silently repair the candidate they are reviewing.

**DEV-REL is separate from deployment.** It creates the deployable release candidate. The actual external write still occurs through your existing IE → post-HITL Outbound MCP path.

There is no need for a separate "retry agent", "AST agent", "linter agent", "formatter agent", or "test agent". Those are capabilities, not autonomous responsibilities.

---

# 3. Agent → Sub-Agent → Tool Hierarchy

The architectural distinction should be explicit:

```text
INTELLIGENCE ENGINE
│
├── Role: Global orchestrator + MCP host
├── Owns: Policy, authoritative context, global CTS, data/RAG access
│
└── DEVELOPMENT ENGINE (W_DEV)
    │
    ├── Role: Bounded worker-agent + deterministic sub-workflow controller
    ├── Cannot: bypass IE policy, directly query enterprise stores,
    │           deploy externally, or skip HITL
    │
    ├── DEV-PLAN
    ├── DEV-CMS
    ├── DEV-UI
    ├── DEV-CODE
    ├── DEV-VERIFY
    ├── DEV-SEC
    └── DEV-REL
         │
         └── Sandbox Controller — infrastructure, NOT an agent
              │
              ├── Tools
              │    ├── test runner
              │    ├── compiler
              │    ├── linter
              │    ├── package manager
              │    ├── file patcher
              │    └── SAST scanner
              │
              └── Microtools
                   ├── AST parser
                   ├── symbol extractor
                   ├── diff calculator
                   ├── schema validator
                   ├── checksum generator
                   └── manifest parser
```

The categories should mean:

| Category                | Meaning                                                                              | Can reason autonomously? |  Can invoke other capabilities? |
| ----------------------- | ------------------------------------------------------------------------------------ | -----------------------: | ------------------------------: |
| **Agent**               | Model-bearing bounded reasoning unit                                                 |                      Yes |           Within explicit grant |
| **Sub-agent**           | Agent subordinate to W_DEV with a separate task lifecycle and approval boundary      |                      Yes | Only allow-listed sandbox tools |
| **Tool**                | Deterministic operational capability                                                 |                       No |                     Normally no |
| **Microtool**           | Small deterministic parsing/transformation primitive                                 |                       No |                              No |
| **Sandbox capability**  | Execution/environment function such as filesystem, shell, browser, process execution |                       No |                             N/A |
| **Security control**    | Enforcement mechanism such as seccomp, network policy or cgroups                     |                       No |                             N/A |
| **Orchestration logic** | Backend state-transition rules                                                       |        No LLM discretion |                 Controls agents |

## Decomposition of the existing “Component Coder + Linter + AST Parser” concept

The current composite `S_CODE` should **not remain one sub-agent**.

Recommended decomposition:

```text
Current:
Component Coder & Linter
    └── AST Parser microtool

Replace with:

DEV-CODE — Code Implementation Agent
    ├── file/patch tool
    ├── formatter
    └── AST Parser microtool

DEV-VERIFY — Verification Agent
    ├── linter
    ├── compiler/type checker
    ├── test runner
    └── AST Parser microtool

DEV-SEC — Security Review Agent
    ├── SAST scanner
    ├── dependency scanner
    ├── secret scanner
    └── AST Parser microtool
```

The **AST parser remains a microtool**, because parsing an AST is deterministic and has no independent goal or lifecycle.

The **linter remains a tool**, because a linter deterministically analyzes source. The agent-worthy responsibility is interpreting combined lint/build/test evidence and deciding what it means for the task.

That gives you genuine separation of duties without fake agent proliferation.

---

# 4. Sequential Execution and Human-Approval Loop

The normal path should be:

```text
IE Task Grant
   ↓
DEV-PLAN
   ↓
Seal outputs + provenance
   ↓
HITL-1
   ↓ approved
DEV-CMS       [conditional]
   ↓
HITL-2
   ↓ approved
DEV-UI        [conditional]
   ↓
HITL-3
   ↓ approved
DEV-CODE      [conditional]
   ↓
HITL-4
   ↓ approved
DEV-VERIFY
   ↓
HITL-5
   ↓ machine + human pass
DEV-SEC
   ↓
HITL-6
   ↓ machine + human pass
DEV-REL
   ↓
HITL-7
   ↓ approved
Return release candidate to IE
   ↓
IE post-approval outbound MCP
```

`DEV-CMS`, `DEV-UI`, and `DEV-CODE` may be marked `SKIPPED_NOT_APPLICABLE` by the **approved DEV-PLAN**, but they cannot be skipped dynamically later by an LLM.

`DEV-PLAN`, `DEV-VERIFY`, `DEV-SEC`, and `DEV-REL` should normally be mandatory for a release-producing task.

### Single-active-agent invariant

Enforce this as a database/state-machine property, not merely an instruction:

```text
active_subagent_count(task_id) <= 1
```

I would add a lease such as:

```text
DevelopmentExecutionLease {
    task_id
    workflow_version
    current_step
    step_attempt
    agent_id
    sandbox_id
    acquired_at
    expires_at
}
```

No second sub-agent may obtain the lease until the current one has:

1. terminated,
2. produced a sealed result,
3. had its sandbox finalized,
4. entered HITL,
5. received a valid decision,
6. and had the checkpoint transition committed.

### Approval token

Approval should not simply be a Boolean.

Bind approval cryptographically to the exact result:

```text
approval_id
task_id
workflow_id
step_id
attempt_id
subagent_id
input_snapshot_hash
output_snapshot_hash
review_dossier_hash
policy_version
decision
reviewer_identity
issued_at
expires_at
signature
```

If the candidate changes by one byte after approval, the approval no longer matches.

The next sub-agent therefore requires:

```text
valid_policy_decision
AND valid_HITL_approval
AND approved_output_hash == next_input_hash
```

This prevents approval reuse against modified artifacts.

### Human approval is necessary, but not always sufficient

For security-critical rules:

```text
Human APPROVE + machine DENY = DENY
```

A reviewer should not be able to override:

* sandbox isolation failure,
* invalid provenance chain,
* untrusted artifact digest,
* prohibited network access,
* secret leakage,
* unresolved critical security finding,
* unsigned/incorrect approval token,
* tenant/work-region mismatch.

If you later need "break glass", make that an entirely separate governance path rather than ordinary HITL approval.

---

# 5. Sandbox and Security Boundary Model

This is the area where I recommend changing the current architecture most strongly.

Your uploaded architecture describes `agent_sandbox` as providing micro-virtualization, cgroups/namespaces, egress control and execution interception.

The referenced AIO Sandbox documentation does **not currently establish that complete guarantee**. Its standard quick-start runs the sandbox as a Docker container and recommends `--security-opt seccomp=unconfined`. It also describes the local setup as intended for trusted local development. ([AIO Sandbox][2])

Therefore:

> **AIO Sandbox should be treated as the tool/runtime payload inside your sandbox boundary, not as the complete Enterprise_OS security boundary.**

For hostile or untrusted generated code, a stronger outer isolation layer is required. Firecracker, for example, uses KVM as a virtualization boundary and recommends its jailer, namespace/cgroup restrictions and seccomp as defense-in-depth controls. ([GitHub][3])

NIST SP 800-190 also treats container isolation and container-host security as a distinct security concern rather than assuming container packaging alone provides a sufficient trust boundary. ([NIST][4])

## Recommended runtime stack

```text
Host / Sandbox Control Plane
│
├── Policy enforcement
├── Provenance collector
├── network egress proxy
├── immutable artifact transfer
├── credentials broker
│
└── MicroVM boundary
      │
      ├── dedicated guest kernel
      ├── unique sandbox UID/GID
      ├── cgroup v2 quotas
      ├── guest/process namespaces
      ├── seccomp / LSM restrictions
      ├── ephemeral filesystem
      │
      └── AIO Sandbox runtime
            │
            ├── one sub-agent
            ├── allowed tools only
            └── candidate workspace
```

Linux namespaces isolate kernel-visible resources, while cgroup v2 supplies resource controls, and seccomp reduces the exposed syscall surface. ([man7.org][5])

### Per-sub-agent isolation

Use **one fresh sandbox instance per sub-agent attempt**.

Do not carry a mutable sandbox from DEV-CODE into DEV-VERIFY.

Instead:

```text
Approved Snapshot N
       ↓
Fresh Sandbox
       ↓
DEV-CODE
       ↓
Candidate Snapshot N+1
       ↓
Seal + destroy sandbox
       ↓
Human approval
       ↓
Promote N+1
       ↓
Fresh Sandbox
       ↓
DEV-VERIFY
```

This provides much stronger isolation, repeatability and recovery.

Cross-engine/work-region isolation should key the sandbox by something like:

```text
tenant_id
work_region_id
sub_region_id
engine_id
task_id
step_id
attempt_id
```

Each key gets independent:

* microVM,
* network namespace,
* credentials,
* writable filesystem,
* process namespace,
* memory allocation,
* execution log stream.

Only digest-pinned **read-only base images** may be shared.

There should be no writable cache or workspace shared across engines or sub-agents.

### Filesystem model

The Development Engine itself should not manipulate repository files.

Only the sandbox receives a materialized snapshot.

Use:

```text
immutable source snapshot
        ↓
copy-on-write sandbox workspace
        ↓
candidate diff
        ↓
content-addressed output bundle
```

The candidate is not made canonical until the HITL gateway approves it.

### Network model

Default:

```text
DENY_ALL
```

Allow specific egress only where the task requires it.

For example:

```text
DEV-VERIFY
    → no external network

DEV-CODE
    → registry.npmjs.org only if an approved dependency action exists

DEV-UI browser
    → localhost preview only

DEV-CMS
    → no production CMS access
```

Dependency retrieval should go through a host-controlled allow-list proxy, ideally with hashes/pins.

No sandbox should directly reach:

* the enterprise database,
* Agentic RAG,
* MCP host internals,
* cloud metadata,
* sibling sandboxes,
* internal orchestration APIs.

This preserves your existing Model A rule.

### Credentials

Do not place long-lived platform credentials inside a sandbox.

Prefer a brokered design where the host performs authenticated actions or provides narrowly scoped, short-lived credentials.

### Ephemeral-memory scrubbing

At completion:

```text
stop processes
→ capture required evidence
→ revoke tokens
→ unmount workspace
→ destroy VM
→ discard guest memory
→ destroy scratch volumes
→ invalidate sandbox identity
```

For high-sensitivity environments, disable host swap or use encrypted swap; Firecracker's production guidance specifically discusses swap as a potential data-remanence concern. ([GitHub][3])

### No external editor/IDE

AIO Sandbox exposes `code-server` as one of its optional workspace services, but you do not need it. ([AIO Sandbox][6])

For Enterprise_OS:

```text
code-server = disabled / not exposed
```

Source modification occurs through sandbox file/patch APIs and command-line development tools. The human reviews generated diffs and dossiers through the governance interface, not an IDE.

---

# 6. Audit Trail and W3C PROV Provenance Model

W3C PROV is appropriate for your lineage model because it defines exactly the three core types needed here:

* `prov:Entity`
* `prov:Activity`
* `prov:Agent`

and relationships including `prov:used`, `prov:wasGeneratedBy`, `prov:wasDerivedFrom`, `prov:wasAssociatedWith`, and `prov:actedOnBehalfOf`. ([W3C][7])

## Mapping

| Enterprise_OS object     | PROV representation  |
| ------------------------ | -------------------- |
| Intelligence Engine      | `prov:SoftwareAgent` |
| Development Engine       | `prov:SoftwareAgent` |
| DEV-CODE etc.            | `prov:SoftwareAgent` |
| Human reviewer           | `prov:Person`        |
| Sandbox controller       | `prov:SoftwareAgent` |
| Task grant               | `prov:Entity`        |
| Source snapshot          | `prov:Entity`        |
| Context bundle           | `prov:Entity`        |
| Candidate patch          | `prov:Entity`        |
| Test report              | `prov:Entity`        |
| Approval grant/rejection | `prov:Entity`        |
| Release bundle           | `prov:Entity`        |
| Sub-agent execution      | `prov:Activity`      |
| Tool invocation          | `prov:Activity`      |
| Human review             | `prov:Activity`      |
| Release packaging        | `prov:Activity`      |

Delegation becomes:

```text
DEV-CODE
    prov:actedOnBehalfOf
Development Engine

Development Engine
    prov:actedOnBehalfOf
Intelligence Engine
```

Execution:

```text
code_execution
    prov:wasAssociatedWith DEV-CODE
    prov:used source_snapshot_12
    prov:used task_grant_45
```

Output:

```text
candidate_snapshot_13
    prov:wasGeneratedBy code_execution
    prov:wasDerivedFrom source_snapshot_12
```

Review:

```text
approval_activity
    prov:wasAssociatedWith human_reviewer
    prov:used candidate_snapshot_13

approval_grant
    prov:wasGeneratedBy approval_activity
```

Next step:

```text
verification_activity
    prov:used candidate_snapshot_13
    prov:used approval_grant
```

W3C PROV provides the **lineage semantics**. It does **not by itself make storage immutable**.

Your immutable-ledger implementation therefore needs an additional integrity layer.

Recommended event envelope:

```text
event_id
task_id
workflow_id
step_id
attempt_id
tenant_id
work_region_id
agent_id
activity_id
sandbox_id
sandbox_image_digest
tool_name
tool_version
policy_version
input_entity_hashes[]
output_entity_hashes[]
command_or_action_digest
started_at
ended_at
exit_status
trace_id
previous_event_hash
event_hash
control_plane_signature
```

The provenance service—not sandbox user code—must create/sign the authoritative record.

This matches modern software-provenance practice: SLSA specifically recommends generating provenance inside the trusted build/control plane and protecting signing material from user-controlled build steps. ([SLSA][8])

For software release artifacts, I recommend supplementing W3C PROV with **SLSA/in-toto attestations**, not replacing PROV. In-toto is particularly aligned with your sequential model because its layout defines authorized supply-chain steps and records signed link metadata for what each step consumed and produced. ([in-toto][9])

### Important refinement to your existing “full prompt logs” concept

Do not put arbitrary plaintext secrets or credentials permanently into an immutable ledger.

Instead:

```text
Ledger:
    prompt/context hash
    provenance relationship
    classification metadata
    encrypted-payload reference

Evidence store:
    encrypted sanitized prompt/context
    strict retention/access controls
```

You still get immutable proof of what context was used without turning the permanent audit ledger into a secret archive.

---

# 7. Failure, Rejection, Retry, and Recovery Flow

| Situation                                  | Required transition                                                      |
| ------------------------------------------ | ------------------------------------------------------------------------ |
| Human rejects DEV-PLAN                     | Issue revision directive → new DEV-PLAN attempt                          |
| Human rejects schema/UI/code candidate     | Re-run responsible authoring agent from last **approved** snapshot       |
| Scope fundamentally changes                | Return to DEV-PLAN rather than patching the old plan                     |
| DEV-VERIFY reports lint/test/build failure | Hard block advancement; route remediation to DEV-CODE, DEV-UI or DEV-CMS |
| DEV-SEC reports critical finding           | Hard block; route to responsible authoring agent                         |
| Release package incorrect                  | Return to DEV-REL                                                        |
| Transient sandbox provisioning failure     | Bounded infrastructure retry from identical inputs                       |
| Tool process crashes                       | Record failed attempt; bounded same-step retry if classified transient   |
| Sandbox integrity/security failure         | Destroy sandbox immediately; no candidate promotion                      |
| Provenance write/sign failure              | Fail closed; do not proceed                                              |
| Human approval expires                     | Re-enter HITL; never silently reuse it                                   |
| Workflow service restarts                  | Resume from durable CTS checkpoint                                       |
| Retry budget exhausted                     | `MANUAL_EXCEPTION` or `FAILED`; never advance automatically              |

A rejected candidate must remain immutable as historical evidence.

Do not overwrite:

```text
candidate-v3
```

with a corrected version.

Generate:

```text
candidate-v4
    wasDerivedFrom candidate-v3
```

and retain the rejection as part of provenance.

### Verification loop example

```text
DEV-CODE attempt 1
    ↓ approved
DEV-VERIFY
    ↓ FAIL
HITL
    ↓ correction requested
DEV-CODE attempt 2
    ↓ approved
DEV-VERIFY
    ↓ PASS
HITL
    ↓ approved
DEV-SEC
```

Verification itself should not fix the source, because doing so would collapse reviewer and author responsibilities again.

---

# 8. Implementation-Oriented Workflow / State Machine

I would model the Development Engine workflow with these canonical states:

```text
RECEIVED
    ↓
POLICY_BOUND
    ↓
PLANNING
    ↓
RESULT_SEALED
    ↓
HITL_PENDING
    ↓
APPROVED
    ↓
SANDBOX_PROVISIONING
    ↓
SUBAGENT_RUNNING
    ↓
RESULT_SEALED
    ↓
HITL_PENDING
    ├── APPROVED ─────→ NEXT_STEP
    ├── REJECTED ─────→ CORRECTION_REQUIRED
    └── ABORTED ──────→ ABORTED

CORRECTION_REQUIRED
    ↓
RETRY_PREPARED
    ↓
SANDBOX_PROVISIONING

NEXT_STEP
    ├── another sub-agent → SANDBOX_PROVISIONING
    └── no steps left     → RELEASE_READY

RELEASE_READY
    ↓
COMPLETED
```

Every `SUBAGENT_RUNNING` state contains exactly one:

```text
subagent_id
sandbox_id
attempt_id
input_snapshot
capability_grant
```

### Transition guards

`SANDBOX_PROVISIONING → SUBAGENT_RUNNING`

requires:

```text
execution lease held
approved predecessor
valid task grant
valid policy envelope
artifact hashes verified
sandbox isolation attested
```

`RESULT_SEALED → HITL_PENDING`

requires:

```text
process stopped
outputs hashed
filesystem delta captured
execution events ingested
PROV record created
candidate frozen
```

`HITL_PENDING → APPROVED`

requires:

```text
valid reviewer identity
approval binds exact candidate hash
approval binds exact step + attempt
```

`APPROVED → NEXT_STEP`

requires:

```text
no hard policy denial
approval still valid
output promoted as approved checkpoint
previous sandbox destroyed
single-active-agent invariant satisfied
```

## Fit with your existing backend

Your uploaded `Backend Hierarchy.md` already contains most of the required control-plane components:

```text
orchestration/
    intelligence_engine.py
    dag_scheduler.py
    task_state_machine.py
    policy_evaluator.py
    hitl_preview_generator.py

services/
    hitl.py
    task_state.py
    provenance.py

integrations/sandbox/
    client.py
    capabilities.py

schemas/
    task_state.py
    agent_contracts.py
    sandbox.py
    action_preview.py
    provenance.py
```

I would extend it approximately as follows:

```text
app/
├── agents/
│   └── development_engine/
│       ├── development.py
│       └── subagents/
│           ├── planning.py
│           ├── cms_contract.py
│           ├── ui_layout.py
│           ├── implementation.py
│           ├── verification.py
│           ├── security_review.py
│           └── release_ops.py
│
├── orchestration/
│   └── development_state_machine.py
│
├── integrations/
│   └── sandbox/
│       ├── client.py
│       ├── capabilities.py
│       ├── micro_tools.py
│       └── sandbox_policy.py
│
└── schemas/development/
    ├── development_plan.py
    ├── development_result.py
    ├── approval_token.py
    └── provenance.py
```

Your existing `dag_scheduler.py` can remain for enterprise-level dependency scheduling, but the W_DEV internal graph must effectively operate as a **linearized DAG with `max_concurrency=1` and approval nodes between all execution nodes**.

No LLM call should be able to change that concurrency value.

### MCP consideration

Do not store the Development workflow's authoritative state inside an MCP transport session. The current MCP `2026-07-28` release uses a stateless protocol core; workflow state belongs in your CTS/task-state services. The current MCP release also provides better request-level routing/auth characteristics, which fit an IE-owned gateway. ([Model Context Protocol Blog][10])

That means:

```text
MCP = capability/transport boundary
CTS = workflow truth
```

not:

```text
MCP connection/session = workflow truth
```

---

# 9. Research Findings and Sources

The external research supports five main architectural decisions.

**First, use deterministic workflow orchestration.** Microsoft's current agent architecture guidance explicitly distinguishes workflows from open-ended model-controlled agents when ordering and approval points must be predetermined. Its sequential orchestration and HITL mechanisms support exactly the pause/response/checkpoint pattern required here. LangGraph likewise implements HITL through resumable interrupts and persisted checkpoints. ([Microsoft Learn][1])

**Second, W3C PROV is the right semantic lineage model.** PROV defines entities, activities, agents, derivation, usage, generation, association and delegation—all directly applicable to IE → W_DEV → sub-agent execution. ([W3C][7])

**Third, immutable provenance needs controls beyond W3C PROV.** SLSA emphasizes provenance generated and protected by the trusted control plane, signed provenance, isolation between builds and protection of signing material from user-defined workloads. In-toto supplies an additional step/authorization model that fits software build and release pipelines. ([SLSA][8])

**Fourth, the sandbox must combine multiple enforcement layers.** NIST treats container isolation as a security engineering concern; Linux namespaces, cgroups and seccomp each address different parts of containment. Firecracker documents a layered model using KVM, jailer restrictions, namespaces, cgroups and seccomp rather than depending on one mechanism. ([NIST][4])

**Fifth, the current AIO Sandbox should not be equated with your complete required security boundary.** Its documented Docker quick-start uses `seccomp=unconfined`, so your micro-virtualization and syscall-isolation requirements must be supplied and independently validated by the outer Enterprise_OS runtime. ([AIO Sandbox][2])

Primary standards/documentation include [W3C PROV-O specification](https://www.w3.org/TR/prov-o/?utm_source=chatgpt.com), [NIST SP 800-190](https://www.nist.gov/publications/application-container-security-guide?utm_source=chatgpt.com), [SLSA v1.2 provenance specification](https://slsa.dev/spec/v1.2/provenance?utm_source=chatgpt.com), and [in-toto documentation](https://in-toto.io/docs/getting-started/?utm_source=chatgpt.com).

---

# 10. Final Recommended Architecture

The architecture I recommend adopting is therefore:

```text
                        INTELLIGENCE ENGINE
                  Global Orchestration + MCP Host
                              │
                     Signed bounded grant
                              │
                              ▼
                     DEVELOPMENT ENGINE
               Bounded worker/sub-orchestrator
              Deterministic FSM, concurrency = 1
                              │
                              ▼
                      DEV-PLAN + HITL
                              │
                              ▼
              DEV-CMS [conditional] + HITL
                              │
                              ▼
               DEV-UI [conditional] + HITL
                              │
                              ▼
              DEV-CODE [conditional] + HITL
                              │
                              ▼
                     DEV-VERIFY + HITL
                              │
                              ▼
                      DEV-SEC + HITL
                              │
                              ▼
                      DEV-REL + HITL
                              │
                              ▼
                   Sealed Release Candidate
                              │
                              ▼
                    INTELLIGENCE ENGINE
                              │
                     Signed dispatch only
                              ▼
                    Outbound Actuation MCP
                              │
                              ▼
                     CMS / Website / Runtime
```

Every sub-agent execution gets:

```text
fresh sandbox
+ minimum capability grant
+ immutable approved input snapshot
+ deny-by-default egress
+ independent process/filesystem/network isolation
+ bounded CPU/memory/process limits
+ action interception
+ complete audit stream
+ content-addressed output
+ sandbox destruction after sealing
```

Every transition gets:

```text
machine policy check
+ immutable provenance
+ exact candidate digest
+ human decision
```

And no next sub-agent starts until all four are valid.

## Assumptions

This recommendation assumes the Intelligence Engine remains the exclusive RAG/data-access broker, as defined in your uploaded architecture; W_DEV sub-agents receive bounded context rather than directly querying enterprise data.

It also assumes your current HITL service can be extended to issue cryptographically bound approvals rather than simple approval flags.

The Development Engine is assumed to be allowed to maintain an internal subordinate workflow, while the IE remains the authoritative enterprise-level orchestrator.

## Decisions that should now be treated as resolved

* **Component coder and reviewer must be separated.**
* **Linter is a tool, not a sub-agent.**
* **AST parser is a microtool, not a sub-agent.**
* **Verification is a separate sub-agent.**
* **Security review is a separate sub-agent.**
* **Deployment preparation and external deployment are separate responsibilities.**
* **No Development sub-agents run concurrently.**
* **HITL occurs after every sub-agent.**
* **Rejected work is never promoted into the next canonical checkpoint.**
* **Sub-agent files/processes execute only inside the sandbox.**
* **CTS, not MCP transport state, owns workflow state.**
* **W3C PROV defines lineage; cryptographic append-only storage provides immutability.**
* **No IDE/editor belongs in the execution architecture.**

## Components requiring further validation

The biggest unresolved item is the **actual hardened sandbox substrate**. The currently referenced AIO Sandbox does not, from its documented default deployment alone, satisfy your stated micro-virtualization + seccomp + hostile-code isolation requirement. You need to choose and certify the outer runtime—Firecracker, a gVisor-class runtime, another microVM solution, or an equivalent implementation—and then test its guarantees explicitly. ([AIO Sandbox][2])

You also still need concrete technology selections for the **immutable PROV ledger**, signing/key-management mechanism, content-addressed artifact registry, sandbox attestation mechanism, and exact approval-signature scheme. Your uploaded backend architecture already marks several of these persistence technologies as TBD.

With those items resolved, the Development Engine can be implemented without introducing an external editor, unrestricted autonomous collaboration, direct worker data access, parallel sub-agents, or ungoverned deployment paths.

[1]: https://learn.microsoft.com/en-us/agent-framework/journey/workflows?utm_source=chatgpt.com "Workflows | Microsoft Learn"
[2]: https://sandbox.agent-infra.com/guide/start/quick-start?utm_source=chatgpt.com "Quick Start - AIO Sandbox"
[3]: https://github.com/firecracker-microvm/firecracker/blob/main/docs/prod-host-setup.md?utm_source=chatgpt.com "firecracker/docs/prod-host-setup.md at main · firecracker-microvm/firecracker · GitHub"
[4]: https://www.nist.gov/publications/application-container-security-guide?utm_source=chatgpt.com "Application Container Security Guide | NIST"
[5]: https://man7.org/linux/man-pages/man7/namespaces.7.html?utm_source=chatgpt.com "namespaces(7) - Linux manual page"
[6]: https://sandbox.agent-infra.com/guide/advanced/workspace?utm_source=chatgpt.com "Workspace - AIO Sandbox"
[7]: https://www.w3.org/TR/prov-o/?utm_source=chatgpt.com "PROV-O: The PROV Ontology"
[8]: https://slsa.dev/spec/v1.2-rc1/build-requirements?utm_source=chatgpt.com "SLSA • Build: Requirements for producing artifacts"
[9]: https://in-toto.io/docs/getting-started/?utm_source=chatgpt.com "Getting started | in-toto"
[10]: https://blog.modelcontextprotocol.io/posts/2026-07-28/?utm_source=chatgpt.com "The 2026-07-28 Specification | Model Context Protocol Blog"
