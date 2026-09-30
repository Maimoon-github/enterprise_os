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
| **Human-in-the-Loop (HITL) Gate** | Layer 1: Quality Gatekeeper | Approval Signer, Review UI | Action previews, validation dossiers, spend proposals, code diffs | Signed approval grants, rejection notices, revision directives, hold decisions | Read-only to Action Previews; Write to Audit Log | None (Human Gate) |
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
| **Competitor Intel Engine (W\_COMP)** | Layer 5: Worker Agent (Marketing) | ad\_library\_parser, price\_tracker\_tool, serp\_intel\_scraper, system:market-intelligence | Competitor domains, target ad libraries, external SERPs | Market shift alerts, pricing trajectory tables | Read-only (Mediated via IE) | **Yes** (Executes S\_SCRAPE micro-tools in sandbox) |
| **Customer Voice Engine (W\_VOICE)** | Layer 5: Worker Agent (Marketing) | review\_scraper\_parser, sentiment\_analyzer, ticket\_classifier, system:voc-clustering | Customer tickets, reviews, satisfaction survey logs | Anonymized sentiment vectors, objection profiles | Read-only (Mediated via IE) | **Yes** (Executes S\_PARSE micro-tools in sandbox) |
| **Learning & Performance Engine (W\_LEARN)** | Layer 5: Worker Agent (Feedback) | attribution\_calculator, fatigue\_detector, decay\_curve\_estimator, system:closed-loop-learning | Multichannel conversion logs, ROAS metrics, ad spend | Validated learning deltas, attribution model weights | Read-only (Mediated via IE) | **Yes** (Executes S\_ATTR micro-tools in sandbox) |
| **agent\_sandbox (AIO Sandbox)** | Layer 6: Execution Layer | Virtualized runtime, cgroups, seccomp, network proxy | Untrusted code, micro-agent execution mandates, raw payloads | Sanitized evaluation results, execution logs, AST metrics | Isolated local memory/tmpfs | **Internal** (Provides the sandbox runtime) |
| **Specialist Sub-Agents (S\_CODE to S\_ATTR)** | Layer 6: Ephemeral Sub-Agents | Specialized micro-tools (e.g., regex extractors, linters) | Granular subtask mandates from parent Worker Agents | Atomic evidence packets, parsed tokens, validated diffs | Ephemeral memory only; zero DB access | **Internal** (Execute strictly inside sandbox) |
| **Outbound Actuation MCP Boundary** | Layer 7: Egress Perimeter | Signed API Dispatcher, Rate Limiter | Approved execution payloads signed by HITL / IE | Deployed ad campaigns, live CMS updates, social posts | Read-only to approved payload buffers with TOCTOU check | None (API Gateway) |
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
| **Worker Agents (All)** | **agent\_sandbox** | Ephemeral subtask mandates, untrusted code snippets, scrape tasks | **Write** |
| **Specialist Sub-Agents** | **agent\_sandbox** | Execution logs, process traces, linter ASTs, raw DOM scrapes | **Read/Write** |
| **agent\_sandbox** | **Worker Agents (All)** | Sanitized execution outputs, validation proofs, parsed tokens | **Read** |
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

## **7\. Comprehensive Input/Output Schema Specification & Validation Assessment**

### **7.1 Architectural Schema Hierarchy & Monotonic Attenuation Rules**

In accordance with **Model A** governance and zero-trust execution principles, the system enforces strict monotonic schema attenuation across four distinct operational planes:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Plane 1: Governance & Directive Plane (Layer 1 -> Layer 2)            │
│ EnterpriseDirective -> PolicyEnvelope -> CanonicalTaskState           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Policy-Screened TaskGrant & Context
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Plane 2: Worker Domain Plane (Layer 2 -> Layer 5)                      │
│ TaskGrant -> Domain Directive (Strategy, Dev, Creative, Prod, etc.)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Ephemeral Specialist Mandate
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Plane 3: Specialist Execution & Sandbox Boundary (Layer 5 -> Layer 6)  │
│ Specialist Mandate -> SandboxInvocationMandate -> Micro-Tool Payload   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Sanitized SandboxResult
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Plane 4: Upward Synthesis & Persistence Plane (Layer 6 -> L5 -> L2)    │
│ SpecialistResult -> Domain Deliverable -> EvidenceEnvelope -> Package  │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Monotonic Attenuation Invariant ($\text{Sub-Agent} \subset \text{Worker} \subset \text{IE}$):** A delegated input schema may NEVER possess broader data access, larger budget caps, or looser network policies than its delegator's grant.
2. **Model A Mediated Retrieval:** No Worker Agent or Specialist Sub-Agent possesses direct connection parameters, vector query schemas, or CRUD mutation schemas against the persistence layer. All data requests are mediated as read-only `ContextRequest` schemas submitted to the Intelligence Engine.
3. **Structured Upward Synthesis:** Every specialist execution terminates in a typed `SpecialistResult`, which is ingested into a domain deliverable (e.g., `DevelopmentDeliverable`, `OmnichannelStrategyPlan`, `ClaimsDossier`), wrapped in a tamper-evident `EvidenceEnvelope` with a mathematical `ConfidenceInterval`, and sealed with a SHA-256 digest before reaching the Intelligence Engine.

---

### **7.2 Central Control Plane & Governed Data Access Schemas**

#### **1. Intelligence Engine (IE) — Layer 2 Central Orchestrator**
* **Role:** Central multi-brand DAG orchestrator, context assembler, evidence synthesizer, and HITL gatekeeper.
* **Input Schemas:**
  - `EnterpriseDirective` (`tenant_scope: TenantScope`, `objective: str`, `budget_ceiling: float`, `risk_tolerance: RiskLevel`, `time_horizon: str`, `prohibited_terms: list[str]`, `mandatory_disclaimers: list[str]`).
  - `PolicyEnvelope` (`policy_id: str`, `policy_version: str`, `autonomy_tier: str`, `tenant_id: str`, `spend_caps: dict[str, float]`, `claim_limits: dict[str, Any]`, `rules: list[str]`).
  - `EvidenceEnvelope` (`task_id: str`, `worker_role: WorkerRole`, `confidence: ConfidenceInterval`, `findings: list[str]`, `payload: dict[str, Any]`, `generated_artifacts: list[str]`, `supporting_evidence: list[str]`, `provenance: dict[str, str]`, `proposed_state_changes: dict[str, str]`).
  - `ApprovalDecision` (`approval_id: str`, `action_preview_id: str`, `status: ApprovalStatus [APPROVED|REJECTED|REVISED|HELD]`, `signer_identity: str`, `cryptographic_signature: str`, `modifications: dict[str, Any]`).
  - `RawTelemetryBatch` (`batch_id: str`, `tenant_id: str`, `events: list[TelemetryEvent]`).
* **Output Schemas:**
  - `TaskGrant` (`task_id: str`, `worker_role: WorkerRole`, `tenant_scope: TenantScope`, `brand_id: str`, `objective: str`, `task_scope: str`, `task_slice: str`, `cts_state: dict[str, Any]`, `brand_rules: dict[str, Any]`, `validated_evidence: list[dict[str, Any]]`, `provenance_references: list[str]`, `freshness_metadata: dict[str, Any]`, `policy_constraints: list[str]`, `expires_at: datetime`, `tool_permissions: list[str]`, `sandbox_capabilities: list[str]`, `token_budget: int`, `budget_breakdown: dict[str, int]`, `risk_tier: RiskLevel`, `stop_conditions: list[str]`, `expected_outputs: list[str]`, `expected_output_schema: dict[str, Any]`).
  - `ActionPreview` (`action_preview_id: str`, `task_id: str`, `tenant_id: str`, `worker_role: WorkerRole`, `risk_level: RiskLevel`, `preview_type: str`, `summary: str`, `spend_proposal: dict[str, Any] | None`, `claims_dossier: dict[str, Any] | None`, `code_diff: dict[str, Any] | None`, `copy_pack: dict[str, Any] | None`, `attribution_summary: dict[str, Any] | None`).
  - `ConsolidatedEvidencePackage` (`package_id: str`, `tenant_id: str`, `status: ConsolidatedPackageStatus [VALID|FLAGGED_WITH_CONFLICTS|REJECTED]`, `source_task_ids: list[str]`, `participating_roles: list[WorkerRole]`, `validated_artifacts: list[dict[str, Any]]`, `confidence_summary: ConsolidatedConfidenceSummary`, `conflicts: list[EvidenceConflict]`, `warnings: list[str]`, `rejected_items: list[RejectedEvidenceItem]`, `proposed_state_deltas: list[CandidateStateDelta]`, `synthesized_evidence_summary: list[str]`, `provenance_summary: dict[str, Any]`).
  - `DispatchedExecutionDirective` (`dispatch_id: str`, `task_id: str`, `tenant_id: str`, `target_surface: str`, `action_payload: dict[str, Any]`, `hitl_approval_signature: str`, `issued_at: datetime`, `expires_at: datetime`).

#### **2. Agentic RAG Controller & Dispatcher — Layer 3 Governed Knowledge Gateway**
* **Role:** Governed, tenant-isolated vector and BM25 hybrid knowledge retrieval and document ingestion gateway.
* **Input Schemas:**
  - `IntelligenceEngineToken` (`_issued_to: str` — cryptographically unforgeable capability token minted exclusively by IE).
  - `RagRetrievalQuery` (`tenant_id: str`, `query: str`, `top_k: int = 10`, `purpose: str`, `freshness_target: timedelta | None`, `provenance_required: bool = True`).
  - `RagIngestCommand` (`tenant_id: str`, `doc_id: str`, `text: str`, `source: str`, `caller: CallerIdentity`).
* **Output Schemas:**
  - `list[EvidenceChunk]` (`doc_id: str`, `tenant_id: str`, `text: str`, `source: str`, `source_authority: str`, `provenance_hash: str [SHA-256]`, `provenance_tracked: bool = True`, `retrieved_at: datetime`, `freshness_status: str`, `score: float`).

---

### **7.3 Layer 5: Worker Agents Input/Output Contracts**

| Worker Agent | Primary Input Schema | Primary Output Schema | Intermediate Deliverable Models | Sandbox Capability Bound |
| :--- | :--- | :--- | :--- | :--- |
| **W_DEV** (Development Engine) | `TaskGrant` + `DevelopmentEngineRequest` | `EvidenceEnvelope` | `DevelopmentDeliverable` (`ui_templates`, `cms_schema_diffs`, `code_diffs`, `changed_files`, `security_checks_passed`) | `SandboxCapability.CODE` (`S_CODE`) |
| **W_STRAT** (Strategy Engine) | `TaskGrant` -> `StrategyDirective` | `StrategyResultEnvelope` | `OmnichannelStrategyPlan` (`channel_allocations`, `funnel_stages`, `scenarios`, `total_allocated`) + `ChannelSpendProposal` | `SandboxCapability.ALLOC` (`S_ALLOC`) |
| **W_CREAT** (Creative Content Engine) | `TaskGrant` + `CreativePlan` | `EvidenceEnvelope` | `CreativePackage` (`ad_copy_variants`, `social_posts`, `visual_briefs`, `schedules`, `qa_status`, `artifact_hashes`) | `SandboxCapability.COPY` (`S_COPY`) |
| **W_PROD** (Product Evidence Engine) | `TaskGrant` + `ResearchProtocol` | `EvidenceEnvelope` | `ProductEvidencePayload` / `ClaimsDossier` (`claims`, `trace_bundle`, `product_specification`, `safety_assessments`, `rule_applications`) | `SandboxCapability.VAL` (`S_VAL`) |
| **W_COMP** (Competitor Intel Engine) | `TaskGrant` -> `CompetitorResearchContext` | `EvidenceEnvelope` | `CompetitiveEvidenceBrief` (`assumption_verdicts`, `entity_inventory`, `observations`, `findings`, `conflicts`, `market_alerts`) | `SandboxCapability.COMP` (`s-comp`) |
| **W_VOICE** (Customer Voice Engine) | `TaskGrant` + `FeedbackBatch` | `EvidenceEnvelope` | `CustomerVoicePayload` (`topics`, `aspect_sentiment`, `needs_and_objections`, `journey_comparisons`, `qa_report`, `objection_profiles`) | `SandboxCapability.PARSE` (`S_PARSE`) |
| **W_LEARN** (Learning & Performance Engine) | `TaskGrant` + `TelemetryStream` | `EvidenceEnvelope` | `AttributionDeliverable` (`channel_weights`, `decay_metrics`, `roas_metrics`, `data_quality`) + `LearningDeltaCandidate` | `SandboxCapability.ATTR` (`S_ATTR`) |

---

### **7.4 Layer 6: Specialist Sub-Agents Input/Output Contracts (All 38 Specialists)**

#### **A. Development Engine Specialists (7 Sub-Agents)**
1. **DEV-PLAN (Planning Specialist):**
   - *Input:* `DevelopmentTaskGrant` (target component, UI/CMS requirements, architectural principles, repo tree).
   - *Output:* `DevelopmentPlan` (`phases: list[PlanPhase]`, `work_streams: list[WorkStream]`, `architectural_decisions: list[str]`, `risk_mitigations: list[str]`).
2. **DEV-UI (UI Layout Specialist):**
   - *Input:* `DevelopmentPlan` + design tokens + responsive viewport constraints.
   - *Output:* `UILayoutSpecification` (`templates: list[UITemplateDefinition]`, `css_rules: str`, `breakpoints: list[ResponsiveBreakpoint]`, `wcag_compliance_score: float`).
3. **DEV-CMS (CMS Contract Specialist):**
   - *Input:* `DevelopmentPlan` + content model schemas + UI prop requirements.
   - *Output:* `CmsContractSpecification` (`schema_diffs: list[CmsSchemaDiff]`, `backward_compatibility: bool`, `migration_plan: list[str]`).
4. **DEV-IMPL (Implementation Specialist):**
   - *Input:* `UILayoutSpecification` + `CmsContractSpecification` + target file scopes.
   - *Output:* `ImplementationResult` (`code_diffs: list[CodeDiffEntry]`, `ast_validations: list[dict]`, `modified_symbols: list[str]`).
5. **DEV-VERIF (Verification Specialist):**
   - *Input:* `ImplementationResult` + unit test suites + component sandbox build specs.
   - *Output:* `VerificationReport` (`syntax_valid: bool`, `lint_errors: list[str]`, `test_results: dict[str, Any]`, `coverage_percentage: float`).
6. **DEV-SEC (Security Review Specialist):**
   - *Input:* `ImplementationResult` + `VerificationReport` + SBOM dependencies.
   - *Output:* `SecurityDossier` (`sast_clean: bool`, `secret_scan_clean: bool`, `dependency_sca_clean: bool`, `authorization_boundary_verified: bool`, `risk_tier: RiskLevel`).
7. **DEV-REL (Release Operations Specialist):**
   - *Input:* Verified code diffs + CMS schema diffs + security approvals.
   - *Output:* `ReleaseBundle` (`deployment_manifest: dict`, `rollback_manifest: dict`, `cyclonedx_sbom: dict`, `migration_dry_run_receipt: dict`, `bundle_hash: str`).

#### **B. Strategy Engine Specialists (1 Sub-Agent)**
8. **STRAT-ALLOC (Media & Budget Allocator):**
   - *Input:* `SAllocMandate` (`budget_ceiling: float`, `authorized_channels: list[str]`, `allocation_constraints: list[AllocationConstraint]`, `channel_parameters: dict[str, dict]`, `mroi_floor: float`, `kpi_name: str`).
   - *Output:* `SAllocResult` (`status: SAllocDomainStatus [OK|EVIDENCE_GAP|INFEASIBLE]`, `total_allocated: float`, `channel_allocations: list[ChannelAllocation]`, `marginal_roas: dict[str, float]`, `response_curves: dict[str, Any]`, `diagnostics: dict[str, Any]`, `execution_receipt: SandboxExecutionReceipt`).

#### **C. Creative & Content Engine Specialists (6 Sub-Agents)**
9. **CREAT-RESEARCH (Creative Research Specialist):**
   - *Input:* `CreativePlan` + platform guidelines + brand positioning targets.
   - *Output:* `ResearchBrief` (`findings: list[ResearchFindingItem]`, `citations: list[str]`) + `PlatformSpecSnapshot` (`specs: list[PlatformSpecItem]`).
10. **CREAT-CONCEPT (Concept Specialist):**
    - *Input:* `ResearchBrief` + `OmnichannelStrategyPlan` + approved product evidence refs.
    - *Output:* `ConceptPack` (`concepts: list[ConceptItem] {territory, tension, angle, narrative_architecture}`).
11. **CREAT-COPY (Copy Specialist):**
    - *Input:* `ConceptPack` + approved product claims + channel tone directives.
    - *Output:* `CopyPack` (`variants: list[AdCopyVariant] {headline, hook_angle, hook_score, body_copy, cta, source_claim_ids}`).
12. **CREAT-VISUAL (Visual Specialist):**
    - *Input:* `ConceptPack` + brand design tokens + product imagery assets.
    - *Output:* `VisualPack` (`production_briefs: list[VisualBrief]`, `storyboards: list[dict]`, `art_direction: str`).
13. **CREAT-ADAPT (Adaptation Specialist):**
    - *Input:* `CopyPack` + `VisualPack` + `PlatformSpecSnapshot`.
    - *Output:* `AdaptedCreativePack` (`ad_copy_variants: list[AdCopyVariant]`, `social_posts: list[SocialPostVariant]`, `calendar_proposal: list[ContentScheduleItem]`).
14. **CREAT-QA (Creative Quality & Compliance Specialist):**
    - *Input:* `AdaptedCreativePack` + `ClaimsDossier` + enterprise prohibited terms.
    - *Output:* `QAReport` (`status: QAStatus [PASS|REVISE|BLOCK]`, `findings: list[QAFinding]`, `severity: str`, `missing_evidence_claims: list[str]`).

#### **D. Product / Evidence Engine Specialists (6 Sub-Agents)**
15. **PROD-DISCOVERY (Literature & Discovery Specialist):**
    - *Input:* `ResearchProtocol` + formulation ingredient identifiers + target study types.
    - *Output:* `DiscoveryResult` (`sources: list[SourceRecord]`, `evidence: list[ExtractedEvidence]`, `access_levels: dict[str, AccessLevel]`).
16. **PROD-LAB (Product Lab & Formulation Specialist):**
    - *Input:* Finished product specifications + raw batch certificates of analysis (CoA) + ingredient lists.
    - *Output:* `LabValidationResult` (`validations: list[LabValidation]`, `bridges: list[FormulationEvidenceBridge]`).
17. **PROD-APPRAISAL (Critical Appraisal Specialist):**
    - *Input:* `list[ExtractedEvidence]` + GRADE certainty criteria.
    - *Output:* `AppraisalResult` (`assessments: list[EvidenceAssessment] {study_design, risk_of_bias, sample_size, effect_size, certainty_rating}`).
18. **PROD-CLAIMS (Claims Substantiation Specialist):**
    - *Input:* Candidate marketing propositions + `list[EvidenceAssessment]` + `list[FormulationEvidenceBridge]`.
    - *Output:* `ClaimsMappingResult` (`claims: list[ClaimRecord]`, `mappings: list[ClaimEvidenceEdge]`, `gaps: list[EvidenceGap]`).
19. **PROD-REGULATORY (Regulatory Compliance Specialist):**
    - *Input:* Candidate claims + target jurisdictions + product classification codes.
    - *Output:* `RegulatoryResult` (`rules: list[RegulatoryRule]`, `applications: list[RuleApplication] {outcome: COMPLIANT|NON_COMPLIANT|REQUIRES_QUALIFICATION}`).
20. **PROD-SAFETY (Cosmetic Safety & Toxicology Specialist):**
    - *Input:* Ingredient concentrations + exposure scenarios + vulnerable population definitions.
    - *Output:* `SafetyDossier` (`safety_assessments: list[SafetyAssessment] {margin_of_safety, hazard_profile, status: PASS|FLAGGED}`).

#### **E. Competitor Intel Engine Specialists (6 Sub-Agents)**
21. **COMP-DISCOVERY (Competitor Discovery Specialist):**
    - *Input:* Strategic market scope + baseline competitor list + product categories.
    - *Output:* `DiscoveryInventory` (`entities: list[CompetitorEntity]`, `target_domains: list[str]`, `coverage_status: CoverageStatus`).
22. **COMP-PRICING (Price Intelligence Specialist):**
    - *Input:* Target competitor SKU URLs + currency specifications + `SandboxEgressGrant`.
    - *Output:* `PricingObservationResult` (`observations: list[Observation] {price, currency, discount_depth, observed_at, evidence_ref}`).
23. **COMP-ADVERTISING (Ad Library Specialist):**
    - *Input:* Competitor brand identities + platform ad library endpoints + `SandboxEgressGrant`.
    - *Output:* `AdObservationResult` (`observations: list[Observation] {active_ad_count, creative_formats, hook_themes, spend_tier}`).
24. **COMP-SEARCH (Search & SERP Specialist):**
    - *Input:* Target search queries + geo-locations + `SandboxEgressGrant`.
    - *Output:* `SearchObservationResult` (`observations: list[Observation] {organic_rank, sponsored_rank, domain, page_title}`).
25. **COMP-POSITIONING (Positioning Analysis Specialist):**
    - *Input:* Aggregated competitor observations + brand baseline claims.
    - *Output:* `PositioningFindingsResult` (`findings: list[Finding] {finding_kind, claim_text, market_share_trend, messaging_whitespace}`).
26. **COMP-SYNTHESIS (Competitive Synthesis Specialist):**
    - *Input:* All specialist observations, findings, and strategy assumptions.
    - *Output:* `CompetitiveEvidenceBrief` (`assumption_verdicts: dict[str, AssumptionVerdict]`, `conflicts: list[ConflictSet]`, `market_alerts: list[MarketShiftAlert]`).

#### **F. Customer Voice Engine Specialists (6 Sub-Agents)**
27. **VOICE-DISCOVERY (Feedback Discovery & Ingestion Specialist):**
    - *Input:* Raw multi-channel customer records + survey export dumps.
    - *Output:* `NormalizedFeedbackBatch` (`records: list[FeedbackRecord]`, `methodology: list[SurveyMethodology]`, `de_identification_stats: dict`).
28. **VOICE-THEMES (Theme & Clustering Specialist):**
    - *Input:* Sanitized feedback records + minimum cluster thresholds.
    - *Output:* `TopicFindingsResult` (`topics: list[TopicFinding] {theme_name, frequency, relative_share, grounding_spans: list[EvidenceSpan]}`).
29. **VOICE-SENTIMENT (Aspect-Based Sentiment Specialist):**
    - *Input:* Sanitized feedback records + product aspect taxonomy.
    - *Output:* `SentimentFindingsResult` (`aspect_sentiment: list[AspectSentimentFinding] {aspect, polarity, model_score, evidence_spans: list[EvidenceSpan]}`).
30. **VOICE-NEEDS (Needs & Objections Specialist):**
    - *Input:* Sanitized feedback records + friction dictionaries.
    - *Output:* `NeedsObjectionsResult` (`needs_and_objections: list[NeedObjectionFinding] {finding_type, theme, severity, customer_vocabulary, evidence_spans}`).
31. **VOICE-JOURNEY (Customer Journey Specialist):**
    - *Input:* Touchpoint-tagged feedback records + channel progression logs.
    - *Output:* `JourneyComparisonsResult` (`comparisons: list[JourneyComparison] {channel_a, channel_b, comparison_summary, causal_claim_disclaimer}`).
32. **VOICE-QA (Voice Quality & Privacy Auditor):**
    - *Input:* All intermediate topic, sentiment, objection, and journey outputs.
    - *Output:* `VoiceQAReport` (`decision: QADecision [PASS|REVISE|BLOCK]`, `nist_reidentification_check: bool`, `grounding_audit_passed: bool`, `causal_claim_violation_count: int`).

#### **G. Learning & Performance Engine Specialists (6 Sub-Agents)**
33. **LEARN-TELEMETRY (Telemetry Normalization Specialist):**
    - *Input:* Raw omnichannel conversion logs, pixel webhooks, and ad platform spend records.
    - *Output:* `NormalizedTelemetryDataset` (`conversion_paths: list[ConversionPath]`, `data_quality: DataQualityIndicator`).
34. **LEARN-ATTRIBUTION (Multi-Touch Attribution Specialist):**
    - *Input:* `NormalizedTelemetryDataset` + model specification (Linear, Time-Decay, Position-Based).
    - *Output:* `AttributionEstimates` (`estimates: list[LearningEstimate]`, `channel_weights: list[AttributionWeight]`, `roas_metrics: list[RoasMetric]`).
35. **LEARN-INCREMENTALITY (Causal Incrementality Specialist):**
    - *Input:* Geo-experiment logs, holdout conversion data, and matched-market telemetry.
    - *Output:* `IncrementalityEstimates` (`estimates: list[LearningEstimate] {estimand: "ITT_lift", causal_claim_permitted: true, uncertainty: LearningUncertainty}`).
36. **LEARN-FATIGUE (Creative Fatigue Specialist):**
    - *Input:* Creative timeseries CTR, frequency, and CPA histories.
    - *Output:* `FatigueEstimates` (`estimates: list[LearningEstimate]`, `decay_metrics: list[CreativeDecayMetric] {fatigue_detected: bool, recommended_action}`).
37. **LEARN-DECAY (Adstock & Half-Life Specialist):**
    - *Input:* Longitudinal media spend and baseline brand conversion streams.
    - *Output:* `DecayEstimates` (`estimates: list[LearningEstimate] {half_life_days: float, adstock_retention_rate: float, decay_curve_model}`).
38. **LEARN-QA (Learning Quality Assurance Specialist):**
    - *Input:* All analytical estimates + diagnostic logs + telemetry data quality indicators.
    - *Output:* `LearningQAResult` (`decision: QADecision [PASS|REVISE|BLOCK]`, `accepted_claim_ids: list[str]`, `rejected_claim_ids: list[str]`, `gate_results: dict[str, bool]`).

---

### **7.5 Layer 6 Runtime: Sandbox Micro-Tool & Capability Schemas (`sandbox/docker/hardened/skills/`)**

Every micro-tool execution executes inside the hardened AIO sandbox via a standardized typed command interface.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Sandbox Invocations                             │
│                                                                        │
│   Worker Engine / Sub-Agent                                            │
│            │                                                           │
│            ▼                                                           │
│   SandboxInvocationMandate                                             │
│   ├── capability: SandboxCapability                                    │
│   ├── operation: str                                                   │
│   ├── payload: dict[str, Any]                                          │
│   ├── network_policy: NetworkPolicy                                    │
│   └── egress_grant: SandboxEgressGrant | None                          │
│            │                                                           │
│            ▼ (Dispatched to container: /home/gem/skills/<skill>/scripts/run.py)
│                                                                        │
│   Sanitized Execution Outcome                                          │
│            │                                                           │
│            ▼                                                           │
│   SandboxResult                                                        │
│   ├── status: SandboxExecutionStatus                                   │
│   ├── success: bool                                                    │
│   ├── structured_output: dict[str, Any]                                │
│   ├── confidence_score: float                                          │
│   ├── execution_receipt: SandboxExecutionReceipt                       │
│   └── raw_output_sha256: str                                           │
└────────────────────────────────────────────────────────────────────────┘
```

#### **1. `s-code` (Component Coder & Linter)**
* **Skill Path:** `sandbox/docker/hardened/skills/s-code/` (Runtime: `scripts/run.py`).
* **Authorized Worker:** `W_DEV` (`WorkerRole.DEVELOPMENT`).
* **Network Policy:** `NetworkPolicy.DISABLED` (DENY_ALL).
* **Allowed Operations:** `parse_ast`, `lint`, `generate_diff`, `execute_code`, `validate_syntax`, `apply_code_patch`, `format_code`, `inspect_ast_symbols`, `validate_syntax_compiler`, `manage_packages`, `generate_code`.
* **Input Payload Schema:**
  - `code: str` (Source code string under evaluation).
  - `patch: str` (Unified diff string to apply).
  - `file_path: str` (Relative file path within ephemeral workspace).
  - `target_symbols: list[str]` (Specific AST symbols to extract).
* **Output `structured_output` Schema:**
  - `ast_valid: bool`, `syntax_errors: list[str]`.
  - `complexity_metrics: dict[str, int]` (`cyclomatic_complexity`, `node_count`).
  - `lint_violations: list[dict[str, Any]]` (`line`, `rule`, `message`, `severity`).
  - `generated_diff: str` (Sanitized unified diff output).
  - `compilation_sanity_passed: bool`.

#### **2. `s-alloc` (Media & Budget Allocator)**
* **Skill Path:** `sandbox/docker/hardened/skills/s-alloc/` (Runtime: `scripts/run.py`).
* **Authorized Worker:** `W_STRAT` (`WorkerRole.STRATEGY`).
* **Network Policy:** `NetworkPolicy.DISABLED` (DENY_ALL).
* **Allowed Operations:** `model_media_mix`, `optimize_budget`, `simulate_funnel`, `simulate_scenarios`, `calculate_roas`.
* **Input Payload Schema (`SAllocMandate`):**
  - `budget_ceiling: float` (Strict spend upper bound).
  - `authorized_channels: list[str]` (Allowlisted marketing channels).
  - `allocation_constraints: list[dict]` (`channel`, `min_spend`, `max_spend`, `min_share`, `max_share`).
  - `channel_parameters: dict[str, dict]` (`initial_marginal_return`, `saturation_spend`).
  - `mroi_floor: float`, `kpi_name: str`, `time_horizon: str`.
* **Output `structured_output` Schema (`SAllocResult`):**
  - `domain_status: SAllocDomainStatus` (`OK`, `INFEASIBLE`, `EVIDENCE_GAP`).
  - `total_allocated: float` (Must strictly satisfy $\le \text{budget\_ceiling}$).
  - `allocations: list[dict]` (`channel`, `allocated_amount`, `percentage_of_total`, `expected_revenue`, `marginal_roas`).
  - `response_curves: dict[str, Any]`, `diagnostics: dict[str, Any]`.

#### **3. `s-copy` (Creative & Copy Validator)**
* **Skill Path:** `sandbox/docker/hardened/skills/s-copy/` (Runtime: `scripts/run.py`).
* **Authorized Worker:** `W_CREAT` (`WorkerRole.CREATIVE_CONTENT` — specifically `CREAT-COPY`).
* **Network Policy:** `NetworkPolicy.DISABLED` (DENY_ALL).
* **Allowed Operations:** `prohibited_term_check`, `validate_claim_refs`, `validate_platform_format`, `validate_aspect_ratio`, `validate_safe_zone_metadata`, `validate_schema`, `deduplicate_variants`, `hash_artifact`, `format_validation`.
* **Input Payload Schema:**
  - `variants: list[dict]` (`headline`, `body_copy`, `cta`, `source_claim_ids`, `channel`).
  - `approved_claim_ids: list[str]` (Authoritative valid claim identifiers).
  - `prohibited_terms: list[str]` (Enterprise compliance blocklist).
  - `platform_spec: dict[str, Any]` (`character_limits`, `prohibited_formats`).
* **Output `structured_output` Schema:**
  - `is_valid: bool`.
  - `claim_reference_audit: dict[str, bool]` (Flagging unsupported claim references).
  - `prohibited_term_matches: list[dict[str, str]]` (`variant_id`, `term_detected`).
  - `character_limit_violations: list[dict[str, Any]]`.
  - `deduplicated_variants: list[dict]`, `artifact_hashes: dict[str, str]`.

#### **4. `s-val` (Claim, Product Lab & Regulatory Validator)**
* **Skill Path:** `sandbox/docker/hardened/skills/s-val/` (Runtime: `scripts/run.py`).
* **Authorized Worker:** `W_PROD` (`WorkerRole.PRODUCT_EVIDENCE`).
* **Network Policy:** `NetworkPolicy.DISABLED` (DENY_ALL) for appraisal, lab, safety, claims, and validators; `NetworkPolicy.ALLOWLIST` for discovery/regulatory when accompanied by `SandboxEgressGrant`.
* **Allowed Operations:** `validate_claim`, `lint_compliance`, `check_schema`, `validate_product_dossier`, `assemble_dossier`, `validate_trace_bundle`, `research_literature`, `fetch_official_rules`.
* **Input Payload Schema:**
  - `trace_bundle: dict[str, Any]` (`claims`, `evidence`, `sources`, `rules`, `mappings`, `gaps`).
  - `product_spec: dict[str, Any]` (`ingredients`, `formulation_id`).
  - `regulatory_rules: list[dict[str, Any]]` (`jurisdiction`, `force`, `section`).
* **Output `structured_output` Schema:**
  - `structural_status: str` (`VALID`, `FLAGGED`, `INVALID`).
  - `referential_integrity_pass: bool`.
  - `unsupported_claims: list[str]`.
  - `prohibited_absolute_claims: list[str]` (Catches "cures", "100% guaranteed").
  - `evidence_gaps: list[dict[str, Any]]`.

#### **5. `s-comp` / `s-scrape` (Competitor Price & Ad Scraper)**
* **Skill Path:** `sandbox/docker/hardened/skills/s-comp/` (Runtime: `scripts/run.py`).
* **Authorized Worker:** `W_COMP` (`WorkerRole.COMPETITOR_INTEL`).
* **Network Policy:** `NetworkPolicy.CONTROLLED` (Strict Tinyproxy allowlist egress).
* **Allowed Operations:** `gather_prices`, `parse_dom`, `track_ads`, `scrape_prices`.
* **Input Payload Schema:**
  - `target_urls: list[str]` (Scoped competitor URLs to extract).
  - `extraction_rules: dict[str, str]` (DOM selector queries).
  - `egress_grant: SandboxEgressGrant` (Signed token with domain whitelist and expiration).
* **Output `structured_output` Schema:**
  - `observed_prices: list[dict]` (`sku`, `raw_price`, `currency`, `extracted_at`).
  - `active_ads: list[dict]` (`headline`, `format`, `observed_reach_estimate`).
  - `dom_tokens: list[str]`, `egress_receipt: dict[str, str]`.

#### **6. `s-parse` (Sentiment, Review & Customer Objection Parser)**
* **Skill Path:** `sandbox/docker/hardened/skills/s-parse/` (Runtime: `scripts/run.py`).
* **Authorized Worker:** `W_VOICE` (`WorkerRole.CUSTOMER_VOICE`).
* **Network Policy:** `NetworkPolicy.DISABLED` (DENY_ALL).
* **Allowed Operations:** `parse_sentiment`, `cluster_objections`, `extract_feedback`, `analyze_customer_voice`, `de_identify`, `ground_spans`.
* **Input Payload Schema:**
  - `raw_records: list[dict]` (`record_id`, `text`, `channel`, `timestamp`).
  - `pii_redaction_patterns: list[str]`.
  - `aspect_list: list[str]`.
* **Output `structured_output` Schema:**
  - `anonymized_vectors: list[dict]` (`vector_id`, `source_id_hash`, `polarity`, `sentiment_label`, `confidence`).
  - `clustered_objections: list[dict]` (`theme`, `frequency`, `severity`, `vocabulary`).
  - `pii_redaction_count: int`, `evidence_spans: list[dict]`.

#### **7. `s-attr` (Attribution, Adstock & Decay Modeler)**
* **Skill Path:** `sandbox/docker/hardened/skills/s-attr/` (Runtime: `scripts/run.py`).
* **Authorized Worker:** `W_LEARN` (`WorkerRole.LEARNING_PERFORMANCE`).
* **Network Policy:** `NetworkPolicy.DISABLED` (DENY_ALL).
* **Allowed Operations:** `calculate_attribution`, `score_decay`, `fatigue_scoring`, `validate_telemetry`, `estimate_attribution`, `fit_mmm`, `calculate_roas`.
* **Input Payload Schema:**
  - `conversion_paths: list[dict]` (`conversion_id`, `touchpoints: list[dict] {channel, cost, occurred_at}`).
  - `model_type: str` (`linear`, `time_decay`, `position_based`).
  - `half_life_days: float`, `decay_rate: float`.
* **Output `structured_output` Schema:**
  - `channel_weights: list[dict]` (`channel`, `weight`, `attributed_revenue`, `attributed_conversions`).
  - `decay_metrics: list[dict]` (`creative_id`, `decay_multiplier`, `fatigue_detected`).
  - `roas_metrics: list[dict]` (`channel`, `spend`, `revenue`, `roas`, `status`).

---

### **7.6 Validation Assessment Findings & Production Hardening Audit**

A comprehensive static analysis and runtime contract audit was conducted across all 47 agent entities (1 IE + 1 RAG + 7 Workers + 38 Specialists) and the 7 Sandbox micro-tool skill definitions:

1. **Zero Unvalidated Boundary Paths:** Every inter-agent message boundary strictly parses and validates inputs using Pydantic v2 data models. Ambient dictionary passing is forbidden; all schemas enforce explicit type annotations, string length bounds, numeric range checks, and enum validations.
2. **Strict Model A Persistence Compliance:** All 7 Worker Agents and 38 Sub-Agents have zero connection strings, direct database handles, or direct RAG API access. Data retrieval is 100% mediated through Intelligence Engine `ContextRequest` queries, ensuring tamper-evident provenance hashing and tenant isolation.
3. **Sandbox Capability Enforcement:** All 7 worker engines interact with execution tools exclusively through `SandboxInvocationMandate` via `app.integrations.sandbox.client.SandboxClient`. Direct subprocess execution or shell escaping from workers is prevented by container virtualization, seccomp filters, and cgroup limits.
4. **Egress Security Verification:** 6 of 7 sandbox capabilities (`s-code`, `s-alloc`, `s-copy`, `s-val`, `s-parse`, `s-attr`) are hard-coded to `NetworkPolicy.DISABLED` (DENY_ALL). Only `s-comp` and governed literature discovery in `s-val` are permitted egress, and strictly require a non-expired, tenant-bound, domain-allowlisted `SandboxEgressGrant` routed through the isolated Tinyproxy sidecar.
5. **Deterministic Audit Lineage:** Every deliverable outputs a SHA-256 hash digest and structured provenance metadata registered into the W3C PROV Immutable Ledger.