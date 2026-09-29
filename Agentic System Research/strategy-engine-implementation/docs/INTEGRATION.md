# Integration with the actual Enterprise OS repository

## Files that require source reconciliation

The supplied trees already list `agents/base.py`, `agents/strategy.py`,
`agents/strategy_engine/*`, `schemas/strategy.py`, `integrations/sandbox/client.py`,
`capabilities.py`, `s_alloc_core.py` and the S_ALLOC skill. Their contents were
not supplied. Treat this as a reference implementation overlay, not a verified
patch against those files. Do not replace unrelated agents, capability mappings,
auth checks or ledger code.

1. Compare actual `BaseAgent`, agent contracts, provenance contracts and
   `SandboxClient` signatures. Merge/alias shared models to avoid a second
   canonical grant or evidence format. Do not loosen scope or strict validation
   to make an adapter pass.
2. Register `StrategyEngine.execute(TaskGrant) -> EvidenceEnvelope` through the
   actual BaseAgent/worker interface. `ports.StrategyWorker` is an explicit
   structural interface; inheritance from the unseen BaseAgent is not claimed.
   Keep the legacy `app/agents/strategy.py` registry/re-export compatible.
3. Bind the IE/PAB and audit ports at the trusted composition root. Worker and
   specialist packages must not import RAG, persistence, CMS or SDK internals.
4. Merge the S_ALLOC-specific wrapper into the existing `SandboxClient` and
   register W_STRAT -> S_ALLOC in the existing capability map.
5. Install the shared schema and runtime in an immutable solver image, register
   its digest, and let the existing sandbox controller own all execution.
6. Run the full repository suite and the live production gate. Resolve conflicts
   with existing Layer 2/3/4/6/9 contracts before enabling worker registration.

No host adapter below is implemented by guessing the missing APIs.

## Required trusted bindings

### IntelligenceEnginePort

`authorize(grant)` must verify the authenticated caller, the original signed
grant and parent chain, brand/tenant ownership, revocation, time bounds, allowed
capability, resource ceilings and monotonic attenuation. Compare the full
canonical grant hash. A caller-provided `authorization_ref` is not proof.
Rejected authorizations must be audited by the control plane that rejects them.

`request_context(request)` must query enterprise data through IE's existing
governed RAG/data gateway path. Bind an immutable context snapshot to the grant
so a retry receives identical bytes. Return only requested brand/task/channel
scope. Convert all rows to the typed common currency/time-period contract.

`submit(envelope)` must recheck authorization/revocation atomically at ingest,
verify scope/hashes, persist evidence and a proposed CTS transition through the
existing owner, and deduplicate `artifact_id`. Only return `durable=True` after
commit. Use the existing transaction/outbox for a submission/audit crash window.
No acknowledgment authorizes spending or outbound actions.

### AuditPort

Persist the complete `AuditEvent` and `event.to_prov_jsonld()` graph. Enforce
uniqueness of event ID and exact-byte equality on replay; verify the per-run
previous hash, serialize concurrent appends, stamp receipt time, and retain
immutable payloads. Sign/checkpoint chains using the existing Layer 9 service.
Return a durable receipt containing the canonical event hash only after commit.

The worker does not contain a fake file/SQLite/in-memory production ledger.
`tests.support.TestLedger` is confined to test code.

### AgentSandboxControllerPort

The existing `SandboxClient` must call the installed `agent_sandbox` SDK through
its controller implementation of `execute_s_alloc`. That trusted controller
must enforce the exact policy, execution-ID idempotency and fixed entrypoint.
The package intentionally has no direct SDK shell call or local solver fallback
that could bypass your pre-existing containment boundary.

Use fresh Kata or Firecracker instances with deny-all network egress, no DB/CMS
credentials or host mounts, read-only root, private memory/tmpfs, restricted
syscalls, no-new-privileges, all capabilities dropped, non-root UID, cgroup RAM,
CPU/time/PID limits and disabled swap/core dumps. Prevent direct worker access to
the general SDK endpoint. The trusted host's control channel must not become a
guest-accessible egress route.

The controller owns creation, signed execution traces, timeout/cancellation
cleanup, memory/tmpfs destruction and the final attestation. Do not accept
guest-generated booleans or let the solver sign its own isolation claims.
`verify_attestation` must use independently configured controller public keys
and verify every attested field. The sample HMAC in tests is not deployable.

The attestation is returned only after confirmed teardown. On controller error
or uncertain teardown, return no successful evidence; surface the incident
through the existing audit/control-plane owner. Recover controller crashes from
a durable execution registry, not the worker's memory.

### Build boundary

The optional Dockerfile copies only the strategy schemas and fixed solver.
Build from the repository root with a vetted digest-pinned Python base:

```bash
docker build \
  --build-arg PYTHON_BASE='your-approved-python-image@sha256:YOUR_VERIFIED_DIGEST' \
  -f sandbox/docker/hardened/skills/s-alloc/Dockerfile \
  -t s-alloc:review .
```

Replace the digest with the actual approved base. Resolve dependencies through
your existing locked image build, record the resulting image digest, and pass
that digest to `SandboxClient`. No image was built in this session: Docker and
the sandbox runtime are absent. A built container image is not itself a VM;
the controller must launch it with the required micro-VM runtime.

## Replay, failure and recovery semantics

| Situation | Behavior / owner |
|---|---|
| Successful retry of the same valid grant | Same context, mandate, solver result, artifact and audit event identities; IE/controller/ledger deduplicate |
| Changed context for an existing grant | Immutable event conflict; IE must issue a new grant/snapshot identity |
| Same execution ID with different payload/seed | Controller rejects, never silently recomputes |
| `infeasible` or `search_limit` | Audited NEEDS_REVISION envelope; no spend preview |
| Unauthorized, expired or invalid grant | No execution; IE/PAB owns rejection audit |
| Audit append failure | Stop; no next side effect without receipt |
| Runtime failure or cancellation | Worker attempts a bounded failure audit; controller independently tears down and audits |
| Terminal failure already appended | Treat grant run as terminal; IE issues a new grant ID for a new attempt |
| Crash after IE commit but before final audit | Reconcile through IE's durable idempotency/outbox; do not issue duplicate spend |

The worker does not invent a new retry scheduler, lease manager, canonical state
store or ledger. IE remains responsible for those established functions.

## Live acceptance fixture

Implement an async factory in your deployment test package returning the
`tests.live_contract.LiveEnvironment` interface. Supply a real authorized test
grant, real worker bindings, a controlled test tenant and cleanup. The factory
must not import test doubles. Its methods actively probe and retain evidence of:

- Real IE -> SDK -> VM -> evidence -> durable artifact/ledger roundtrip.
- IPv4/IPv6/DNS/metadata/internal-service denial, worker SDK bypass denial,
  tmpfs/read-only-root, blocked restricted syscalls, memory isolation, absent
  secrets, resource limits, cancellation and timeout teardown.
- Ledger replay equality, conflicting replay rejection, concurrent append
  serialization, restart persistence, mutation denial and complete PROV retention.

Typed reports reject false results. The report is not a substitute for probes:
retain raw runtime inspection output and audit traces identified by `trace_hash`.

The local static import allowlist and network tripwire validate current code
paths. They cannot prevent malicious Python in a credentialed, network-enabled
host process. Actual worker network/credential isolation and authenticated RPC
boundaries must enforce that stronger security claim.
