**1. Research/architecture findings**

* **Project-defined:** Architecture §4 requires Model A, decreasing delegated authority, CTS-controlled mutations and governed HITL dispatch. Layer 2 has no sandbox capability.
* **Document-verified:** Both diagrams contain `CDB → W_LEARN`, contradicting Model A. Interpret this as IE-mediated retrieval. Owner→IE likewise requires PAB enforcement before processing.
* **Source-unverified:** Only documents/inventories were supplied; implementation, duplication, dead paths and passing tests cannot be established. `governance_milestone.py` appears in Backend Hierarchy but not the backend inventory.
* **Research-backed:** NIST supports identity-based authorization and distinct decision/enforcement responsibilities; this does not require additional infrastructure. ([CSRC][1])
* RFC 8693’s nested actor history does **not** establish inherited authority; attenuation requires separately validated grants. ([rfc-editor.org][2])

**2. Layer-2 responsibility/access matrix**

| Owner            | Responsibility                                                      | Access                                 |
| ---------------- | ------------------------------------------------------------------- | -------------------------------------- |
| IE               | Orchestration, context, scheduling, evidence, previews, MCP hosting | Governed R/W through existing services |
| PAB              | Deterministic Allow/Deny/Escalate                                   | Read policy/scope; emit audit records  |
| CTS              | Deterministic transitions, dependencies, recovery                   | Canonical ledger R/W                   |
| Policy engine    | Versioned policy envelopes                                          | Existing policy source                 |
| RAG/data gateway | IE-authorized retrieval/ingestion                                   | Scoped enterprise stores               |
| HITL/outbound    | Approval, final enforcement, dispatch                               | Approval records/external adapters     |
| Provenance       | Append immutable lineage                                            | Audit ledger                           |

**3. Authoritative execution flow**

Directive → PAB → IE → CTS/DAG → governed context/RAG → policy-screened bounded grant → worker evidence → IE validation → CTS → required HITL → reauthorization/CTS check → signed outbound dispatch → receipt/provenance.

Deny stops execution; Escalate holds it. Every authoritative mutation requires authorization and deterministic CTS checks.

**4. Final file/folder hierarchy**

Existing paths below follow Backend Hierarchy §2 and the backend inventory. `[MODIFY]` means **conditional on a demonstrated gap**; otherwise retain. No `[ADD]` is justified yet. Grouped filenames share the stated responsibility.

```text
backend/
  app/
    orchestration/
      intelligence_engine.py [MODIFY] orchestration only
      dag_scheduler.py [MODIFY] CTS-backed scheduling
      task_state_machine.py [MODIFY] deterministic legality
      policy_evaluator.py [MODIFY] apply PAB decisions
      context_assembly.py [KEEP] bounded context
      rag_query_dispatch.py [KEEP] IE-exclusive bridge
      evidence_synthesis.py [KEEP] evidence consolidation
      hitl_preview_generator.py [KEEP] review dossiers
    security/
      authorization_boundary.py [MODIFY] authoritative PAB decision
      scope_evaluator.py [MODIFY] tenant/authority containment
      cryptographic_validator.py [MODIFY] signed authorization validation
    services/
      policy_engine.py [KEEP] policy-envelope owner
      task_state.py [MODIFY] transaction/recovery coordinator
      hitl.py [MODIFY] approval binding/revocation
      provenance.py [MODIFY] PROV lineage
      rag/controller.py [KEEP] governed retrieval/ingestion
    schemas/
      governance.py [MODIFY] decision contract
      agent_contracts.py [MODIFY] grant/evidence contracts
      task_state.py [MODIFY] transitions/checkpoints
      dispatch.py [MODIFY] approval-bound dispatch
      provenance.py [MODIFY] lineage contract
    mcp/
      host.py [KEEP] IE-owned host
      data_gateway.py [MODIFY] identity/tenant enforcement
      outbound_gateway.py [MODIFY] final dispatch enforcement
    persistence/repositories/
      task_state.py [MODIFY] atomic canonical persistence
      provenance.py [MODIFY] immutable append
    agents/strategy_engine/ [KEEP] Layer-5 ownership
  tests/ [MODIFY] extend existing suites listed below
```

**5. Necessary codebase modifications only**

* **`authorization_boundary.py`, `scope_evaluator.py`, `governance.py`:** authenticate caller/service; validate tenant, delegation, policy version and risk. Require child resources/actions/tools/budgets/lifetime within parent authority; prevent sibling budget oversubscription. Record decision, reason and correlation IDs. Missing/invalid policy fails closed; escalation never grants access.
* **`cryptographic_validator.py`, `agent_contracts.py`:** if JWT-like grants exist, enforce trusted keys, algorithm allowlist, issuer, audience, subject/current actor, explicit type and lifetime. Bind grants to tenant/task/parent; durably reject replay. RFC 8725 supports algorithm and token-context validation. ([rfc-editor.org][3])
* **CTS files:** preserve existing state names. Proposed semantic progression, pending source inspection: pending→ready→running→review→completed; material actions require approval→dispatch→completion. Define failure/cancellation/hold edges explicitly; recovery resumes only a validated checkpoint. LLM output cannot authorize transitions.
* **`dag_scheduler.py`, CTS repository/service:** reject cycles and incomplete dependencies. Atomically check authorization, expected version and guards; commit state, checkpoint, idempotency result and transition history together. Use tenant-scoped keys and workflow-row locking for DAG mutations. Bound whole-transaction retries after deadlock/serialization errors; reject stale commands. PostgreSQL documents these locking/retry requirements. ([postgresql.org][4])
* **IE/policy evaluator/data gateway:** use one PAB implementation; eliminate bypasses only when demonstrated. Workers receive context/evidence contracts, never store credentials. No Layer-2 process execution.
* **HITL/dispatch files:** bind approval to exact payload hash, tenant, task and policy version; recheck expiry/revocation immediately before dispatch. Persist intent and stable idempotency key; reconcile uncertain external outcomes before retrying.
* **Provenance files:** Entities = policies, grants, decisions, snapshots, approvals, artifacts; Activities = authorization, retrieval, transition, approval, dispatch; Agents = authenticated humans/services/workers. Link `used`, `wasGeneratedBy`, `wasAssociatedWith`, `wasDerivedFrom`. PROV defines semantics; immutable storage requires separate append-only enforcement and tamper detection. ([w3.org][5])

**6. Validation/test matrix**

All are existing `backend/tests/` files to extend conditionally; none were executed.

| File                                               | Required proof                                                                             |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `unit/test_policy_authorization.py`                | Allow/deny/escalate; forged/expired grants; attenuation and budget bounds                  |
| `integration/test_security_boundaries_negative.py` | Cross-tenant IDs, replay, policy outage, forged delegation fail closed                     |
| `unit/test_task_state_machine.py`                  | Exhaustive legal/illegal edges, holds, cycles, dependency guards                           |
| `unit/test_task_state_service_and_recovery.py`     | Competing updates, duplicate requests, rollback, checkpoint recovery; real DB transactions |
| `integration/test_model_a_data_access.py`          | Worker/sub-agent store and RAG bypass denied; Layer-2 sandbox denied                       |
| `integration/test_outbound_after_approval.py`      | Payload changes, revoked approvals, duplicate dispatch, ambiguous outcomes                 |
| `integration/test_provenance_persistence.py`       | Complete lineage; tenant isolation; append-only enforcement; audit failure blocks commit   |
| `acceptance/test_governed_end_to_end_flow.py`      | Directive→evidence→HITL→dispatch→receipt, including hold/recovery                          |

**7. Unresolved assumptions**

Repository evidence must establish actual states, entry-point wiring, database transactions/migrations, token format, key management, audit durability and external idempotency support. Inspect inventoried research, `raw_code/` and development state-machine imports before declaring duplication. No new dependency, service or worker modification is currently justified.

[1]: https://csrc.nist.gov/pubs/sp/800/207/final?utm_source=chatgpt.com "SP 800-207, Zero Trust Architecture"
[2]: https://www.rfc-editor.org/rfc/rfc8693.html?utm_source=chatgpt.com "RFC 8693: OAuth 2.0 Token Exchange"
[3]: https://www.rfc-editor.org/rfc/rfc8725.html?utm_source=chatgpt.com "RFC 8725: JSON Web Token Best Current Practices"
[4]: https://www.postgresql.org/docs/current/transaction-iso.html?utm_source=chatgpt.com "PostgreSQL: Documentation: 18: 13.2. Transaction Isolation"
[5]: https://www.w3.org/TR/prov-dm/?utm_source=chatgpt.com "PROV-DM: The PROV Data Model"
