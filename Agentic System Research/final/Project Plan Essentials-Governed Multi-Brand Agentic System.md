# **Project Plan Essentials: Governed Multi-Brand Agentic System**

* **Project Window:** 2026-09-11 (Friday) to 2026-10-14 (Wednesday) (34 Calendar Days)  
*   
* **Access-Control Governance Model:** Model A (Intelligence Engine as exclusive broker for Agentic RAG and data plane)  
*   
* **Execution Boundary:** agent\_sandbox (AIO Sandbox) hosting all ephemeral sub-agents and micro-tools  
* 

### **1\. Task List & Schedule**

| ID | Task | Start | End | Duration | Dependencies | Milestone | Resource(s) | Progress |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **T01** | Define enterprise objectives, tenant scopes, and budget boundaries | 2026-09-11 | 2026-09-12 | 2 days | None | M1 | Brand Stakeholder / Portfolio Owner | 100% \[INFERRED\] |
| **T02** | Configure machine-readable policy rules, autonomy tiers, and claim limits | 2026-09-11 | 2026-09-12 | 2 days | None | M1 | Enterprise Policy Engine | 100% \[INFERRED\] |
| **T03** | Establish Policy & Authorization Boundary (PAB) evaluation rules | 2026-09-12 | 2026-09-14 | 3 days | T01, T02 | M1 | Policy & Authorization Boundary (PAB) | 100% \[INFERRED\] |
| **T04** | Initialize Canonical Task State Machine (CTS) and DAG execution schema | 2026-09-12 | 2026-09-14 | 3 days | T01 | M1 | Canonical Task State Machine (CTS) | 100% \[INFERRED\] |
| **T05** | Provision Central Enterprise Database (CDB) relational tables & vector stores | 2026-09-14 | 2026-09-16 | 3 days | T04 | M2 | Central Enterprise Database (CDB) | 100% \[INFERRED\] |
| **T06** | Connect Headless CMS content models and staging layout schemas | 2026-09-14 | 2026-09-16 | 3 days | T04 | M2 | Headless CMS & Web Store (CMS) | 100% \[INFERRED\] |
| **T07** | Instantiate Institutional Memory Store (MEM) for brand heuristics & rules | 2026-09-14 | 2026-09-16 | 3 days | T04 | M2 | Institutional Memory Store (MEM) | 100% \[INFERRED\] |
| **T08** | Configure Artifact & Evidence Registry (ART) for UUID/hash deliverables | 2026-09-16 | 2026-09-18 | 3 days | T05 | M2 | Artifact & Evidence Registry (ART) | 100% \[INFERRED\] |
| **T09** | Deploy Governed MCP Data Boundary CRUD gateways & connection pools | 2026-09-16 | 2026-09-18 | 3 days | T05, T06, T07 | M2 | Governed MCP Data Boundary | 100% \[INFERRED\] |
| **T10** | Configure Agentic RAG Controller with tenant isolation & freshness gates | 2026-09-18 | 2026-09-19 | 2 days | T03, T09 | M2 | Agentic RAG Controller | 100% \[INFERRED\] |
| **T11** | Deploy agent\_sandbox with cgroups, seccomp, and tmpfs isolation | 2026-09-18 | 2026-09-20 | 3 days | T03 | M3 | Sandbox Controller (agent\_sandbox) | 100% \[INFERRED\] |
| **T12** | Configure sandbox network proxy with strict egress allowlisting (DENY\_ALL) | 2026-09-20 | 2026-09-21 | 2 days | T11 | M3 | Sandbox Controller (agent\_sandbox) | 100% \[INFERRED\] |
| **T13** | Implement sandbox execution audit interception to W3C PROV ledger | 2026-09-21 | 2026-09-22 | 2 days | T11, T12 | M3 | Sandbox Controller & W3C PROV Audit | 100% \[INFERRED\] |
| **T14** | Instantiate specialist sub-agent micro-tools (S\_CODE to S\_ATTR) in sandbox | 2026-09-21 | 2026-09-23 | 3 days | T11, T12 | M3 | Specialist Sub-Agents (L4\_SUBS) | 100% \[INFERRED\] |
| **T15** | Configure Intelligence Engine context assembly & brand persona layer | 2026-09-23 | 2026-09-24 | 2 days | T04, T10 | M4 | Intelligence Engine (IE) | 100% \[INFERRED\] |
| **T16** | Ingest & verify product formulations and compliance dossiers (W\_PROD) | 2026-09-24 | 2026-09-26 | 3 days | T10, T14, T15 | M4 | Product / Evidence Engine & S\_VAL | 100% \[INFERRED\] |
| **T17** | Ingest & parse customer support tickets and review sentiment (W\_VOICE) | 2026-09-24 | 2026-09-26 | 3 days | T10, T14, T15 | M4 | Customer Voice Engine & S\_PARSE | 100% \[INFERRED\] |
| **T18** | Scrape competitor ad libraries, pricing, and market positioning (W\_COMP) | 2026-09-24 | 2026-09-26 | 3 days | T12, T14, T15 | M4 | Competitor Intel Engine & S\_SCRAPE | 100% \[INFERRED\] |
| **T19** | Develop omnichannel marketing roadmaps & budget allocations (W\_STRAT) | 2026-09-26 | 2026-09-29 | 4 days | T16, T17, T18 | M4 | Strategy Engine & S\_ALLOC | 100% \[INFERRED\] |
| **T20** | Generate creative ad copy variants, hooks, visual briefs & posts (W\_CREAT) | 2026-09-29 | 2026-10-02 | 4 days | T16, T19 | M4 | Creative & Content Engine & S\_COPY | 100% \[INFERRED\] |
| **T21** | Engineer responsive UI templates, CMS schemas & code diffs (W\_DEV) | 2026-09-26 | 2026-10-02 | 7 days | T06, T14, T15 | M4 | Development Engine & S\_CODE | 100% \[INFERRED\] |
| **T22** | Consolidate worker evidence envelopes & verify confidence intervals | 2026-10-02 | 2026-10-04 | 3 days | T19, T20, T21 | M5 | Intelligence Engine (IE) | 50% \[INFERRED\] |
| **T23** | Generate structured action previews (spend, code diffs, claims, copy) | 2026-10-04 | 2026-10-05 | 2 days | T22 | M5 | Intelligence Engine (IE) | 25% \[INFERRED\] |
| **T24** | Execute Human-in-the-Loop (HITL) quality, legal, and deploy sign-off | 2026-10-05 | 2026-10-06 | 2 days | T23 | M5 | Human-in-the-Loop (HITL) Gate | 0% \[INFERRED\] |
| **T25** | Initialize Outbound Actuation MCP Boundary with audience tokens | 2026-10-06 | 2026-10-07 | 2 days | T24 | M6 | Outbound Actuation MCP Boundary | 0% \[INFERRED\] |
| **T26** | Deploy live schemas, catalog updates & layout code to Website & CMS | 2026-10-07 | 2026-10-09 | 3 days | T25 | M6 | Outbound MCP & Website / CMS | 0% \[INFERRED\] |
| **T27** | Publish ad campaigns and bid targets to Paid Ad Platforms | 2026-10-07 | 2026-10-09 | 3 days | T25 | M6 | Outbound MCP & Paid Ad Platforms | 0% \[INFERRED\] |
| **T28** | Publish scheduled social media posts and assets to Social Channels | 2026-10-07 | 2026-10-09 | 3 days | T25 | M6 | Outbound MCP & Social Channels | 0% \[INFERRED\] |
| **T29** | Connect Omnichannel Telemetry Engine webhooks, pixel events & logs | 2026-10-09 | 2026-10-10 | 2 days | T26, T27, T28 | M6 | Omnichannel Telemetry Engine | 0% \[INFERRED\] |
| **T30** | Ingest live store traffic, checkout transactions & conversion logs into CDB | 2026-10-10 | 2026-10-11 | 2 days | T29 | M7 | Telemetry Engine & Central Database | 0% \[INFERRED\] |
| **T31** | Calculate multi-touch attribution, creative decay & ROAS (W\_LEARN) | 2026-10-11 | 2026-10-13 | 3 days | T30 | M7 | Learning Engine & S\_ATTR | 0% \[INFERRED\] |
| **T32** | Promote validated memory deltas into Institutional Memory and IE | 2026-10-13 | 2026-10-14 | 2 days | T31 | M7 | Learning Engine, Memory Store & IE | 0% \[INFERRED\] |
| **T33** | Validate end-to-end W3C PROV audit lineage, state integrity & logs | 2026-10-13 | 2026-10-14 | 2 days | T30, T31 | M7 | W3C PROV Immutable Ledger | 0% \[INFERRED\] |
| **T34** | Perform final project verification against acceptance criteria & close | 2026-10-14 | 2026-10-14 | 1 day | T32, T33 | M7 | Intelligence Engine & Brand Owner | 0% \[INFERRED\] |

### **2\. Dependencies**

#### **2.1 Direct Dependency Listing**

* T03 depends on T01, T02  
*   
* T04 depends on T01  
*   
* T05, T06, T07 depend on T04  
*   
* T08 depends on T05  
*   
* T09 depends on T05, T06, T07  
*   
* T10 depends on T03, T09  
*   
* T11 depends on T03  
*   
* T12 depends on T11  
*   
* T13, T14 depend on T11, T12  
*   
* T15 depends on T04, T10  
*   
* T16, T17 depend on T10, T14, T15  
*   
* T18 depends on T12, T14, T15  
*   
* T19 depends on T16, T17, T18  
*   
* T20 depends on T16, T19  
*   
* T21 depends on T06, T14, T15  
*   
* T22 depends on T19, T20, T21  
*   
* T23 depends on T22  
*   
* T24 depends on T23  
*   
* T25 depends on T24  
*   
* T26, T27, T28 depend on T25  
*   
* T29 depends on T26, T27, T28  
*   
* T30 depends on T29  
*   
* T31 depends on T30  
*   
* T32 depends on T31  
*   
* T33 depends on T30, T31  
*   
* T34 depends on T32, T33  
* 

#### **2.2 Dependency Details**

| Predecessor | Successor | Type | Evidence & Structural Rule |
| :---- | :---- | :---- | :---- |
| **T01, T02** | **T03** | Finish-to-Start (FS) | Strategic intent & policy rules must exist before PAB can enforce bounds. |
| **T01** | **T04** | Finish-to-Start (FS) | Scope and budgets are prerequisites for Canonical Task State DAG initialization. |
| **T04** | **T05, T06, T07** | Finish-to-Start (FS) | State ledger schemas must precede database tables, CMS models, and memory namespaces. |
| **T05, T06, T07** | **T09** | Finish-to-Start (FS) | Physical data stores must be provisioned before MCP Data Gateway establishes CRUD adapters. |
| **T03, T09** | **T10** | Finish-to-Start (FS) | PAB access rules and MCP data connectors are required to configure Agentic RAG Controller. |
| **T03** | **T11** | Finish-to-Start (FS) | Security policies dictate sandbox cgroup and seccomp profile definitions. |
| **T11, T12** | **T13, T14** | Finish-to-Start (FS) | Sandbox virtualization and egress proxy must be active before sub-agents and audit hooks launch. |
| **T04, T10** | **T15** | Finish-to-Start (FS) | Task state schema and RAG access must be active before IE context assembly can operate. |
| **T10, T14, T15** | **T16, T17, T18** | Finish-to-Start (FS) | Workers require RAG data access, sandbox micro-tools, and IE context grants to ingest domain intel. |
| **T16, T17, T18** | **T19** | Finish-to-Start (FS) | Omnichannel marketing strategy requires verified claims, customer voice, and competitor intel. |
| **T16, T19** | **T20** | Finish-to-Start (FS) | Creative copy and visual briefs depend on approved claims and strategic channel allocations. |
| **T06, T14, T15** | **T21** | Finish-to-Start (FS) | Website development requires CMS staging models, AST coder tools, and IE directives. |
| **T19, T20, T21** | **T22** | Finish-to-Start (FS) | Strategy plans, creative assets, and code diffs must be compiled into evidence envelopes. |
| **T22** | **T23** | Finish-to-Start (FS) | Validated evidence envelopes are required to format structured action previews. |
| **T23** | **T24** | Finish-to-Start (FS) | Action previews are the mandatory input for the Human-in-the-Loop approval gate. |
| **T24** | **T25** | Finish-to-Start (FS) | Signed cryptographic HITL approval grants release execution directives to Outbound MCP. |
| **T25** | **T26, T27, T28** | Finish-to-Start (FS) | Outbound MCP gateway must be authenticated before dispatching web code, ads, and social posts. |
| **T26, T27, T28** | **T29** | Finish-to-Start (FS) | External surfaces must be active before Omnichannel Telemetry Engine webhooks can attach. |
| **T29** | **T30** | Finish-to-Start (FS) | Telemetry listeners must be online to ingest live traffic, conversions, and transaction records. |
| **T30** | **T31** | Finish-to-Start (FS) | Attribution and creative decay algorithms require live performance metrics from Central DB. |
| **T31** | **T32** | Finish-to-Start (FS) | Attribution weights must be validated before promotion into Institutional Memory. |
| **T30, T31** | **T33** | Finish-to-Start (FS) | Complete execution and telemetry logs must be sealed in W3C PROV audit registry. |
| **T32, T33** | **T34** | Finish-to-Start (FS) | Final project acceptance occurs only after closed-loop learning and audit integrity verification. |

### **3\. Milestones**

| ID | Milestone | Date | Linked Tasks | Status |
| :---- | :---- | :---- | :---- | :---- |
| **M1** | Governance, Policy & Canonical State Initialization | 2026-09-14 | T01, T02, T03, T04 | Complete \[INFERRED\] |
| **M2** | Governed Data Plane & Central Storage Integration (Model A) | 2026-09-19 | T05, T06, T07, T08, T09, T10 | Complete \[INFERRED\] |
| **M3** | Sandbox Isolation & Specialist Sub-Agent Readiness | 2026-09-23 | T11, T12, T13, T14 | Complete \[INFERRED\] |
| **M4** | Domain Intelligence Ingestion & Asset Synthesis Complete | 2026-10-02 | T15, T16, T17, T18, T19, T20, T21 | Complete \[INFERRED\] |
| **M5** | HITL Gateway Clearance & Cryptographic Authorization | 2026-10-06 | T22, T23, T24 | In Progress \[INFERRED\] |
| **M6** | Outbound Actuation, Telemetry & Omnichannel Go-Live | 2026-10-10 | T25, T26, T27, T28, T29 | Planned \[INFERRED\] |
| **M7** | Closed-Loop Telemetry Optimization & Final Project Closeout | 2026-10-14 | T30, T31, T32, T33, T34 | Planned \[INFERRED\] |

### **4\. Resource Assignments**

| Resource | Assigned Tasks | Load / Operational Notes |
| :---- | :---- | :---- |
| **Brand Stakeholder / Portfolio Owner** | T01, T34 | High strategic responsibility; inputs business goals at kickoff and accepts final delivery at project close. |
| **Enterprise Policy Engine** | T02 | Automated policy rule definition; defines risk matrices and compliance envelopes. |
| **Policy & Authorization Boundary (PAB)** | T03 | Core security gate; evaluates caller identity, token validity, and monotonic attenuation per invocation. |
| **Canonical Task State Machine (CTS)** | T04 | Central state tracking engine; manages DAG transitions, task holds, checkpoints, and dependency locks. |
| **Central Enterprise Database (CDB)** | T05, T30 | Primary system of record for operational tables, vector namespaces, and telemetry time-series. |
| **Headless CMS & Web Store (CMS)** | T06, T26 | Digital asset and page model store; handles staged layout schemas and live storefront content. |
| **Institutional Memory Store (MEM)** | T07, T32 | Long-term knowledge base; stores promoted heuristics, brand voice rules, and model deltas. |
| **Artifact & Evidence Registry (ART)** | T08 | Immutable blob storage; stores deliverables, code diffs, and evidence dossiers by UUID/SHA-256. |
| **Governed MCP Data Boundary** | T09 | Database gateway; exposes read/write CRUD capability facades under strict schema validation. |
| **Agentic RAG Controller** | T10 | Sole authorized data broker for Intelligence Engine under Model A; manages hybrid vector search and freshness. |
| **Sandbox Controller (**agent\_sandbox**)** | T11, T12, T13 | Isolated execution environment; enforces cgroups, seccomp filters, tmpfs shredding, and network proxying. |
| **Specialist Sub-Agents (**L4\_SUBS**)** | T14, T16, T17, T18, T19, T20, T21, T31 | Ephemeral micro-tool workers (S\_CODE, S\_ALLOC, S\_COPY, S\_VAL, S\_SCRAPE, S\_PARSE, S\_ATTR). |
| **Intelligence Engine (IE / Orchestrator)** | T15, T22, T23, T32, T34 | Primary central planner and MCP host; manages task grants, context assembly, synthesis, and recovery. |
| **Product / Evidence Engine (**W\_PROD**)** | T16 | Domain worker; ingests formulations, maps clinical evidence, and prepares compliance dossiers. |
| **Customer Voice Engine (**W\_VOICE**)** | T17 | Domain worker; ingests customer reviews, support tickets, and analyzes sentiment and objection patterns. |
| **Competitor Intel Engine (**W\_COMP**)** | T18 | Domain worker; monitors competitor pricing, ad copy trends, and positioning shifts. |
| **Strategy Engine (**W\_STRAT**)** | T19 | Domain worker; formulates omnichannel roadmaps, funnel structures, and budget allocation proposals. |
| **Creative & Content Engine (**W\_CREAT**)** | T20 | Domain worker; drafts multi-channel copy, creative hooks, visual briefs, and social media schedules. |
| **Development Engine (**W\_DEV**)** | T21 | Domain worker; engineers responsive UI components, CMS schemas, layout templates, and code diffs. |
| **Human-in-the-Loop (HITL) Gate** | T24 | Mandatory human sign-off; reviews action previews for spend, legal compliance, and code deployment. |
| **Outbound Actuation MCP Boundary** | T25, T26, T27, T28 | Security egress perimeter; validates audience tokens and dispatches signed API calls to external surfaces. |
| **Live Website & Headless CMS Surface** | T26 | External production runtime; hosts live storefront, product catalog, and user-facing web applications. |
| **Paid Ad Platforms (Meta, Google, TikTok)** | T27 | External media platforms; receives campaign payloads, audience targeting, and spend allocations. |
| **Social Channels (Instagram, X, YouTube)** | T28 | External content channels; receives scheduled social posts, copy packages, and media assets. |
| **Omnichannel Telemetry Engine** | T29, T30 | Real-time event ingestor; aggregates conversion webhooks, pixel events, and server logs. |
| **Learning & Performance Engine (**W\_LEARN**)** | T31, T32 | Domain worker; calculates attribution curves, creative fatigue, ROAS optimization, and memory deltas. |
| **W3C PROV Immutable Ledger** | T13, T33 | Audit authority; records tamper-evident entity-activity-agent relationships and cryptographic signatures. |

### **5\. Progress Tracking**

| Task ID | % Complete | Status Color | Evidence / Notes |
| :---- | :---- | :---- | :---- |
| **T01** | 100% \[INFERRED\] | Green | Architectural scope, objectives, and budget envelopes established in source blueprint. |
| **T02** | 100% \[INFERRED\] | Green | Compliance rules, autonomy tiers, and brand constraints defined in policy engine specification. |
| **T03** | 100% \[INFERRED\] | Green | PAB monotonic attenuation logic and verification formulas validated in control plane. |
| **T04** | 100% \[INFERRED\] | Green | Canonical Task State Machine lifecycle states (CREATED to COMPLETED) configured. |
| **T05** | 100% \[INFERRED\] | Green | Relational tables, JSONB schemas, and pgvector stores defined in Central DB model. |
| **T06** | 100% \[INFERRED\] | Green | Headless CMS content schemas and staging layout diffs integrated. |
| **T07** | 100% \[INFERRED\] | Green | Long-term institutional memory schemas and brand book namespaces established. |
| **T08** | 100% \[INFERRED\] | Green | Content-addressable artifact storage with UUID and SHA-256 hash validation defined. |
| **T09** | 100% \[INFERRED\] | Green | MCP Data Boundary read/write CRUD capability facades verified against storage layer. |
| **T10** | 100% \[INFERRED\] | Green | Model A Agentic RAG Controller deployed with tenant-scoped filtering and provenance tagging. |
| **T11** | 100% \[INFERRED\] | Green | agent\_sandbox (AIO Sandbox) virtualized container environment instantiated. |
| **T12** | 100% \[INFERRED\] | Green | Network egress firewall configured with default DENY\_ALL policy and domain whitelist proxy. |
| **T13** | 100% \[INFERRED\] | Green | Sandbox execution interceptor piped directly to W3C PROV audit logging service. |
| **T14** | 100% \[INFERRED\] | Green | Specialist micro-tools (S\_CODE through S\_ATTR) containerized inside sandbox. |
| **T15** | 100% \[INFERRED\] | Green | Intelligence Engine context assembler and brand persona layer initialized. |
| **T16** | 100% \[INFERRED\] | Green | W\_PROD specifications mapped and verified against regulatory claim linters (S\_VAL). |
| **T17** | 100% \[INFERRED\] | Green | W\_VOICE sentiment analysis and customer objection clustering completed (S\_PARSE). |
| **T18** | 100% \[INFERRED\] | Green | W\_COMP ad library scraping and competitor pricing benchmark extraction verified (S\_SCRAPE). |
| **T19** | 100% \[INFERRED\] | Green | W\_STRAT omnichannel media mix, budget allocation, and funnel models formulated (S\_ALLOC). |
| **T20** | 100% \[INFERRED\] | Green | W\_CREAT ad copy variants, hooks, social calendars, and visual briefs generated (S\_COPY). |
| **T21** | 100% \[INFERRED\] | Green | W\_DEV responsive UI templates, CMS schemas, and code diffs compiled (S\_CODE). |
| **T22** | 50% \[INFERRED\] | Yellow | Evidence envelopes consolidated; final confidence interval verification underway. |
| **T23** | 25% \[INFERRED\] | Yellow | Action preview generator compiling spend proposals and code diff dossiers for HITL review. |
| **T24** | 0% \[INFERRED\] | Red | Awaiting formal Human-in-the-Loop review and cryptographic approval sign-off. |
| **T25** | 0% \[INFERRED\] | Red | Outbound Actuation MCP Boundary standing by for signed execution directives. |
| **T26** | 0% \[INFERRED\] | Red | Live website schema deployment and catalog push scheduled post-approval. |
| **T27** | 0% \[INFERRED\] | Red | Paid ad campaign launch across Meta, Google, and TikTok scheduled post-approval. |
| **T28** | 0% \[INFERRED\] | Red | Social media publishing and scheduled content broadcast queued. |
| **T29** | 0% \[INFERRED\] | Red | Omnichannel telemetry stream listeners and webhook endpoints queued for go-live. |
| **T30** | 0% \[INFERRED\] | Red | Live transaction, order event, and server log ingestion awaiting production traffic. |
| **T31** | 0% \[INFERRED\] | Red | Multi-touch attribution modeling and creative decay scoring queued on telemetry feed. |
| **T32** | 0% \[INFERRED\] | Red | Memory promotion of validated optimization deltas scheduled post-campaign run. |
| **T33** | 0% \[INFERRED\] | Red | End-to-end W3C PROV audit trail verification and cryptographic sealing scheduled. |
| **T34** | 0% \[INFERRED\] | Red | Final project sign-off and contract closure scheduled for 2026-10-14. |

### **6\. Assumptions & Gaps**

* \[ASSUMPTION\] **Model A Exclusivity:** As specified in Section 4 of the Markdown artifact, Model A is strictly enforced. The Intelligence Engine maintains sole access authority over Agentic RAG; Worker Agents have zero direct database or CMS access and must route all read requests through the Intelligence Engine.  
*   
* \[ASSUMPTION\] **Date Inference Protocol:** The source Markdown and HTML files contain system architectures, data flows, and component matrices without explicit calendar dates. In accordance with the extraction rules, all task start/end dates were inferred based on logical DAG dependencies and mapped strictly across the project window: 2026-09-11 (Friday) to 2026-10-14 (Wednesday) (marked \[INFERRED\]).  
*   
* \[ASSUMPTION\] **Progress Inference Protocol:** Completion percentages were inferred from the source document status: architectural design, data modeling, sandbox configuration, and pipeline specifications are documented as verified (Done (100%)), evidence consolidation is actively resolving (In Progress (25–50%)), and live deployment/actuation tasks are future-scheduled (Not Started (0%)).  
*   
* \[ASSUMPTION\] **Calendar Days Standard:** All task durations are calculated in continuous calendar days (inclusive of weekends) as permitted by project rules, ensuring the 34-task DAG completes on Day 34 (2026-10-14).  
*   
* \[MISSING\] **Specific Platform API Credentials:** Specific client secrets and OAuth credentials for Meta Ads, Google Ads, TikTok Ads, and Headless CMS production servers are omitted from the source files and are assumed to be injected via secure environment vaults during task T25.  
*   
* \[MISSING\] **Exact Budget Figures:** Financial limits and campaign spend caps are referenced conceptually in data flows (W\_STRAT \-\> HITL) but lack discrete numerical currency values; exact budget amounts will be provided by the Brand Stakeholder in T01.  
*   
* \[CONFLICT\] None identified between Final-Level Full Architecture.md and flowchart.drawio.html. The HTML source represents the exact Draw.io/Mermaid export of the Markdown document; all components, node IDs, and directional data-flow permissions are structurally identical.