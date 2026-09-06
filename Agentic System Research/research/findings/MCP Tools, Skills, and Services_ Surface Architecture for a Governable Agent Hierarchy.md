# MCP Tools, Skills, and Services: Surface Architecture for a Governable Agent Hierarchy

## Scope and interpretation

This report isolates one architecture dimension: **MCP tools, skills, and services**. It covers only surface architecture—participants, ownership, trust and access boundaries, capability routing, APIs at a conceptual level, and control/data flow—across the following logical hierarchy:

> **Governable Orchestrator → Worker Agents → Agent-Specific Sub-Agents**

The hierarchy is an architectural application of MCP concepts, not a claim that the MCP specification requires these three layers or defines “worker agent” and “sub-agent” as protocol roles. MCP standardizes context exchange and capability exposure between hosts, clients, and servers; it does not prescribe an agent’s internal planning, delegation, or model-use policy. Accordingly, the mappings below should be treated as governance design guidance.

## 1. MCP’s surface contract

MCP uses a client–host–server architecture. A **host** is the coordinating AI application; it creates and manages one client instance per connected server. A **client** maintains a dedicated relationship with one server, routes requests and responses, and keeps that server’s interaction separate from other servers. A **server** is a focused provider of context and capabilities. Servers may be local or remote, but location does not change the role boundary. The official architecture specification explicitly states that servers should not see the whole conversation or “see into” other servers; the host retains the broader context and controls cross-server interaction.[1]

For the target hierarchy, the cleanest surface mapping is:

| Target layer | MCP-oriented role | Primary ownership | Boundary responsibility |
|---|---|---|---|
| Governable Orchestrator | Host and policy/control plane | Organization or system owner | User consent, agent identity, task scope, client creation, capability allowlists, aggregation, audit, escalation, and termination |
| Worker Agent | Host-managed agent context plus one or more MCP clients | Orchestrator delegates a bounded task | Selects only capabilities authorized for the task; sends requests through its assigned clients; returns results and status to the orchestrator |
| Agent-Specific Sub-Agent | A subordinate execution context, usually reached through an orchestrator/worker-controlled interface; optionally an MCP client when it independently consumes MCP servers | Worker/orchestrator under explicit delegation | Receives only a narrowed task/context/capability set; cannot inherit ambient access merely by being a child; reports outputs through the worker |
| MCP service/server | Capability and context provider | Service owner/data owner | Exposes only declared tools, resources, prompts, or extensions; authenticates callers; enforces service-side authorization and data minimization |

A worker or sub-agent is therefore not automatically entitled to act as an MCP host. The governable orchestrator should decide whether a worker receives a client connection, a mediated capability facade, or only data/results. The distinction is important: **MCP connectivity is an access decision, not a consequence of organizational nesting**.

## 2. Primitive ownership and control semantics

The MCP server specification distinguishes three server-exposed primitives by control locus:[2]

| Primitive | Surface purpose | Nominal control locus | Hierarchical governance implication |
|---|---|---|---|
| **Tools** | Callable actions or information retrieval operations | Model-controlled at the interaction surface | The orchestrator must authorize availability and invocation; a worker may propose a call, but policy and user approval can still gate it. Server-side authorization remains mandatory. |
| **Resources** | Contextual data made available to the application/model | Application-controlled | The host/orchestrator decides whether to discover, retrieve, attach, cache, or forward a resource. A sub-agent should receive only the specific resource slices necessary for its task. |
| **Prompts** | Reusable interaction templates or workflow guidance | User-controlled | A prompt can be offered to a user or approved workflow, but it is not an authorization grant. Its presence must not expand a worker’s tool or resource rights. |

This control table prevents a common category error: **a description, prompt, skill, or resource is not itself an authority to invoke a tool**. A tool declaration describes a callable capability; it does not replace policy, consent, authentication, authorization, or service-side validation.

MCP’s architecture overview describes discovery and retrieval as dynamic: clients can list server primitives and then request the relevant item or invoke an eligible tool.[3] In a governed hierarchy, discovery should be filtered at each boundary. The worker should not see the full catalog if the orchestrator has approved only a subset, and a sub-agent should receive an even narrower view. Filtering is a control-plane operation; the eventual resource content or tool result is data-plane output.

## 3. Services and access boundaries

An MCP server is the boundary around a specialized service, data domain, or action domain. The server owns the semantics of what its tools do and remains responsible for protecting its underlying resources. The host/client boundary is different: the host owns conversation context, client lifecycle, consent UX, aggregation, and policy decisions, while the client owns the dedicated protocol relationship to one server.[1]

The target hierarchy should preserve at least four distinct boundaries:

1. **Orchestrator ↔ worker boundary.** The orchestrator issues a task grant containing the worker identity, purpose, allowed capability set, data scope, time/quantity limits, approval requirements, and reporting obligations. The worker receives no implicit access to the orchestrator’s full conversation, credentials, or unrelated workers.
2. **Worker ↔ sub-agent boundary.** Delegation must be explicit and least-privilege. A sub-agent gets a task-specific projection of the worker’s authority, not the worker’s entire authority. The worker remains accountable for the sub-agent’s requests and results.
3. **Client ↔ server boundary.** Each client communicates with exactly one server. Cross-server joins, data forwarding, or chained tool calls are coordinated above the client/server boundary by the host/orchestrator, not assumed to be visible to a server.[1]
4. **Server ↔ protected service/data boundary.** The server enforces its own authorization and validates calls before accessing upstream APIs or data. The server must not treat an MCP caller’s self-reported name or capability claims as a security identity; the base specification says identity metadata is for display/logging/debugging and is not verified by the protocol.[4]

The official architecture specification makes isolation a design principle: a server should receive only necessary context, should not receive the full conversation, and should not see other servers. This supports a **brokered context model** in which the orchestrator decides what crosses each boundary, rather than allowing a worker or sub-agent to freely relay all context.

## 4. Capability routing

MCP capability negotiation is a compatibility and routing signal: clients and servers advertise the features they support, and each side must respect the other side’s declared capabilities.[1][4] It is not an enterprise authorization policy. A capable client is not automatically permitted to use every server capability, and a server’s advertised tool is not automatically approved for every agent.

A governable routing pipeline should therefore have two tests:

* **Capability compatibility:** Does the target client/server pair support the relevant primitive or extension?
* **Policy authorization:** Is this particular principal, task, data scope, and action allowed now?

The orchestrator should maintain a capability registry or policy view with at least: server identity and trust classification; primitive/skill identifiers; allowed caller classes; data sensitivity; action impact; approval mode; rate or budget limits; and revocation status. It should expose to a worker only the capabilities that pass the policy test. The worker may then route an allowed request via the client dedicated to the selected server. A sub-agent’s route must be derived from the worker’s grant and intersected with the orchestrator’s policy, never unioned with it.

Conceptually:

> **Sub-agent route = orchestrator-approved capabilities ∩ worker task grant ∩ sub-agent task scope ∩ server authorization**

The intersection must be evaluated at invocation time as well as discovery time. Dynamic listings and notifications can change what a server offers; a newly listed tool or skill should not bypass the orchestrator’s policy. Revocation, expiration, or changed sensitivity should remove the capability from downstream projections and cause pending or future calls to be denied.

## 5. Skills over MCP

The MCP Skills Over MCP Working Group describes **agent skills** as rich, structured instructions for agent workflows discovered, distributed, and consumed through MCP. Its current direction is an extension using existing resource primitives; it also records that registry ownership, client implementation mandates, and installable bundles are outside that group’s scope.[5]

At this surface level, a skill is best treated as **governed guidance and workflow context**, not as a privileged execution identity. A skill may tell a worker or sub-agent how to approach a task, which resources to consult, and which eligible tools might be appropriate. It should be discoverable only through an authorized route, carry provenance and trust metadata, and be evaluated for applicability before activation. Skill activation should not enlarge the capability intersection defined above. If a skill references a tool, that is a request for routing—not a grant.

Ownership should be separated:

* The **skill publisher/owner** owns the content, intended workflow, version/provenance, and stated prerequisites.
* The **orchestrator** owns whether the skill is trusted, available to a worker class, and usable for a particular task.
* The **worker** owns local task application of an authorized skill and must report material skill-selected actions.
* The **sub-agent** may consume a narrowly scoped skill excerpt or instruction set, but should not be able to activate additional skills or tools unless the delegation grant says so.
* The **server** may provide skill material as resources, but providing content does not make the server the authority over the orchestrator’s policy.

This separation protects against prompt or skill content being mistaken for policy. It also supports progressive disclosure: expose a skill summary first, retrieve detailed guidance only when authorized and relevant, and withhold unrelated workflow context from downstream agents.

## 6. API surface and access control

At the conceptual API surface, a host-managed client performs operations such as capability discovery, primitive listing, resource retrieval, prompt retrieval, tool invocation, subscription/notification handling, and cancellation or progress coordination where supported. These operations are **bidirectional protocol interactions**, but the direction does not determine authority. A server may request client-side input through supported client features; the host still owns the user-facing decision and should mediate any sensitive input.[1][3]

For HTTP-based protected servers, the MCP authorization specification assigns the MCP client the role of OAuth client and the protected MCP server the role of resource server; an authorization server issues access tokens. The client discovers the authorization service through protected-resource metadata, obtains a token for the intended MCP server, and presents it on subsequent requests. The server must validate that the token is intended for itself and must not return data to unauthorized parties.[6]

This produces an important boundary for the hierarchy: a worker or sub-agent should not receive reusable broad credentials merely because it can reach an MCP client. Prefer a short-lived, audience-bound, task-scoped authorization context mediated by the orchestrator. Where a server calls an upstream API, the authorization specification requires a separate upstream token and prohibits passing through the token received from the MCP client.[6] Thus, the MCP server is an authorization boundary, not a transparent credential tunnel.

For local process-style connections, the authorization specification says the HTTP authorization flow does not apply and credentials should instead be obtained from the environment; this report does not prescribe an implementation. The architectural rule remains the same: the orchestrator must know which principal is being represented, which service is being accessed, and where the authorization decision is enforced.

## 7. Control and data flow for the target hierarchy

The following flow separates governance decisions from context and result movement:

1. **Task intake and policy classification (control plane).** The orchestrator receives a user or system task, establishes the governing principal and purpose, classifies data/action sensitivity, and decides whether delegation is allowed.
2. **Worker grant (control plane).** The orchestrator creates a worker task grant: identity, scope, permissible servers/primitives/skills, data handling rules, approval gates, limits, deadline, and reporting channel. The grant is narrower than the orchestrator’s own authority.
3. **Capability projection (control plane).** The orchestrator creates or authorizes only the client connections/routes required by that grant. The worker sees a filtered capability catalog, not all available servers or primitives.
4. **Optional sub-agent delegation (control plane).** The worker requests a sub-agent or performs a delegated subtask. The orchestrator or worker—according to policy—creates a further grant whose allowed set is a strict subset of the worker’s set. Any independent MCP access by the sub-agent must be explicitly enabled.
5. **Discovery and selection (control plus metadata flow).** The relevant client discovers server capabilities and available primitives. The orchestrator/worker filters the result against policy. A skill may be retrieved as authorized workflow context; it does not change the grant.
6. **Context ingress (data plane).** An approved resource or prompt is retrieved and passed only to the agent that needs it. The orchestrator controls whether results are summarized, redacted, transformed, or forwarded to another agent. Servers do not receive unrelated conversation or other server outputs by default.
7. **Action request (control plus data plane).** A worker or sub-agent proposes a tool call. Policy evaluates identity, task scope, parameters, sensitivity, approval state, limits, and current authorization. A human approval gate can be required for high-impact actions.
8. **Service execution and result return (data plane).** The MCP server authenticates/authorizes the request, performs the service operation, and returns a result or error. The result flows back through the client to the worker and then to the orchestrator, subject to redaction and output policy.
9. **Audit, revocation, and termination (control plane).** The orchestrator records the delegation, capability decision, approval, call outcome, and data transfer at an appropriate level. It can revoke a worker/sub-agent grant, close a client route, stop further calls, or terminate the task. Pending results must not be treated as permission to continue.

A useful conceptual diagram is:

```text
User / governing policy
          |
          v
[Governable Orchestrator]
  owns identity, consent, policy,
  routing, aggregation, audit, stop
          |
  bounded task grant + filtered capability view
          v
[Worker Agent]
  owns task execution within grant
          |
  narrower delegation (optional)
          v
[Agent-Specific Sub-Agent]
  receives least context + least capability
          |
  approved client route only
          v
[MCP Client]  -- dedicated relationship -->  [MCP Server / Service]
                                                    |
                                          protected data/action domain

Data and results flow upward through the same governed boundaries.
Policy, authorization, consent, and revocation flow downward and can interrupt calls.
Cross-server data movement is orchestrated above individual client/server links.
```

## 8. Governance rules and design findings

The surface architecture yields the following rules for a governable implementation:

* **Use MCP role separation as a control boundary.** The orchestrator is the host-like coordinator; clients are narrow connectors; servers are focused capability/data providers.
* **Treat delegation as attenuation.** Every worker and sub-agent grant must be a subset of its issuer’s effective authority, with no automatic credential or context inheritance.
* **Separate discovery from permission.** Capability listings, tool descriptions, prompts, resources, and skills are metadata/context; authorization is a separate decision.
* **Keep servers isolated.** A server should receive only the context required for its request. Cross-server correlation, if permitted, is an orchestrator-controlled operation.
* **Make data movement explicit.** Resources and tool results may be forwarded to downstream agents only under a data-scope rule; the default should be deny or minimum necessary.
* **Use server-side enforcement as a second line.** Orchestrator policy cannot replace the MCP server’s own authentication, authorization, input validation, and data protection.
* **Bind authorization to the intended service.** Tokens and credentials should be audience/service-specific; an MCP client credential should not be reused as an upstream service credential.
* **Preserve user control.** The MCP specification’s security principles require explicit consent for data exposure and tool invocation. The orchestrator is the natural point for consent, approval, explanation, and stop controls.[4]
* **Do not use self-reported labels as identity.** Client/server names and versions can support display and audit, but the base specification says they are not verified security attributes.[4]
* **Treat skills as non-authoritative guidance.** Skills can improve routing and workflow consistency, but cannot grant access, bypass approval, or expand the server/tool/resource allowlist.

## Sources

[1] **Model Context Protocol, “Architecture” (official specification, 2026-07-28).** https://modelcontextprotocol.io/specification/2026-07-28/architecture

[2] **Model Context Protocol, “Server Features: Overview” (official specification, 2026-07-28).** https://modelcontextprotocol.io/specification/2026-07-28/server

[3] **Model Context Protocol, “Architecture overview” (official documentation, 2026-07-28).** https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture

[4] **Model Context Protocol, “Specification” (official specification, 2026-07-28).** https://modelcontextprotocol.io/specification/2026-07-28

[5] **Model Context Protocol, “Skills Over MCP Charter” (official community working-group charter).** https://modelcontextprotocol.io/community/working-groups/skills-over-mcp

[6] **Model Context Protocol, “Authorization” (official specification, 2025-06-18).** https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization

[7] **Model Context Protocol, “Security Best Practices” (official security guidance, 2026-07-28).** https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices

[8] **National Institute of Standards and Technology, “AI Agent Standards Initiative.”** https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative

[9] **Anthropic, “Introducing the Model Context Protocol” (25 November 2024).** https://www.anthropic.com/news/model-context-protocol

## Source notes

The MCP sources establish the host/client/server roles, primitive control loci, capability negotiation, server isolation, authorization boundaries, consent requirements, and the current status of Skills over MCP. NIST’s initiative provides independent governance context by emphasizing trusted, interoperable, secure agentic systems and research into agent identity and authentication.[8] Anthropic’s announcement is included as historical primary-source context for MCP’s goal of standardized, two-way connections between AI applications and external data/capabilities.[9] The design recommendations in this report—especially worker/sub-agent grant attenuation and orchestrator-mediated routing—are architectural deductions for the requested hierarchy, not normative requirements of MCP itself.
