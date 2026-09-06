# Architecture Patterns and Trade-offs

## Scope and framing

This report examines **surface architecture only** for a three-level agent arrangement:

> **Governable Orchestrator → Worker Agents → Agent-Specific Sub-Agents**

“Surface architecture” here means the visible allocation of responsibility and authority: system boundaries, ownership of work and state, access relationships, and control/data flow. It does **not** address code, deployment, low-level data formats, vendors, or hidden reasoning. The pattern labels describe organizational and interaction choices; they are not mutually exclusive implementation categories. In particular, a system can be hierarchical in its authority while using event-driven communication or a blackboard for shared state.

The central governance question is: **who is allowed to decide, who may see or change which state, and how can a decision or data change be traced across the three layers?** NIST’s current agent-standards work emphasizes trusted interoperability, agent authentication/identity, and authorization for actions taken by software and AI agents.[^nist-standards][^nist-identity] Those concerns apply regardless of topology.

## Pattern comparison at a glance

| Pattern | Primary boundary and owner | Access model | Control flow | Data flow | Main strengths | Main trade-offs |
|---|---|---|---|---|---|---|
| **Centralized** | One Governable Orchestrator owns global task state, policy decisions, routing, and final acceptance. Workers and sub-agents are subordinate execution boundaries. | Orchestrator grants scoped work and information access; workers normally access only assigned context and their sub-agents. | Top-down dispatch; bottom-up status, results, exceptions, and evidence. | Mostly point-to-point request/result flow through the orchestrator. | Strong policy enforcement, auditability, prioritization, and global consistency. | Orchestrator is a bottleneck and a high-value failure or attack point; limited autonomy and potentially higher coordination latency. |
| **Hierarchical** | Authority and ownership are delegated by level: orchestrator governs workers; each worker governs a bounded team of agent-specific sub-agents. | Parent grants least-privilege scope to child; lateral access is normally mediated or prohibited. | Commands and constraints descend; summaries, escalations, and completion signals ascend. | Aggregated information crosses levels; local detail stays within the lower boundary unless promoted. | Scales coordination through decomposition and abstraction; preserves local autonomy while retaining global direction. | Errors, stale summaries, or conflicting objectives can propagate across levels; parent failure can affect a whole subtree; cross-branch coordination is harder. |
| **Peer-to-peer** | No permanent superior owns the whole workflow. Workers and/or sub-agents are peers that retain local state and negotiate responsibility; an orchestrator may be only a policy boundary or convening role. | Peers expose selected capabilities/state directly and decide which requests to accept. Access is bilateral or governed by shared policy rather than command hierarchy. | Lateral negotiation, proposals, commitments, and consensus; upward control is weak or absent. | Direct agent-to-agent exchange; information may be replicated or selectively shared. | Resilience, local responsiveness, parallelism, and no single coordination bottleneck. | Harder global policy enforcement and audit; discovery, conflict resolution, convergence, and identity/authorization become system-wide concerns; communication can grow rapidly with peers. |
| **Blackboard** | A shared problem-space/knowledge state is the boundary. A control component (which may be the orchestrator or a delegated controller) owns admission, prioritization, and conflict policy; agents own contributions within their scopes. | Agents read/write designated regions or classes of shared state; control policy decides which contributions are visible, actionable, or promotable. | State changes enable or trigger the next eligible agent; control is based on board conditions rather than a fixed call chain. | Agents publish partial results, observations, hypotheses, and status to the common state; other agents consume what their role permits. | Loose coupling, incremental cooperation, heterogeneous specialists, and shared situational awareness. | Shared-state contention, unclear provenance/ownership, stale or conflicting contributions, and controller complexity. IEEE research specifically notes that central-repository MAS use the blackboard pattern and that agent control strategies can become inherently complex; an event-based control strategy separates control policies from the control component to ease evolution.[^ieee-blackboard] |
| **Event-driven** | Producers own the fact/event they emit; consumers own their reaction and local view. An event channel is an interaction boundary. A mediator, if present, owns workflow state and command routing; a broker does not own a multistep transaction. | Consumers subscribe to permitted event classes; producers do not need to know consumers. Authorization still limits who can publish, observe, or act on an event. | Asynchronous, trigger-based progression. Broker topology has no central orchestration; mediator topology explicitly controls event flow and error/restart handling. | Events move from producers through a channel to one or many consumers. Consumers may maintain independent views; streaming supports replay, while publish-subscribe generally does not retain past events for new subscribers.[^ms-event] | Decoupling, responsiveness, fan-out, independent scaling of responsibilities, and natural reaction to new information. | Eventual consistency, ordering/replay and duplicate-handling concerns, difficult end-to-end transaction ownership, and reduced immediate visibility of who caused a downstream action. A mediator improves control but introduces coupling and can become a bottleneck.[^ms-event] |
| **Hybrid** | Ownership is intentionally split: the orchestrator retains global policy, safety, budgets, and acceptance; workers own bounded plans; sub-agents or peer groups own local execution; shared/event state connects boundaries. | Layered least privilege for authority, plus selective subscriptions or blackboard regions; local autonomy is constrained by parent policy. | Strategic top-down control combined with local negotiation, blackboard eligibility, or event-triggered execution. | Global directives and summaries cross levels; detailed local state remains local; salient changes are published as events or shared artifacts. | Balances governability and resilience; supports different coordination modes for different subproblems and failure domains. | More difficult to reason about than a single pattern; overlapping ownership and mixed synchronization can create policy gaps, contradictory state, or ambiguous accountability. Requires explicit precedence rules and escalation paths. |

The descriptions above synthesize the hierarchical taxonomy’s dimensions of control hierarchy, information flow, role/task delegation, temporal layering, and communication structure,[^hierarchy] the IEEE blackboard account,[^ieee-blackboard] the event-driven architecture guidance,[^ms-event] and NIST’s identity/authorization framing.[^nist-identity]

## Pattern analyses in the three-level arrangement

### 1. Centralized: the orchestrator as the control plane

In a centralized arrangement, the **Governable Orchestrator** is the authoritative owner of the overall objective, task decomposition, policy evaluation, worker assignment, and final decision. A Worker Agent is an execution boundary rather than an independent authority: it may plan within its assigned domain, but the orchestrator controls admission, scope, priority, cancellation, and acceptance. An Agent-Specific Sub-Agent is even more tightly bounded and normally receives work only through its parent Worker Agent.

The characteristic flow is a command/result loop. The orchestrator sends a bounded task and constraints downward. The worker may delegate a subtask to an agent-specific sub-agent, then returns a status, result, exception, and supporting record upward. Data tends to follow the same path, which makes responsibility legible: the orchestrator can identify which worker and sub-agent acted and under which delegation. Access is naturally centralized as well: the orchestrator can issue, narrow, suspend, or revoke the authority that a worker passes to a sub-agent.

The trade-off is concentrated control. The same component that provides global consistency and a clear audit boundary becomes a throughput, availability, and attack concentration point. It may also become over-involved in local decisions, increasing latency and reducing the benefits of specialization. Centralization is therefore strongest when tasks are tightly coupled, policy is stringent, and a single accountable decision-maker is more valuable than local autonomy.

### 2. Hierarchical: authority and abstraction by level

Hierarchy preserves a chain of command but distributes coordination. The orchestrator operates at a **global or strategic** level; workers operate at a **domain or task-team** level; agent-specific sub-agents operate at a **specialist or local execution** level. Each parent owns the boundary of its child team: it allocates work, sets constraints, aggregates results, and escalates conditions it cannot resolve. The child does not automatically inherit the parent’s full visibility or authority.

Control flows down as goals, budgets, priorities, constraints, and escalation rules. Information flows up as summaries, confidence/quality indicators, exceptions, and completion evidence. Lateral communication may be disallowed, mediated by a parent, or enabled selectively where two worker domains have a recognized dependency. Keeping detailed local state within the worker/sub-agent boundary reduces global communication, while promoting only decision-relevant summaries protects the orchestrator from unnecessary detail.

The principal benefit is **scalable coordination through decomposition**. The hierarchical taxonomy describes how hierarchy can reduce communication overhead and establish clear authority, while allowing higher levels to operate at broader abstraction or longer time horizons and lower levels to react locally at shorter horizons.[^hierarchy] The cost is abstraction loss: summaries can omit important context, and a local decision can optimize its subtree while harming a global objective. Governance must therefore specify what may be delegated, what must be escalated, how parent directives override child preferences, and how a child reports uncertainty or a policy conflict.

### 3. Peer-to-peer: lateral autonomy among workers or sub-agents

In a peer-to-peer arrangement, workers (or sub-agents within a worker’s domain) are **equals in authority for their respective local responsibilities**. There is no permanent parent that owns every decision. A Governable Orchestrator can still define system-level policy, identity, safety constraints, or a goal, but it is not the mandatory router for every interaction. Agents communicate directly to negotiate task ownership, exchange observations, coordinate dependencies, and resolve conflicts.

Ownership is local and explicit: each peer owns the state and commitments associated with its work. Access is granted through bilateral or shared rules, not assumed from organizational rank. Data flow is lateral, and control flow is a sequence of proposals, acknowledgements, commitments, and peer decisions. If consensus or voting is used, the authority of that mechanism must be part of the surface governance model; otherwise, “peer” can conceal an informal leader with unclear accountability.

Peer-to-peer removes the central bottleneck and can keep local work operating when another peer is unavailable. It is a poor fit when a single actor must enforce a globally ordered policy or provide a definitive final acceptance. The architecture shifts complexity from the orchestrator into discovery, trust, conflict resolution, convergence, and audit. NIST’s emphasis on agent authentication and authorization is particularly relevant here: direct communication increases the number of access relationships that must be governed.[^nist-standards][^nist-identity]

### 4. Blackboard: shared state as the meeting boundary

The blackboard pattern replaces a fixed call graph with a **shared problem space**. In the three-level model, the orchestrator may own the global blackboard and its control policy; each worker may own a bounded board partition or a namespace for its domain; agent-specific sub-agents contribute observations or partial solutions. Alternatively, a worker can be the local control component for its own board while the orchestrator controls only the global board. The ownership distinction matters: shared visibility does not imply shared authority to overwrite, approve, or promote information.

Agents read what their role permits and write contributions, partial results, hypotheses, status, or identified conditions. A control component watches the board and chooses which eligible capability should act next. Thus, control flow is **state- and policy-driven** rather than necessarily command-driven. Data flow is many-to-many through the shared state. This makes heterogeneous specialists composable: a contribution can enable another specialist without the first agent knowing its identity.

The pattern’s governance hazards are provenance and contention. The architecture should make visible who produced a contribution, who may amend it, which entries are authoritative, and how conflicts are resolved. Otherwise, the orchestrator cannot distinguish a proposed observation from an accepted decision. The IEEE paper on event-based blackboard architecture describes the classic central repository and argues that combining blackboard with implicit invocation can separate control policies from the control component, improving evolvability.[^ieee-blackboard] In this layered arrangement, that suggests a useful division: the orchestrator owns promotion and safety policy, workers own domain contributions, and sub-agents cannot directly turn a tentative contribution into a global commitment.

### 5. Event-driven: facts and reactions across agent boundaries

Event-driven architecture makes **state changes or notable occurrences** the primary coordination boundary. A Worker Agent or sub-agent publishes an event when it observes a relevant condition or completes a bounded activity. The orchestrator, workers, or other sub-agents consume only the event classes to which they are authorized. The publisher need not know every consumer, which reduces direct coupling.

The flow differs by topology. In a broker-style topology, events are broadcast and consumers independently decide whether to act; there is no central component that owns the state of a multistep transaction. This maximizes decoupling but makes global progress, restart, and consistency harder to attribute and manage. In a mediator-style topology, a coordinator maintains workflow state and dispatches commands to designated consumers, improving control and error handling at the cost of greater coupling and a possible bottleneck.[^ms-event]

For the three-level model, event-driven interaction is most governable when events are treated as **claims about what happened**, not as unrestricted commands. The orchestrator can subscribe to worker-level milestones and exceptions, while workers subscribe to sub-agent outcomes relevant to their domain. A worker should not infer that publication itself grants permission for a downstream action. Authorization to act, the owner of the resulting state, and the escalation path remain separate decisions. The event guidance also highlights the consistency trade-off: asynchronous consumers can hold different views temporarily, and durable streams may support replay while ordinary publish-subscribe does not necessarily preserve past events for later consumers.[^ms-event]

### 6. Hybrid: constrain the mix, do not merely combine it

Hybrid architecture is usually the most realistic choice for the stated three-level arrangement. A common surface allocation is: centralized governance at the top, hierarchy for delegation, peer-to-peer coordination inside a worker team, and event-driven or blackboard exchange for observations and incremental results. The orchestrator retains non-delegable responsibilities—global policy, safety boundaries, resource or priority limits, final acceptance, and cross-domain escalation. Workers own domain plans and coordinate their own sub-agents. Sub-agents retain autonomy only within the worker’s explicit scope.

A hybrid’s essential boundary is the **authority/data distinction**. Shared events or blackboard entries can improve awareness without transferring decision rights. A worker may receive peer observations but still require orchestrator approval for a cross-domain or high-impact action. Similarly, an orchestrator can delegate a goal without granting unrestricted access to all worker or sub-agent state. NIST’s identity and authorization work supports making these delegation relationships explicit rather than relying on implicit organizational membership.[^nist-identity]

Hybrid designs offer a useful compromise: local failures need not stop unrelated work, while the top level can maintain a coherent policy. Their principal risk is ambiguous precedence. The architecture must state which rule wins when an orchestrator directive conflicts with a peer agreement, when a blackboard contribution conflicts with an event-derived view, and when a worker’s local autonomy reaches an escalation threshold. Without those rules, a hybrid is not a controlled composition but a collection of overlapping authorities.

## Decision guidance for the Governable Orchestrator

The following choices keep the pattern decision at the surface-architecture level:

1. **Make authority explicit.** Identify the owner of global policy, worker-level plans, sub-agent actions, shared state, and final acceptance. A component that can observe or publish should not automatically be treated as a component that can authorize.
2. **Separate delegation from visibility.** A child may need a goal and limited context without receiving the parent’s full state. Define which information is inherited, summarized, shared laterally, or kept private.
3. **Choose the control path per dependency.** Use direct hierarchical commands for safety-critical or strongly ordered steps; use peer negotiation for locally coupled work; use blackboard or events for incremental, many-consumer observations.
4. **Define escalation and revocation.** A worker or sub-agent should know when it must stop, ask its parent, or surface a conflict. The orchestrator should be able to revoke or narrow delegated authority and identify affected descendants.
5. **Preserve end-to-end accountability.** For each consequential action, the surface record should identify the initiating goal, delegating parent, acting agent, applicable policy, and resulting state owner. This is especially important in brokered events and shared blackboards, where causal paths are less obvious.
6. **Design for the failure mode you can govern.** Centralized and strict hierarchical patterns simplify control but concentrate failure. Peer-to-peer and brokered event patterns distribute failure but complicate consistency and audit. Hybrid designs can balance both only if boundaries and precedence are explicit.

## Findings

1. **Centralized control maximizes policy visibility and global consistency but concentrates authority, failure, and throughput risk in the Governable Orchestrator.**
2. **Hierarchy is a delegation boundary, not merely a visual layering:** each Worker Agent should own a bounded sub-tree, while the orchestrator retains non-delegable policy and acceptance authority.
3. **Peer-to-peer trades command simplicity for distributed coordination:** local ownership and resilience improve, but identity, authorization, consensus, conflict resolution, and audit must span lateral relationships.
4. **A blackboard makes shared state the data boundary and a control policy the decision boundary; read/write visibility must not be confused with authority to approve or commit.**
5. **Event-driven systems decouple producers from consumers and support fan-out, but asynchronous flow creates eventual-consistency windows and weakens inherent ownership of multistep transactions.**
6. **Mediator-style event flow restores workflow control and restart/error ownership, but introduces coupling and a potential central bottleneck; broker-style flow is more autonomous but harder to govern end-to-end.**
7. **Hybrid architecture is suitable when global governance and local autonomy are both required, provided the design states authority precedence, escalation thresholds, state ownership, and how events/blackboard entries relate to commands.**
8. **Across all patterns, identity and authorization are architectural boundaries:** every delegation, subscription, shared-state write, peer request, and consequential action needs an accountable owner and a permitted scope.

## Sources

[^nist-standards]: National Institute of Standards and Technology (NIST), **“AI Agent Standards Initiative”**. https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative

[^nist-identity]: National Cybersecurity Center of Excellence (NCCoE), NIST, **“Software and AI Agent Identity and Authorization.”** https://www.nccoe.nist.gov/projects/software-and-ai-agent-identity-and-authorization

[^hierarchy]: David J. Moore, **“A Taxonomy of Hierarchical Multi-Agent Systems: Design Patterns, Coordination Mechanisms, and Industrial Applications,”** arXiv:2508.12683 (2025). https://arxiv.org/html/2508.12683

[^ieee-blackboard]: J. Dong, S. Chen, and J.-J. Jeng, IEEE, **“Event-based blackboard architecture for multi-agent systems,”** International Conference on Information Technology: Coding and Computing (ITCC’05), DOI: 10.1109/ITCC.2005.149. https://ieeexplore.ieee.org/document/1425173/

[^ms-event]: Microsoft Azure Architecture Center, **“Event-driven architecture style.”** https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven

## Source-quality note

The sources include two official U.S. government pages (NIST/NCCoE), an IEEE-published conference record, a recent academic taxonomy available through arXiv, and an authoritative architecture-style guide. The pattern comparison is an explicit synthesis for the requested three-level agent arrangement; it should not be read as claiming that any one source standardizes all six patterns or prescribes a single architecture.

## Caveat on scope

No claims are made here about implementation mechanisms, deployment topology, model internals, low-level message schemas, or hidden reasoning. The report deliberately stays at the level of visible boundaries, ownership, access, and control/data flow.

---

**Prepared for:** Architecture-pattern research for a Governable Orchestrator → Worker Agents → Agent-Specific Sub-Agents system.

**Report date:** 2026-09-02

**Report file:** `/home/ubuntu/research_agentic_architecture/06-patterns.md`

*Note: The report date reflects the research environment’s current date.*

## References

1. NIST, “AI Agent Standards Initiative.” https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative
2. NIST NCCoE, “Software and AI Agent Identity and Authorization.” https://www.nccoe.nist.gov/projects/software-and-ai-agent-identity-and-authorization
3. Moore, “A Taxonomy of Hierarchical Multi-Agent Systems.” https://arxiv.org/html/2508.12683
4. Dong, Chen, and Jeng, “Event-based blackboard architecture for multi-agent systems.” https://ieeexplore.ieee.org/document/1425173/
5. Microsoft Azure Architecture Center, “Event-driven architecture style.” https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven

> **Bottom line:** Select the topology based on where authority must reside, then make every cross-boundary access, state transition, and escalation path explicit enough to govern.
