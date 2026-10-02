# Validation report

Date: 2026-09-29. Environment: CPython 3.12.14, Pydantic 2.13.5.

**64 tests discovered: 61 passed, 3 skipped, 0 failures/errors.** All Python
source files compile. Local validation exits 0. `--require-live` exits 2,
correctly blocking production acceptance because real services are unavailable.
Full output: `test-results.txt` and `production-gate.txt`.

## Acceptance status

| Requested criterion | Evidence | Status |
|---|---|---|
| Boundary enforcement | Strict import allowlist, forbidden-dependency mutation examples, worker network tripwire, no local wrapper fallback, signed output validation | Local application checks pass; kernel/runtime proof pending |
| Model A | Zero worker imports of persistence, RAG, CMS, external HTTP, SDK, subprocess or dynamic import facilities; context only through IE port | Static/current-code paths pass; deployment credentials and network policies pending |
| IE grant-to-envelope cycle | Real coordinator/schema/adapter/solver with explicit IE, ledger and controller test doubles; injected/fetched context, valid/invalid receipts, two tenants | Local integration passes; actual host interface compatibility pending |
| Optimization efficacy | Independent exhaustive oracle, five channels, random budget invariants, rounded bounds, infeasible ROAS/CPA, search-limit distinctions, seeded bootstrap, Pareto checks | Pass for the declared discrete saturation model |
| Audit fidelity | Full-payload hashes, action/scope binding, previous-hash chain, standard PROV-O JSON-LD, immutable replay conflicts, entity/activity/agent/delegation graph | Local contract tests pass; durable immutable backing and concurrency proof pending |

## Tests that ran

- Strict JSON/Python serialization, extra-field rejection, no numeric coercion,
  no NaN/Infinity, frozen nested revalidation, channel uniqueness, date validation,
  tenant/brand/task/currency/period matching, scope attenuation and budget lattice.
- Fixed-seed repeatability, changed-seed bootstrap sensitivity, hard spend and
  channel bounds, global/per-channel CPA, ROAS, zero-conversion handling,
  infeasibility, incomplete search, exact candidate-limit edge and roadmap totals.
- Expired/revoked grants, revocation during context/audit, zero-token execution,
  context-call limits, missing/foreign context, evidence receipts, proposal-only
  previews, idempotent replay, changed-context conflict and cancellation.
- Audit failure before dispatch/submission, graph references and event tampering.
- Signature/image mismatches, oversized/malformed output, signed overspending,
  signed roadmap tampering, replay with changed seed, and timeout rejection.
- Separate-process solver stdin/stdout protocol, size limits and error responses
  that do not reflect secret-like input. This subprocess is a unit test, not
  an isolation demonstration.

## Tests that did not run

1. Real IE/PAB -> agent_sandbox -> micro-VM -> durable artifact/ledger cycle.
2. Real IPv4/IPv6/DNS/metadata/internal-service blocking, direct SDK bypass denial,
   tmpfs, read-only root, syscall restriction, peer-memory isolation, resource
   ceilings, cancellation and timeout teardown.
3. Immutable ledger persistence across restart, rejected mutation/conflicting
   replay, concurrent append serialization and complete retained PROV payloads.

The sandbox SDK, Docker/micro-VM runtime, actual backend Python files, controller
keys and ledger service were not present. No deployment or live infrastructure
claim is made. Test attestations explicitly identify `TEST_ONLY`; test ledgers
and controllers live only under `tests/`.

## Review changes made during implementation

- Added authorization rechecks after context, after execution and immediately
  before IE submission; the trusted IE must still check atomically at commit.
- Rejected changing deadlines on retry, preserving deterministic mandate hashes.
- Bound artifact/execution identity, tenant scope and provenance entity hashes
  to the same evidence data.
- Added explicit audit action/payload/scope identity checks and correct linked
  PROV record identifiers.
- Added no-plan semantics for incomplete search and explicit extrapolation notes.
- Added bounded failure-audit attempts and an outer task-expiry timeout.
- Added a nonzero production gate for skipped live tests.

## Observation after host integration

Use the existing telemetry/audit owners to record execution ID, policy/image
digest, grant/context/output hashes, solver status, candidate count, runtime,
peak memory, append latency, retry conflicts and teardown outcome. Alert on
signature mismatch, tenant mismatch, revoked grants, failed append, unexpected
network attempts, missing teardown and rising `search_limit` frequency. Avoid
dumping raw context to general application logs; the governed audit store owns
full evidence retention. No production observations exist from this session.
