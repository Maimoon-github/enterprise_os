# 1. Verified Architecture Decisions and Gaps

## Confirmed from supplied architecture

* **Model A is authoritative:** `Worker → IE → Agentic RAG → MCP Data Gateway → Layer 4`.
* CDB, CMS, MEM, and ART are Layer-4 systems of record.
* Workers receive **read-only mediated context** and return evidence/state proposals; they never possess Layer-4 credentials.
* `W_STRAT` is Layer 5 and uses `S_ALLOC` through the sandbox.
* Existing repository boundaries already exist for operational data, CTS, vectors, telemetry, memory, artifacts, and provenance.
* Existing `mcp/data_gateway.py` is the correct Layer-4 capability facade.
* Existing `integrations/cms/client.py` is the correct CMS provider boundary.
* Existing `services/memory_promotion.py` owns governed promotion into institutional memory.
* Existing `services/provenance.py` + `repositories/provenance.py` own provenance persistence.
* Sandbox executions remain ephemeral and receive zero database/storage credentials.

## Required corrections

| Gap / inconsistency                                                      | Required decision                                                                                                                  |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| Architecture shows `CDB → W_LEARN` directly                              | Remove. Route `CDB → MCP Data Gateway → Agentic RAG → IE → W_LEARN`.                                                               |
| Architecture shows `TELEMETRY → CDB` directly                            | Route persistence through the governed Data Gateway.                                                                               |
| IE component table says direct CDB/MEM access                            | Treat as logical authority, not physical access. IE must use RAG → Data Gateway.                                                   |
| “Every entity stored in CDB” conflicts with CMS/MEM/ART ownership        | CDB stores authoritative operational metadata/references. CMS owns content, MEM owns promoted memory, ART owns immutable payloads. |
| No backend migration hierarchy is present                                | Add versioned Layer-4 SQL migrations.                                                                                              |
| No immutable blob-store adapter is present                               | Add provider-neutral ART storage adapter.                                                                                          |
| No dedicated memory schema contract is present                           | Add `schemas/memory.py`.                                                                                                           |
| No explicit storage health aggregation is present                        | Add Layer-4 readiness/health service.                                                                                              |
| Concrete DB driver/ORM/migration framework is absent                     | Do not select one without further repository evidence.                                                                             |
| Concrete CMS, WORM/blob provider and immutable-ledger backend are absent | Keep adapter-driven and mark provider selection TBD.                                                                               |

PostgreSQL RLS becomes default-deny where RLS is enabled and no applicable policy exists, but table owners normally bypass it; `FORCE ROW LEVEL SECURITY` applies policies to owners, while superusers and `BYPASSRLS` roles remain exceptional. Therefore runtime connections must be non-owner, non-superuser and `NOBYPASSRLS`.

---

# 2. CDB / CMS / MEM / ART Implementation Specification

| Store   | Physical implementation                                                           | Authoritative responsibility                                                                                         | Access                                                     | Lifecycle / failure rule                                                                       |
| ------- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **CDB** | PostgreSQL + pgvector + TimescaleDB                                               | relational state, CTS/operational metadata, retrieval embeddings, telemetry, Layer-4 references, provenance metadata | repositories behind Data Gateway only                      | ACID transactions; PITR-capable backup; reject writes lacking tenant/provenance context        |
| **CMS** | Provider-neutral Headless CMS client                                              | canonical page/product/content models, staged layouts, CMS assets                                                    | Data Gateway → CMS client                                  | idempotent staging; never report success until mutation result/provenance is persisted         |
| **MEM** | Dedicated logical PostgreSQL schema using existing PostgreSQL/pgvector deployment | promoted/versioned brand rules, heuristics, validated learning                                                       | `memory.py` + `vector.py` repositories                     | only `memory_promotion.py` may promote; append a new version rather than silently overwrite    |
| **ART** | Immutable content-addressable object/blob backend + PostgreSQL metadata           | binary/text deliverables, dossiers, diffs, evidence bundles                                                          | Data Gateway → artifact repository + artifact-store client | SHA-256 before/after persistence; immutable object key; fail on mismatch; no payload overwrite |

**MEM does not require a new database technology.** Use the existing PostgreSQL/pgvector infrastructure until scale or isolation evidence justifies separation.

**ART separation:** `repositories/artifact.py` owns metadata, UUID/hash lookup and authorization. `integrations/artifact_store/client.py` owns blob I/O. This prevents object-store SDK logic from leaking into repositories or workers.

SHA-256 is appropriate for detecting artifact changes; NIST defines secure hash digests specifically for detecting whether message data has changed.

---

# 3. Layer-4 Data / Access Flow

```text
Layer 5 Worker
    │ ContextRequest / EvidenceEnvelope
    ▼
Intelligence Engine
    │ authorized retrieval / persistence request
    ▼
Agentic RAG Controller
    │ validated tenant + freshness + provenance scope
    ▼
MCP Data Gateway
    │
    ├── CDB
    │    ├── operational.py
    │    ├── task_state.py
    │    ├── telemetry.py
    │    ├── vector.py
    │    └── provenance.py
    │
    ├── MEM
    │    └── memory.py → PostgreSQL/pgvector
    │
    ├── CMS
    │    └── integrations/cms/client.py
    │
    └── ART
         ├── repositories/artifact.py
         └── integrations/artifact_store/client.py
```

Persistence of worker output is therefore:

```text
Worker
  → EvidenceEnvelope
  → IE validation
  → Agentic RAG ingestion
  → MCP Data Gateway
  → correct Layer-4 owner
```

Never:

```text
Worker → repository
Worker → RAG
Worker → Data Gateway
Worker → CMS client
Worker → artifact store
Worker → database connection
Sandbox → any Layer-4 endpoint
```

Telemetry follows the same storage boundary:

```text
Telemetry ingress
→ IE/governed ingestion path
→ Agentic RAG
→ Data Gateway
→ telemetry repository
→ Timescale hypertable
```

---

# 4. Final Layer-4 File / Folder Hierarchy

`[R]` reuse, `[M]` modify, `[A]` add.

```text
backend/
├── migrations/                                      [A]
│   ├── README.md                                    [A]
│   └── sql/
│       ├── 0001_layer4_extensions.sql               [A]
│       ├── 0002_layer4_core.sql                     [A]
│       ├── 0003_memory_artifact_provenance.sql      [A]
│       ├── 0004_telemetry_hypertable.sql            [A]
│       ├── 0005_tenant_rls_privileges.sql           [A]
│       └── 0006_layer4_indexes.sql                  [A]
│
├── app/
│   ├── core/
│   │   └── settings.py                              [M]
│   │
│   ├── mcp/
│   │   └── data_gateway.py                          [M]
│   │
│   ├── integrations/
│   │   ├── cms/
│   │   │   ├── __init__.py                         [R]
│   │   │   └── client.py                            [M]
│   │   └── artifact_store/                          [A]
│   │       ├── __init__.py                          [A]
│   │       └── client.py                            [A]
│   │
│   ├── persistence/
│   │   ├── database.py                              [M]
│   │   └── repositories/
│   │       ├── base.py                              [M]
│   │       ├── operational.py                       [R]
│   │       ├── task_state.py                        [R]
│   │       ├── vector.py                            [M]
│   │       ├── telemetry.py                         [M]
│   │       ├── memory.py                            [M]
│   │       ├── artifact.py                          [M]
│   │       └── provenance.py                        [M]
│   │
│   ├── schemas/
│   │   ├── agent_contracts.py                       [R]
│   │   ├── governance.py                            [R]
│   │   ├── artifact.py                              [M]
│   │   ├── cms.py                                   [M]
│   │   ├── memory.py                                [A]
│   │   ├── provenance.py                            [M]
│   │   └── telemetry.py                             [M]
│   │
│   └── services/
│       ├── rag/
│       │   ├── controller.py                        [M]
│       │   ├── hybrid_retriever.py                  [M]
│       │   ├── freshness.py                         [R]
│       │   └── schema_validator.py                  [R]
│       ├── memory_promotion.py                       [M]
│       ├── provenance.py                             [M]
│       └── storage_health.py                         [A]
│
└── tests/
    ├── unit/
    │   ├── test_governed_mcp_data_gateway.py         [M]
    │   ├── test_rag_governance.py                    [M]
    │   ├── test_memory_promotion_t32.py               [M]
    │   ├── test_audit_lineage_validator_t33.py        [M]
    │   └── test_layer4_repository_contracts.py        [A]
    │
    └── integration/
        ├── test_model_a_data_access.py                [M]
        ├── test_provenance_persistence.py             [M]
        ├── test_telemetry_learning_loop.py            [M]
        ├── test_layer4_tenant_isolation.py            [A]
        ├── test_artifact_integrity.py                 [A]
        └── test_layer4_failure_recovery.py            [A]
```

Do **not** add separate CDB, MEM, CMS or ART service packages. Existing repository/integration boundaries already provide the correct separation.

---

# 5. Strategy Engine Touchpoint Hierarchy

Current Strategy Engine structure remains unchanged:

```text
app/agents/
├── strategy.py                         # existing compatibility/worker boundary
└── strategy_engine/
    ├── __init__.py
    ├── strategy.py                     # W_STRAT domain coordinator
    └── subagents/
        ├── __init__.py
        └── allocation.py               # S_ALLOC-facing specialization
```

Allowed relationships:

```text
IE
 ├── bounded task grant
 ├── tenant-screened context slice
 └── approved tool/capability set
      │
      ▼
strategy_engine/strategy.py
      │
      ▼
integrations/sandbox/
      │
      ▼
S_ALLOC
      │
      ▼
EvidenceEnvelope / ArtifactReference
      │
      ▼
IE
```

`strategy_engine/**` must not import or instantiate:

```text
app.persistence.*
app.mcp.data_gateway
app.services.rag.*
app.integrations.cms.*
app.integrations.artifact_store.*
database drivers
pgvector clients
Timescale APIs
```

No Layer-4 file is added beneath `strategy_engine/`.

---

# 6. Exact ADD / MODIFY / REUSE Change List

## ADD

**`migrations/sql/*`**
Create extensions, Layer-4 structures, Timescale conversion, RLS/privileges and indexes without introducing an ORM or migration framework.

**`schemas/memory.py`**
Define promoted-memory/version/reference contracts.

**`integrations/artifact_store/client.py`**
Provider-neutral capability interface:

```text
put_if_absent()
get()
head()
verify_integrity()
healthcheck()
```

Provider must support immutable/object-lock semantics before production ART certification.

**`services/storage_health.py`**
Aggregate dependency readiness without exposing credentials, tenant data or object paths.

**Layer-4 tests**
Add RLS, integrity, repository-contract and failure/recovery coverage.

## MODIFY

**`database.py`**

* pool/connection ownership;
* transaction context;
* tenant-scoped session/transaction context;
* extension capability check;
* health check;
* prohibit privileged application roles.

**`repositories/base.py`**

* require authorization/tenant context on every operation;
* expose transaction handle rather than opening independent connections.

**`vector.py`**

* namespace + tenant enforcement;
* exact-search baseline;
* configurable ANN strategy.

**`telemetry.py`**

* Timescale-backed event persistence;
* idempotent ingestion;
* time-range retrieval.

**`memory.py`**

* promoted versions only;
* provenance linkage;
* tenant-scoped retrieval.

**`artifact.py`**

* artifact metadata only;
* UUID/hash mapping;
* immutable-reference semantics.

**`provenance.py`**

* append-only writes only;
* no normal update/delete API.

**`data_gateway.py`**

* single Layer-4 facade;
* authenticate caller;
* validate delegation/tenant;
* route to correct repository/adapter;
* require provenance/idempotency on writes;
* reject Worker/Sub-Agent identity.

**`cms/client.py`**

* maintain provider-neutral contract;
* idempotent staged mutations;
* version/reference return values;
* health check.

**`memory_promotion.py`**

* validate source evidence;
* reject unapproved/raw deltas;
* create new memory version;
* persist provenance atomically.

**RAG controller/retriever**

* preserve IE-exclusive invocation;
* pass tenant/access context through Data Gateway;
* never instantiate repositories directly.

## REUSE UNCHANGED

* Intelligence Engine architecture
* authorization boundary
* cryptographic validator
* scope evaluator
* CTS/state machines
* HITL
* sandbox integration
* Strategy Engine
* other Layer-5 workers
* outbound MCP boundary

---

# 7. Schemas, Migrations, Indexing and Transactions

## PostgreSQL logical ownership

Use separate logical schemas unless an existing database convention is later discovered:

```text
core.*        operational + canonical state
vector.*      retrieval embeddings
telemetry.*   time-series events
mem.*         promoted institutional memory
art.*         artifact metadata/reference registry
prov.*        append-only provenance
```

CMS content itself remains outside PostgreSQL.

## Minimum required records

**Vector record**

```text
tenant
namespace
source reference
embedding
embedding model/version
embedding dimension
content hash
metadata
created_at
provenance reference
```

Do not hard-code embedding dimensions or distance metrics until the configured embedding model is known.

**Telemetry event**

```text
tenant
event_time
event_type
source/channel
external/idempotency identifier
payload
provenance reference
ingested_at
```

Only this genuinely time-oriented dataset should initially become a Timescale hypertable. Hypertables automatically partition time-series data by time, and unique constraints involving hypertables have partition-dimension restrictions that must be considered when designing deduplication.

**Memory record**

```text
memory identifier
tenant
logical key
version
content/value
source evidence references
supersedes reference
promoted_at
promoted_by
provenance reference
```

Promotion inserts a new version. Raw learning deltas stay outside MEM until validated.

**Artifact record**

```text
artifact UUID
tenant
SHA-256
media/content type
byte length
immutable object locator
logical version
source/provenance reference
created_at
retention/legal-hold metadata
```

The object locator is not an authorization token.

## JSONB indexing

Do not create broad GIN indexes automatically. Add GIN/expression indexes only for observed query predicates. PostgreSQL supports both `jsonb_ops` and narrower `jsonb_path_ops`; the latter supports fewer operators but can perform better for the operators it supports.

## pgvector indexing

Start with exact nearest-neighbor search as the correctness/recall baseline.

Benchmark per namespace:

```text
exact
vs HNSW
vs IVFFlat
```

Measure:

```text
P50/P95 latency
recall@k
index size
build time
write cost
tenant-filter selectivity
```

Do not declare HNSW or IVFFlat globally. pgvector's approximate indexes trade recall for speed, and filtered ANN queries may under-return because filtering can occur after index scanning; iterative scans are available in pgvector 0.8+.

## Transaction boundaries

**Database-only mutation**

```text
BEGIN
  authorization/tenant context
  domain mutation
  provenance append
COMMIT
```

Failure of provenance must roll back the domain write.

**ART mutation**

```text
1. Compute SHA-256.
2. put_if_absent(content-addressed key).
3. Verify object hash/length.
4. BEGIN DB transaction.
5. Insert artifact metadata.
6. Append provenance.
7. COMMIT.
8. Return ArtifactReference.
```

If step 4–7 fails, retain the unreferenced immutable object for reconciliation/garbage collection; never publish metadata referencing a missing object.

**CMS mutation**

Use a stable idempotency/mutation ID:

```text
record intent
→ perform staged CMS mutation
→ obtain provider version/reference
→ append result provenance
→ return success
```

No live CMS deployment bypasses HITL/outbound actuation.

---

# 8. Security, Tenant Isolation, Provenance and Immutability

Every tenant-scoped PostgreSQL table must:

```sql
ENABLE ROW LEVEL SECURITY
FORCE ROW LEVEL SECURITY
```

and have explicit read/write policies with both visibility and write-check semantics.

Runtime application role requirements:

```text
not superuser
not table owner
NOBYPASSRLS
no schema-owner privileges
no migration privileges
minimum DML grants only
```

Use a separate migration/administration identity. PostgreSQL explicitly documents that `BYPASSRLS` roles bypass row security and that table ownership normally bypasses it unless forced.

Defense in depth:

```text
PAB authorization
+ MCP Data Gateway enforcement
+ repository tenant binding
+ PostgreSQL RLS
+ CMS document tenant filtering
+ ART tenant authorization
```

A caller-supplied `tenant_id` never grants authority; it must match the authenticated/delegated tenant context.

ART hash values and object URIs never bypass authorization.

Sandbox environments receive:

```text
no DB URI
no CMS credentials
no object-store credentials
no internal Layer-4 DNS/network route
```

W3C PROV records must represent at minimum the relevant **Entity, Activity, Agent**, usage/generation/derivation and delegation relationships. W3C PROV explicitly defines those responsibility and lineage concepts.

`provenance.py` must expose append/read operations only. Application ACLs alone do not provide cryptographic or storage-level immutability against a database administrator; production-grade “immutable provenance” therefore also requires the selected immutable-ledger/WORM backend or immutable checkpoint mechanism.

Recommended persistence invariant:

```text
hash(previous checkpoint + ordered provenance records)
→ immutable ART checkpoint
→ retain checkpoint hash/reference in provenance metadata
```

This does not replace W3C PROV; it protects its persisted history.

## Backup / recovery

CDB and PostgreSQL-backed MEM require tested base backup + WAL archiving/PITR. PostgreSQL documents continuous archiving specifically as the mechanism enabling point-in-time recovery; `pg_dump` remains useful for logical export but is not a replacement for WAL-based production recovery.

Do not invent retention periods. Apply deletion/compression/retention policies only after business/legal requirements are defined.

---

# 9. Test Plan

## Unit

Verify:

* Gateway rejects absent/invalid tenant context.
* Gateway rejects Worker/Sub-Agent identities.
* repository methods require access context;
* SHA-256 generation/verification;
* artifact hash mismatch rejection;
* memory promotion rejects unvalidated deltas;
* new memory promotion creates a version rather than destructive overwrite;
* provenance has no update/delete service methods;
* CMS mutation IDs are stable/idempotent;
* ANN configuration validates metric/dimension compatibility.

## Integration

Use at least two tenants.

Verify:

```text
Tenant A cannot SELECT Tenant B.
Tenant A cannot INSERT/UPDATE rows as Tenant B.
Missing RLS policy fails closed.
Runtime role cannot bypass RLS.
Worker cannot construct/use Data Gateway directly.
RAG can invoke Data Gateway only through authorized IE flow.
Cross-tenant vector results never appear.
Cross-tenant artifact hash/UUID resolution is denied.
Cross-tenant MEM retrieval is denied.
```

Verify Timescale telemetry creation, time-range queries and duplicate-event behavior.

Verify DB mutation + provenance rollback atomically.

Verify ART:

```text
upload
→ hash verification
→ metadata commit
→ retrieval
→ re-hash
```

Verify simulated corrupted content fails closed.

## Negative security

Test:

* spoofed tenant;
* forged delegation;
* missing provenance;
* missing idempotency key;
* worker repository import/use;
* sandbox DB/network attempt;
* CMS cross-tenant identifier;
* ART URI guessing;
* privileged DB-role misconfiguration.

## Failure

Inject:

```text
PostgreSQL unavailable
CMS timeout
object-store timeout
partial object upload
hash mismatch
provenance failure
duplicate telemetry delivery
process crash between object upload and metadata commit
```

No operation may report success before authoritative persistence is complete.

## Recovery

Regularly test:

* PostgreSQL restore from base backup + WAL;
* schema migration from clean DB;
* ANN index rebuild from stored embeddings;
* artifact metadata reconciliation against immutable objects;
* orphan object detection;
* CMS restoration according to selected provider;
* provenance checkpoint verification.

---

# 10. Dependencies and Explicit TBDs

## Required / already architectural

* PostgreSQL
* pgvector
* TimescaleDB
* Python standard-library SHA-256 implementation is sufficient for hashing
* existing sandbox SDK
* existing MCP/RAG/security architecture

## Do not add yet

* new ORM;
* separate vector database;
* separate MEM database;
* second RAG framework;
* second state system;
* vendor-specific CMS SDK;
* vendor-specific object-storage SDK;
* provenance framework/library.

## TBD before production implementation

1. PostgreSQL target version and compatible pgvector/TimescaleDB versions.
2. Existing PostgreSQL driver and connection-pool implementation.
3. Migration execution mechanism; supplied tree shows no backend migration framework.
4. Existing physical table names/tenant-key type; source bodies were not supplied.
5. Embedding provider/model, dimension and distance metric.
6. Exact pgvector ANN choice after benchmark.
7. CMS provider and API/versioning semantics.
8. ART immutable/WORM storage provider.
9. Immutable provenance-ledger/checkpoint backing technology.
10. Encryption/KMS and key-rotation implementation.
11. Backup destination and replication topology.
12. Required RPO/RTO.
13. Telemetry, memory, artifact and provenance retention periods.
14. Legal-hold requirements.
15. CMS backup/export and disaster-recovery capabilities.

**Implementation boundary:** the supplied attachments expose architecture and repository hierarchy, but not the source bodies of `database.py`, repositories, Data Gateway, or CMS client. Therefore the file-level plan above is definitive at the architectural level; driver-specific function signatures and SQL mappings must be matched to those implementations rather than invented.

**Resulting invariant**

```text
Governance / HITL
        ↓
Intelligence Engine
        ↓
Agentic RAG
        ↓
MCP Data Gateway
        ↓
┌────────┬────────┬────────┬────────┐
│  CDB   │  CMS   │  MEM   │  ART   │
└────────┴────────┴────────┴────────┘

Layer-5 workers: zero direct Layer-4 authority.
Layer-6 sandbox: zero persistent-store authority.
Every accepted mutation: tenant-bound + authorized + provenance-linked.
```
