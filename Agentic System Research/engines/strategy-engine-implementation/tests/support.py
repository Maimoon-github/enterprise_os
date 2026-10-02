"""In-memory test doubles ONLY. They do not provide production isolation/storage."""
import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import importlib.util
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.agents.strategy_engine.strategy import StrategyEngine
from app.agents.strategy_engine.subagents.allocation import AllocationSpecialist
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.s_alloc_core import SAllocCore
from app.schemas.strategy import *

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('s_alloc_unit_runtime', ROOT / 'sandbox/docker/hardened/skills/s-alloc/scripts/run.py')
solver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(solver)
NOW = datetime(2026, 9, 29, 9, tzinfo=timezone.utc)
IMAGE = 'sha256:' + 'a'*64
TEST_KEY = b'unit-test-only-not-a-controller-key'


def uid(text):
    return uuid5(NAMESPACE_URL, text)


def fixture(tenant='tenant-a', *, injected=False):
    tenant_id, brand_id, task_id = uid(tenant), uid(tenant+'-brand'), uid(tenant+'-task')
    spend = SpendConstraints(currency='PKR', total_cap_minor=12000, spend_target_minor=10000,
        quantum_minor=1000, channel_bounds=(ChannelBound(channel='Meta', minimum_minor=1000, maximum_minor=8000),
                                           ChannelBound(channel='Google', minimum_minor=1000, maximum_minor=8000)))
    directive = StrategyDirective(directive_id=uid(tenant+'-directive'), tenant_id=tenant_id, brand_id=brand_id,
                                   objective='maximize_revenue', spend=spend, horizon_days=30)
    channels = tuple(ChannelData(channel=channel, observations=tuple(
        Observation(period=f'2026-0{i+1}-01', spend_minor=s, revenue_minor=int(mult*s/(3000+s)),
                    impressions=10000, clicks=1000, conversions=int(300*s/(3000+s)))
        for i, s in enumerate((1000, 2000, 4000, 6000)))) for channel, mult in (('Meta', 60000), ('Google', 40000)))
    context = ContextIngestion(tenant_id=tenant_id, brand_id=brand_id, task_id=task_id,
        snapshot_id=uid(tenant+'-snapshot'), as_of=NOW-timedelta(hours=1), valid_until=NOW+timedelta(hours=2),
        currency='PKR', period_days=30, channels=channels, evidence_hashes=('b'*64,),
        brand_constraints=('Use only approved claims.',))
    grant = TaskGrant(grant_id=uid(tenant+'-grant'), task_id=task_id, tenant_id=tenant_id, brand_id=brand_id,
        parent_grant_id=uid(tenant+'-parent'), directive=directive, issued_at=NOW-timedelta(minutes=1),
        expires_at=NOW+timedelta(hours=1), token_budget=1000, seed=42, authorization_ref='signed-grant-reference',
        context=context if injected else None)
    return grant, context


def mandate(grant=None, context=None):
    if grant is None:
        grant, context = fixture()
    return SandboxMandate(execution_id=uid('execution'), grant_id=grant.grant_id, tenant_id=grant.tenant_id,
        brand_id=grant.brand_id, task_id=grant.task_id, grant_hash=digest(grant), context_hash=digest(context),
        seed=grant.seed, directive=grant.directive, context=context,
        policy=SandboxPolicy(timeout_seconds=60), max_candidates=grant.max_candidates,
        bootstrap_samples=grant.bootstrap_samples)


class TestController:
    """Deliberately local test double; signature demonstrates binding, not trust."""
    def __init__(self):
        self.calls = []
        self.cache = {}
        self.mutate = None
        self.fail_signature = False
        self.delay = 0

    def sign(self, attestation):
        raw = attestation.model_dump_json(exclude={'signature'}).encode()
        return hmac.new(TEST_KEY, raw, sha256).hexdigest()

    async def execute_s_alloc(self, m):
        self.calls.append(m)
        if self.delay:
            await asyncio.sleep(self.delay)
        if m.execution_id in self.cache:
            old_hash, raw = self.cache[m.execution_id]
            if old_hash != digest(m):
                raise ValueError('execution ID conflict')
            return raw
        output = solver.solve(m)
        if self.mutate:
            output = self.mutate(output)
        attestation = ExecutionAttestation(execution_id=m.execution_id, mandate_hash=digest(m),
            output_hash=digest(output), policy_hash=digest(m.policy), image_digest=IMAGE,
            runtime='kata', instance_id='test-double-no-real-vm', fresh_instance=True, destroyed=True,
            network_denied=True, tmpfs_verified=True, seccomp_verified=True, memory_limit_verified=True,
            trace_hash='c'*64, issuer='TEST_ONLY', signature='x'*64)
        attestation = attestation.model_copy(update={'signature':self.sign(attestation)})
        raw = SandboxResult(output=output, attestation=attestation).model_dump_json().encode()
        self.cache[m.execution_id] = digest(m), raw
        return raw

    def verify_attestation(self, a):
        return not self.fail_signature and hmac.compare_digest(a.signature, self.sign(a))


class TestLedger:
    def __init__(self):
        self.events = []
        self.by_id = {}
        self.head = {}
        self.fail_action = None

    async def append(self, event):
        event = AuditEvent.model_validate(event)
        if event.action == self.fail_action:
            raise OSError('test audit unavailable')
        h = digest(event)
        if event.event_id in self.by_id:
            if self.by_id[event.event_id] != h:
                raise ValueError('immutable event conflict')
        else:
            if event.previous_hash != self.head.get(event.run_id):
                raise ValueError('audit chain mismatch')
            self.by_id[event.event_id] = h
            self.head[event.run_id] = h
            self.events.append(event)
        return AuditReceipt(event_id=event.event_id, event_hash=h)


class TestIE:
    def __init__(self, grant, context):
        self.grant, self.context = grant, context
        self.requests, self.envelopes = [], []
        self.receipts = {}
        self.revoke = False

    async def authorize(self, grant):
        if self.revoke or digest(grant) != digest(self.grant):
            raise PermissionError('grant not authorized')
        return AuthorizationReceipt(grant_hash=digest(grant), tenant_id=grant.tenant_id,
            task_id=grant.task_id, valid_until=grant.expires_at, policy_version='test-policy-v1')

    async def request_context(self, request):
        self.requests.append(request)
        return self.context

    async def submit(self, envelope):
        envelope = EvidenceEnvelope.model_validate(envelope)
        key = envelope.artifact_id
        receipt = SubmissionReceipt(artifact_id=key, envelope_hash=digest(envelope),
                                    tenant_id=envelope.tenant_id, task_id=envelope.task_id)
        if key in self.receipts and self.receipts[key] != receipt:
            raise ValueError('artifact conflict')
        if key not in self.receipts:
            self.envelopes.append(envelope)
            self.receipts[key] = receipt
        return receipt


def system(grant=None, context=None):
    if grant is None:
        grant, context = fixture()
    ie, ledger, controller = TestIE(grant, context), TestLedger(), TestController()
    client = SandboxClient(controller, image_digest=IMAGE)
    worker = StrategyEngine(ie, ledger, AllocationSpecialist(SAllocCore(client)), clock=lambda: NOW)
    return worker, ie, ledger, controller, grant
