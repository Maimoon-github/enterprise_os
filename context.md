You need to research on to Build a universal, research-driven, multi-agent **AI Brand Strategy Engine** that analyzes personal portfolios and eCommerce websites, identifies weaknesses, opportunities, and competitive gaps, and generates a structured, evidence-based growth strategy.

The system will use coordinated AI agents to execute the research and strategy-development workflow sequentially. Using a VNC-based browser, it will explore the target website, relevant social media platforms, and competitors' online presence in depth, examining the brand as a human researcher would. All strategic recommendations must be grounded in collected evidence and observed data. Using Google Antigravity SDK,and local Ollama models.

```
## Mode A — Personal Branding and Portfolio Strategy

Designed for freelancers, developers, data scientists, consultants, creators, agencies, and other professionals. Analyze personal portfolios, professional positioning, expertise, target audiences, portfolio projects, credibility signals, brand identity, website messaging, SEO, content strategy, competitor presence, and lead-generation opportunities. Identify positioning gaps, audience misalignment, competitive advantages, and actionable opportunities to strengthen professional authority and attract relevant clients or career opportunities.

## Mode B — eCommerce Growth Strategy

Designed for online stores selling physical or digital products. Analyze product positioning, category structure, product descriptions, target customers, competitor offerings, search visibility, brand messaging, trust signals, conversion barriers, customer journeys, merchandising, retention opportunities, and content strategy. Identify market gaps, product differentiation opportunities, customer friction, and evidence-based initiatives to improve visibility, conversions, customer experience, and sustainable growth.

## Mode C — Shared Strategic Intelligence Engine

Both modes operate on the same research-driven, multi-agent infrastructure, including website and social platform analysis, VNC-based browser research, competitor investigation, evidence collection, audience intelligence, business-context modeling, strategic planning, prioritization, validation, reporting, and performance feedback. The Website and Social Platform Analyst, Audience Strategist, Brand Strategist, SEO and Content Strategist, Growth Strategist, and Strategy Validator collaborate sequentially to transform collected evidence into a context-specific, prioritized, and actionable growth strategy. Shared capabilities remain consistent across both modes, while analytical criteria, strategic recommendations, and success metrics adapt to the selected business type.
```

Provide me the Recommended enterprise_os system architecture
And The agents which are the needs of this engine
```
# Universal AI Brand Strategy Engine

**1. Multi-Agent Architecture**: 

**1.1. Website and Social Platform Analyst**: Analyzes the target brand's website, products, services, portfolio, and relevant social media profiles. Examines website structure, user experience, existing content, SEO performance indicators, and overall digital presence. Identifies relevant competitors and investigates their websites and social media profiles through the VNC browser to gather comparative evidence.

**1.2. Audience Strategist**: Identifies and evaluates the brand's target audience using the collected research. Defines the Ideal Customer Profile (ICP), audience personas, user intent, buyer friction, and audience–brand alignment. Determines whether the brand's offerings, messaging, and positioning address the needs and expectations of the intended audience.

**1.3. Brand Strategist**: Evaluates the brand's positioning, messaging, identity, differentiation, and perceived market value. Determines how the brand is presented, how it may be perceived by its target audience, and how it can establish a clearer, more distinctive, and competitive brand identity.

**1.4. SEO and Content Strategist**: Develops data-driven SEO and content recommendations based on the website analysis, competitor research, audience insights, and market evidence. Identifies relevant keyword opportunities, content gaps, search intent, on-page SEO issues, and potential content strategies aligned with the brand's objectives.

**1.5. Growth Strategist**: Synthesizes the findings produced by the preceding agents to identify meaningful patterns, opportunities, bottlenecks, and competitive advantages. Translates these insights into a prioritized, actionable growth strategy with clear objectives, recommended initiatives, and measurable performance indicators.

**1.6. Strategy Validator**: Independently evaluates the proposed strategy for factual accuracy, evidence quality, logical consistency, feasibility, prioritization, and alignment with the collected research. Identifies unsupported assumptions, contradictions, missing evidence, and impractical recommendations, then requires revisions where necessary before approving the final strategy.

**2. Execution Principle**: The agents will work in a coordinated, sequential workflow, with each agent using the relevant findings from previous stages. The system will transform browser-based research and collected evidence into an integrated brand growth strategy rather than producing generic recommendations. The final output must be research-backed, context-specific, prioritized, actionable, and validated before delivery.

# Universal AI Brand Strategy Engine: System Architecture & Agent Specifications

The Universal AI Brand Strategy Engine coordinates autonomous, research-grounded agents through a centralized Manager pattern. Operating across **Mode A (Personal Branding & Portfolio Strategy)** and **Mode B (eCommerce Growth Strategy)** on a unified intelligence core (**Mode C**), the engine executes live VNC-based visual and DOM exploration, maps competitors, establishes evidence chains, and produces structured, validated growth initiatives.

---

## 1. Engine Architecture & Shared State Schema

### 1.1 Orchestration Pattern: The Centralized Manager

The engine implements a **Hierarchical Supervisor (Manager) Pattern**. The Manager agent maintains the master state, delegates tasks sequentially to domain specialists via tool invocation, and manages conditional revision loops triggered by the Strategy Validator.

```
                  ┌───────────────────────────────────────────────┐
                  │       Brand Strategy Orchestrator (Manager)   │
                  └──────┬──────────────────────┬───────────▲─────┘
                         │                      │           │ (Revisions)
       ┌─────────────────▼────────┐   ┌─────────▼────────┐  │
       │ 1. Website & Social      │   │ 2. Audience      │  │
       │    Platform Analyst      │   │    Strategist    │  │
       └─────────────────┬────────┘   └─────────┬────────┘  │
                         └───────────┬──────────┘           │
                                     ▼                      │
                      ┌────────────────────────────┐        │
                      │ 3. Brand Strategist        │        │
                      └──────────────┬─────────────┘        │
                                     ▼                      │
                      ┌────────────────────────────┐        │
                      │ 4. SEO & Content           │        │
                      │    Strategist              │        │
                      └──────────────┬─────────────┘        │
                                     ▼                      │
                      ┌────────────────────────────┐        │
                      │ 5. Growth Strategist       │        │
                      └──────────────┬─────────────┘        │
                                     ▼                      │
                      ┌────────────────────────────┐        │
                      │ 6. Strategy Validator      ├────────┘
                      └──────────────┬─────────────┘
                                     │ (Approved)
                                     ▼
                      ┌────────────────────────────┐
                      │ Validated Strategy Plan    │
                      └────────────────────────────┘

```

### 1.2 Unified Engine State Schema

All agents read from and mutate a centralized, strongly typed state object throughout the execution pipeline:

```json
{
  "session_id": "str (uuid)",
  "mode": "Mode_A_Personal | Mode_B_eCommerce",
  "brand_profile": {
    "website_url": "https://example.com",
    "brand_name": "str",
    "website_type": "personal_portfolio | agency | direct_to_consumer | marketplace",
    "industry": "str",
    "value_proposition": "str",
    "products_or_services": [],
    "target_market": [],
    "business_goals": []
  },
  "research_repository": {
    "dom_snapshots": {},
    "visual_evidence_vnc": [
      {
        "evidence_id": "ev_001",
        "url": "str",
        "source_type": "dom_node | screenshot | social_post | serp_result",
        "timestamp": "iso8601",
        "raw_data_ref": "s3_or_blob_uri",
        "summary": "str"
      }
    ],
    "social_footprint": {},
    "content_inventory": [],
    "competitors": [
      {
        "competitor_name": "str",
        "website_url": "str",
        "benchmarked_metrics": {},
        "observed_advantages": [],
        "observed_deficiencies": []
      }
    ]
  },
  "strategic_artifacts": {
    "audience_analysis": {},
    "brand_positioning": {},
    "seo_and_content_plan": {},
    "synthesized_growth_initiatives": []
  },
  "validation_report": {
    "status": "pending | passed | failed_needs_revision",
    "iteration_count": 0,
    "audit_log": []
  }
}

```

---

## 2. Standardized Strategic Output Contract

Every initiative produced by the engine must strictly conform to the following schema. Initiatives lacking verifiable source records in the `research_repository` fail validation automatically.

```json
{
  "recommendation_id": "REC-001",
  "finding": "Observed phenomenon, friction point, or structural gap on the target property.",
  "evidence": {
    "source_url": "https://example.com/checkout or /portfolio",
    "evidence_id": "ev_001",
    "dataset_reference": "VNC Screenshot #12 / DOM Selector #pricing-grid",
    "observation_notes": "Concrete visual or structural data observed during inspection."
  },
  "business_implication": "Quantified risk or missed business objective tied to this finding.",
  "recommendation": "Prescriptive, step-by-step remediation or strategic initiative.",
  "priority": {
    "impact": "High | Medium | Low",
    "effort": "High | Medium | Low",
    "cost": "High | Medium | Low",
    "confidence": "High (90-100%) | Medium (70-89%) | Low (<70%)"
  },
  "success_metric": {
    "kpi": "Primary quantitative metric to measure outcome",
    "baseline": "Current observed or inferred level",
    "target": "Target threshold indicating strategic success"
  },
  "approval_status": "Proposed | Approved | Implemented | Evaluated"
}

```

---

## 3. Comprehensive Agent Specifications

### Agent 0: Brand Strategy Orchestrator (Manager Agent)

* **Role & Mandate:** Serves as the central state controller and supervisor. Initializes the execution session, selects operational modes, invokes specialist agents sequentially, resolves context discrepancies, and routes rejected recommendations back to responsible agents for remediation.
* **Model Tier:** High-capacity reasoning model (e.g., GPT-4o / Claude 3.5 Sonnet / Gemini 1.5 Pro) with native structured tool calling and schema enforcement.
* **Available Tools:**
* `initialize_engine_state(url, mode, business_goals)`
* `delegate_task(agent_name, input_state_slice)`
* `merge_agent_payload(agent_name, response_payload)`
* `route_revisions(failed_initiatives, target_agent)`
* `compile_final_strategy_dossier(validated_state)`


* **Operational Instructions:**
* Enforce step-by-step pipeline execution: Analyst $\rightarrow$ Audience $\rightarrow$ Brand $\rightarrow$ SEO/Content $\rightarrow$ Growth $\rightarrow$ Validator.
* Maintain context isolation: Pass only required state subsets to each downstream specialist to minimize hallucination and context bleed.
* If the Strategy Validator returns an iteration error, freeze pipeline compilation and route the rejected recommendation back to the initiating agent with the validator's audit log. Limit feedback iterations to a maximum of 3 cycles.



---

### Agent 1: Website and Social Platform Analyst

* **Role & Mandate:** Performs automated, empirical reconnaissance of the target brand and up to three direct competitors. Operates a headless browser with visual recording to collect DOM snapshots, responsive UX behaviors, social link mappings, and competitor comparative metrics.
* **Model Tier:** Multimodal reasoning model capable of analyzing raw DOM hierarchies alongside visual screen captures.
* **Available Tools:**
* `vnc_browser_navigate(url, viewport_size, wait_until)`
* `vnc_browser_interact(action_type, selector, input_text)` (click, scroll, type)
* `capture_visual_evidence(full_page, highlight_selector)`
* `extract_dom_metadata(extract_keys)` (meta tags, headings, schema markup, OpenGraph)
* `social_profile_lookup(platform, handle_or_url)`
* `competitor_discovery_scan(brand_name, industry_keywords)`


* **Mode-Specific Behavior:**
* *Mode A (Personal Brand):* Scans homepage hero layout, proof of work, case study structure, technical stack tags, resume/CV downloads, social validation (GitHub activity, LinkedIn publications, X/Twitter threads), contact forms, and booking link reliability.
* *Mode B (eCommerce):* Inspects cart and checkout flows, above-the-fold value proposition, category navigation filters, mobile responsiveness, PDP (Product Detail Page) assets, shipping/return policy transparency, reviews integration, and trust seals.


* **Input State:** Raw URL, designated operating mode, business objectives.
* **Output State:** Populated `research_repository.dom_snapshots`, `visual_evidence_vnc`, `content_inventory`, and `competitors` records.
* **Active Guardrails:**
* Zero-Assumptions Constraint: Every identified structural issue must reference a concrete `evidence_id` linked to a screenshot or DOM path.
* Robots & Rate-Limiting: Adhere to target property scraping limits; fail gracefully if pages require private authenticated credentials.



---

### Agent 2: Audience Strategist

* **Role & Mandate:** Translates empirical website findings into audience models. Defines Ideal Customer Profiles (ICPs), maps customer journeys, uncovers buyer friction points, and diagnoses misalignments between observed content and user intent.
* **Model Tier:** Advanced analytical language model with specialized market segmentation frameworks.
* **Available Tools:**
* `query_market_demographics(industry, niche)`
* `map_customer_journey(touchpoints_array)`
* `analyze_sentiment_and_reviews(brand_name, competitor_names)`
* `friction_point_calculator(checkout_or_contact_steps)`


* **Mode-Specific Behavior:**
* *Mode A (Personal Brand):* Identifies hiring managers, enterprise clients, startup founders, or venture partners. Evaluates whether the portfolio communicates technical authority, reliability, and project ownership within the first 5 seconds of scanning.
* *Mode B (eCommerce):* Evaluates customer intent (impulse vs. high-consideration), price-to-trust sensitivity, demographic alignment, checkout drop-off triggers, and post-purchase expectations.


* **Input State:** `research_repository` (Analyst findings, visual evidence, competitor baselines).
* **Output State:** `strategic_artifacts.audience_analysis` (ICP schemas, buyer personas, observed friction triggers, persona-to-content alignment scores).
* **Active Guardrails:**
* Persona Grounding: Banned from generating generic personas (e.g., "Tech Enthusiast Tim") without citing specific indicators observed on the target property or verified competitor footprints.



---

### Agent 3: Brand Strategist

* **Role & Mandate:** Analyzes market positioning, visual/tonal identity, UVP (Unique Value Proposition) differentiation, and brand equity relative to discovered competitors.
* **Model Tier:** High-capacity language model specializing in brand architecture, messaging frameworks, and narrative structure.
* **Available Tools:**
* `extract_brand_voice_attributes(corpus_text)`
* `benchmark_differentiation(brand_features, competitor_features)`
* `uvp_clarity_evaluator(hero_copy, subheadings)`
* `category_positioning_matrix_plot(dimensions, competitors)`


* **Mode-Specific Behavior:**
* *Mode A (Personal Brand):* Pinpoints the individual's "Category of One" (e.g., "Full-Stack Engineer" vs. "Production-Grade AI Workflow Architect"). Identifies clichéd copy, weak proof-of-competence statements, and absence of clear personal authority.
* *Mode B (eCommerce):* Assesses brand narrative, perceived product quality, premium vs. commodity pricing justification, emotional resonance, and consistency across marketing touchpoints.


* **Input State:** `research_repository`, `strategic_artifacts.audience_analysis`.
* **Output State:** `strategic_artifacts.brand_positioning` (Core messaging hierarchy, differentiation matrix, value proposition critique, identity improvement playbook).
* **Active Guardrails:**
* Competitive Truth Standard: Claims of "unique capabilities" must be checked against the `competitor` dataset. If a competitor uses identical messaging, the agent must flag it as commoditized rather than differentiated.



---

### Agent 4: SEO and Content Strategist

* **Role & Mandate:** Audits search engine discoverability, information architecture, on-page optimization, content depth, and commercial intent mapping. Formulates high-ROI content and keyword initiatives.
* **Model Tier:** Analytical language model grounded in modern information retrieval, semantic search heuristics, and technical SEO standards.
* **Available Tools:**
* `analyze_onpage_elements(dom_snapshot)`
* `serp_intent_cluster_analyzer(keywords)`
* `content_gap_scanner(target_inventory, competitor_inventory)`
* `technical_seo_auditor(crawl_data)`


* **Mode-Specific Behavior:**
* *Mode A (Personal Brand):* Audits personal search visibility (knowledge graph presence, branded queries), project case study discoverability, topical authority in niche technical domains, and social indexing.
* *Mode B (eCommerce):* Audits collection page architectures, schema.org product markups, transactional keyword rankings, internal linking structures, canonicalization, and non-branded organic customer acquisition funnels.


* **Input State:** `research_repository.dom_snapshots`, `research_repository.competitors`, `strategic_artifacts.brand_positioning`.
* **Output State:** `strategic_artifacts.seo_and_content_plan` (Technical issue log, content gap inventory, keyword opportunity matrix, content editorial blueprint).
* **Active Guardrails:**
* No Keyword Stuffing: Recommended keywords must match verified search intent categories (Informational, Commercial, Transactional).
* Implementation Feasibility: Technical SEO recommendations must be scoped to standard CMS capabilities unless custom infrastructure is verified.



---

### Agent 5: Growth Strategist

* **Role & Mandate:** Functions as the synthesis engine. Consolidates diagnostic outputs from Agents 1 through 4 into high-leverage strategic initiatives formatted according to the engine's strict output contract.
* **Model Tier:** High-capacity strategic reasoning model specializing in product-led growth, conversion rate optimization (CRO), and operational prioritization.
* **Available Tools:**
* `calculate_ice_score(impact, confidence, ease)`
* `model_growth_projection(baseline_metric, expected_lift)`
* `build_standardized_recommendation(finding, evidence, implication, action, priority, metric)`


* **Mode-Specific Behavior:**
* *Mode A (Personal Brand):* Focuses on converting site visits into contract inquiries, high-value employment outreach, or speaking engagements. Prioritizes clear call-to-actions (CTAs), social proof placement, and interactive demos.
* *Mode B (eCommerce):* Focuses on average order value (AOV), conversion rate (CR), cart abandonment recovery, lifetime customer value (LTV), cross-sells, and checkout velocity.


* **Input State:** Complete aggregated output from Agents 1, 2, 3, and 4.
* **Output State:** `strategic_artifacts.synthesized_growth_initiatives` (Array of unvalidated initiatives following the Section 2 recommendation contract).
* **Active Guardrails:**
* Traceability Mandate: Every single initiative must directly incorporate findings from prior agents and explicitly cite an `evidence_id`. No disconnected suggestions allowed.



---

### Agent 6: Strategy Validator

* **Role & Mandate:** Serves as the independent quality assurance and adversarial verification gate. Scrutinizes every proposed recommendation for evidentiary support, internal consistency, operational practicality, and metric validity. Holds strict veto power over the final report.
* **Model Tier:** High-precision, zero-temperature critical audit model instructed to assume an adversarial posture.
* **Available Tools:**
* `verify_evidence_provenance(evidence_id, raw_repository)`
* `audit_logical_consistency(recommendation_object)`
* `validate_metric_feasibility(success_metric, business_type)`
* `issue_rejection_notice(rec_id, failure_reasons)`
* `issue_approval_certificate(recommendations_array)`


* **Operational Validation Protocol:**
1. **Provenance Check:** Does the cited `evidence_id` exist in the raw visual/DOM repository? If the evidence is generic, missing, or fabricated, reject immediately.
2. **Alignment Check:** Does the recommendation address the stated `business_goals` of the target profile?
3. **Feasibility Check:** Can a business in this mode reasonably implement this change without disproportionate capital expenditure?
4. **Metric Integrity Check:** Is the `success_metric` quantitatively verifiable via standard analytics platforms (e.g., Google Analytics 4, PostHog, Shopify Analytics)?


* **Output State:** `validation_report` updating every initiative's status from `Proposed` to `Approved` or returning `failed_needs_revision` with a corrective remediation log.

---

## 4. Execution Walkthrough by Mode

| Dimension | Mode A: Personal Portfolio Engine | Mode B: eCommerce Growth Engine |
| --- | --- | --- |
| **Primary Target Entity** | Freelancers, developers, researchers, creators | Online stores, DTC brands, digital product shops |
| **Primary Business Goal** | Authority, inbound inquiries, consulting leads, career offers | Conversions, reduced CAC, higher AOV, lower bounce rates |
| **Analyst Focus (Agent 1)** | Proof-of-work UX, GitHub/social links, bio, resume accessibility | Catalog structure, PDP layout, checkout funnel, reviews |
| **Audience Focus (Agent 2)** | Recruiters, enterprise clients, agency partners | High-intent shoppers, price-sensitive consumers, repeat buyers |
| **Brand Focus (Agent 3)** | Niche positioning, authority signals, personal differentiation | Product value props, trust badges, unboxing/aesthetic storytelling |
| **SEO Focus (Agent 4)** | Branded search, personal domain authority, niche technical terms | Product schema, category ranking, long-tail commercial queries |
| **Growth Focus (Agent 5)** | Lead form conversion, booking flows, social proof anchoring | Cart abandonment, cross-sells, free-shipping bars, exit offers |
| **Core KPI (Validator)** | Inbound conversion rate, contact form submissions | Conversion rate (CVR), Average Order Value (AOV), ROAS lift |

---

## 5. End-to-End Recommendation Examples

### Example: Mode A (Personal Portfolio Strategy)

```json
{
  "recommendation_id": "REC-A-01",
  "finding": "The hero section contains a generic headline ('Full-Stack Developer & Passionate Problem Solver') with no immediate proof of domain specialization or quantitative project impact.",
  "evidence": {
    "source_url": "https://alexchen.dev",
    "evidence_id": "ev_vnc_screen_004",
    "dataset_reference": "DOM node: h1.hero-title and section.hero-content",
    "observation_notes": "Above-the-fold content contains zero links to live production code, client outcomes, or primary architectural specializations."
  },
  "business_implication": "High bounce rates (estimated >65%) from high-value engineering leaders and enterprise clients seeking specialized distributed systems talent.",
  "recommendation": "Rewrite hero copy to define a clear Category of One: 'Distributed Systems & High-Throughput Data Infrastructure Engineer'. Position a live interactive terminal preview and a 2-sentence case study link above the fold.",
  "priority": {
    "impact": "High",
    "effort": "Low",
    "cost": "Low",
    "confidence": "High (95%)"
  },
  "success_metric": {
    "kpi": "Inbound Lead Contact Form Click-Through Rate",
    "baseline": "1.2% of sessions",
    "target": "4.5% of sessions"
  },
  "approval_status": "Approved"
}

```

### Example: Mode B (eCommerce Growth Strategy)

```json
{
  "recommendation_id": "REC-B-01",
  "finding": "Mobile PDP (Product Detail Page) hides customer reviews, sizing charts, and return policy information beneath three separate collapsed accordion menus requiring multiple manual taps.",
  "evidence": {
    "source_url": "https://nordicapparel.com/products/merino-wool-hoodie",
    "evidence_id": "ev_vnc_mobile_019",
    "dataset_reference": "VNC 390x844 Mobile Emulation #019 / div.pdp-accordion-group",
    "observation_notes": "User must scroll past 4 related product carousels to reach shipping details; sizing chart link fails to open in a modal on Safari iOS."
  },
  "business_implication": "Significant mobile checkout abandonment and elevated pre-purchase friction for first-time visitors on high-consideration apparel items ($180+ AOV).",
  "recommendation": "Implement a sticky 'Add to Bag' footer on mobile containing dynamic size selector, surface 4 key trust badges directly below the CTA, and convert the sizing guide into an overlay bottom-sheet.",
  "priority": {
    "impact": "High",
    "effort": "Medium",
    "cost": "Low",
    "confidence": "High (92%)"
  },
  "success_metric": {
    "kpi": "Mobile Add-to-Cart Conversion Rate",
    "baseline": "1.8%",
    "target": "3.1%"
  },
  "approval_status": "Approved"
}

```

---

## 6. Guardrail Execution Matrix

```
                        ┌─────────────────────────────────────┐
                        │   Agent Generates Recommendation    │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
             ┌───────────────────────────────────────────────────────────┐
             │            Guardrail 1: Provenance Verification           │
             │   Does evidence_id exist in VNC capture or DOM dataset?   │
             └─────────────┬───────────────────────────────┬─────────────┘
                          Yes                              No
                           │                               │
                           ▼                               ▼
       ┌───────────────────────────────────────┐   ┌─────────────────────────────┐
       │ Guardrail 2: Logical Consistency      │   │ Veto: Flag as Hallucination │
       │ Does action remediate the finding?    │   │ Return to Initiating Agent  │
       └──────┬─────────────────────────┬──────┘   └─────────────────────────────┘
             Yes                        No
              │                          │
              ▼                          ▼
       ┌────────────────────────┐   ┌─────────────────────────────┐
       │ Guardrail 3: Metric    │   │ Veto: Logic Disconnect      │
       │ Feasibility Check      │   │ Return to Initiating Agent  │
       └──────┬──────────┬──────┘   └─────────────────────────────┘
             Yes         No
              │           │
              ▼           ▼
       ┌───────────┐ ┌───────────────────────────────────────────┐
       │ APPROVED  │ │ Veto: Infeasible Metric; Force Correction │
       └───────────┘ └───────────────────────────────────────────┘

```

1. **Optimistic Execution with Concurrent Auditing:** Specialists generate analyses proactively against state snapshots. Guardrail checks execute asynchronously and flag exceptions before the Manager commits outputs to the master state.
2. **Evidence Strictness:** If an agent suggests an SEO change, a structural flaw, or a competitor gap without an operational DOM node or visual screenshot coordinate, the recommendation is dropped immediately.
3. **Loop Boundary Enforcement:** The Strategy Validator can cycle revisions up to a hard ceiling of 3 iterations. If an initiative fails verification three times, it is permanently discarded from the final strategy dossier to prevent infinite loop stalls.

## Project Architecture, Agent Access, Context Management, Memory, and RAG Integration

After completing the preceding work, create a comprehensive project hierarchy based on the provided context file and the existing VNC Browser computer hierarchy. The objective is to map the entire Universal AI Brand Strategy Engine accurately, including its components, dependencies, internal tools, agent responsibilities, permissions, and execution workflows.

The VNC Browser computer must be represented as an **internal component of the engine**, not as an external-facing system. Authorized agents should be able to access and use its capabilities directly through the appropriate tool interfaces. Map the relationship between the browser infrastructure, specialist agents, manager agent, and other engine components according to their actual responsibilities and permissions.

### 1. Project Hierarchy and Component Mapping

Create a clear, logically structured hierarchy of the entire project. Map the existing architecture accurately, identifying the purpose, relationships, dependencies, and access permissions of each component. Distinguish internal infrastructure from external integrations and ensure that each agent has access to the tools and resources required for its assigned responsibilities.

### 2. Context Window and Context Management

Improve the engine's context-management capabilities by providing a larger effective context window wherever supported by the selected model and runtime. Ensure that agents can access sufficient relevant information throughout complex, multi-stage research and strategy-development workflows without unnecessarily losing important findings, instructions, or business context.

The design should account for context-window limits, relevant-context retrieval, conversation and task summaries, and the transfer of essential findings between agents.

### 3. Short-Term and Long-Term Memory

Implement distinct short-term and long-term memory capabilities according to their intended purposes.

- **Short-term memory:** Maintains the current task's working context, active research findings, intermediate results, execution state, and information required for coordination between agents.
- **Long-term memory:** Preserves relevant information across tasks and sessions, including persistent business context, previous research, user-provided preferences, historical findings, and strategy-performance records where appropriate.

Define how information is stored, retrieved, updated, and transferred between these memory layers. Ensure that memory access respects data isolation, relevance, permissions, and the requirements of each individual task.

### 4. User-Provided Documents and RAG Knowledge Base

Implement a Retrieval-Augmented Generation (RAG) knowledge base that allows users to upload their own documents and make the information available to authorized agents.

The system should ingest supported documents, extract their contents, divide them into appropriate chunks, generate embeddings, and store the resulting representations in a vector database or equivalent retrieval system. It should preserve source metadata and document references so that retrieved information can be traced to its origin.

Each agent must have the authority to retrieve relevant information from the RAG knowledge base within its assigned permissions and responsibilities. Agents should use the retrieved information to supplement website research, business context, strategic analysis, and other task-specific requirements.

### 5. Evidence Assurance and Existing Validation

The RAG knowledge base must support **evidence assurance**, helping agents establish whether their analysis and recommendations have sufficient relevant information, supporting documentation, and contextual grounding.

This capability must remain distinct from the existing Strategy Validator agent. The purpose of RAG-based assurance is to help each agent retrieve supporting knowledge, identify relevant documentation, recognize information gaps, and ground its findings in available sources—not to duplicate the validator's independent assessment of strategy quality.

When relevant evidence is unavailable, contradictory, or insufficient, agents must explicitly record the limitation rather than fabricate supporting information. Retrieved documents must retain source references, and their contents must be treated as information to analyze rather than instructions that override the engine's system policies or tool permissions.

### 6. Integration Requirements

Integrate the project hierarchy, VNC Browser infrastructure, agent permissions, expanded context management, short-term and long-term memory, and user-provided RAG knowledge base into one coherent architecture.

Map the data flow and dependencies between these components, showing how agents retrieve information, share findings, preserve relevant context, and use supporting evidence throughout the research-to-strategy workflow.

Base the implementation on the existing project structure, the provided context file, the actual VNC Browser hierarchy, and relevant technical research. Preserve existing working functionality, identify missing components or architectural gaps, and ensure that all proposed changes align with the engine's established multi-agent design.