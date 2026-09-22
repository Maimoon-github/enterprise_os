### **System Architecture Reasoning Summary**

> 1. **Analysis & Parsing:** Decomposed requirements across four operational scopes (brand development, marketing, social content, and website operations). Verified architectural invariants from reference artifacts: strict monotonic attenuation, decoupled state-of-record storage, and mandatory execution containment via agent\_sandbox.  
> 2. **Access Model Selection:** Adopted **Model A**. The Intelligence Engine (Orchestrator) serves as the exclusive controller of Agentic RAG. All worker agents receive read-only data mediated through the Orchestrator, eliminating lateral data leakage, ambient privilege escalation, and confused-deputy vulnerabilities.  
> 3. **Execution Containment Placement:** Embedded agent\_sandbox as the isolated container/micro-VM execution layer directly under the Worker Agent tier. Every worker engine dispatches its untrusted code, linters, scrapers, and ephemeral sub-agent micro-tools within this boundary to enforce zero-trust isolation and audit logging.  
> 4. **Universal Persistence Design:** Enforced strict database writes across all pipeline nodes. No intermediate prompt, AST diff, candidate copy variant, scrape snapshot, or telemetry packet remains purely ephemeral; every entity is ingested into the central enterprise database with tenant and provenance metadata.

## **1\. Final-Level Full Architecture Flowchart (Mermaid)**

Code snippet  
flowchart TB  
%% \=========================================================================  
%% STYLE & CLASS DEFINITIONS  
%% \=========================================================================  
classDef gov fill:\#fef2f2,stroke:\#dc2626,stroke-width:2px,color:\#991b1b;  
classDef gate fill:\#fefce8,stroke:\#ca8a04,stroke-width:2.5px,color:\#713f12;  
classDef orch fill:\#f5f3ff,stroke:\#7c3aed,stroke-width:2.5px,color:\#4c1d95;  
classDef rag fill:\#eff6ff,stroke:\#2563eb,stroke-width:2px,color:\#1e40af;  
classDef store fill:\#ede9fe,stroke:\#6d28d9,stroke-width:2.5px,color:\#2e1065;  
classDef worker fill:\#f0fdf4,stroke:\#16a34a,stroke-width:2px,color:\#14532d;  
classDef sandbox fill:\#fdf6b2,stroke:\#b45309,stroke-width:2px,stroke-dasharray:4 4,color:\#78350f;  
classDef sub fill:\#fffbeb,stroke:\#d97706,stroke-width:1.5px,stroke-dasharray:3 3,color:\#78350f;  
classDef mcp fill:\#f1f5f9,stroke:\#475569,stroke-width:2px,color:\#0f172a;  
classDef ext fill:\#f8fafc,stroke:\#64748b,stroke-width:1.5px,color:\#1e293b;  
classDef audit fill:\#fdf4ff,stroke:\#c026d3,stroke-width:2px,color:\#701a75;  
classDef bus fill:\#ffffff,stroke:\#4b5563,stroke-width:1.5px,stroke-dasharray:5 4,color:\#111827;

%% \=========================================================================  
%% 1\. GOVERNANCE & POLICY PLANE  
%% \=========================================================================  
subgraph L0 \["1 · Governance, Policy & Authority Plane"\]  
    direction LR  
    OWNER\["Brand Stakeholder / Portfolio Owner\<br/\>\<i\>(Objectives, Budgets, Risk Appetite)\</i\>"\]:::gov  
    POLICY\["Enterprise Policy Engine\<br/\>\<i\>(Tenant Scopes, Legal Rules, Claim Boundaries)\</i\>"\]:::gov  
    HITL{"Human-in-the-Loop (HITL) Gate\<br/\>\<i\>\[Sign-Off: Spend, Legal Claims, Code & Deploys\]\</i\>"}:::gate  
end

%% \=========================================================================  
%% 2\. CENTRAL CONTROL PLANE (INTELLIGENCE ENGINE)  
%% \=========================================================================  
subgraph L1 \["2 · Central Control Plane: Governable Intelligence Engine"\]  
    direction TB  
    IE\["Intelligence Engine (Orchestrator / MCP Host)\<br/\>• Dynamic Context Assembly & Brand Persona Layer\<br/\>• Canonical Task State Machine & Global DAG Engine\<br/\>• Monotonic Attenuation & Tool/Skill Allowlisting\<br/\>• Upward Evidence Synthesis & Validation Gates"\]:::orch  
    PAB\["Policy & Authorization Boundary\<br/\>\<i\>(Caller ID • Delegation Chain • Tenant Scope • Risk Tier)\</i\>"\]:::orch  
    CTS\[\["Canonical Task State Machine\<br/\>\<i\>(Task Lifecycle • Checkpoints • Dependency Graph • Holds)\</i\>"\]\]:::orch  
    IE \<--\> PAB  
    IE \<--\> CTS  
end

OWNER \--\>|"Directives & Budgets \[Write\]"| IE  
POLICY \--\>|"Versioned Policy Envelopes \[Read\]"| PAB  
IE \<--\>|"Action Previews & Approval Signatures \[Read/Write\]"| HITL

%% \=========================================================================  
%% 3\. AGENTIC RAG & GOVERNED DATA ACCESS (MODEL A COMPLIANT)  
%% \=========================================================================  
subgraph L2 \["3 · Governed Knowledge & Data Access Layer (Model A)"\]  
    direction TB  
    RAG\["Agentic RAG Controller\<br/\>• Semantic Search & Vector Indexing\<br/\>• Tenant Partitioning & Row/Document Security\<br/\>• Freshness Checks & Provenance Attestation"\]:::rag  
    MCP\_DATA\["Governed Data Access MCP Gateway\<br/\>\<i\>(Read/Write Gateway to Database & CMS)\</i\>"\]:::rag  
    RAG \<--\> MCP\_DATA  
end

IE \<--\>|"Exclusive Bidirectional Data Bridge\<br/\>\[Authorized Read Queries & Ingestion Streams: Read/Write\]"| RAG

%% \=========================================================================  
%% 4\. PERSISTENT STORAGE & SYSTEM OF RECORD  
%% \=========================================================================  
subgraph L\_DATA \["4 · Central Enterprise Storage & System of Record"\]  
    direction LR  
    CDB\[("Central Enterprise Database\<br/\>• Relational Tables & JSONB Docs\<br/\>• Vector Namespaces & Embeddings\<br/\>• State Ledgers & Telemetry Logs")\]:::store  
    CMS\[("Headless CMS & Content Store\<br/\>• Staged Page Models & Schemas\<br/\>• Catalog Diffs & Digital Assets")\]:::store  
    MEM\[("Institutional Memory Store\<br/\>• Promoted Long-Term Knowledge\<br/\>• Brand Books & Learned Heuristics")\]:::store  
    ART\[("Artifact & Evidence Registry\<br/\>• Deliverables by UUID / Hash\<br/\>• Copy Packs, Code Diffs, Dossiers")\]:::store  
end

MCP\_DATA \<--\>|"Database CRUD & Index Sync \[Read/Write\]"| CDB  
MCP\_DATA \<--\>|"CMS Content Models & Staging \[Read/Write\]"| CMS  
MCP\_DATA \<--\>|"Institutional Knowledge Queries \[Read/Write\]"| MEM  
MCP\_DATA \<--\>|"Artifact Resolution by Hash/URI \[Read/Write\]"| ART

%% \=========================================================================  
%% COMMUNICATION BUSES  
%% \=========================================================================  
GRANT\["Bounded Task Grants (Downward) ▼\<br/\>Task Slice • Tenant Scope • Token Budget • Tool Allowlist • Stop Rules"\]:::bus  
EVID\["Evidence Envelopes (Upward) ▲\<br/\>Validated Findings • Confidence Intervals • Artifact UUIDs • Proposed State Deltas"\]:::bus

IE \==\> GRANT  
GRANT \==\> L3\_WORKERS  
L3\_WORKERS \==\> EVID  
EVID \==\> IE

%% \=========================================================================  
%% 5\. BOUNDED WORKER AGENT LAYER  
%% \=========================================================================  
subgraph L3\_WORKERS \["5 · Worker Agent Layer: Bounded Domain Execution"\]  
    direction TB  
    W\_DEV\["Development Engine\<br/\>\<i\>(CMS Schemas, UI Layouts, Code Diffs, Ops)\</i\>"\]:::worker  
    W\_STRAT\["Strategy Engine\<br/\>\<i\>(Omnichannel Roadmaps, Funnels, Budgets)\</i\>"\]:::worker  
    W\_CREAT\["Creative & Content Engine\<br/\>\<i\>(Copy, Hooks, Visual Briefs, Social Posts)\</i\>"\]:::worker  
    W\_PROD\["Product / Evidence Engine\<br/\>\<i\>(Specs, Compliance, Clinical Dossiers)\</i\>"\]:::worker  
    W\_COMP\["Competitor Intel Engine\<br/\>\<i\>(Pricing Trajectories, Ad Libraries, Trends)\</i\>"\]:::worker  
    W\_VOICE\["Customer Voice Engine\<br/\>\<i\>(CX Feedback, Sentiment, Objections)\</i\>"\]:::worker  
    W\_LEARN\["Learning & Performance Engine\<br/\>\<i\>(Attribution, Decay, ROAS Optimization)\</i\>"\]:::worker  
end

%% Model A: All Worker data requests routed exclusively via Intelligence Engine  
W\_DEV \-.-\>|"Read-Only Context Request \[Read\]"| IE  
W\_STRAT \-.-\>|"Read-Only Context Request \[Read\]"| IE  
W\_CREAT \-.-\>|"Read-Only Context Request \[Read\]"| IE  
W\_PROD \-.-\>|"Read-Only Context Request \[Read\]"| IE  
W\_COMP \-.-\>|"Read-Only Context Request \[Read\]"| IE  
W\_VOICE \-.-\>|"Read-Only Context Request \[Read\]"| IE  
W\_LEARN \-.-\>|"Read-Only Context Request \[Read\]"| IE

%% \=========================================================================  
%% 6\. AGENT SANDBOX EXECUTION LAYER (AGENT\_SANDBOX)  
%% \=========================================================================  
subgraph SB\_LAYER \["6 · agent\_sandbox (Isolated Execution Layer)"\]  
    direction TB  
    SANDBOX\_CTRL\["Sandbox Controller & Security Boundary\<br/\>• Micro-Virtualization & Process Isolation (cgroups/namespaces)\<br/\>• Egress Filtering & Strict Capability Allowlisting\<br/\>• Ephemeral Memory Scrubbing & Execution Audit Interception"\]:::sandbox  
      
    subgraph L4\_SUBS \["Specialist Sub-Agents & Micro-Tools"\]  
        direction LR  
        S\_CODE\["Component Coder & Linter\<br/\>\<i\>\[Micro-Tool: AST Parser\]\</i\>"\]:::sub  
        S\_ALLOC\["Media & Budget Allocator\<br/\>\<i\>\[Micro-Tool: Optimization Modeler\]\</i\>"\]:::sub  
        S\_COPY\["Copy Drafter & Hook Critic\<br/\>\<i\>\[Micro-Tool: Variant Generator\]\</i\>"\]:::sub  
        S\_VAL\["Claim & Schema Validator\<br/\>\<i\>\[Micro-Tool: Compliance Linter\]\</i\>"\]:::sub  
        S\_SCRAPE\["Price & Ad Scraper\<br/\>\<i\>\[Micro-Tool: External DOM Tracker\]\</i\>"\]:::sub  
        S\_PARSE\["Sentiment & Review Parser\<br/\>\<i\>\[Micro-Tool: NLP Classifier\]\</i\>"\]:::sub  
        S\_ATTR\["Attribution Modeler\<br/\>\<i\>\[Micro-Tool: Decay Scorer\]\</i\>"\]:::sub  
    end  
end

%% Sandbox Access: Every Worker Agent executes tools/sub-agents inside the sandbox  
W\_DEV \<--\>|"Invoke Sandbox Execution \[Read/Write\]"| S\_CODE  
W\_STRAT \<--\>|"Invoke Sandbox Execution \[Read/Write\]"| S\_ALLOC  
W\_CREAT \<--\>|"Invoke Sandbox Execution \[Read/Write\]"| S\_COPY  
W\_PROD \<--\>|"Invoke Sandbox Execution \[Read/Write\]"| S\_VAL  
W\_COMP \<--\>|"Invoke Sandbox Execution \[Read/Write\]"| S\_SCRAPE  
W\_VOICE \<--\>|"Invoke Sandbox Execution \[Read/Write\]"| S\_PARSE  
W\_LEARN \<--\>|"Invoke Sandbox Execution \[Read/Write\]"| S\_ATTR

%% \=========================================================================  
%% 7\. OUTBOUND EXECUTION PERIMETER  
%% \=========================================================================  
subgraph L5\_GATEWAY \["7 · Governed Outbound Actuation Perimeter"\]  
    direction TB  
    MCP\_ACT\["Outbound Actuation MCP Boundary\<br/\>\<i\>(Audience Tokens, Cryptographic Signing, Rate Limiting & Dispatch)\</i\>"\]:::mcp  
end

HITL \--\>|"Signed Clearance \[Read\]"| IE  
IE \==\>|"Authorized Dispatch Directives (Post-HITL) \[Write\]"| MCP\_ACT

%% \=========================================================================  
%% 8\. EXTERNAL SURFACES & TELEMETRY  
%% \=========================================================================  
subgraph L6\_EXT \["8 · External Digital Surfaces & Telemetry Loop"\]  
    direction LR  
    WEBSITE\["Live Website & Headless CMS\<br/\>\<i\>(Storefront, Catalog, Blog, SaaS App)\</i\>"\]:::ext  
    CH\_ADS\["Paid Ad Platforms\<br/\>\<i\>(Meta, Google, TikTok, LinkedIn)\</i\>"\]:::ext  
    CH\_SOC\["Social Channels\<br/\>\<i\>(Instagram, X, TikTok, YouTube)\</i\>"\]:::ext  
    TELEMETRY\["Omnichannel Telemetry Engine\<br/\>\<i\>(Webhooks, Server Logs, Conversions, ROAS)\</i\>"\]:::ext  
end

MCP\_ACT \--\>|"Deploy Live Schemas & Code \[Write\]"| WEBSITE  
MCP\_ACT \--\>|"Publish Campaigns & Bids \[Write\]"| CH\_ADS  
MCP\_ACT \--\>|"Publish Scheduled Posts \[Write\]"| CH\_SOC

WEBSITE \-.-\>|"Store Traffic & Orders \[Read\]"| TELEMETRY  
CH\_ADS \-.-\>|"Ad Spend & Conversion Telemetry \[Read\]"| TELEMETRY  
CH\_SOC \-.-\>|"Engagement & Reach Signals \[Read\]"| TELEMETRY

TELEMETRY \-.-\>|"Raw Telemetry Ingestion Stream \[Write\]"| CDB  
CDB \-.-\>|"Timeseries Metric Feed \[Read\]"| W\_LEARN  
W\_LEARN \-.-\>|"Continuous Learning Loop: Validated Memory Deltas \[Write\]"| IE

%% \=========================================================================  
%% 9\. UNIVERSAL AUDIT & PROVENANCE  
%% \=========================================================================  
subgraph L\_AUDIT \["9 · Immutable Audit Trail & Provenance Registry (W3C PROV)"\]  
    AUDIT\[("W3C PROV Immutable Ledger\<br/\>• Entity-Activity-Agent Relationships\<br/\>• Delegation Lineage & Tool Invocations\<br/\>• HITL Approvals & Execution Deltas\<br/\>• Full Prompt & Context Logs")\]:::audit  
end

%% Universal Persistence Streams to Audit  
IE \-.-|"Task Contracts & States \[Write\]"| AUDIT  
PAB \-.-|"Policy Decisions \[Write\]"| AUDIT  
HITL \-.-|"Signatures & Overrides \[Write\]"| AUDIT  
RAG \-.-|"Retrieval Lineage \[Write\]"| AUDIT  
SANDBOX\_CTRL \-.-|"Sandbox Invocations \[Write\]"| AUDIT  
MCP\_ACT \-.-|"Dispatch Records \[Write\]"| AUDIT

## **2\. Component Table**

| Component Name | System Layer & Role | Tools & Skills | Inputs | Outputs | Data Access | Sandbox Access |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **Brand / Business Owner** | Layer 1: Governance Authority | Business Portal / Governance Console | Enterprise objectives, operational targets, budget constraints | High-level directives, approved budget caps, risk envelopes | Read/Write to Task Registry | None (Human User) |
| **Enterprise Policy Engine** | Layer 1: Governance Engine | Policy Linter, Compliance Matrix | Organizational policies, statutory guidelines | Versioned policy rules, autonomy tiers, claim limits | Read-only to Policy Store | None (Policy Service) |
| **Human-in-the-Loop (HITL) Gate** | Layer 1: Quality Gatekeeper | Approval Signer, Review UI | Action previews, validation dossiers, spend proposals, code diffs | Signed approval grants, rejection notices, revision directives | Read-only to Action Previews; Write to Audit Log | None (Human Gate) |
| **Intelligence Engine (IE)** | Layer 2: Central Orchestrator | dag\_scheduler, policy\_evaluator, rag\_query\_dispatch, hitl\_preview\_generator, system:multi-brand-orchestration | Objectives, policy rules, evidence envelopes, channel telemetry | Bounded task grants, context slices, authorized dispatch commands | Read/Write to Central DB, Memory Store, Canonical State | None (Control Plane Host; orchestrates sandbox execution) |
| **Policy & Authorization Boundary (PAB)** | Layer 2: Security Intermediary | Cryptographic Validator, Scope Evaluator | Execution requests, caller tokens, delegated authorization chains | Allow / Deny / Escalate authorization decisions | Read-only to Tenant Scope & Policy DB | None (Control Plane Gate) |
| **Canonical Task State (CTS)** | Layer 2: State Machine | State Transition Engine, DAG Tracker | State deltas, checkpoint signals, worker progress reports | Authoritative task status, dependency locks, exception logs | Read/Write to Canonical State Ledger | None (Internal State Engine) |
| **Agentic RAG Controller** | Layer 3: Data Management Gateway | Hybrid Vector/BM25 Ranker, Freshness Verifier, Schema Linter | Scoped retrieval queries from IE, ingestion streams from DB | Validated evidence chunks, provenance metadata, vector embeddings | Exclusive Read/Write to Central DB & CMS (via MCP Data Gateway) | None (Data Management Service) |
| **MCP Data Boundary** | Layer 3: Capability Facade | CRUD Adapters, Database Connection Pools | Validated requests from Agentic RAG Controller | Raw database records, page schemas, assets | Read/Write to Central DB, CMS, Memory, Artifacts | None (Protocol Boundary) |
| **Central Enterprise DB (CDB)** | Layer 4: System of Record | PostgreSQL / pgvector / TimescaleDB Engine | Relational data, telemetry events, vector embeddings, audit logs | Authoritative persistent records | Read/Write via MCP Data Gateway | None (Persistent Storage) |
| **Headless CMS & Web Store (CMS)** | Layer 4: System of Record | Headless API, Content Model Engine | Page schemas, product catalogs, layout configurations | Rendered UI models, catalog data, assets | Read/Write via MCP Data Gateway | None (Content Storage) |
| **Institutional Memory Store (MEM)** | Layer 4: System of Record | Key-Value Feature Store, Vector Store | Promoted brand heuristics, long-term learning deltas | Contextual memory slices, brand rules | Read/Write via MCP Data Gateway | None (Memory Storage) |
| **Artifact & Evidence Registry (ART)** | Layer 4: System of Record | Immutable Content-Addressable Blob Store | Generated copy packs, code diffs, clinical proof dossiers | Versioned artifact references by UUID/Hash | Read/Write via MCP Data Gateway | None (Artifact Storage) |
| **Development Engine (W\_DEV)** | Layer 5: Worker Agent (Brand Dev / Ops) | ast\_code\_linter, cms\_schema\_validator, git\_diff\_builder, system:web-architecture | Technical directives, design tokens, UI specifications | Validated code diffs, CMS schemas, layout templates | Read-only (Mediated via IE) | **Yes** (Executes S\_CODE micro-tools in sandbox) |
| **Strategy Engine (W\_STRAT)** | Layer 5: Worker Agent (Marketing) | media\_mix\_modeler, budget\_allocator\_tool, funnel\_simulator, system:marketing-strategy | Market intelligence, performance telemetry, spend targets | Media mix models, campaign proposals, budget plans | Read-only (Mediated via IE) | **Yes** (Executes S\_ALLOC micro-tools in sandbox) |
| **Creative & Content Engine (W\_CREAT)** | Layer 5: Worker Agent (Social / Content) | copy\_variant\_generator, hook\_ranker, visual\_brief\_formatter, system:creative-generation | Strategic briefs, brand persona rules, grounded specs | Copy variations, hooks, social media calendars, briefs | Read-only (Mediated via IE) | **Yes** (Executes S\_COPY micro-tools in sandbox) |
| **Product / Evidence Engine (W\_PROD)** | Layer 5: Worker Agent (Product) | evidence\_dossier\_builder, claim\_mapper, regulatory\_linter, system:regulatory-compliance | Raw product formulations, lab trials, compliance standards | Verified claims dossiers, product specification sheets | Read-only (Mediated via IE) | **Yes** (Executes S\_VAL micro-tools in sandbox) |
| **Competitor Intel Engine (W\_COMP)** | Layer 5: Worker Agent (Marketing) | research\_proposer, brief\_validator, conflict\_detector, system:market-intelligence | Competitor entities, search/ad/price findings | Competitive evidence briefs, market shift alerts | Read-only (Mediated via IE) | **No** (Reasoning-only; sandboxed execution delegated to IE-authorized specialists) |
| **Customer Voice Engine (W\_VOICE)** | Layer 5: Worker Agent (Marketing) | review\_scraper\_parser, sentiment\_analyzer, ticket\_classifier, system:voc-clustering | Customer tickets, reviews, satisfaction survey logs | Anonymized sentiment vectors, objection profiles | Read-only (Mediated via IE) | **Yes** (Executes S\_PARSE micro-tools in sandbox) |
| **Learning & Performance Engine (W\_LEARN)** | Layer 5: Worker Agent (Feedback) | attribution\_calculator, fatigue\_detector, decay\_curve\_estimator, system:closed-loop-learning | Multichannel conversion logs, ROAS metrics, ad spend | Validated learning deltas, attribution model weights | Read-only (Mediated via IE) | **Yes** (Executes S\_ATTR micro-tools in sandbox) |
| **agent\_sandbox (AIO Sandbox)** | Layer 6: Execution Layer | Virtualized runtime, cgroups, seccomp, network proxy | Untrusted code, micro-agent execution mandates, raw payloads | Sanitized evaluation results, execution logs, AST metrics | Isolated local memory/tmpfs | **Internal** (Provides the sandbox runtime) |
| **Specialist Sub-Agents (S\_CODE to S\_ATTR)** | Layer 6: Ephemeral Sub-Agents | Specialized micro-tools (e.g., regex extractors, linters) | Granular subtask mandates from parent Worker Agents | Atomic evidence packets, parsed tokens, validated diffs | Ephemeral memory only; zero DB access | **Internal** (Execute strictly inside sandbox) |
| **Outbound Actuation MCP Boundary** | Layer 7: Egress Perimeter | Signed API Dispatcher, Rate Limiter | Approved execution payloads signed by HITL / IE | Deployed ad campaigns, live CMS updates, social posts | Read-only to approved payload buffers | None (API Gateway) |
| **Website & Production Surfaces** | Layer 8: Public Surfaces | Public HTTP endpoints, Frontend Runtimes | Production code diffs, published articles, active catalog | Live user interactions, customer orders, traffic events | Authoritative runtime surface | None (External Surface) |
| **Omnichannel Telemetry Engine** | Layer 8: Telemetry Collector | Webhook Listeners, Event Stream Consumers | Raw pixel events, conversion webhooks, ad platform metrics | Structured timeseries logs, error traces | Write-only stream to Central DB | None (Telemetry Ingestor) |
| **W3C PROV Immutable Ledger** | Layer 9: Audit Trail | Append-Only Cryptographic Log Engine | Audit events from IE, PAB, HITL, RAG, Sandbox, MCP | Immutable, tamper-evident governance traces | Append-Only Write | None (Audit Store) |

## **3\. Data-Flow Table**

| Source | Destination | Data Payload / Artifact | Read / Write |
| :---- | :---- | :---- | :---- |
| **Brand Owner** | **Intelligence Engine** | Strategic intent, operational scope, budget boundaries | **Write** |
| **Enterprise Policy Engine** | **Policy & Auth Boundary** | Machine-readable compliance rules, tenant constraints, risk tiers | **Read** |
| **Intelligence Engine** | **Canonical Task State** | Task initialization, dependency declarations, lifecycle transitions | **Write** |
| **Intelligence Engine** | **Agentic RAG Controller** | Scoped query requests, tenant tokens, freshness targets | **Read** |
| **Agentic RAG Controller** | **MCP Data Boundary** | Filtered relational queries, vector search parameters, chunk updates | **Read/Write** |
| **MCP Data Boundary** | **Central Database (CDB)** | Operational records, vector embeddings, state ledgers, telemetry | **Read/Write** |
| **MCP Data Boundary** | **Headless CMS & Web** | Content schemas, staging diffs, catalog objects, assets | **Read/Write** |
| **MCP Data Boundary** | **Institutional Memory** | Long-term heuristics, brand guidelines, claim rules | **Read/Write** |
| **MCP Data Boundary** | **Artifact Registry** | Generated deliverables, code patches, compliance dossiers | **Read/Write** |
| **Intelligence Engine** | **Worker Agents (All)** | Bounded task grants: task slice, token budget, tool allowlist | **Write** |
| **Worker Agents (All)** | **Intelligence Engine** | Context requests (read-only queries for evidence) | **Read** |
| **Worker Agents (All)** | **Intelligence Engine** | Evidence envelopes: candidate artifacts, confidence, state deltas | **Write** |
| **Authorized Workers / Specialists (excluding W\_COMP)** | **agent\_sandbox** | Ephemeral subtask mandates, untrusted code snippets, scrape tasks | **Write** |
| **Specialist Sub-Agents** | **agent\_sandbox** | Execution logs, process traces, linter ASTs, raw DOM scrapes | **Read/Write** |
| **agent\_sandbox** | **Authorized Workers / Specialists (excluding W\_COMP)** | Sanitized execution outputs, validation proofs, parsed tokens | **Read** |
| **Intelligence Engine** | **HITL Quality Gate** | Action previews: spend proposals, live code diffs, claims dossiers | **Write** |
| **HITL Quality Gate** | **Intelligence Engine** | Signed approval grants, rejection notices, parameter modifications | **Read** |
| **Intelligence Engine** | **Outbound Actuation MCP** | Authorized, signed execution directives (post-HITL approval) | **Write** |
| **Outbound Actuation MCP** | **Website & CMS** | Staged-to-live production code, layout models, catalog updates | **Write** |
| **Outbound Actuation MCP** | **Paid Ad Platforms** | Ad campaign configurations, target parameters, spend budgets | **Write** |
| **Outbound Actuation MCP** | **Social Channels** | Scheduled social content, media assets, copy variations | **Write** |
| **Website & CMS** | **Telemetry Engine** | User conversion events, pageview logs, checkout errors | **Read** |
| **Paid Ad Platforms** | **Telemetry Engine** | Real-time ad spend, CTR, CPA, ROAS, impression metrics | **Read** |
| **Social Channels** | **Telemetry Engine** | Engagement counts, reach statistics, sentiment comments | **Read** |
| **Telemetry Engine** | **Central Database (CDB)** | Raw timeseries telemetry streams, conversion data feeds | **Write** |
| **Central Database (CDB)** | **Learning Engine** | Normalized performance timeseries, attribution data feeds | **Read** |
| **Learning Engine** | **Intelligence Engine** | Continuous learning loop: model weights, decay adjustments | **Write** |
| **All Control Nodes** | **W3C PROV Audit Ledger** | State deltas, policy checks, tool calls, approval signatures, logs | **Write** |

## **4\. Selected Access-Control Model & Rationale**

### **Selected Model: Model A**

Under **Model A**:

> 1. **Agentic RAG exclusively interfaces with the Intelligence Engine (Orchestrator).**  
> 2. **The Intelligence Engine possesses sole authority to request data input/output from Agentic RAG.**  
> 3. **All other agents (Worker Agents and Sub-Agents) request data from the Intelligence Engine for read-only retrieval.**

Plaintext  
\[Worker Agents / Sub-Agents\]  
             │  
      (Read-Only Query)  
             ▼  
   \[Intelligence Engine\] ◄==== Universal Persistence \===► \[Central Database & CMS\]  
             │  
   (Authorized Scoped I/O)  
             ▼  
    \[Agentic RAG Controller\]  
             │  
     (CRUD & Vector Search)  
             ▼  
   \[Central Database & CMS\]

### **Architectural Rationale**

> 1. **Strict Monotonic Attenuation:** In a governable hierarchical agent architecture, authority must monotonically decrease down the delegation tree ($\\text{Sub-Agent} \\subset \\text{Worker} \\subset \\text{IE}$). If Worker Agents or Sub-Agents could directly query or write to Agentic RAG or the database, they would bypass the Orchestrator's policy envelope and gain ambient privilege over enterprise data.  
> 2. **Elimination of Confused-Deputy Vulnerabilities:** If specialized worker agents (e.g., Creative Engine, Development Engine) possessed direct write or retrieval authority against the database, prompt injection in untrusted customer feedback or competitor ad copy could trick a worker into querying or corrupting cross-tenant data. Model A forces every data interaction through the central Policy & Authorization Boundary (PAB).  
> 3. **Single Source of Canonical Truth:** Direct database mutations from multiple distributed workers cause race conditions, schema drift, and fragmented audit trails. Centralizing all data ingestion through the Intelligence Engine guarantees that every state change is validated against the Canonical Task State (CTS) machine before persistence.  
> 4. **Context Window vs. Persistent Storage Decoupling:** Model context windows represent transient, lossy working memory. Model A prevents workers from treating local context as persistent truth; durable records re-enter worker scopes strictly as policy-screened, cited evidence envelopes.

## **5\. agent\_sandbox (AIO Sandbox) Placement & Isolation Boundaries**

### **Architectural Placement**

The agent\_sandbox (referenced from \[https://github.com/agent-infra/sandbox\](https://github.com/agent-infra/sandbox)) operates as an **isolated execution abstraction layer** positioned strictly between the Worker Agents (Layer 5\) and their ephemeral Specialist Sub-Agents / Micro-Tools (Layer 6).

Plaintext  
┌────────────────────────────────────────────────────────────────────────┐  
│                   Layer 5: Bounded Worker Agents                       │  
│    \[W\_DEV\]   \[W\_STRAT\]   \[W\_CREAT\]   \[W\_PROD\]   \[W\_COMP\]   \[W\_VOICE\]   │  
└───────────────────────────────────┬────────────────────────────────────┘  
                                    │ Bounded Task Mandate  
                                    ▼  
┌────────────────────────────────────────────────────────────────────────┐  
│                        agent\_sandbox Perimeter                         │  
│                                                                        │  
│   ┌────────────────────────────────────────────────────────────────┐   │  
│   │                 Sandbox Security Controller                    │   │  
│   │   • Micro-virtualization (Namespaces, cgroups, seccomp)        │   │  
│   │   • Default Network Egress: DENY\_ALL (Strict Proxy Whitelist)   │   │  
│   │   • Ephemeral Memory Isolation & Deterministic Tear-Down       │   │  
│   │   • Real-Time Syscall & Execution Logging to Audit Ledger      │   │  
│   └───────────────────────────────┬────────────────────────────────┘   │  
│                                   │ Spawns isolated container/process  │  
│                                   ▼                                    │  
│   ┌────────────────────────────────────────────────────────────────┐   │  
│   │            Layer 6: Specialist Sub-Agents & Micro-Tools        │   │  
│   │     \[S\_CODE\]   \[S\_ALLOC\]   \[S\_COPY\]   \[S\_VAL\]   \[S\_SCRAPE\]     │   │  
│   └────────────────────────────────────────────────────────────────┘   │  
└───────────────────────────────────┬────────────────────────────────────┘  
                                    │ Sanitized Evidence Envelope (Only)  
                                    ▼  
┌────────────────────────────────────────────────────────────────────────┐  
│              Layer 2: Central Intelligence Engine (Control)            │  
└────────────────────────────────────────────────────────────────────────┘

### **Security & Isolation Boundaries**

> 1. **Process & Memory Virtualization:** Every sub-agent or micro-tool execution runs inside an ephemeral container or lightweight virtualized sandbox with strict memory limits (cgroups) and system-call filtering (seccomp). Sibling sub-agents cannot inspect or access peer memory.  
> 2. **Network Egress Denial (DENY\_ALL):** Compute sub-agents (e.g., Code Linter, Copy Drafter, Attribution Modeler) have zero outbound network connectivity. External tools (e.g., Price Scraper) route traffic strictly through a domain-whitelisted proxy. Lateral access to internal databases, orchestrator APIs, or cloud metadata endpoints is strictly blocked.  
> 3. **Ephemeral Filesystem (tmpfs):** All scratchpads, temporary code artifacts, and intermediate diffs exist exclusively on a memory-backed filesystem that is securely shredded upon task termination.  
> 4. **Tool & Skill Encapsulation:** When a Worker Agent executes a tool or skill, execution occurs inside the sandbox container, exposing only the minimum parameters declared in the task grant.  
> 5. **Continuous Audit Streaming:** Every command, execution exit code, memory spike, and standard error stream is intercepted by the Sandbox Controller and piped directly to the W3C PROV Immutable Ledger.

## **6\. Validation Checklist**

* \[x\] **All data stored in database:** Every generated data item—strategic roadmaps, scraped market snapshots, customer sentiment vectors, copy variants, code diffs, approval signatures, and raw telemetry—is persisted to the Central Enterprise Database and W3C PROV Immutable Ledger. No ephemeral-only data paths exist.  
* \[x\] **All worker agents have sandbox access:** All 7 Worker Agents (W\_DEV, W\_STRAT, W\_CREAT, W\_PROD, W\_COMP, W\_VOICE, W\_LEARN) possess direct, operational access to invoke tools and ephemeral sub-agents within the agent\_sandbox boundary.  
* \[x\] **Orchestrator / Agentic RAG authority is consistent:** Architecture adheres strictly to **Model A**. Agentic RAG exclusively interfaces with the Intelligence Engine, which acts as the sole authorized broker for reading and writing data on behalf of Worker Agents.  
* \[x\] **No ambiguous or redundant components:** System boundaries are decoupled and non-overlapping. Storage is centralized in the Systems of Record (Layer 4); control is centralized in the Intelligence Engine (Layer 2); execution is distributed across Worker Agents (Layer 5); and isolation is enforced by agent\_sandbox (Layer 6).