# Strategy Engine implementation package

Implemented: a typed `W_STRAT` coordinator, specialist handles, `S_ALLOC`
numerical runtime, sandbox dispatch/validation layer, provenance records,
approval previews, and automated tests.

**Validation: 61 local tests passed; 3 live acceptance tests skipped. Production
acceptance is pending.** The attachments contain architecture and file listings,
not executable repository source. No existing application was edited, deployed,
or connected to a database, IE, SDK service, or immutable ledger.

## Run the implementation tests

Use Python 3.12 and Pydantic 2.13.5:

```bash
python -m pip install pydantic==2.13.5
python tools/validate.py
```

Tests use the standard library `unittest`; pytest is optional. The command adds
`backend/` to the Python path. Production code consistently imports `app.*`.
Do not load both `app.*` and `backend.app.*` as different module identities.

Run the real deployment gates after providing host bindings:

```bash
STRATEGY_LIVE_FACTORY=your_deployment_tests:create_environment \
  python tools/validate.py --require-live
```

`--require-live` returns exit code 2 if live checks are skipped. A passing local
suite cannot silently count as production acceptance.

## What is included

```text
backend/app/
├── agents/strategy_engine/
│   ├── __init__.py
│   ├── strategy.py
│   ├── profiles.py
│   ├── ports.py
│   └── subagents/
│       ├── __init__.py
│       ├── allocation.py
│       ├── funnel.py
│       └── roadmap.py
├── schemas/strategy.py
└── integrations/sandbox/
    ├── client.py
    ├── capabilities.py
    └── s_alloc_core.py
sandbox/docker/hardened/skills/s-alloc/
├── SKILL.md
├── Dockerfile
└── scripts/run.py
tests/
├── support.py
├── live_contract.py
├── strategy_engine/
│   ├── __init__.py
│   ├── test_allocation.py
│   ├── test_contracts.py
│   ├── test_ie_roundtrip.py
│   ├── test_provenance.py
│   ├── test_runtime_cli.py
│   └── test_sandbox_security.py
└── integration/
    ├── test_strategy_integration.py
    └── test_live_strategy.py
tools/validate.py
docs/
├── DESIGN.md
├── INTEGRATION.md
├── VALIDATION.md
└── test-results.txt
pyproject.toml
TREE.txt
SHA256SUMS.txt
```

Package `__init__.py` files are also supplied for standalone imports. `TREE.txt`
lists every packaged file. `client.py` and `capabilities.py` are reference
extensions: **merge their S_ALLOC behavior into the existing files; do not
overwrite other capabilities.** The same source-level reconciliation is needed
for files already present in the supplied listings.

## Behavior

1. IE/PAB authorizes the grant, including its parent chain and tenant scope.
2. The worker records the grant through an append-only audit port.
3. The worker consumes injected context or makes one typed read-only IE request.
4. It validates tenant/brand/task, freshness, channel scope, currency, modeling
   period, spend limits and monotonic attenuation.
5. It rechecks authorization and dispatches one mandate through
   `SAllocCore -> app.integrations.sandbox.client.SandboxClient -> existing
   agent_sandbox controller`. The mandate uses capability `S_ALLOC`.
6. The sandbox performs curve fitting, constrained budget enumeration,
   bootstrapping, funnel calculations and roadmap calculations.
7. The wrapper verifies the controller signature, execution/request/output/policy
   hashes and pinned image, then validates allocations and roadmap invariants.
8. The worker creates a verified `EvidenceEnvelope`, immutable provenance
   identifiers, and an unapproved spend preview. It audits the proposal,
   reauthorizes, submits to IE, checks the durable receipt and audits submission.

No LLM call is required for this deterministic baseline. Token use is zero,
within the grant's budget. `profiles.py` supplies domain/persona boundaries for
future model-assisted orchestration; it does not grant authority. Funnel and
roadmap files are host-side typed handles; their numerical implementations run
inside `S_ALLOC`, not in the worker process.

## Important limits

- The allocator is an exact optimizer **on the explicitly declared discrete
  budget grid**, using a fitted observational saturation model. It is not a
  causal MMM, continuous global optimizer, or guaranteed performance forecast.
- All money is integer minor units in one declared currency. No implicit FX or
  currency conversion takes place.
- `infeasible` means no plan satisfies modeled ROAS/CPA constraints on that
  grid. `search_limit` means the bounded search was incomplete. Neither returns
  a spend proposal.
- Confidence intervals quantify conditional bootstrap uncertainty only.
  `confidence_score` is a disclosed sample-support heuristic.
- Brand rules expressed as text appear in the review preview. IE must translate
  enforceable budget rules to typed `narrowed_spend`; text is never executable.
- The roadmap uses three duration-weighted phases. It is a planning template,
  not a learned scheduling policy, and performs no external scheduling.
- Host authentication, actual SDK compatibility, micro-VM provisioning,
  kernel network/syscall isolation, controller signatures, durable idempotency,
  and immutable ledger storage must be bound and tested in the actual repository.

Read [INTEGRATION.md](docs/INTEGRATION.md) before merging and
[VALIDATION.md](docs/VALIDATION.md) for the exact acceptance status.
