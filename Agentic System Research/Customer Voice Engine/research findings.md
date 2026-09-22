# Customer Voice Engine (`W_VOICE`) — Implementation Specification

**Research cut-off:** 22 September 2026
**Repository inspected:** live `Maimoon-github/enterprise_os` `main` plus the six supplied architecture/tree files.

## 1. Architecture decision

Keep **exactly six Voice specialists**. No seventh agent is justified.

```text
Intelligence Engine
      │ bounded Voice TaskGrant + IE-mediated feedback/context
      ▼
W_VOICE                         own LLM; NO sandbox capability
      │
      ▼
VOICE-DISCOVERY                 fresh AIO
      │ normalize/de-identify/dedupe/capture
      ▼
 ┌──────────────┬───────────────┬──────────────┐
 ▼              ▼               ▼
VOICE-THEMES  VOICE-SENTIMENT  VOICE-NEEDS
fresh AIO     fresh AIO        fresh AIO
 └──────────────┴───────────────┴──────────────┘
                       │ immutable join
                       ▼
                 VOICE-JOURNEY
                    fresh AIO
                       │
                       ▼
                    VOICE-QA
          fresh read-only AIO; evaluator only
                       │
              PASS / REVISE / BLOCK
                       ▼
                    W_VOICE
              sanitized synthesis only
                       │
                 EvidenceEnvelope
                       ▼
                       IE
         persistence / CTS / HITL / outbound
```

`DISCOVERY → [THEMES || SENTIMENT || NEEDS] → JOURNEY → QA` is a **fixed workflow**, not LLM-selected orchestration. Parallel execution of the middle three is permitted because each consumes the same immutable sanitized corpus and has no sibling communication.

This task supersedes the uploaded architecture's current direct `W_VOICE ↔ S_PARSE` relationship and the statement that all seven top-level workers have sandbox access.

---

## 2. Research findings

ISO 10002:2018 supports systematic handling, analysis, and evaluation of complaints to improve products, services, and customer service. ISO confirms the 2018 edition remains current after its 2023 review. ISO 10004:2018 similarly defines processes for monitoring and measuring customer satisfaction. These support treating Voice as an evidence/research engine rather than simply a sentiment parser. ([ISO][1])

Survey evidence needs methodology attached to it. AAPOR's current standards distinguish coverage, measurement, and nonresponse error and explicitly state that response rate alone does not determine nonresponse error. Its 2026 ethics/transparency guidance calls for disclosure of collection mode, dates, sample design, sample size, weighting, and precision methodology. ([AAPOR][2])

Semantic embeddings are valid inputs to text clustering; Sentence-Transformers documents k-means, agglomerative, similarity-threshold, and topic-modeling uses. BERTopic uses embedding clustering but explicitly notes that no single clustering model is universally best. Cluster parameters therefore require dataset-specific evaluation rather than hard-coded confidence. Silhouette analysis can be one internal separation diagnostic, not proof that topic labels are semantically correct. ([SentenceTransformers][3])

Aspect-level sentiment is a well-established analysis task rather than only whole-document positive/negative classification; SemEval's ABSA benchmark formalized aspect extraction and aspect polarity evaluation. ([ACL Anthology][4])

NIST IR 8053 establishes the important privacy boundary: de-identification can reduce privacy risk but does **not** eliminate re-identification risk, including for free-form text. Voice outputs therefore must be described as de-identified/pseudonymized, not guaranteed anonymous. ([NIST][5])

AIO exposes browser, shell, file, code, Jupyter, and related execution APIs, but its documented quick start still uses `seccomp=unconfined`. Its own multi-sandbox example treats different sandboxes as separate containers/endpoints. Therefore a task-scoped workspace on one cached AIO service is **not equivalent to a fresh sandbox runtime**. ([AIO Sandbox][6])

---

## 3. Verified repository findings

### Confirmed implementation gaps

Live source inspection found:

* `CustomerVoiceAgent.capability = SandboxCapability.PARSE`; therefore W_VOICE currently has direct sandbox authority.
* `BoundedWorkerAgent` already supports `capability=None`, so **no base-agent redesign is needed**.
* `CustomerVoiceAgent._normalize_context()` invents `"Customer reviews and feedback."` when evidence is absent. **Remove this fallback; missing feedback must remain missing.**
* Current `interpret_result()` manufactures confidence intervals from polarity magnitude/item count. They are not statistically calibrated confidence intervals.
* `capabilities.py` still registers direct `W_VOICE → S_PARSE`.
* `main.py` asserts capability ownership for W_VOICE and injects the shared generic LLM rather than seven distinct Voice identities.
* `SandboxClient` provides remote AIO implementations for `S_ALLOC` and `S_VAL`, but **not `S_PARSE`**.
* Without a configured remote endpoint, `S_PARSE` can reach in-process `dispatch_micro_tool()`. Production Voice therefore lacks the required fail-closed AIO guarantee.
* The remote sandbox client is cached. Unique `/workspace/<execution_id>` paths do not prove fresh AIO container/microVM instances.
* Current `execute_s_parse()` is based on small hand-built word lists, regex PII detection, keyword objections, heuristic confidence, and:
  `trend = increasing if frequency >= 3`.
  Frequency alone cannot establish a trend.
* Current S_PARSE skill script contains its own default feedback sentence.
* Existing Voice contracts lack first-class evidence spans, survey-method metadata, clustering diagnostics, aspect-level sentiment, coverage limitations, and explicit population-inference controls.
* Existing integration/unit tests explicitly assume direct `W_VOICE → S_PARSE` access and therefore must change.

### Already reusable

The repository already has:

* `specialist_id`, `stage_attempt_id`, allowed tools/operations and egress binding in sandbox mandates;
* `SandboxIdentity` with tenant/engine/specialist/task/step/attempt identity;
* deny-all network policy, ephemeral workspaces, resource ceilings and output sealing;
* independent `LlmClient(agent_identity=...)`;
* existing PROV/persistence/HITL infrastructure;
* a compatibility wrapper at `app/agents/customer_voice.py`.

These should be extended, not duplicated.

---

## 4. Verified vs inferred decisions

| Decision                                   | Classification                  | Result                                          |
| ------------------------------------------ | ------------------------------- | ----------------------------------------------- |
| IE-exclusive enterprise/RAG access         | Project-defined                 | Preserve                                        |
| `W_VOICE` has zero sandbox authority       | Project override                | Required                                        |
| Six named Voice specialists                | Project requirement + justified | Required; add no seventh                        |
| Independent LLM identities                 | Project requirement             | 7 clients: parent + 6 specialists               |
| Fresh AIO per specialist attempt           | Project requirement             | Required; current runtime does not yet prove it |
| Discovery-only public research             | Project requirement             | `ALLOWLIST`; all others `DENY_ALL`              |
| Fixed Voice DAG                            | Engineering inference           | Adopt                                           |
| Parallel Themes/Sentiment/Needs            | Engineering inference           | Allowed only over immutable corpus              |
| Embeddings/clustering as tools             | Research-backed                 | Yes; not separate agents                        |
| Aspect sentiment                           | Research-backed                 | Replace whole-document-only design              |
| Population prevalence from reviews/tickets | Unsupported                     | Prohibit                                        |
| Trend from frequency                       | Unsupported current behavior    | Remove                                          |
| Regex-only de-identification guarantee     | Unsupported                     | Treat as one detector, not proof of anonymity   |
| Voice-specific DB/RAG/MCP/state machine    | Unnecessary                     | Do not add                                      |

---

## 5. Specialist responsibility and access

| Component           | Responsibility                                                                          | Main sandbox capabilities                         | Network                                                 |
| ------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------- |
| **W_VOICE**         | scope validation, fixed orchestration, sanitized synthesis                              | **None**                                          | None                                                    |
| **VOICE-DISCOVERY** | approved own-brand source acquisition; normalization; language ID; PII handling; dedupe | browser only when granted; parser/redactor/dedupe | `ALLOWLIST` when explicitly granted; otherwise disabled |
| **VOICE-THEMES**    | embeddings, clusters, themes, observed share, topic change analysis                     | embedding/clustering/statistics                   | `DENY_ALL`                                              |
| **VOICE-SENTIMENT** | aspect sentiment/emotion, span grounding, model uncertainty                             | ABSA/classification validators                    | `DENY_ALL`                                              |
| **VOICE-NEEDS**     | needs, pains, objections, desired outcomes, customer vocabulary                         | extraction/grouping/evidence validators           | `DENY_ALL`                                              |
| **VOICE-JOURNEY**   | descriptive channel/touchpoint/segment/time comparisons                                 | aggregation/statistics                            | `DENY_ALL`                                              |
| **VOICE-QA**        | independent privacy, trace, bias, contradiction, coverage and schema checks             | read-only validators                              | `DENY_ALL`                                              |

`VOICE-DISCOVERY` must only retrieve sources explicitly listed in an IE-issued own-brand source/domain grant. Competitor URLs or competitor-research objectives are rejected and remain `W_COMP` scope.

---

## 6. LLM boundary

Create these identities:

```text
W_VOICE
VOICE-DISCOVERY
VOICE-THEMES
VOICE-SENTIMENT
VOICE-NEEDS
VOICE-JOURNEY
VOICE-QA
```

Each receives a distinct `LlmClient` instance, profile ID/digest, system contract, context window, token/cost budget, fallback policy and provenance identity. They may resolve to the same physical provider/model.

`profiles.py` should model at least:

```text
profile_id
profile_version
specialist_id
model_id / model_revision
reasoning_mode
prompt_version
output_schema_version
context_limit
max_output_tokens
max_attempts
budget_limit
data_classification_allowlist
allowed_operations
allowed_tools
network_policy
endpoint_policy_ref
fallback_profile_ids
profile_digest
```

Provider credentials remain in trusted host transport. No provider key is placed in an AIO filesystem, prompt, task JSON, or specialist output. AIO's own documentation explicitly supports the pattern where the agent/orchestration and credentials stay outside while sandbox capabilities are called remotely. ([AIO Sandbox][7])

**Raw customer text must not be passed to the W_VOICE parent LLM.** The parent handles raw input references/metadata deterministically; Discovery performs the first de-identification pass. Downstream LLMs receive only policy-permitted sanitized data.

---

## 7. Required Customer Voice contracts

Add `backend/app/schemas/customer_voice.py` and keep legacy `agent_contracts.py` types as compatibility types unless source-level integration proves otherwise.

Core types:

```text
CustomerVoiceTask
VoiceSpecialistTask
VoiceSpecialistResult
FeedbackRecord
SurveyMethodology
EvidenceSpan
TopicFinding
AspectSentimentFinding
NeedObjectionFinding
JourneyComparison
VoiceQAReport
CustomerVoicePayload
```

Every normalized record should preserve:

```text
opaque_record_id
record_hash
source_ref
source_type
channel / touchpoint
timestamp
locale
product_ref
explicit_segment_refs
sanitized_text
redaction_summary
dedupe_group
survey_methodology_ref
provenance_ref
```

`SurveyMethodology` should carry, when supplied:

```text
population_definition
sampling_method
sampling_frame
collection_mode
fieldwork_dates
questionnaire_version
invited_or_eligible_n
completed_n
response_rate
response_rate_definition
weighting_method
weight_variables
design_effect
precision_method
```

Unknown values remain `null + reason`.

### Evidence grounding

Every material Voice finding requires one or more `EvidenceSpan` references containing:

```text
record_id
sanitized_text_hash
start_offset
end_offset
span_hash
source_ref
```

Do not let an LLM-generated quote become evidence unless it resolves to the exact sanitized record span.

---

## 8. Analysis rules

### Themes

Store separately:

* `observed_count`;
* `observed_share_of_analyzed_corpus`;
* optional properly weighted survey estimate;
* outlier/unassigned rate;
* cluster algorithm/version/parameters;
* embedding model/version;
* cluster-quality diagnostics;
* representative evidence spans.

Never rename observed review/ticket frequency as population prevalence.

A theme trend becomes `increasing/decreasing` only when comparable time windows exist with sufficient records and a declared change method. Otherwise return `not_assessed`.

### Sentiment

Use aspect-level outputs:

```text
aspect
polarity
model_score
score_is_calibrated
emotion[]        optional
evidence_spans[]
model_version
locale
uncertainty_reason
```

A raw model score must not be called a probability unless calibration has actually been evaluated.

### Journey

Comparisons remain descriptive:

> channel A contained more observed price objections than channel B during the supplied interval.

Do **not** convert that into:

> channel A caused more price objections.

Segments come from explicit supplied metadata. Do not infer race, health status, religion, political affiliation, sexual orientation, or other sensitive demographics from feedback text.

---

## 9. Privacy and bias controls

Use a two-layer identifier model:

* content hash → integrity/provenance;
* opaque or HMAC-based pseudonymous record ID → cross-step linkage.

Do not use predictable plain SHA-256 of a low-entropy ticket ID as the sole pseudonymization boundary.

Discovery performs PII detection/redaction before downstream analysis. QA performs an independent residual-PII scan. A privacy failure is `BLOCK`, not a warning.

NIST's findings mean the system must retain a `reidentification_risk`/privacy-limitation field even after de-identification. ([NIST][5])

For surveys, distinguish probability, non-probability and unknown sampling. AAPOR states response rate by itself is insufficient to establish nonresponse bias; reporting should retain sample construction, mode, weighting and precision assumptions. ([AAPOR][2])

Tickets, unsolicited reviews and ordinary support logs default to:

```text
inference_scope = observed_feedback_only
population_representativeness = not_established
```

---

## 10. Provenance

Reuse the existing Enterprise OS provenance service.

W3C PROV mapping:

```text
Entity:
  IE task/context snapshot
  raw source snapshot
  sanitized feedback corpus
  embedding/cluster artifact
  specialist result
  QA report
  final CustomerVoicePayload

Activity:
  source acquisition
  normalization/redaction
  deduplication
  embedding
  clustering
  sentiment inference
  needs extraction
  journey aggregation
  QA
  W_VOICE synthesis

Agent:
  IE
  W_VOICE
  each VOICE-* specialist
  model identity
  sandbox controller
  human reviewer
```

Use `prov:used`, `prov:wasGeneratedBy`, `prov:wasDerivedFrom`, `prov:wasAssociatedWith`, and `prov:actedOnBehalfOf`. These constructs are directly defined by PROV-O. ([W3C][8])

PROV expresses lineage; existing Enterprise OS hashing/signing/persistence remains responsible for immutability.

---

## 11. Exact repository delta

```text
backend/app/agents/
├── customer_voice.py                              REUSE
└── customer_voice_engine/
    ├── __init__.py                                REUSE
    ├── customer_voice.py                          MODIFY
    ├── profiles.py                                ADD
    └── subagents/
        ├── __init__.py                            ADD
        ├── discovery.py                           ADD
        ├── themes.py                              ADD
        ├── sentiment.py                           ADD
        ├── needs_objections.py                    ADD
        ├── journey.py                             ADD
        └── quality.py                             ADD

backend/app/schemas/
├── customer_voice.py                              ADD
└── sandbox.py                                     REUSE / CONDITIONAL

backend/app/integrations/sandbox/
├── s_parse_core.py                                ADD
├── micro_tools.py                                 MODIFY - MINIMAL
├── capabilities.py                                MODIFY
├── client.py                                      MODIFY
└── sandbox_policy.py                              REUSE / CONDITIONAL

backend/app/
└── main.py                                        MODIFY

sandbox/docker/hardened/skills/s-parse/
├── SKILL.md                                       MODIFY
└── scripts/run.py                                 MODIFY

backend/tests/customer_voice_engine/
├── __init__.py                                    ADD
├── test_contracts.py                              ADD
├── test_profiles_and_llm_isolation.py             ADD
├── test_analysis.py                               ADD
├── test_privacy_bias.py                           ADD
└── test_provenance.py                             ADD

backend/tests/unit/
├── test_customer_voice_verification.py            MODIFY
└── test_llm_wiring_verification.py                MODIFY

backend/tests/integration/
├── test_customer_voice_integration.py             MODIFY
├── test_worker_sandbox_boundary.py                MODIFY
├── test_model_a_data_access.py                    EXTEND
└── test_security_boundaries_negative.py           EXTEND
```

`schemas/sandbox.py` remains unchanged unless implementation proves that existing `specialist_id`, attempt identity, expected-output schema and provenance fields cannot carry Voice contracts.

`sandbox_policy.py` already provides generic identity, fresh-workspace, credential, resource and sealing primitives. Modify it only if connecting those contracts to **actual fresh remote AIO lifecycle provisioning** requires a generic cross-engine lease or provisioner.

---

## 12. Minimum code changes

### `customer_voice.py`

Set:

```python
capability = None
```

Override the generic sandbox-running `run()` path. W_VOICE must:

1. validate grant/tenant/scope;
2. reject missing Voice evidence instead of manufacturing fallback feedback;
3. freeze a `CustomerVoiceTask`;
4. execute the static Voice DAG;
5. expose raw feedback only to Discovery's bounded preprocessing path;
6. synthesize only sanitized, typed specialist results;
7. preserve contradictions/unknowns;
8. return `EvidenceEnvelope`.

It never calls `SandboxClient.invoke()` itself.

### `profiles.py`

Implement immutable profile registration, digest validation, delegated-scope attenuation, independent LLM construction and common specialist mandate creation.

### `capabilities.py`

Remove direct coordinator authority:

```text
W_VOICE → S_PARSE             REMOVE
VOICE-* → S_PARSE             ADD
```

Add specialist-specific allowlists.

`VOICE-DISCOVERY` gets allowlisted network capability only with a valid task/tenant/specialist/domain-bound egress grant.

### `s_parse_core.py`

Move Voice deterministic operations out of the large generic micro-tool module:

```text
normalize_records
detect_language
redact_pii
deduplicate
embed_feedback
cluster_feedback
score_aspect_sentiment
classify_ticket
aggregate_findings
compute_descriptive_change
validate_evidence_spans
validate_voice_bundle
```

Models and algorithms must be version-pinned. If an approved model/dependency is unavailable, return `not_assessed/configuration_gap`; never silently fall back to the current toy lexicons.

`micro_tools.py` becomes a compatibility router to `s_parse_core`, not a second Voice implementation.

### `client.py`

Add true remote `S_PARSE` execution using the mounted:

```text
/home/gem/skills/s-parse/scripts/run.py
```

Production Voice execution must:

```text
AIO unavailable
→ FAIL CLOSED
→ no dispatch_micro_tool() backend fallback
```

Discovery browser acquisition must pass the existing egress validator before retrieval.

Most importantly, bind:

```text
SandboxIdentity
→ fresh remote runtime
→ execute
→ seal
→ destroy
```

for **each specialist attempt**.

A unique workspace on the current cached remote AIO client is insufficient. AIO's own multi-sandbox model uses separate containers/endpoints for isolation. ([AIO Sandbox][7])

### `main.py`

Construct seven independent Voice clients and the six specialists:

```text
w_voice_llm
voice_discovery_llm
voice_themes_llm
voice_sentiment_llm
voice_needs_llm
voice_journey_llm
voice_qa_llm
```

Special-case W_VOICE just as the composition root already does for zero-sandbox Creative coordination. Close all clients during shutdown.

No `llm/client.py` modification is currently justified.

---

## 13. Validation and release tests

Acceptance must prove at least:

| Test                                                     | Required result                          |
| -------------------------------------------------------- | ---------------------------------------- |
| W_VOICE invokes sandbox directly                         | **DENIED**                               |
| `get_capability_for_role(W_VOICE)` grants S_PARSE        | **must no longer occur**                 |
| Unknown `VOICE-*` specialist                             | **DENIED**                               |
| Six specialists share one LLM object                     | test fails                               |
| Six independent clients/identities                       | passes                                   |
| Missing customer evidence                                | explicit incomplete/needs-context result |
| Missing evidence becomes default feedback                | test fails                               |
| Discovery approved own-brand domain                      | allowed                                  |
| Discovery competitor/unapproved/private domain           | **DENIED**                               |
| Themes/Sentiment/Needs/Journey/QA request web            | **DENIED**                               |
| Discovery egress grant reused by sibling                 | **DENIED**                               |
| Cross-tenant record/result                               | **DENIED**                               |
| Specialist accesses RAG/DB/CMS/memory/MCP                | **DENIED**                               |
| Specialist accesses sibling workspace/process            | **DENIED**                               |
| Same AIO runtime reused across attempts                  | test fails                               |
| Production AIO unavailable                               | **fails closed**                         |
| Regex redaction misses synthetic PII                     | QA blocks candidate                      |
| Raw PII reaches downstream LLM fixture                   | test fails                               |
| Finding lacks evidence span                              | QA `BLOCK/REVISE`                        |
| Topic has no diagnostics/model version                   | validation fails                         |
| Three records in one theme automatically = “increasing”  | test fails                               |
| Organic-review percentage labelled population prevalence | validation fails                         |
| Survey output drops mode/sample/weight metadata          | validation fails                         |
| Unsupported locale/model                                 | `not_assessed`, never fabricated         |
| QA changes candidate hash                                | test fails                               |
| QA before/after hashes identical                         | passes                                   |
| Missing specialist/model/tool provenance                 | validation fails                         |
| Existing HITL/outbound gate bypassed                     | existing denial tests remain valid       |

Tests for clustering should use frozen synthetic corpora and assert traceability/stability rather than specific generated topic names. Sentence clustering is supported by embedding-based tooling, but the number/quality of clusters remains model- and parameter-dependent. ([SentenceTransformers][3])

---

## 14. Unresolved gaps / release blockers

1. **Fresh remote AIO lifecycle is not currently demonstrated.** The live client caches one AIO connection. Before acceptance, the deployed controller must prove separate runtime/container identities per specialist attempt, not merely directories.

2. **Voice model stack is not established.** Verify installed dependencies before selecting embedding, ABSA, language-ID, PII, clustering or statistical packages. Sentence-Transformers/BERTopic are validated architectural references, **not automatically required dependencies**.

3. **No calibrated Voice evaluation corpus is supplied.** Define representative labeled fixtures by supported language/domain before setting production sentiment/topic-quality thresholds.

4. **Supported locales are unspecified.** Unsupported language must remain `not_assessed`; translation must not occur silently.

5. **Discovery egress policy is unspecified.** IE/governance must define approved own-brand domains/marketplace listing sources and version the allowlist.

6. **Survey methodology quality cannot be reconstructed from response text.** If IE does not supply sample frame, weighting, mode, field dates and related metadata, population inference stays unavailable.

7. **PII retention/re-identification policy remains governance-owned.** Define which raw source artifacts may be retained, how long, and which reviewer roles may resolve opaque source references.

8. **Architecture documentation is stale by design after this decision.** Remove the direct `W_VOICE ↔ S_PARSE` flowchart edge and replace it with `W_VOICE → VOICE-* → sandbox`; also revise the “all seven workers have direct sandbox access” assertion.

### Final resolved architecture

```text
W_VOICE
  own LLM                 YES
  direct sandbox          NO
  direct enterprise data  NO — IE-mediated only
  persistence/HITL        NO
  outbound/customer contact NO

VOICE-* specialists
  count                    SIX
  own LLM identity         YES
  fresh AIO attempt        YES
  sibling RPC              NO
  direct enterprise access NO
  outbound credentials     NO

S_PARSE
  monolithic sentiment agent   NO
  bounded Voice tool runtime   YES
  production host fallback     NO
```

The result preserves Model A while replacing the current monolithic parser with a research-capable Voice evidence pipeline: **raw feedback is bounded and de-identified first, analyses remain source-traceable, observed frequency is kept separate from population inference, QA is independent and non-mutating, and W_VOICE coordinates without acquiring execution authority.**

[1]: https://www.iso.org/standard/71580.html?utm_source=chatgpt.com "ISO 10002:2018 - Quality management — Customer satisfaction — Guidelines for complaints handling in organizations"
[2]: https://aapor.org/standards-and-ethics/standard-definitions/?utm_source=chatgpt.com "Standard Definitions - AAPOR"
[3]: https://sbert.net/examples/sentence_transformer/applications/clustering/README.html?utm_source=chatgpt.com "Clustering — Sentence Transformers documentation"
[4]: https://aclanthology.org/S14-2004/?utm_source=chatgpt.com "SemEval-2014 Task 4: Aspect Based Sentiment Analysis - ACL Anthology"
[5]: https://www.nist.gov/publications/de-identification-personal-information?utm_source=chatgpt.com "De-Identification of Personal Information | NIST"
[6]: https://sandbox.agent-infra.com/guide/start/quick-start?utm_source=chatgpt.com "Quick Start - AIO Sandbox"
[7]: https://sandbox.agent-infra.com/guide/start/agent-sandbox?utm_source=chatgpt.com "Agent Call Sandbox vs In Sandbox - AIO Sandbox"
[8]: https://www.w3.org/TR/2013/PR-prov-o-20130312/?utm_source=chatgpt.com "PROV-O: The PROV Ontology"
