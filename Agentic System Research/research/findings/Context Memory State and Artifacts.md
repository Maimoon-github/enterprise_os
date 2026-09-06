# Context Memory State and Artifacts

## Scope and architectural stance

This report covers one dimension only: **context memory, task state, and artifacts** across a three-level agent hierarchy—**Governable Orchestrator (GO) → Worker Agents → Agent-Specific Sub-Agents**. It describes surface architecture, boundaries, ownership, access, and control/data flow. It deliberately excludes implementation code, deployment topology, low-level storage formats, vendor products, and hidden model reasoning.

The central architectural distinction is that a model’s **bounded context window is working memory**, not the authoritative system record. Durable memory, task state, and artifacts therefore require explicit boundaries and governed movement into and out of a context window. This follows the virtual-memory analogy in MemGPT, which separates a finite “main context” from external context and uses explicit retrieval and eviction to manage data movement [4]. Retrieval-augmented generation likewise distinguishes model-parameter memory from explicit non-parametric memory that can be updated and accompanied by provenance [6].

The recommended architecture treats the GO as the **control and authority boundary**. Workers and sub-agents perform bounded work, but they do not become independent authorities for cross-task memory, canonical task state, or organizational artifacts. The hierarchy is therefore not a shared-memory mesh; it is a **mediated information-flow system**.

## Reference surface architecture

```text
                         GOVERNANCE / CONTROL PLANE
  policies • identity/scope • context budgets • access decisions • lifecycle • audit
                                  │
                                  ▼
+--------------------------------------------------------------------------+
| Governable Orchestrator (GO)                                             |
| Canonical task state • memory/artifact registry • retrieval broker       |
| admission/assignment • promotion/merge • approval • revocation           |
+-------------------------┬----------------------------------┬-------------+
                          │ task envelope / state deltas     │ governed query
                          ▼                                  ▼
+-----------------------------------+             +-------------------------+
| Worker Agent                       |             | Durable governed stores |
| Task working state • scoped        |◄───────────►| Long-term memory        |
| context assembly • delegation     |   mediated  | Task-state record       |
| • artifact production             |   access     | Artifact registry/evidence|
+------------------┬----------------+             +-------------------------+
                   │ minimal delegation context
                   ▼
+-----------------------------------+
| Agent-Specific Sub-Agent           |
| Ephemeral/local working context    |
| Scoped task slice • explicit input |
| Result/state delta/artifact refs   |
+-----------------------------------+
```

The stores in the diagram are logical architectural responsibilities, not prescribed physical products. The important boundary is that **durability and authority are outside any model context window** and that every upward or outward information flow passes through a policy-aware interface.

## Memory, state, and artifact classes

| Class | Lifetime and purpose | Canonical owner | What an agent receives | Recommended control boundary |
|---|---|---|---|---|
| **Invocation context** | One inference or sub-task execution; current instructions, selected evidence, recent messages, and active working notes. It is bounded and disposable. | The active execution scope, under GO policy | Only the minimum task-relevant slice that fits the context budget | GO sets the budget and immutable instructions; the worker assembles the worker context; a sub-agent receives a smaller delegated context |
| **Session / short-term memory** | Current conversation or task episode: recent observations, decisions, pending actions, and provisional summaries. | Worker for its assigned task; GO retains the authoritative checkpoint | Worker can read/write its task-local working view; sub-agent receives selected items | Isolated by task, user/tenant, and delegation scope; no implicit cross-worker visibility |
| **Long-term memory** | Durable facts, preferences, policies, lessons, prior task summaries, and approved historical records that may support later tasks. | GO-governed memory authority | Retrieved records or references, only after scope and policy checks | Explicit read retrieval; promotion from short-term memory requires a governed decision; deletion, retention, correction, and use restrictions remain enforceable |
| **Canonical task state** | Lifecycle status, assignment, dependencies, checkpoints, approvals, exceptions, and completion criteria. | GO | Worker receives a task-scoped working view and submits state deltas; sub-agent normally receives only its slice | GO is the source of truth; worker-local plans and status are proposals until accepted or checkpointed |
| **Artifacts and evidence** | Durable outputs or intermediate deliverables that can be inspected, reused, approved, superseded, or delivered. | GO-controlled artifact authority; producing worker is attributable producer | Agents receive references or explicitly authorized content; sub-agents return artifact references through the worker | Separate artifact lineage from conversational memory; immutable/superseding lifecycle and provenance are preferable to silent overwrite |
| **Provenance and audit record** | Record of what activity used, generated, derived, or attributed each state item or artifact. | GO governance/audit function | Usually metadata and verification evidence, not unrestricted raw history | Append-oriented, access-controlled, and available for review without exposing hidden reasoning |

This separation prevents four common category errors: treating a context window as durable memory; treating a worker’s local plan as canonical task state; treating a generated file as an informal chat message; and treating a memory retrieval result as trustworthy merely because it was retrieved.

## Ownership and authority boundaries

### Governable Orchestrator

The GO owns the **governance contract** for all three lower levels. Its responsibilities are to establish identity and scope for each task, select or authorize a worker, set context and retention budgets, decide which memory namespaces are queryable, authorize delegation, maintain the canonical task record, mediate cross-worker access, accept or reject state transitions, register artifacts, and preserve provenance and audit metadata. NIST AI RMF describes governance as cross-cutting, requiring documented roles, transparent policies, ongoing monitoring, and lifecycle controls [1]. The NIST Generative AI Profile adds the importance of content provenance, incident reporting, human review where appropriate, and tracking changes that affect verifiability [2].

The GO should not be modeled as a giant prompt containing every memory item. It is the **policy and coordination authority** that determines what may enter a context window and what may become durable. It can maintain references and summaries while delegating task execution, but it remains responsible for the canonical record and final authority over sharing, promotion, correction, retention, and revocation.

### Worker Agent

A worker owns the **execution-local view** of one assigned task. It may organize the task, maintain short-term working state, request approved retrievals, delegate bounded subtasks, produce artifacts, and submit explicit state changes. It does not own organization-wide memory or unilaterally publish a fact into shared long-term memory. Its durable writes should be expressed as a proposed memory item, checkpoint, artifact, or state delta with task identity, scope, producer, and provenance attached.

A worker may read the task envelope and the GO-approved context references. For a cross-task or cross-worker fact, it should use the GO’s retrieval boundary rather than directly browsing another worker’s context. This keeps task isolation meaningful and gives the GO a point at which to apply authorization, filtering, retention, and conflict handling.

### Agent-Specific Sub-Agent

A sub-agent is a **narrow delegated execution scope**, not a peer memory authority. It receives a minimum necessary task slice: objective, constraints, relevant evidence or artifact references, and an explicit output contract. Its context and short-term state are isolated from sibling sub-agents and from unrelated worker tasks. It returns an explicit result, state delta, finding, or artifact reference to its parent worker; it does not directly alter canonical task state or shared long-term memory.

A sub-agent may create a candidate artifact or a local observation, but publication, promotion, merging, or delivery is performed by the worker and/or GO. Its lifetime can end without losing the canonical task record because the authoritative state is above the sub-agent boundary. This also limits accidental propagation of stale, speculative, or irrelevant context.

## Context-window and retrieval flow

1. **Task admission.** An external request or scheduled objective arrives at the GO. The GO creates a task identity, establishes the applicable user/tenant/project and data scopes, sets completion criteria and context limits, and records the initial task state.

2. **Task envelope.** The GO assigns a worker and sends a bounded envelope containing the objective, constraints, permitted capabilities, relevant state, approved memory/artifact references, and the worker’s authority to delegate. The envelope is not a dump of all historical context.

3. **Context assembly.** The worker combines the current task input, recent task-local short-term memory, canonical state needed for the next action, and selected results from governed retrieval. Retrieval should return the smallest sufficient evidence set plus source/provenance metadata. MemGPT demonstrates the architectural pattern: out-of-context material must be explicitly moved into the main context, and paging/retrieval must respect the finite context limit [4].

4. **Memory pressure and compaction.** As the bounded context fills, the worker may summarize or evict low-value short-term material, but compaction is not silent deletion of the authoritative record. The GO or governed state service retains the original task events, approved summaries, and artifact references according to policy. MemGPT’s queue manager illustrates warnings, eviction, recursive summaries, and recall of evicted messages through explicit functions [4].

5. **Delegation.** If a specialized operation is needed, the worker creates a sub-agent scope with a minimal context slice. It should pass references instead of duplicating large records when possible, while ensuring the sub-agent has only the evidence and permissions needed for that slice.

6. **Return and merge.** The sub-agent returns a bounded result, explicit uncertainty or validation status where relevant, and any artifact references. The worker evaluates the result against the delegated contract, incorporates it into task-local state, and sends an explicit state delta or artifact registration request upward. The GO validates the transition and updates canonical task state.

7. **Retrieval and re-entry.** A later worker or sub-agent can request long-term memory or prior artifacts through the GO’s retrieval boundary. The result is re-entered into a fresh bounded context only after authorization, relevance selection, and provenance checks. RAG research supports the separation of parametric model knowledge from externally retrieved memory and identifies provenance as an open concern that the architecture must address [6].

8. **Completion and closure.** On completion, the GO records status, accepted outputs, unresolved issues, provenance, and retention instructions. It decides which short-term observations are eligible for long-term promotion, which artifacts are deliverables versus transient intermediates, and which delegation scopes should be closed or revoked.

## Retrieval, isolation, and access rules

**Retrieval is a controlled data flow, not an unrestricted memory read.** A retrieval request should be evaluated against task identity, principal/agent identity, purpose, sensitivity, retention, and artifact or memory scope before content is returned. Relevance alone is insufficient. The Generative Agents work describes retrieval using relevance, recency, and importance, while also identifying retrieval failures and fabricated embellishments as common errors [5]. A governable architecture should therefore expose retrieval provenance and confidence/validation status to the consuming worker, and should permit the GO to constrain or deny retrieval.

**Isolation defaults to deny.** A worker sees its own task state and approved shared references; it does not see another worker’s working context by default. A sub-agent sees only its delegated slice; sibling sub-agents do not share state unless the worker explicitly routes an approved result. Cross-task memory is accessed through the GO, not through peer-to-peer context copying. This prevents accidental disclosure and limits contamination by irrelevant or adversarial task history.

**Context is intentionally lossy; authority is not.** A context window can contain a summary, selected evidence, and current working notes. It should not be treated as the source of truth for task status, artifact identity, access rights, or historical events. Summaries are derived views and should remain linked to the source state or evidence they summarize.

**Writes are more privileged than reads.** Reading approved evidence may be delegated; publishing a durable memory, changing canonical task status, changing retention, or superseding an artifact should require an explicit upward write path. The GO can distinguish candidate observations from accepted memory, and draft artifacts from approved deliverables.

## Task-state and artifact boundaries

### Task state as a governed state machine

The GO should maintain a canonical task record containing at least the task identity and scope, current lifecycle status, assigned worker, dependency and checkpoint references, delegation relationships, approvals or holds, artifact references, unresolved exceptions, and closure/retention decision. A worker may maintain a richer local working view, but it must submit explicit deltas rather than silently redefining the task. Sub-agent status is subordinate and should not independently advance the parent task.

Control flow is therefore: **GO creates/authorizes → worker proposes and executes → sub-agent reports → worker consolidates → GO accepts, rejects, or requests revision**. Data flow is: **task inputs and approved references downward; bounded results, state deltas, artifact references, and evidence upward**. The same distinction applies to retries or reassignment: the GO can rehydrate a new worker from canonical state and accepted artifacts without copying an old worker’s entire context.

### Artifacts as first-class, attributable entities

Artifacts include deliverables, evidence packages, intermediate analyses, plans intended for reuse, validation results, and externally observable state changes. They should be distinguishable from memory because an artifact has a lifecycle, an audience, a producer, possible reviewers, and a relationship to the task that generated it. The worker may produce it, but the GO controls registration, visibility, acceptance, supersession, retention, and delivery.

The W3C PROV model supplies a useful surface vocabulary: an **entity** is a physical, digital, conceptual, or other thing with fixed aspects; an **activity** acts upon or generates entities; and provenance can express generation, usage, derivation, attribution, and responsibility [3]. Applied here, the worker/sub-agent activity uses approved inputs and generates an artifact entity; a later activity may derive a revised artifact; and the producing agent or worker can be attributed without exposing hidden reasoning. This makes an artifact auditable as an output of a governed task flow rather than an unexplained blob in a chat transcript.

At minimum, every accepted artifact should be linked to its task, producing worker/sub-agent scope, input references, generation activity, validation/approval status, and supersession or retention decision. The link should remain available when only a reference—not the artifact body—is placed in a context window.

## Promotion and lifecycle policy

A practical lifecycle is **observe → hold in short-term task memory → validate/normalize → propose promotion → GO accept/reject → retrieve by scope → revise or expire**. The worker can identify candidate durable facts, summaries, or lessons, but the GO should determine whether they are sufficiently reliable, permitted, and useful for cross-task retention. A candidate memory should retain source task and artifact links so later users can distinguish direct evidence from a derived summary.

Promotion should be conservative for sensitive, user-specific, speculative, or low-confidence material. Correction and deletion must propagate to derived summaries and retrieval indexes conceptually, not just to the most recent copy. NIST’s GenAI Profile specifically calls for tracking dataset modifications, deletions, rectification requests, and changes affecting the verifiability of content origins [2]. Although the profile is not an agent-memory protocol, the same lifecycle principle applies to governed memory and artifact lineage.

Long-term memory should not be a universal shared scratchpad. Use explicit namespaces and scopes such as task, user/tenant, project, organizational policy, and public/reference. The GO controls whether a worker can query, contribute to, or derive from each namespace. A worker’s task-local summary can be retained without making every underlying conversation globally searchable.

## Architectural findings

1. **A context window is bounded working memory, not durable state.** External memory and explicit paging/retrieval are required when a task exceeds the context limit; the GO must preserve authority outside the window [4].

2. **Short-term memory should be worker/task scoped.** Recent messages, provisional observations, and working summaries belong to the active task and should not leak to sibling workers or sub-agents unless explicitly routed.

3. **Long-term memory requires a governance boundary.** The GO owns namespace, authorization, promotion, retention, correction, and deletion; workers submit candidates rather than directly publishing shared memory.

4. **Retrieval is both a data-plane and control-plane event.** The result must be selected for task relevance and bounded context fit, but also checked for scope, authorization, provenance, and possible staleness. Relevance, recency, and importance are useful retrieval dimensions, not sufficient trust guarantees [5].

5. **Canonical task state belongs above the worker.** Workers and sub-agents may maintain local working views and propose state deltas, but the GO owns lifecycle status, dependencies, assignments, approvals, exceptions, and closure.

6. **Sub-agents should be isolated, minimal-context executors.** A sub-agent receives only a delegated slice and returns an explicit result, state delta, or artifact reference; it has no default access to peer contexts or shared durable memory.

7. **Artifacts must be separated from memory and treated as attributable outputs.** W3C PROV’s entity/activity/agent relationships provide a useful conceptual boundary for usage, generation, derivation, and attribution [3].

8. **Context compaction must not erase canonical history.** Summaries and evictions are derived views; source task events, accepted state, evidence, and artifact lineage remain governed outside the window [4].

9. **Downward flow carries bounded authority and references; upward flow carries evidence and proposed changes.** This asymmetry limits lower-level agents’ ability to broaden access or silently change system truth.

10. **Governance is continuous and lifecycle-wide.** Documented roles, monitoring, provenance practices, human review/override where warranted, and safe decommissioning or retention decisions are architectural controls, not afterthoughts [1][2].

## Sources

[1] National Institute of Standards and Technology, **“Artificial Intelligence Risk Management Framework (AI RMF 1.0)”**, NIST AI 100-1 (2023). https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf

[2] National Institute of Standards and Technology, **“Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile”**, NIST AI 600-1 (2024). https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf

[3] W3C Provenance Working Group, **“PROV-DM: The PROV Data Model”**, W3C Recommendation (2013), and overview at **“PROV-Overview: An Overview of the PROV Family of Documents.”** https://www.w3.org/TR/2013/REC-prov-dm-20130430/ ; https://www.w3.org/TR/prov-overview/

[4] Charles Packer et al., **“MemGPT: Towards LLMs as Operating Systems,”** arXiv:2310.08560 (2023; revised 2024). https://arxiv.org/abs/2310.08560

[5] Joon Sung Park et al., **“Generative Agents: Interactive Simulacra of Human Behavior,”** arXiv:2304.03442 (2023). https://arxiv.org/abs/2304.03442

[6] Patrick Lewis et al., **“Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,”** NeurIPS 2020, arXiv:2005.11401. https://arxiv.org/abs/2005.11401

## Caveat

The GO/worker/sub-agent hierarchy and its ownership rules are a **reference architecture synthesis** derived from the cited governance, provenance, retrieval, and memory-management sources; none of the cited sources alone standardizes this exact three-level organizational decomposition. The sources support the underlying separations—bounded context versus external memory, explicit retrieval, task/activity provenance, and lifecycle governance—while the proposed authority boundaries adapt those principles to a governable multi-agent system.
      
