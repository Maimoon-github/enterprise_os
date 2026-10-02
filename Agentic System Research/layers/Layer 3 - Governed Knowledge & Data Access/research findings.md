**1. Validated Layer 3 architecture decisions**

**Review status:** The six attachments establish the architecture, module locations, and intended responsibilities. They do **not** include Python implementations, dependency-file contents, database definitions, or executable tests. The architecture below is validated against those attachments and official documentation; existing implementation correctness remains unverified.

Evidence labels used below:

* **[S] Source-backed:** supplied architecture, hierarchy, flowchart, file trees, or explicit requirements.
* **[V] Externally validated:** current official technical documentation.
* **[D] Design decision:** a proposed implementation choice, subject to checking existing code.

Source references: **Architecture** means *Final-Level Full Architecture*, **Hierarchy** means *Backend Hierarchy*, **Flowchart** means the decoded Draw.io attachment, and **Trees** means the three supplied file trees.

| ID | Decision                                                                                                                                                                                                                                                  | Basis                                                                        |
| -- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| D1 | Preserve `IE → rag_query_dispatch → Agentic RAG → MCP Data Boundary → repositories/CMS adapter → Layer 4`. Return validated evidence along the reverse path.                                                                                              | **[S]** Architecture §§2–4; Hierarchy §2.                                    |
| D2 | Only authenticated IE execution may invoke RAG. Worker requests retain their originating identity and attenuated scope when IE mediates them. An IE service identity must not automatically grant its full privileges to a worker-originated request.     | **[S/D]** Model A and monotonic attenuation.                                 |
| D3 | Use deterministic RAG services. Retrieval, validation, fusion, ingestion, and evidence packaging do not require additional autonomous agents.                                                                                                             | **[S/D]** Existing service layout and task constraints.                      |
| D4 | RAG owns retrieval and ingestion logic. The gateway owns capability enforcement and adapter dispatch. Repositories own database operations. Existing domain services retain CTS transitions, memory-promotion decisions, and outbound approval ownership. | **[S]** Hierarchy §2.                                                        |
| D5 | Layer 3 receives no sandbox client, sandbox credentials, execution capability, or dependency on sandbox internals. Keep `W_STRAT` and other worker engines unchanged.                                                                                     | **[S]** Architecture component table; explicit constraints.                  |
| D6 | Apply authorization before storage access, enforce tenant isolation within storage, and revalidate returned records before evidence release. A namespace, UUID, hash, or URI is an identifier—not authorization.                                          | **[S/D]** Tenant partitioning, document security, and artifact requirements. |
| D7 | Support governed CMS reads and staging operations. Live publishing, deployment, and production schema changes remain behind the existing outbound/HITL boundary.                                                                                          | **[S]** Architecture data-flow table.                                        |
| D8 | Reuse existing provenance schemas, service, repository, and audit validator. RAG emits lineage through these components without implementing another ledger.                                                                                              | **[S]** Architecture Layer 9; Trees.                                         |

**Authorization and storage contract**

**[D]** Reuse the existing governance contract to carry a trusted authorization context containing the logical equivalents of:

`authenticated_principal`, `originating_principal`, `delegation_chain`, `tenant_id`, permitted brand/resource scopes, allowed operation, task/grant reference, policy version, expiry, and correlation ID.

The actual field names should follow existing schemas. Build this context from verified credentials and policy decisions; never accept a tool argument such as `caller="IE"` as proof of identity.

The effective permission is the intersection of the authenticated principal’s authority, the originating grant, resource policy, and requested operation. Missing scope, invalid delegation, expired grants, or attempted widening must deny access.

For PostgreSQL-backed tenant data:

* Enable RLS with policies covering reads and writes. Use `USING` for eligible existing rows and `WITH CHECK` for inserted or changed rows.
* Use an application role without superuser or `BYPASSRLS` privileges. Separate schema ownership from application access; apply `FORCE ROW LEVEL SECURITY` where owner access could otherwise bypass policies.
* Do not grant runtime DDL or `TRUNCATE` privileges. Review overlapping policies because permissive policies combine with OR. **[V]** PostgreSQL documents these enforcement rules and bypass conditions. ([postgresql.org][1])

**[D]** Set any tenant session context through the trusted database adapter inside each transaction. Missing context must fail closed, and pooled connections must not retain another request’s scope. PostgreSQL supports transaction-local settings through `set_config(..., true)`. Such a setting is an enforcement input, not an independent authentication mechanism. ([postgresql.org][2])

Bind query values through the installed driver. Keep table names, sort expressions, operations, and resource types in server-owned allowlists. No arbitrary SQL capability is required. PostgreSQL’s parameterized execution separates values from SQL command text. ([postgresql.org][3])

**Retrieval contract**

**[V]** Use the accurate description **“pgvector semantic search + PostgreSQL full-text search”** unless code and dependencies prove a genuine BM25 implementation. PostgreSQL’s `ts_rank` and `ts_rank_cd` are its full-text ranking functions; pgvector explicitly documents combining vector search with PostgreSQL FTS and using reciprocal rank fusion. ([postgresql.org][4])

**[D]** Implement retrieval as follows:

1. Validate the request and establish its authorized tenant, brands, collections, document visibility, freshness policy, and result limits.
2. Obtain the query embedding through the existing provider boundary.
3. Request vector and lexical candidates through the gateway. Both branches must use the same authorized corpus and compatible source/index versions.
4. Fuse ranked lists in `hybrid_retriever.py`:

   $$
   RRF(d)=\sum_{b\in\{\text{vector, lexical}\}}\frac{w_b}{c+\operatorname{rank}_b(d)}
   $$

   Ranks start at one; an absent document contributes zero. Use positive, versioned configuration for \(c\) and weights. Equal weights and \(c=60\) are a proposed starting configuration, not a measured optimum.
5. Deduplicate by tenant, source revision, and chunk identity. Resolve equal scores with a stable chunk identifier.
6. Validate freshness, schema, authorization, and citation integrity before returning bounded evidence.

Determinism applies to fusion over identical candidate lists and configuration. Approximate vector retrieval does not guarantee identical candidates across index changes.

Filtered approximate searches can return fewer candidates. Test scoped recall and use bounded oversampling, supported iterative scans, or a scoped exact-search fallback where needed. Never broaden authorization to fill the result count. **[V]** pgvector documents filtering and iterative-scan behavior. ([GitHub][5])

**Ingestion and index lifecycle**

**[D]** Keep ingestion orchestration in the existing controller:

* Every ingestion operation requires an IE-authorized write grant. Database changes or ingestion events must enter through an IE-authorized dispatch path.
* Validate source ownership, schema, supported format, immutable source revision, and content hash before indexing.
* Use deterministic normalization and chunking with recorded versions.
* Record embedding provider/model revision, vector dimensions, distance metric, and index generation. Reject incompatible dimensions or mixed embedding spaces.
* Scope idempotency keys by tenant and operation. Store a request digest: the same key and digest returns the prior receipt; the same key with different content produces a conflict.
* Use database uniqueness and concurrency control, not only an application-level “already exists” check.
* Build replacement generations separately. Activate a complete generation atomically; retain the previous valid generation until replacement succeeds.
* Propagate source deletion, access revocation, and tombstones into retrieval eligibility. Re-embedding must not overwrite the historical lineage of earlier vectors.

Compute embeddings outside long-held database transactions. Recheck authorization and source revision before committing.

For co-located data, commit ingestion records, chunk/index state, idempotency receipt, and provenance in one unit of work. For external CMS or artifact systems, use the project’s existing durable retry/reconciliation mechanism. Do not claim a PostgreSQL transaction makes remote writes atomic.

**Evidence, freshness, and provenance contracts**

**[D]** Extend existing contracts only where fields are missing:

| Contract                     | Required logical contents                                                                                                                                                                                                             |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Retrieval request            | Query, permitted source filters, requested result count, freshness requirement, schema version, task/grant reference. Trusted authorization is supplied separately.                                                                   |
| Evidence chunk               | Tenant/brand scope, source ID and revision, chunk ID, source locator, excerpt, excerpt/source hashes, offsets or structured field path, source timestamps, freshness assessment, embedding/index version, retrieval ranks and scores. |
| Evidence envelope            | Request/task ID, policy version, retrieval configuration, authorized evidence list, provenance references, retrieval time, and explicit `complete`, `partial`, or `no_evidence` status.                                               |
| Ingestion receipt            | Tenant, idempotency reference, source revision/hash, accepted record/chunk references, index generation/status, provenance references, and completion/failure state.                                                                  |
| Data-boundary request/result | Allowlisted operation and resource type, typed parameters, bounded pagination, concurrency precondition where applicable, and sanitized result/error fields.                                                                          |

Freshness must derive from source timestamps, validity windows, and verification policy. Retrieval time alone does not make evidence current. Unknown freshness is not “fresh”; hard freshness requirements must fail or return no qualifying evidence.

Citation validation establishes source identity and excerpt correspondence. It must not present schema validity or retrieval scores as proof that a claim is true.

Map lineage explicitly:

| Enterprise record                                          | W3C PROV mapping         |
| ---------------------------------------------------------- | ------------------------ |
| Source revision, chunk, embedding, evidence envelope       | `prov:Entity`            |
| Ingestion, normalization, embedding, retrieval, validation | `prov:Activity`          |
| IE, RAG service, responsible source actor                  | `prov:Agent`             |
| Activity consumes source/chunk                             | `prov:used`              |
| Chunk/embedding/envelope produced by activity              | `prov:wasGeneratedBy`    |
| Derived entity relates to its source entity                | `prov:wasDerivedFrom`    |
| Activity responsibility                                    | `prov:wasAssociatedWith` |
| Entity attribution                                         | `prov:wasAttributedTo`   |
| Verified delegation                                        | `prov:actedOnBehalfOf`   |

These classes and relationships are defined by PROV-O. **[V]** ([w3.org][6])

**[S/D]** Immutability is enforced by the existing ledger implementation, append-only permissions, integrity verification, and retention controls. PROV compatibility alone does not provide immutability. Corrections create new records and derivation links; they do not rewrite old lineage.

**MCP contract**

The official latest specification resolved to **`2026-07-28`** during this review. It introduces stateless requests, per-request version/capability metadata, `server/discover`, and required `resultType` fields. Preserve an explicit compatibility profile for any supported older peer; do not silently combine protocol versions. **[V]** ([Model Context Protocol][7])

**[D]** Keep IE’s host/client ownership in `app/mcp/host.py`. Keep capability execution in `data_gateway.py`. An existing in-process facade does not justify creating a new network server solely because its name contains MCP.

Where an actual MCP transport exists:

* Use typed input and output schemas, validate both sides, and return bounded structured results.
* Distinguish malformed protocol requests from tool execution failures; use `isError` for execution failures. An unavailable store must not become a successful empty result.
* Use the selected protocol version’s result and cache fields. Tenant-specific cached results remain private and authorization-sensitive. **[V/D]** ([Model Context Protocol][8])

For protected HTTP transport, validate access tokens for the intended resource, apply scope checks, and follow protected-resource discovery requirements. Invalid tokens receive 401; insufficient permissions receive 403. Do not pass the incoming token through to unrelated downstream systems. STDIO uses a different credential model. **[V]** ([Model Context Protocol][9])

**[D]** Record request/task correlation, policy decision, resource class, latency, candidate counts, rejected evidence counts, index generation, and audit receipt. Keep credentials and raw sensitive content out of ordinary logs.

---

**2. Gaps and inconsistencies**

| Finding                                                   | Evidence/status                                                                                                                                            | Required resolution                                                                                                                       |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Implementations cannot be inspected                       | Only documentation, trees, and diagram content were supplied.                                                                                              | Inspect actual modules, imports, manifests, DDL, and tests before finalizing a patch. File existence does not establish working behavior. |
| Direct `CDB → W_LEARN` edge contradicts Model A           | Present in Architecture §3 and the decoded Flowchart.                                                                                                      | Interpret the feed as IE-mediated retrieval. Correct the documentation edge; do not grant the worker database access.                     |
| IE-to-RAG ingestion is inconsistently described           | Flowchart shows authorized read/write ingestion; the data-flow table lists IE-to-RAG as read-only; the component table mentions ingestion streams from DB. | State explicitly that IE authorizes both retrieval and ingestion. A database event is not an independent RAG caller.                      |
| “Vector/BM25” is asserted without implementation evidence | Architecture component table and Hierarchy description.                                                                                                    | Verify the lexical backend. Use FTS terminology unless genuine BM25 code/dependencies are present.                                        |
| CMS staging and live mutation need an explicit boundary   | Data gateway permits CMS writes; outbound boundary owns production changes.                                                                                | Allow only approved staging operations through Layer 3. Keep publishing and deployment in Layer 7.                                        |
| RAG retrieval contracts are not separately identified     | Existing `agent_contracts.py` already owns context requests and evidence envelopes.                                                                        | Inspect and extend that contract before adding another schema module.                                                                     |
| Embedding and ingestion lifecycle behavior is unspecified | Paths exist, but implementations and database definitions are unavailable.                                                                                 | Verify model/version metadata, idempotency, generation activation, deletion handling, and concurrency semantics.                          |
| Isolation enforcement is unverified                       | No RLS policies, role grants, connection code, or adapter implementation supplied.                                                                         | Verify runtime-role isolation and non-SQL store authorization with real integration tests.                                                |
| MCP name does not establish protocol conformance          | `host.py` and `data_gateway.py` are listed without contents.                                                                                               | Identify actual transport, SDK, supported protocol revision, authentication, and wire behavior.                                           |
| PROV representation and immutable storage are unverified  | Schemas, service, repository, and validator paths exist.                                                                                                   | Verify relationship completeness, append-only behavior, transaction coupling, and tamper detection.                                       |
| Migration/dependency conventions remain unknown           | Hierarchy §4 explicitly leaves driver, ORM, migration tool, CMS vendor, and several backing stores unspecified.                                            | Reuse verified project choices. No new framework, migration directory, or package is presently justified.                                 |
| Research copies may resemble runtime modules              | Enterprise tree includes `Agentic System Research/raw_code/agentic_rag.py` and related files.                                                              | Check runtime imports before classifying anything as duplication. Preserve research files unless runtime duplication is proven.           |

---

**3. Exact target file/folder hierarchy with change markers**

This is the **Layer 3 scope projection** of the existing tree. All unlisted paths remain `KEEP`.

`MODIFY` identifies the existing owner of a proposed change. Because implementations were not supplied, each remains conditional: if its contract already passes the specified tests, reclassify it as `KEEP`.

**No `ADD`, `MOVE`, or `REMOVE` operation is justified by the available evidence.** Migration files remain unassigned until the actual migration mechanism is inspected.

```text
enterprise_os/                                      KEEP
├── backend/                                        KEEP
│   ├── app/                                        KEEP
│   │   ├── main.py                                 KEEP
│   │   ├── core/                                   KEEP
│   │   │   ├── settings.py                         MODIFY
│   │   │   ├── exceptions.py                       MODIFY
│   │   │   └── logging.py                          KEEP
│   │   ├── orchestration/                          KEEP
│   │   │   ├── intelligence_engine.py              KEEP
│   │   │   ├── context_assembly.py                 KEEP
│   │   │   └── rag_query_dispatch.py               MODIFY
│   │   ├── services/                               KEEP
│   │   │   ├── rag/                                KEEP
│   │   │   │   ├── __init__.py                      KEEP
│   │   │   │   ├── controller.py                    MODIFY
│   │   │   │   ├── hybrid_retriever.py              MODIFY
│   │   │   │   ├── freshness.py                     MODIFY
│   │   │   │   └── schema_validator.py              MODIFY
│   │   │   ├── provenance.py                       MODIFY
│   │   │   ├── audit_validator.py                  MODIFY
│   │   │   └── memory_promotion.py                 KEEP
│   │   ├── mcp/                                    KEEP
│   │   │   ├── host.py                             MODIFY
│   │   │   ├── data_gateway.py                     MODIFY
│   │   │   └── outbound_gateway.py                 KEEP
│   │   ├── schemas/                                KEEP
│   │   │   ├── governance.py                       MODIFY
│   │   │   ├── agent_contracts.py                  MODIFY
│   │   │   ├── provenance.py                       MODIFY
│   │   │   ├── artifact.py                         KEEP
│   │   │   └── cms.py                              KEEP
│   │   ├── security/                               KEEP
│   │   │   ├── authorization_boundary.py           MODIFY
│   │   │   ├── scope_evaluator.py                  MODIFY
│   │   │   └── cryptographic_validator.py          MODIFY
│   │   ├── integrations/                           KEEP
│   │   │   ├── llm/                                KEEP
│   │   │   │   └── client.py                        MODIFY
│   │   │   ├── cms/                                KEEP
│   │   │   │   └── client.py                        MODIFY
│   │   │   └── sandbox/                            KEEP
│   │   └── persistence/                            KEEP
│   │       ├── database.py                         MODIFY
│   │       └── repositories/                       KEEP
│   │           ├── base.py                         MODIFY
│   │           ├── operational.py                  MODIFY
│   │           ├── vector.py                       MODIFY
│   │           ├── memory.py                       MODIFY
│   │           ├── artifact.py                     MODIFY
│   │           ├── provenance.py                   MODIFY
│   │           ├── task_state.py                   KEEP
│   │           └── telemetry.py                    KEEP
│   ├── tests/                                      KEEP
│   │   ├── conftest.py                             MODIFY
│   │   ├── unit/                                   KEEP
│   │   │   ├── test_rag_governance.py               MODIFY
│   │   │   ├── test_governed_mcp_data_gateway.py    MODIFY
│   │   │   ├── test_policy_authorization.py        MODIFY
│   │   │   └── test_audit_lineage_validator_t33.py  MODIFY
│   │   ├── integration/                            KEEP
│   │   │   ├── test_model_a_data_access.py          MODIFY
│   │   │   ├── test_security_boundaries_negative.py MODIFY
│   │   │   ├── test_provenance_persistence.py       MODIFY
│   │   │   ├── test_outbound_after_approval.py      KEEP
│   │   │   └── test_worker_sandbox_boundary.py      KEEP
│   │   └── acceptance/                             KEEP
│   │       └── test_governed_end_to_end_flow.py     MODIFY
│   ├── .env.example                                MODIFY
│   ├── pyproject.toml                              KEEP
│   └── README.md                                   MODIFY
├── sandbox/                                        KEEP
└── Agentic System Research/                         KEEP
```

Existing package exports remain stable. `main.py`, IE, and context assembly require changes only if source inspection proves that compatible interfaces cannot provide the required wiring.

---

**4. Per-file implementation responsibilities**

Paths below are relative to `backend/`. Interface names describe required behavior; preserve existing equivalent names and signatures.

Test references correspond to Section 6.

| File                                          | Responsibility and interface                                                                                                                                                                       | Dependencies                                                                                  | Tests                |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------- |
| `app/orchestration/rag_query_dispatch.py`     | IE-exclusive `retrieve(request, auth)` and authorized ingestion dispatch. Preserve originating grants; never manufacture authority from request fields.                                            | Existing PAB, RAG controller, contracts.                                                      | T1, T2, T12          |
| `app/services/rag/controller.py`              | Coordinate retrieval/ingestion stages, validation, evidence packaging, receipts, and audit emission. No SQL, store SDK, or sandbox calls.                                                          | Retriever, freshness/schema services, gateway, existing provenance service, embedding client. | T3, T5–T8, T12       |
| `app/services/rag/hybrid_retriever.py`        | Obtain bounded branch candidates through gateway methods; perform deterministic fusion, deduplication, and result selection.                                                                       | Gateway interface, retrieval contracts/configuration.                                         | T4, T11              |
| `app/services/rag/freshness.py`               | Evaluate source-specific freshness using an injected clock and policy. Return explicit fresh/stale/unknown/invalid status and reason.                                                              | Existing policy contract and source metadata.                                                 | T5                   |
| `app/services/rag/schema_validator.py`        | Validate ingestion structures, returned records, embedding metadata, excerpts, and citation locators. Reject unsupported versions and unsafe external schema resolution.                           | Existing schemas and validation library.                                                      | T3, T5               |
| `app/mcp/data_gateway.py`                     | Authorize each allowlisted capability; dispatch typed CRUD/search/staging operations; coordinate repository units of work; sanitize errors. Separate read, ingest, update, and delete permissions. | PAB, repositories, database boundary, CMS adapter, provenance service.                        | T2, T6, T9, T10      |
| `app/mcp/host.py`                             | Preserve IE ownership; bind permitted data capabilities and existing transport authentication. Enforce supported protocol profiles and prevent worker registration of data tools.                  | Gateway, existing MCP SDK/transport, security components.                                     | T1, T2, T10          |
| `app/schemas/governance.py`                   | Represent verified scope, operation authority, expiry, delegation, and policy references. Reuse current governance types.                                                                          | Existing schema conventions.                                                                  | T2, T3               |
| `app/schemas/agent_contracts.py`              | Extend context, retrieval, ingestion, evidence, and receipt contracts without duplicating existing envelope types.                                                                                 | Governance, artifact/CMS references, provenance references.                                   | T3, T12              |
| `app/schemas/provenance.py`                   | Define versioned Entity/Activity/Agent records and typed relationships with tenant, time, source revision, and integrity references.                                                               | Existing serialization conventions.                                                           | T8                   |
| `app/security/authorization_boundary.py`      | Enforce IE-only RAG access and IE-rooted gateway delegation. Recheck operation, resource, current policy, and grant validity.                                                                      | Cryptographic validator and scope evaluator.                                                  | T1, T2               |
| `app/security/scope_evaluator.py`             | Compute intersections of tenant, brand, collection, document, and operation scopes. Missing scope denies; delegation cannot widen it.                                                              | Governance contracts.                                                                         | T2, T7               |
| `app/security/cryptographic_validator.py`     | Verify applicable issuer, audience, signature, lifetime, and delegation binding using the existing credential scheme. Keep OAuth token validation distinct from internal grants.                   | Existing authentication/key configuration.                                                    | T2, T10              |
| `app/integrations/llm/client.py`              | Reuse or add a provider-neutral batch embedding operation returning vectors plus model/version metadata. Enforce dimension, finite-value, timeout, and retry validation.                           | Installed provider SDK/configuration.                                                         | T4, T6               |
| `app/integrations/cms/client.py`              | Resolve tenant/site-bound source revisions; provide bounded reads and authorized staging operations with version preconditions. Never expose live publishing through data capabilities.            | Existing CMS schemas, credentials, HTTP client.                                               | T7, T9               |
| `app/persistence/database.py`                 | Own connections and transaction lifecycle, trusted transaction-local scope, timeout handling, rollback, and pool cleanup.                                                                          | Installed driver/ORM and settings.                                                            | T6, T7               |
| `app/persistence/repositories/base.py`        | Require scoped access and transaction context; provide shared parameterization and pagination conventions. Do not create a parallel persistence framework.                                         | Database boundary, governance context.                                                        | T6, T7               |
| `app/persistence/repositories/operational.py` | Read/write approved operational knowledge records and ingestion receipts where existing ownership fits. Preserve CTS and telemetry ownership.                                                      | Base repository and current data model.                                                       | T6, T7               |
| `app/persistence/repositories/vector.py`      | Own scoped vector/FTS queries, chunk/vector persistence, version compatibility, generation activation, and tombstones. Return branch ranks; keep fusion in RAG.                                    | Database boundary, installed pgvector, current schema.                                        | T4, T6, T7, T11      |
| `app/persistence/repositories/memory.py`      | Scope memory reads/writes and preserve versions. Accept promotion decisions only from the existing authorized promotion workflow.                                                                  | Existing memory backend and promotion contract.                                               | T7, T9               |
| `app/persistence/repositories/artifact.py`    | Resolve by tenant plus artifact/version/hash; verify integrity and permitted storage location. Prevent arbitrary URL fetching and unrestricted filesystem resolution.                              | Existing artifact backend/schema.                                                             | T7–T9                |
| `app/services/provenance.py`                  | Build/record lineage through the existing ledger path. Support a caller-owned unit of work where existing storage allows atomic ingestion and audit.                                               | Provenance schemas and repository.                                                            | T8                   |
| `app/persistence/repositories/provenance.py`  | Append tenant-scoped immutable events; enforce event identity, integrity references, and transaction participation. No application update/delete API for lineage.                                  | Existing ledger/database backend.                                                             | T6–T8                |
| `app/services/audit_validator.py`             | Validate required typed relationships, source references, tenant consistency, timestamps, and existing integrity proofs.                                                                           | Provenance contracts and scoped ledger reads.                                                 | T8                   |
| `app/core/settings.py`                        | Validate bounded retrieval, embedding, freshness, timeout, retry, protocol, and index settings at startup.                                                                                         | Existing settings library.                                                                    | T3, T4, T10          |
| `app/core/exceptions.py`                      | Reuse typed errors for denial, invalid schema, freshness failure, conflict, incompatible embedding, unavailable dependency, and integrity failure.                                                 | Existing exception conventions.                                                               | T3, T6, T10          |
| `.env.example`                                | Document approved configuration keys with non-secret examples.                                                                                                                                     | Existing deployment conventions.                                                              | Configuration review |
| `README.md`                                   | Document corrected Model A flow, actual lexical backend, authorization, ingestion recovery, provenance, and verified test commands.                                                                | Implemented behavior and test evidence.                                                       | Documentation review |

**Dependency direction:** orchestration may call RAG; RAG may call the governed facade and existing provenance service; the facade may call adapters/repositories. Repositories must not import RAG or worker engines. The existing Layer 9 audit service is the documented provenance path, not a new general data-access bypass.

The modified test files own the cases listed below. `conftest.py` should supply two-tenant fixtures, restricted database roles, deterministic embeddings, fixed clocks, source revisions, and controllable adapter failures.

---

**5. Required dependencies, configuration, and migrations**

**Dependencies**

| Area                | Required action                                                                                                                                            |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python driver/ORM   | Inspect `pyproject.toml` and runtime imports. Keep the installed supported stack.                                                                          |
| PostgreSQL/pgvector | Verify deployed versions, enabled extension, operator classes, and supported index features. Documentation review does not establish the deployed version. |
| Embeddings          | Reuse the provider-neutral client and installed SDK. Add a dependency only if the configured provider lacks a usable embedding interface.                  |
| MCP                 | Verify SDK, transport, and protocol support. Upgrade only where the chosen compatibility profile requires it.                                              |
| Schema validation   | Reuse the installed library. Do not introduce another schema framework without a demonstrated limitation.                                                  |
| BM25                | No new BM25 dependency is required for the proposed FTS design. If one already exists, verify its implementation, tenant isolation, and ranking behavior.  |
| PROV                | Typed compatible records do not automatically require an RDF store or new PROV package. Reuse the ledger representation.                                   |

**Configuration**

Use existing setting names where available. Required logical settings are:

* Embedding model/revision, dimensions, distance metric, batch limits, and provider authorization.
* FTS language/configuration, branch candidate limits, final result limit, fusion weights/constant, and retrieval configuration version.
* Freshness policies by source type and bounded clock tolerance.
* Connection, query, provider, and CMS deadlines; bounded retries.
* MCP transport/profile, trusted issuers/audiences, and permitted capability scopes.
* Current index generation and permitted schema versions.

Policy configuration belongs with the existing policy owner. Credentials belong in the existing secret mechanism.

**Conditional database migrations**

No specific migration filename or framework can be established from the attachments.

| Migration candidate   | Apply only if inspection proves it is missing                                                                            |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Tenant isolation      | Required tenant/scope columns, RLS policies, appropriate role grants, and tenant-safe relationship constraints.          |
| Lexical retrieval     | Stored/generated search representation and suitable FTS index using the selected language configuration.                 |
| Embedding metadata    | Model revision, dimensions/metric compatibility, source/chunk revision, and generation fields.                           |
| Ingestion idempotency | Tenant-scoped unique keys, request digest, durable receipt/status, and concurrency-safe activation.                      |
| Provenance integrity  | Required typed references, immutable revision metadata, append-only enforcement, and existing integrity-chain support.   |
| Recovery              | Durable pending-operation/outbox records only if external-write recovery is required and no equivalent mechanism exists. |

Inspect and repair existing data before enabling new constraints. Do not guess ownership for unscoped historical rows. Use shadow index generations and reversible activation where feasible; preserve historical evidence and lineage.

---

**6. Validation and test matrix**

These are required tests, **not reported passing results**.

| ID  | Category                    | Required cases and acceptance condition                                                                                                                                                                                                                                                                              | Existing test owner                                                         |
| --- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| T1  | Model A boundaries          | IE-mediated retrieval succeeds. Direct worker/sub-agent RAG, gateway, repository, CMS, memory, and artifact access fails. Worker-visible tools contain no data capability. Layer 3 imports no sandbox execution path.                                                                                                | `test_model_a_data_access.py`                                               |
| T2  | Negative authorization      | Reject forged IE labels, wrong audience, invalid/expired grants, broken delegation, missing tenant, broader brand scope, read-to-write escalation, and disallowed operations. Rejection occurs before adapter invocation.                                                                                            | `test_policy_authorization.py`; `test_security_boundaries_negative.py`      |
| T3  | Contract validation         | Reject malformed filters, unsupported schemas, oversized limits, invalid timestamps, unsafe schema references, invalid vectors, and unknown operations. Preserve supported old request/envelope shapes.                                                                                                              | `test_rag_governance.py`; `test_governed_mcp_data_gateway.py`               |
| T4  | Retrieval unit/integration  | Verify exact RRF results, one-based ranks, missing-branch behavior, duplicates, stable ties, empty results, compatible embedding versions, and accurate FTS labeling.                                                                                                                                                | `test_rag_governance.py`; `test_model_a_data_access.py`                     |
| T5  | Freshness and citations     | Test fresh/stale/unknown timestamps, expiry boundaries, future dates, changed source revisions, invalid offsets, hash mismatches, and revoked sources. No invalid chunk enters a successful evidence set.                                                                                                            | `test_rag_governance.py`                                                    |
| T6  | Ingestion and transactions  | Concurrent identical requests produce one durable effect. Conflicting key reuse fails. Simulate crashes and failures before/after writes, embedding failure, audit failure, and interrupted activation. No incomplete generation becomes active.                                                                     | `test_governed_mcp_data_gateway.py`; `test_provenance_persistence.py`       |
| T7  | Real tenant isolation       | Run as the restricted application role against PostgreSQL. Exercise reads, joins, vector/FTS searches, upserts, update/delete, counts, pagination, hashes, and foreign references across two tenants. Test pool reuse after commit, rollback, cancellation, and error. Zero unauthorized records or payloads escape. | `test_security_boundaries_negative.py`; `test_model_a_data_access.py`       |
| T8  | Provenance and immutability | Each returned chunk traces to its source revision and generating activity/agent. Reject broken or cross-tenant links; preserve prior records on correction. Detect tampering and failed audit persistence. Application update/delete attempts fail.                                                                  | `test_audit_lineage_validator_t33.py`; `test_provenance_persistence.py`     |
| T9  | Adapter boundaries          | Test wrong CMS site, stale write preconditions, missing promotion authorization, artifact URI manipulation, content-hash mismatch, timeouts, and ambiguous remote completion. Layer 3 cannot publish live content.                                                                                                   | `test_governed_mcp_data_gateway.py`; existing outbound regression tests     |
| T10 | MCP wire/security           | Test the actual selected protocol profile, discovery/metadata, structured results, malformed requests, execution errors, authentication statuses, private caching, retry idempotency, and sanitized observability.                                                                                                   | `test_governed_mcp_data_gateway.py`; `test_security_boundaries_negative.py` |
| T11 | Retrieval quality           | Evaluate judged queries for exact terms, semantic matches, multilingual text where supported, tenant filtering, stale exclusions, and no-answer cases. Measure Recall@k, nDCG@k, filtered ANN recall, and latency against recorded baselines.                                                                        | `test_model_a_data_access.py`, using fixtures in `conftest.py`              |
| T12 | End-to-end                  | IE-authorized ingest → committed source/index/provenance → worker context request → IE dispatch → scoped retrieval → cited read-only envelope. Repeat with revocation, stale evidence, and dependency failure.                                                                                                       | `test_governed_end_to_end_flow.py`                                          |

Security and integrity cases have binary release gates. Retrieval-quality and latency thresholds must be recorded from the project’s baseline and requirements before release; the attachments provide no defensible numerical targets.

Run existing worker, outbound, CTS, and memory-promotion regression tests to verify preserved ownership. Broaden testing only if a changed shared component creates a concrete additional risk.

---

**7. Ordered implementation sequence**

| Task  | Action                                                                                                                                                                                                               | Predecessor | Completion milestone                                                                      | Owner                          |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------- | ------------------------------ |
| L3-01 | Inspect actual source, imports, manifests, database schema/policies, transport, adapters, and existing tests. Classify each proposed modification as required or already satisfied. Resolve documentation conflicts. | None        | Evidence-backed change inventory and baseline results.                                    | Backend maintainer             |
| L3-02 | Finalize compatible authorization, retrieval, ingestion, evidence, error, and provenance contracts. Record protocol and lexical-backend choices.                                                                     | L3-01       | Reviewed interfaces and security invariants.                                              | Backend + security owners      |
| L3-03 | Implement only proven persistence gaps: scoped repositories, RLS/roles, transaction context, idempotency, provenance coupling, and necessary migrations.                                                             | L3-02       | Restricted-role isolation and atomicity tests pass.                                       | Persistence + security owners  |
| L3-04 | Complete governed gateway capabilities, CMS/Memory/Artifact adapters, and the existing MCP transport binding.                                                                                                        | L3-03       | Typed capabilities enforce operation and resource scope.                                  | Backend/integration owner      |
| L3-05 | Complete embeddings, semantic/lexical retrieval, deterministic fusion, freshness/schema checks, citation validation, and evidence lineage.                                                                           | L3-04       | Retrieval and evidence contract tests pass.                                               | RAG owner                      |
| L3-06 | Complete authorized ingestion, deterministic chunking, idempotent retries, index replacement, tombstones, and recovery behavior.                                                                                     | L3-05       | Replay, concurrency, failure, and reindex tests pass.                                     | RAG + persistence owners       |
| L3-07 | Connect the existing IE dispatcher, verify read-only worker delivery, and complete observability and end-to-end tests.                                                                                               | L3-06       | Full Model A path works without ownership changes.                                        | Orchestration + QA owners      |
| L3-08 | Run security, provenance, quality, compatibility, and affected regression gates. Validate migration/activation rollback, document measured limits, and observe staged operation.                                     | L3-07       | Reviewable implementation with recorded evidence and no unresolved release-blocking gaps. | Backend + security + QA owners |

[1]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html?utm_source=chatgpt.com "PostgreSQL: Documentation: 18: 5.9. Row Security Policies"
[2]: https://www.postgresql.org/docs/current/functions-admin.html?utm_source=chatgpt.com "PostgreSQL: Documentation: 18: 9.28. System Administration Functions"
[3]: https://www.postgresql.org/docs/current/libpq-exec.html?utm_source=chatgpt.com "PostgreSQL: Documentation: 18: 32.3. Command Execution Functions"
[4]: https://www.postgresql.org/docs/current/textsearch-controls.html?utm_source=chatgpt.com "PostgreSQL: Documentation: 18: 12.3. Controlling Text Search"
[5]: https://github.com/pgvector/pgvector?utm_source=chatgpt.com "GitHub - pgvector/pgvector: Open-source vector similarity search for Postgres"
[6]: https://www.w3.org/TR/prov-o/?utm_source=chatgpt.com "PROV-O: The PROV Ontology"
[7]: https://modelcontextprotocol.io/specification/latest?utm_source=chatgpt.com "Specification"
[8]: https://modelcontextprotocol.io/specification/2026-07-28/server/tools?utm_source=chatgpt.com "Tools"
[9]: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization?utm_source=chatgpt.com "Authorization"
