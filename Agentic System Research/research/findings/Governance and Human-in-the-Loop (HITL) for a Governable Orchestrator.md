# Governance and Human-in-the-Loop (HITL) for a Governable Orchestrator

## Scope and architectural question

This report examines one architecture dimension only: **governance and human control** across the surface hierarchy **Governable Orchestrator → Worker Agents → Agent-Specific Sub-Agents**. It focuses on governance, policy, authorization, approvals, audit, security, escalation, and recovery—specifically the system boundaries, ownership, access, and control/data flows among these layers.

It intentionally does **not** describe implementation code, deployment topology, low-level message or credential formats, particular vendors, or hidden model reasoning. The terms *agent* and *sub-agent* refer to governed actors in an operating hierarchy, not to autonomous principals with independent organizational authority.

## Executive architecture position

The Governable Orchestrator should be the **policy-enforcing control plane and accountable coordination boundary**. Worker Agents should be **bounded execution coordinators** that receive delegated objectives and scoped authority. Agent-Specific Sub-Agents should be **least-privilege specialists** whose authority is narrower than their parent Worker Agent and whose actions remain attributable through the delegation chain. A human approver or accountable business owner remains the decision authority for actions whose risk, irreversibility, external impact, or uncertainty exceeds the configured autonomy threshold.

The central invariant is: **a child may propose or perform only what its parent was authorized to delegate, and no child action may silently expand the authority of the chain**. Policy evaluation, approval state, identity/delegation context, audit capture, interruption, and recovery therefore sit at or are enforceable through the Orchestrator boundary—not solely inside a Worker Agent or Sub-Agent.

## Surface architecture and ownership

| Layer | Primary ownership | Allowed responsibility | Governance boundary |
|---|---|---|---|
| **Governable Orchestrator** | Organizational AI/system owner, risk/compliance authority, and designated operations owner | Registers the agent hierarchy; maps intended purpose and risk; applies policy; grants and constrains delegation; classifies actions; routes approvals; records authoritative audit events; monitors; pauses, revokes, rolls back, or escalates work | Trust boundary between organizational policy and agent execution. It is the point at which authority is issued, narrowed, checked, and revoked. |
| **Worker Agent** | Domain/workflow owner accountable for the assigned workstream | Decomposes an authorized objective into bounded tasks; calls approved Sub-Agents; presents proposed actions and evidence to the Orchestrator; reports outcomes and exceptions | Trust boundary between a workflow objective and specialist execution. It cannot grant itself new permissions or bypass Orchestrator controls. |
| **Agent-Specific Sub-Agent** | Specialist capability owner, under the Worker Agent’s and Orchestrator’s governance | Performs a narrowly defined specialist task using only the resources and action classes delegated to it; returns outputs, status, control-relevant events, and uncertainty/exception signals | Lowest-trust execution boundary in this hierarchy. It must not directly obtain broader authority, directly approve its own high-impact action, or conceal a failed/blocked operation. |
| **Human oversight / approval function** | Named, trained person(s) with authority appropriate to the risk; for material risk, an independent or separated reviewer | Approves, rejects, modifies, pauses, overrides, or terminates designated actions; handles escalations and appeals; confirms recovery or resumption criteria | Human authority is explicit and role-based. A nominal notification without practical ability to intervene is not meaningful oversight. |

NIST’s AI RMF treats governance as a cross-cutting function and calls for documented roles, lines of communication, executive responsibility for AI risk decisions, and differentiated human-AI oversight responsibilities [1][2]. The proposed hierarchy operationalizes those principles without assigning legal or organizational accountability to an agent itself.

## Control and data flow

1. **Intent and risk registration.** A user or business process submits an objective to the Governable Orchestrator. The Orchestrator binds it to an approved purpose, data/use constraints, risk tier, accountable owner, and permitted operating context. Objectives outside the approved purpose are rejected or routed for governance review.

2. **Delegation.** The Orchestrator issues a bounded work authorization to a Worker Agent. The authorization should express the actor on whose behalf work occurs, permitted action classes and resources, duration/expiry, constraints, approval requirements, and the accountable owner. The Worker Agent may further delegate only a strict subset of this authority to a named Agent-Specific Sub-Agent. The parent-child chain must remain inspectable.

3. **Planning and task proposal.** The Worker Agent proposes task decomposition to the Orchestrator, including which Sub-Agent is needed, what data it may access, what external effect (if any) is sought, and whether the task is reversible. A Sub-Agent may propose a specialist action, but the proposal is not equivalent to authorization.

4. **Policy decision.** The Orchestrator (or an explicitly governed policy decision function at that boundary) checks purpose, actor/delegation chain, resource scope, data sensitivity, action risk, separation-of-duties requirements, rate or volume limits, and current approval state. The decision is **allow, allow-with-conditions, require-human-approval, deny, or pause/escalate**. Failure to establish authorization or to record a required control decision fails closed for high-impact actions.

5. **HITL gate.** For high-impact, irreversible, financial, administrative, security-sensitive, externally visible, or materially rights-affecting actions, the Orchestrator presents a human-readable action preview to an authorized reviewer. The preview should identify the requesting principal, full delegation path, target, intended effect, relevant data, risk classification, material uncertainties, reversibility, and proposed safeguards. Approval is bound to the specific proposed action and expires or is invalidated when material parameters, target, policy, risk, or context changes.

6. **Execution and return flow.** After authorization (and approval where required), the Worker Agent or Sub-Agent performs only the permitted task. Results flow upward with outcome status, policy/approval reference, exceptions, and evidence sufficient for review. A child’s output is treated as untrusted input at the parent boundary; the parent does not inherit more authority merely because a child recommends an action.

7. **Audit and monitoring flow.** The Orchestrator receives authoritative events for delegation, policy decisions, approval requests and responses, tool/resource access at the surface level, execution outcomes, denials, interruptions, escalations, overrides, recovery, and revocation. Monitoring detects anomalous behavior such as repeated denials or approval bypass attempts, unusual privilege use, unexpected action volume, or cross-boundary communication. Sensitive content should be minimized or redacted while preserving accountability and forensic utility.

8. **Escalation and recovery flow.** A child or Worker Agent raises an exception when it encounters uncertainty, policy conflict, missing authority, suspected compromise, unsafe output, or an outcome outside tolerance. The Orchestrator pauses the affected branch, prevents further delegation, preserves the audit trail, and routes the matter to the designated human/domain/security owner. Resumption requires explicit recovery criteria; otherwise the Orchestrator terminates or safely rolls back/compensates where feasible.

## Governance and policy controls

**Purpose limitation and risk-tiered autonomy.** Governance should define approved purposes, prohibited uses, operating contexts, data restrictions, and action risk tiers. Autonomy should be a policy outcome, not a default property of an agent. Low-risk, reversible read or analysis work may proceed under delegated authority; higher-risk actions should require stronger validation, human approval, or two-person/independent review. NIST AI RMF calls for risk management proportionate to organizational risk tolerance, transparent policies, ongoing review, safe decommissioning, and clear responsibility [2].

**Policy ownership and change control.** The organizational policy/risk owner defines risk appetite, prohibited actions, approval classes, escalation severity, retention and review expectations, and exceptions. The Orchestrator owner translates those policies into enforceable control points and maintains the authoritative inventory of agents, owners, purposes, capabilities, and oversight assignments. Domain owners define workflow constraints and acceptable outcomes. Security/privacy/legal functions own their specialized controls and receive escalations within their remit. Policy changes should be versioned, reviewed, and auditable; a changed policy should trigger re-evaluation of pending approvals and long-running work.

**Separation of duties.** The actor proposing an action should not be the sole authority that approves and executes a material action. In particular, a Worker Agent or Sub-Agent cannot approve its own high-impact proposal. For sensitive actions, the Orchestrator should route to an independent human reviewer or a distinct accountable function. This limits manipulation of risk classification, approval thresholds, or delegated scope.

**Bounded delegation.** Delegation is transitive only in the narrowing direction: child scope ≤ parent scope ≤ Orchestrator-approved scope. A Worker Agent must be unable to delegate prohibited actions, sensitive data access, or approval authority unless policy explicitly allows it. Every delegation should preserve attribution to the original human/business principal, the organizational owner, the Worker Agent, and the Sub-Agent. The academic authenticated-delegation work emphasizes that authentication identifies an actor, authorization determines permitted actions and resource access, and auditability allows claims and attributes to be inspected; it also proposes explicit, verifiable chains of authority and fine-grained scope [5].

## Authorization and access boundaries

Authorization should be evaluated at the **action and resource boundary**, not inferred from an agent’s general role or from a parent’s textual instruction. The Orchestrator should evaluate the requesting actor and complete delegation chain, intended purpose, target resource, data classification, action type, context, and approval status. Worker Agents should receive only workflow-level access, while Sub-Agents receive task-level access restricted to the minimum resource set and action class required.

Inter-agent calls are trust-boundary crossings. The receiver should validate the sender’s identity and delegated relationship, recipient, freshness/validity, scope, and message/action type; sanitize untrusted content; and reject unauthorized or stale requests. OWASP recommends trust boundaries between agents, validation of inter-agent communication, prevention of privilege escalation through chains, and circuit breakers against cascading failures [4]. A Sub-Agent’s result is data, not an authority grant. Any request to cross a boundary, access a new class of data, contact an external party, change privileges, or perform an irreversible action returns to Orchestrator policy evaluation.

Access should be revocable independently of the agent’s task state. Revocation, expiry, owner suspension, policy change, suspected compromise, or breach signal should invalidate downstream delegated authority and prevent new child work. Existing work should be paused or terminated according to risk and recovery policy.

## HITL design and approval semantics

HITL should be **risk-adaptive and action-specific**, not a generic “human notified” flag. The Orchestrator should define when a human must be in the decision path, when a human may review asynchronously, and when post-action review is sufficient. For high-risk actions, the human must have sufficient competence, context, time, and authority to understand the proposed effect and intervene. The reviewer should be able to approve, reject, edit constraints, request more evidence, pause the branch, or escalate.

An approval should cover the exact action and relevant context: who requested it, who delegated it, which Worker/Sub-Agent proposed it, what target and effect are intended, the risk tier, constraints, time validity, and the applicable policy. Material changes require a new decision. Approval is not transferable to an unrelated child, target, or later action. If the approver cannot be reached within a risk-defined deadline, the safe default is pause, deny, or controlled fallback—not silent autonomous execution.

NIST’s Generative AI Profile recommends human moderation where appropriate, explicit oversight roles in the system inventory, and post-deployment monitoring with appeal, override, decommissioning, incident response, recovery, and change management [3]. OWASP similarly recommends explicit approval for high-impact/irreversible actions, action previews, autonomy boundaries based on risk, clear audit trails, and the ability to interrupt and roll back operations [4].

## Audit, evidence, and accountability

The Orchestrator should maintain an authoritative, tamper-evident governance record that makes the delegation chain and control decisions reconstructable without retaining unnecessary sensitive content. At minimum, the record should link: objective and approved purpose; accountable owner; Worker and Sub-Agent identities; delegated scope; policy decision and policy version; approval request/decision and reviewer; execution start/stop/outcome; denials, exceptions, interruptions, escalations, overrides, revocations, and recovery actions. The record should distinguish **proposal**, **authorization**, **approval**, and **execution** so that an agent’s recommendation cannot be mistaken for an authorized act.

Audit access should be role-based and separated from agent execution. Agents may emit operational events but should not be able to rewrite, delete, or self-certify authoritative governance records. Reviewers and auditors need enough context to verify that the action stayed within scope while privacy and data-minimization owners constrain exposure. OWASP recommends logging agent decisions, calls, outcomes, authorization outcomes, approval identifiers, execution results, and policy versions, together with anomaly alerts and redaction of sensitive data [4]. The EU AI Act establishes the importance of traceability, documentation, and automatic event records for high-risk systems [6].

Accountability remains with named human and organizational owners. The hierarchy creates traceability; it does not transfer responsibility to a Worker Agent or Sub-Agent. The Orchestrator owner is accountable for control operation, the domain owner for workflow use, the policy/risk owner for risk acceptance and exceptions, and the approving human for the decision they explicitly authorize, subject to the organization’s legal and governance framework.

## Security, escalation, and recovery

**Security signals and escalation.** Escalate when identity/delegation cannot be validated; an action exceeds scope; an agent attempts privilege expansion; data handling violates classification rules; prompt-injected or untrusted content appears to drive a sensitive action; monitoring detects abnormal volume or repeated bypass attempts; a child reports uncertainty or unsafe output; a downstream result conflicts with policy; or an incident affects people, rights, safety, security, or external systems. Severity determines whether the branch is paused, all related authority is revoked, affected systems are isolated, or an incident response process is activated.

**Containment.** The Orchestrator should provide a supervisory stop boundary capable of halting new work, blocking further delegation, invalidating approvals, and preventing retries from amplifying harm. Worker Agents should propagate stop/revocation signals to their Sub-Agents and report acknowledgement. Circuit breakers and bounded retries reduce cascading failures; no child should continue operating on stale authority after a stop or policy change.

**Recovery.** Recovery policy should define safe fallback, rollback or compensating action where feasible, human takeover, evidence preservation, affected-party notification, and conditions for resumption. NIST’s Generative AI Profile calls for fallback technologies that may include manual processing, defined ownership of incident response, rehearsal and retrospective improvement, and post-deployment plans covering recovery and change management [3]. After recovery, the accountable owner should review whether the policy, delegation scope, risk tier, HITL threshold, monitoring, or training/operational practice requires change. A system may be decommissioned or a capability withdrawn when safe operation cannot be restored within risk tolerance.

## Design review checklist

A governance review should be able to answer “yes” to the following questions:

- Is there a named human and organizational owner for each Orchestrator, Worker Agent, and Sub-Agent capability?
- Is every objective tied to an approved purpose, risk tier, data boundary, and action policy?
- Can the Orchestrator distinguish proposal, authorization, approval, execution, and outcome?
- Can a Worker Agent delegate only a strict subset of its own authority, with complete attribution preserved?
- Are high-impact and irreversible actions held at an explicit, action-specific human approval gate?
- Can humans inspect enough context, intervene, reject, override, pause, and escalate?
- Are inter-agent calls treated as trust-boundary crossings with least privilege and anti-escalation controls?
- Are denials, policy conflicts, approval bypass attempts, and anomalous behavior monitored and escalated?
- Can the Orchestrator revoke authority, invalidate pending approvals, halt branches, and prevent cascading retries?
- Are recovery, manual fallback, rollback/compensation, after-action review, and safe decommissioning defined?
- Are audit records attributable, reviewable, privacy-minimized, retained according to policy, and protected from agent modification?

## Findings

1. **The Governable Orchestrator should be the authoritative governance boundary.** It owns policy enforcement, delegation, approval routing, audit, monitoring, revocation, and recovery coordination; Workers and Sub-Agents are bounded execution layers rather than independent principals.
2. **Delegation must narrow monotonically.** A Worker Agent may delegate only a subset of Orchestrator-approved authority, and a Sub-Agent may receive only a narrower specialist scope. No child recommendation or chain depth can create new authority.
3. **Authorization must be explicit and contextual.** Evaluate identity, complete delegation chain, purpose, action, target, data sensitivity, risk, time validity, and approval state at each material boundary; do not infer authorization from a role label or a parent instruction alone.
4. **HITL must be risk-adaptive and action-specific.** High-impact, irreversible, financial, administrative, security-sensitive, externally visible, or rights-affecting actions require a human with appropriate competence and authority to approve, reject, modify, pause, or escalate the exact action.
5. **Proposal, authorization, approval, and execution are separate control states.** The Orchestrator should make these states visible in both flow and audit so that a Worker/Sub-Agent’s proposal cannot be mistaken for permission or an executed result.
6. **Auditability is a cross-layer accountability mechanism.** Records must preserve the human/business principal, organizational owner, Worker, Sub-Agent, delegated scope, policy and approval decisions, outcome, exceptions, overrides, and recovery; agents must not be able to rewrite authoritative records.
7. **Inter-agent communication is a trust-boundary crossing.** Receiver-side validation, least privilege, data minimization, anti-privilege-escalation controls, and circuit breakers are required to prevent a compromised child from propagating harm through the hierarchy.
8. **Escalation and recovery are first-class governance flows.** Scope violations, uncertainty, unsafe outputs, anomalous behavior, policy conflicts, and suspected compromise should pause affected work, block further delegation, preserve evidence, and route to named human/domain/security owners; resumption requires defined recovery criteria.
9. **Accountability remains human and organizational.** Agent hierarchy improves traceability but does not make an agent legally or ethically accountable; policy/risk, domain, Orchestrator, security/privacy, and approving-human responsibilities must be named and differentiated.

## Sources

[1] **National Institute of Standards and Technology (NIST), “Artificial Intelligence Risk Management Framework.”** Official overview and links to AI RMF 1.0 and Playbook. https://www.nist.gov/itl/ai-risk-management-framework

[2] **NIST, “Artificial Intelligence Risk Management Framework (AI RMF 1.0),” NIST AI 100-1 (2023).** See the GOVERN function and categories on governance, accountability, roles, risk tolerance, monitoring, and safe decommissioning. https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf

[3] **NIST, “Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile,” NIST AI 600-1 (2024).** See governance/oversight, human moderation, monitoring, appeal/override, incident response, recovery, fallback, and escalation actions. https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf

[4] **OWASP, “AI Agent Security Cheat Sheet.”** Reputable technical guidance on least privilege, explicit high-impact approvals, action previews, audit trails, monitoring, inter-agent trust boundaries, privilege-escalation prevention, and circuit breakers. https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

[5] **Tobin South et al., “Authenticated Delegation and Authorized AI Agents,” arXiv:2501.09674 (2025).** Academic proposal distinguishing authentication, authorization, and auditability and describing verifiable chains of delegated authority and human oversight. https://arxiv.org/html/2501.09674v1

[6] **European Parliament and Council, “Regulation (EU) 2024/1689 (Artificial Intelligence Act),” EUR-Lex (2024).** Official legal text emphasizing risk management, traceability, technical documentation, record-keeping/logging, and human oversight for high-risk AI systems. https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng

## Source-use caveat

The sources are broad AI governance and agent-security authorities rather than a single prescriptive reference architecture for this exact three-layer hierarchy. The layer boundaries, ownership model, and flows above are an architectural synthesis of their governance, authorization, oversight, audit, security, and recovery requirements. NIST AI RMF is voluntary guidance, OWASP’s cheat sheet is technical guidance, the academic paper is a research proposal, and the EU AI Act applies according to its legal scope and system classification.

---

**Report focus:** Governable Orchestrator → Worker Agents → Agent-Specific Sub-Agents; governance and HITL surface architecture only.
