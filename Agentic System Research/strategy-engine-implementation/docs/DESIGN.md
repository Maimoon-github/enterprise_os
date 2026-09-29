# Design and source traceability

## Source inspection

The six supplied attachments were inspected locally:

| Attachment | Design evidence |
|---|---|
| Backend Hierarchy(20260929-090751).md | IE mediation, existing sandbox wrapper, capability map, service-owned audit and state |
| Final-Level Full Architecture(20260929-090751).md | Model A, bounded grants, downward authority, upward evidence, sandbox-only specialist computation, universal persistence |
| flowchart.drawio(20260929-090752).html | Matching IE/grant/evidence buses, W_STRAT-to-S_ALLOC edge, sandbox security and audit boundary |
| File Tree-backend(20260929-090804).tree | Existing strategy package, base.py, schemas, sandbox client/core/policy seams |
| File Tree-enterprise_os(20260929-090804).tree | Existing backend and sandbox layout, earlier strategy research and test locations |
| File Tree-sandbox(20260929-090804).tree | Existing hardened skills/s-alloc/scripts/run.py and sandbox hardening locations |

Listings establish paths, not function signatures or implementation behavior.
The apparent earlier patch and research reports mentioned in a tree were not
supplied as source and are not treated as inspected code. This package follows
the user's requested root `tests/` layout; the listing's existing tests are
under `backend/tests/`. Reconcile discovery in the actual repository.

## Data-flow contracts

| Edge | Typed contract | Enforcement |
|---|---|---|
| IE -> W_STRAT | TaskGrant / BoundedTaskGrant, StrategyDirective | Strict Pydantic model, signed-grant authorization port, tenant/brand/task match, expiry, capability allowlist |
| W_STRAT -> IE | ContextRequest | Literal read_only, fixed field allowlist, at most one fetch, no arbitrary SQL/URI/query |
| IE -> W_STRAT | ContextIngestion | Same scope, validity window, distinct channel histories, period/currency agreement, narrowed spend only |
| W_STRAT -> S_ALLOC | SandboxMandate | One S_ALLOC call, no arbitrary source/loss code, zero delegated tokens, fixed operations, explicit limits |
| S_ALLOC -> W_STRAT | SandboxResult / SolverOutput / ExecutionAttestation | Bounded bytes, strict schema, trusted signature, hash and image binding, independent spend/roadmap checks |
| W_STRAT -> IE | EvidenceEnvelope / StrategyData / StrategyPreview | Deterministic artifact identity, provenance binding, no outbound authority, receipt verification |
| W_STRAT -> audit service -> ledger | AuditEvent / AuditReceipt | Full payload retention, deterministic IDs, previous-hash chain, append acknowledgment before progression |

The audit port is the explicit append-only edge allowed by the user's matrix;
it does not expose a repository or general read/write storage API. IE owns
artifact persistence and canonical state decisions. Proposed state values are
`AWAITING_REVIEW` and `NEEDS_REVISION`; map them to existing CTS proposals, not
direct state mutations. HITL and outbound actuation remain outside W_STRAT.

## Numerical model

For a channel, take the median observed spend `h` as a fixed half-saturation
parameter. Fit nonnegative revenue and conversion scales independently by
least squares through the origin using `f(s) = s / (h + s)`. All observations
must represent the same number of days as the directive's planning horizon.
The serialized `CurveAST` is a closed saturation expression, not Python source.

Enumerate all budget vectors satisfying the exact target and inward-rounded
channel bounds on a declared integer grid. Check global target ROAS, global CPA
and optional per-channel CPA against model predictions. Maximize revenue or
conversions as directed; break ties using the secondary metric and stable
lexical channel order. Keep nondominated revenue/conversion plans, returning
at most 32 with an explicit truncation flag. Stop without publishing a plan
if the candidate limit or 512-point working frontier limit is exceeded.

For uncertainty, resample channel observations with the grant seed, holding
half-saturation and selected allocation fixed. Return the interpolated 2.5th
and 97.5th percentiles of predicted revenue. This excludes allocation-selection,
model-selection, temporal dependence and causal uncertainty. No causal lift or
incrementality claim is made. Three observations is a schema minimum, not a
claim of adequate statistical support. Score = min(channel sample count)/30,
capped at 1, explicitly labeled a heuristic in every output.

Funnel estimates use aggregate clicks/impressions and conversions/clicks under
a single-touch funnel assumption. The roadmap splits each channel allocation
over three contiguous duration-weighted phases, using exact integer remainders
to preserve the total. Each milestone requires human approval.

## Explicit implementation choices

These values are bounded design choices, not values asserted by the attachments:

- 1–5 channels; named Meta, Google, TikTok, LinkedIn, Programmatic.
- 3–104 observations per channel; a 3–366 day common horizon.
- At most 1,000 budget quanta, 200,000 candidate evaluations and 500 bootstrap
  samples; grant defaults are 50,000 candidates and 100 samples.
- 256 MiB RAM, 32 PIDs, 120-second maximum sandbox timeout, 512 KiB solver input
  and 256 KiB complete sandbox output. Actual resource enforcement belongs to
  the trusted controller. An outer timeout bounds the worker by grant expiry.
- CPython 3.12 / Pydantic 2.13.5 for local validation. Pin the complete production
  image and dependency lock for cross-host reproducibility.
- No LLM dependency, dynamic code execution or arbitrary objective expression.

## Trust and provenance

Hashes bind canonical sorted compact JSON bytes. They are not authorization or
signatures. PAB verifies the original grant chain, brand ownership and policy;
the trusted sandbox controller signs its execution attestation; the audit
service commits append-only records. The worker fails closed without these
acknowledgments. Test doubles demonstrate the expected contracts only.

Each accepted action retains its full typed payload and exports standard
PROV-O Entity/Activity/SoftwareAgent, used, wasGeneratedBy, wasAssociatedWith,
actedOnBehalfOf and wasDerivedFrom relations. The evidence graph binds grant,
context, mandate, output and strategy-data entities, plus delegation, execution
and synthesis activities. Model parameters and seed are retained in the
audited mandate/output. The host ledger stamps real receipt/execution times;
wall-clock timestamps are not mixed into deterministic event IDs.

PROV is a provenance representation, not an immutable storage technology. The
actual ledger must enforce uniqueness, concurrency, retention and tamper
resistance. The parent authority node in the envelope describes the chain
verified by PAB; W_STRAT itself does not authenticate the Brand Owner.

## Primary technical references checked

- [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/):
  strict validation; JSON has intentional representation exceptions for types
  such as UUID/datetime. Models also forbid extra keys and revalidate instances.
- [W3C PROV-O](https://www.w3.org/TR/prov-o/): entity/activity/agent and delegation
  relationships used in the JSON-LD export.
- [AIO Sandbox repository](https://github.com/agent-infra/sandbox): SDK and Docker
  service boundary. Its quick-start Docker command is not evidence that
  micro-VM, deny-all egress or the required seccomp policy is enforced.
- [Docker seccomp](https://docs.docker.com/engine/security/seccomp) and
  [container run](https://docs.docker.com/reference/cli/docker/container/run):
  runtime controls must be applied by deployment, not inferred from a manifest.
