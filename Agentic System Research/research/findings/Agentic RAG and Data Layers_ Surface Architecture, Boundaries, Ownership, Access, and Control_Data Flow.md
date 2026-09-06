# Agentic RAG and Data Layers: Surface Architecture, Boundaries, Ownership, Access, and Control/Data Flow

## Scope and framing

This report covers only the **surface architecture** of a governed agent hierarchy: **Governable Orchestrator → Worker Agents → Agent-Specific Sub-Agents**. It treats retrieval-augmented generation (RAG) as a data-access pattern, not as a model-internals topic. It therefore focuses on the visible responsibilities and flows around retrieval, knowledge stores, databases, schemas, permissions, freshness, provenance, and control. It does not prescribe code, deployment, low-level storage formats, vendors, or hidden reasoning.

NIST defines RAG as pairing a generative model with a separate information-retrieval system or knowledge base; a query identifies relevant information, which is supplied to the model as context, allowing internal model knowledge to be modified without retraining [1]. The core architectural consequence is a **boundary between the authoritative data layer and the generation layer**: the model is not the system of record, and retrieval is a controlled dependency rather than an implicit memory.

## Reference surface architecture

```text
User / calling system
        │ request, identity, purpose, constraints
        ▼
Governable Orchestrator
  - owns task contract, policy decision, delegation, budgets, stop conditions
  - selects workers and approved knowledge domains
        │ scoped work order + delegated authorization context
        ▼
Worker Agents (domain/task owners)
  - own domain retrieval plan and evidence assembly
  - call approved retrieval capabilities and coordinate sub-agents
        │ narrowly scoped subtask + inherited constraints
        ▼
Agent-Specific Sub-Agents
  - perform bounded lookup, comparison, validation, or transformation
  - return evidence and status, not unrestricted data access
        │
        ▼
Policy-enforcing retrieval boundary
  - identity/claims, purpose, tenant/domain, sensitivity, row/document scope
  - query/index/database access, filtering, ranking, freshness checks
        │
        ├── Authoritative source systems / governed databases
        ├── Curated knowledge stores and retrieval indexes
        ├── Provenance and lineage records
        └── Audit, policy, and freshness metadata
```

The retrieval boundary is intentionally shown below the agents. Agents request evidence through a governed capability; they do not become owners of source systems. The orchestrator remains accountable for the overall task and for cross-domain release of results, while workers and sub-agents are accountable for the bounded work they were delegated.

## Control flow and data flow

A governed request should travel with a **task contract** containing the requester or calling-principal identity, delegated agent identity, purpose, permitted domains, sensitivity ceiling, tenant or organizational scope, freshness requirement, output audience, and time or cost budget. The orchestrator evaluates that contract against policy before selecting a worker. Delegation should narrow or preserve authority, never silently expand it. A worker receives a scoped work order, not a general-purpose credential; a sub-agent receives an even narrower subtask and the same or stricter constraints.

The visible RAG loop is a controlled cycle:

1. **Plan and authorize:** the orchestrator determines whether retrieval is needed, which worker domains are eligible, and what data scope is allowed.
2. **Decompose:** a worker may form focused retrieval requests for its domain. Agentic retrieval can use multiple focused subqueries, including parallel subqueries, instead of one broad query [4].
3. **Retrieve:** the retrieval boundary applies identity-, purpose-, domain-, tenant-, and sensitivity-aware filtering before returning candidate records or passages. Microsoft explicitly recommends enforcing document-level access at retrieval time, rather than relying on the model or prompt to hide restricted content [4].
4. **Assess evidence:** the worker or a specialized sub-agent checks relevance, authority, completeness, conflicts, and freshness metadata. A failed or stale evidence check is a control outcome, not a reason to guess.
5. **Refine when necessary:** a bounded follow-up loop may issue a narrower query, consult an approved second store, or ask for a validation subtask. The orchestrator owns the loop limit, budget, allowed sources, and termination condition.
6. **Assemble and release:** the worker returns an evidence package with citations and policy-safe content. The orchestrator checks that the package meets the task contract, applies any cross-domain release rule, and produces the externally visible response or a refusal/needs-review outcome.

This loop is **data-flow control**, not a claim about hidden model reasoning. A useful implementation boundary is that every loop iteration emits an observable event: requested scope, authorized scope, source/index queried, evidence identifiers, freshness result, decision, and reason for continuation or termination.

## Findings

### 1. Keep authoritative knowledge separate from retrieval indexes and generated context

The source system or governed database remains the authority for the underlying fact. A curated knowledge store may normalize or aggregate approved content, while a retrieval index is an optimization for finding relevant material. The context sent to a model is a transient evidence view, not a new authority. This separation supports correction, revocation, re-indexing, and independent audit. NIST’s definition explicitly describes the retrieval system as separate from the generative model [1]; the original RAG work similarly distinguishes parametric memory from an explicit non-parametric memory, represented in its experiment by a dense index [2].

**Boundary and ownership:** source owners govern meaning, retention, classification, and correction of records; the knowledge/retrieval owner governs curation, indexing, and synchronization; agents consume approved views but do not overwrite source truth. The orchestrator owns the decision to use a source, not the source’s content.

### 2. Treat the orchestrator as the policy and delegation boundary

The Governable Orchestrator should be the control point for task scope, worker selection, approved data domains, maximum retrieval breadth, freshness requirements, escalation, and final release. It should maintain an explicit delegation chain: requester → orchestrator → worker → sub-agent. Each hop should preserve an attributable principal and a bounded authority. A worker should not be able to ask a sub-agent to access a store excluded by the orchestrator, and a sub-agent should not be able to turn a read task into a write, export, or permission-changing action.

**Control flow:** authorization is evaluated before retrieval and again at any boundary where data is combined or released. The final response is a new disclosure decision: authorization to retrieve a record does not automatically authorize sending it to every downstream audience.

### 3. Make workers domain owners of evidence assembly, not owners of the data

A Worker Agent is a domain/task coordinator. It can select among approved retrieval capabilities, reconcile results within its scope, request validation, and return a bounded evidence package. It should own the **quality of the retrieval result for its assigned task**—coverage, relevance, conflicts, freshness checks, and citation completeness—but not the underlying business record or its access policy.

A worker’s interface should expose the purpose and scope of each retrieval request and return structured status such as authorized, denied, partial, stale, conflicting, or unavailable. This makes missing evidence visible to the orchestrator. It also prevents a worker from treating an empty result as proof that no information exists; an empty result may reflect authorization filtering or an unavailable source.

### 4. Constrain agent-specific sub-agents to narrow, read-oriented evidence tasks

Agent-Specific Sub-Agents are useful for bounded operations such as finding records matching a declared predicate, comparing two approved documents, checking whether a citation supports a claim, or evaluating freshness metadata. They should receive the minimum scope needed, inherit the parent worker’s restrictions, and return evidence references plus an assessment. They should not receive unrestricted access to all worker stores, nor should they silently broaden a query because the first retrieval was incomplete.

The preferred return is an **evidence envelope**: source or record identifier, permitted excerpt or result, authority/classification labels, source and index timestamps, provenance reference, retrieval status, and any conflict or uncertainty flag. This keeps sub-agent output useful without turning every sub-agent into an ungoverned data broker.

### 5. Apply permission filtering at retrieval time and preserve permissions through composition

Access checks should happen before evidence is placed in a worker or model context. Microsoft’s RAG guidance calls for access control at retrieval time and document-level security filters, and warns that uncontrolled indexes can leak sensitive content [4]. The architecture should also enforce permissions after retrieval: when workers merge results from several domains, the intersection of the caller’s authority, delegated scope, and output audience must govern the assembled package.

Permissions are metadata associated with the source item or data object, not merely instructions in a prompt. The retrieval boundary should evaluate principal, group or role claims, tenant/domain, purpose, sensitivity, and any time or geographic restrictions required by policy. Denials, redactions, and partial results should be explicit and auditable. Retrieved text should be treated as untrusted data: it may contain instructions or content that attempts to alter the agent’s authority; it cannot change policy, delegation, or tool scope [4].

### 6. Use a conceptual schema that travels with every retrievable object

A surface-level schema should represent the object’s identity and governance attributes independently from its searchable content. At minimum, the retrieval view should associate: **stable object identifier; source authority; owner/steward; domain or tenant; classification/sensitivity; access-policy reference; source location; version; effective and observed timestamps; freshness target; retention status; quality/approval status; index status; provenance reference; and citation label**. Content may be chunked or represented in multiple indexes, but all derived representations must link back to the stable source object and version.

This schema is a governance contract, not a low-level format. It allows the retrieval boundary to filter before exposure, lets a worker explain why evidence was selected, and enables the orchestrator to reject evidence lacking required authority or freshness. It also distinguishes **source time** (when the information became effective), **observation time** (when it was read), and **index time** (when the retrieval view was last synchronized), which are materially different freshness signals.

### 7. Make provenance a first-class data flow from source to answer

W3C PROV models provenance as information about entities, activities, and agents involved in producing data, supporting assessments of quality, reliability, and trustworthiness [3]. Applied to agentic RAG, a provenance chain should link the authoritative object and version to curation/indexing activity, retrieval request, worker/sub-agent activity, selected evidence, and final response artifact. The chain should identify responsible owners and agents without exposing hidden reasoning.

Citations are the user-facing projection of this chain; audit records can be more complete than citations. The RAG literature identifies provenance and knowledge updating as open problems [2], so provenance should not be assumed to emerge automatically from retrieval. The orchestrator should require provenance references for material evidence and should mark an answer as unsupported, partial, or requiring review when the chain is missing or broken.

### 8. Make freshness a policy input and define stale-data behavior

RAG is useful for private and frequently changing information, but retrieval alone does not guarantee freshness [1,4]. Each task should carry a freshness requirement, such as “current as of request time,” “effective on a specified date,” or “historical version.” The retrieval boundary should compare source and index timestamps, version/effective dates, synchronization status, and any domain-specific expiry rule.

The architecture must define what happens when freshness is not met: re-check the authoritative source, use a permitted older version with an explicit warning, return a partial result, escalate to a human or source owner, or refuse to answer. A stale index should not be silently presented as current. Freshness failures and revalidation attempts belong in provenance and audit trails, and workers should report them to the orchestrator rather than compensate by broadening access.

### 9. Separate read, write, and policy-changing capabilities

Most RAG retrieval should be read-only. If an agentic workflow can create annotations, update a knowledge curation queue, or request re-indexing, those actions should be distinct capabilities with separate authorization and ownership. A sub-agent that can read evidence should not thereby gain authority to edit the source, alter permissions, approve content, or delete provenance. The orchestrator controls whether a write-like follow-up is allowed, while the domain owner remains accountable for accepting the change.

This capability separation also controls data exfiltration: export, bulk retrieval, cross-tenant joins, and forwarding evidence to an external audience are higher-risk operations than returning a narrow citation-backed answer. The same task contract and provenance chain should cover these transitions.

### 10. Make quality, conflict, and failure visible rather than silently synthesized

Agentic RAG can query multiple stores or subqueries and then combine results. A worker should preserve source identity, authority, version, and conflicts rather than flattening them into an apparently unanimous fact. Ranking improves retrieval relevance but does not establish truth. If approved sources disagree, the evidence package should identify the disagreement and apply a declared precedence rule or escalate.

The orchestrator should distinguish at least: no authorized evidence, no matching evidence, stale evidence, conflicting evidence, source unavailable, and policy-denied evidence. This distinction is important for governance and user trust. Microsoft notes that incomplete or irrelevant retrieval can still produce inaccurate responses even when the system is nominally grounded [4]; therefore grounding and citation should be accompanied by evidence-quality and access status, not treated as a guarantee.

## Ownership and boundary matrix

| Surface component | Primary ownership | May access | Must not decide or change |
| --- | --- | --- | --- |
| Governable Orchestrator | Task governance, delegation, global policy, release decision, loop/budget limits | Approved worker capabilities and policy services | Source meaning, source permissions, or hidden expansion of authority |
| Worker Agent | Domain retrieval plan, evidence assembly, quality and conflict reporting | Approved stores/indexes for its domain under delegated scope | Cross-domain disclosure without authorization; source-of-truth edits |
| Agent-Specific Sub-Agent | Narrow lookup, comparison, validation, or transformation | Only the subtask’s policy-filtered evidence capability | New tools, broader scope, permission changes, or silent write actions |
| Retrieval boundary | Identity evaluation, filtering, query routing, freshness and provenance capture | Source/index metadata and policy decisions | Generation, task interpretation, or overriding source policy |
| Source system / governed database | Record meaning, lifecycle, classification, access policy, correction | Its own authoritative records | Agent task planning or answer synthesis |
| Knowledge store / retrieval index | Curated searchable representation, synchronization, index metadata | Approved source representations | Becoming authoritative merely because it ranks highly |
| Provenance and audit layer | Lineage, attribution, access and decision records | Events and references across the flow | Changing the underlying source or granting access |

## Minimum control points

A governed surface architecture should expose the following checkpoints: **(a)** identity and purpose captured before planning; **(b)** worker and sub-agent delegation narrowed before invocation; **(c)** retrieval-time authorization applied before context exposure; **(d)** untrusted retrieved content prevented from changing policy; **(e)** evidence linked to source, version, authority, and timestamps; **(f)** freshness evaluated against task policy; **(g)** conflicts, denials, partial results, and stale results surfaced; **(h)** final disclosure checked against audience and delegated scope; and **(i)** provenance and audit records retained according to the governing data policy.

These controls make the hierarchy governable without assuming that the orchestrator can inspect or reproduce model-internal reasoning. The control surface is the request, delegation, retrieval, evidence, provenance, freshness, and release path.

## Sources

[1] **National Institute of Standards and Technology (NIST), “retrieval-augmented generation,” NIST Glossary**, citing NIST AI 100-2e2025. <https://csrc.nist.gov/glossary/term/retrieval_augmented_generation>

[2] **Patrick Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” Advances in Neural Information Processing Systems 33 (NeurIPS 2020)**. <https://proceedings.neurips.cc/paper_files/paper/2020/hash/6b493230-Abstract.html>

[3] **W3C, “PROV-Overview: An Overview of the PROV Family of Documents,” W3C Working Group Note (2013)**. <https://www.w3.org/TR/prov-overview/>

[4] **Microsoft Learn, “Retrieval augmented generation (RAG) and indexes,” Microsoft Foundry documentation**. <https://learn.microsoft.com/en-us/azure/foundry/concepts/retrieval-augmented-generation>

[5] **National Institute of Standards and Technology, “Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile,” NIST AI 600-1 (2024)**. <https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence>

## Caveat

The cited sources establish RAG separation, retrieval/augmentation/generation flow, agentic query decomposition, retrieval-time access control, provenance concepts, and the governance rationale for grounding and updates. The three-level ownership and control boundaries in this report are a **synthesized reference architecture** derived from those principles, not a normative standard for a particular product or organization.
