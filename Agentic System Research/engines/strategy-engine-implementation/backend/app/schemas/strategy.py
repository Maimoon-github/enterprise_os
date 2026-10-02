"""Strategy wire contracts. Money is integer minor units in one explicit currency.

These contracts are an integration proposal, not a copy of the unavailable host
agent_contracts/provenance schemas. Merge at the composition boundary.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Annotated, Literal
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Channel = Literal['Meta', 'Google', 'TikTok', 'LinkedIn', 'Programmatic']
Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Money = Annotated[int, Field(ge=0, le=10**12)]
PositiveMoney = Annotated[int, Field(gt=0, le=10**12)]
Number = Annotated[float, Field(ge=0, le=10**18, allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              revalidate_instances='always', validate_default=True,
                              allow_inf_nan=False)


def canonical(value: BaseModel) -> bytes:
    return json.dumps(value.model_dump(mode='json', by_alias=True),
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(value: BaseModel) -> str:
    return sha256(canonical(value)).hexdigest()


class ChannelBound(Contract):
    channel: Channel
    minimum_minor: Money
    maximum_minor: Money
    maximum_cpa_minor: PositiveMoney | None = None

    @model_validator(mode='after')
    def ordered(self):
        if self.minimum_minor > self.maximum_minor:
            raise ValueError('channel minimum exceeds maximum')
        return self


class SpendConstraints(Contract):
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    total_cap_minor: PositiveMoney
    spend_target_minor: PositiveMoney
    quantum_minor: PositiveMoney
    channel_bounds: Annotated[tuple[ChannelBound, ...], Field(min_length=1, max_length=5)]
    target_roas: Number | None = None
    maximum_cpa_minor: PositiveMoney | None = None

    @model_validator(mode='after')
    def feasible_bounds(self):
        b = self.channel_bounds
        if len({x.channel for x in b}) != len(b):
            raise ValueError('duplicate channel bound')
        if self.spend_target_minor > self.total_cap_minor:
            raise ValueError('spend target exceeds total cap')
        q = self.quantum_minor
        if self.spend_target_minor % q:
            raise ValueError('target must be a multiple of the declared quantum')
        if self.spend_target_minor // q > 1000:
            raise ValueError('at most 1000 budget quanta per mandate')
        lows = [(x.minimum_minor + q - 1) // q for x in b]
        highs = [x.maximum_minor // q for x in b]
        if any(lo > hi for lo, hi in zip(lows, highs)):
            raise ValueError('channel has no feasible grid point')
        if not sum(lows) <= self.spend_target_minor // q <= sum(highs):
            raise ValueError('spend target infeasible on declared grid')
        return self

    def attenuates(self, parent: SpendConstraints) -> bool:
        p = {x.channel: x for x in parent.channel_bounds}
        return (self.currency == parent.currency
                and self.quantum_minor == parent.quantum_minor
                and self.total_cap_minor <= parent.total_cap_minor
                and self.spend_target_minor <= parent.spend_target_minor
                and (parent.target_roas is None or
                     self.target_roas is not None and self.target_roas >= parent.target_roas)
                and (parent.maximum_cpa_minor is None or
                     self.maximum_cpa_minor is not None and self.maximum_cpa_minor <= parent.maximum_cpa_minor)
                and all(x.channel in p and x.minimum_minor >= p[x.channel].minimum_minor
                        and x.maximum_minor <= p[x.channel].maximum_minor
                        and (p[x.channel].maximum_cpa_minor is None or
                             x.maximum_cpa_minor is not None and
                             x.maximum_cpa_minor <= p[x.channel].maximum_cpa_minor)
                        for x in self.channel_bounds)
                and all(x.channel in {y.channel for y in self.channel_bounds} or
                        x.minimum_minor == 0 for x in parent.channel_bounds))


class StrategyDirective(Contract):
    directive_id: UUID
    tenant_id: UUID
    brand_id: UUID
    objective: Literal['maximize_revenue', 'maximize_conversions']
    spend: SpendConstraints
    horizon_days: Annotated[int, Field(ge=3, le=366)]


class Observation(Contract):
    period: Annotated[str, Field(pattern=r'^\d{4}-\d{2}-\d{2}$')]
    spend_minor: PositiveMoney
    revenue_minor: Money
    impressions: Annotated[int, Field(ge=0, le=10**12)]
    clicks: Annotated[int, Field(ge=0, le=10**12)]
    conversions: Annotated[int, Field(ge=0, le=10**12)]

    @model_validator(mode='after')
    def funnel_order(self):
        datetime.strptime(self.period, '%Y-%m-%d')
        if not self.conversions <= self.clicks <= self.impressions:
            raise ValueError('single-touch funnel requires conversions <= clicks <= impressions')
        return self


class ChannelData(Contract):
    channel: Channel
    observations: Annotated[tuple[Observation, ...], Field(min_length=3, max_length=104)]

    @model_validator(mode='after')
    def unique_periods(self):
        if len({x.period for x in self.observations}) != len(self.observations):
            raise ValueError('duplicate observation period')
        return self


class ContextIngestion(Contract):
    tenant_id: UUID
    brand_id: UUID
    task_id: UUID
    snapshot_id: UUID
    as_of: AwareDatetime
    valid_until: AwareDatetime
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    period_days: Annotated[int, Field(ge=1, le=366)]
    channels: Annotated[tuple[ChannelData, ...], Field(min_length=1, max_length=5)]
    evidence_hashes: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=100)]
    market_intel: Annotated[tuple[Name, ...], Field(max_length=30)] = ()
    brand_constraints: Annotated[tuple[Name, ...], Field(max_length=30)] = ()
    narrowed_spend: SpendConstraints | None = None

    @model_validator(mode='after')
    def unique_channels(self):
        if len({x.channel for x in self.channels}) != len(self.channels):
            raise ValueError('duplicate context channel')
        if self.as_of >= self.valid_until:
            raise ValueError('context validity window is empty')
        if any(datetime.strptime(row.period, '%Y-%m-%d').date() > self.as_of.date()
               for channel in self.channels for row in channel.observations):
            raise ValueError('observation period starts after the context snapshot')
        return self


class TaskGrant(Contract):
    grant_id: UUID
    task_id: UUID
    tenant_id: UUID
    brand_id: UUID
    parent_grant_id: UUID
    issuer: Literal['IE'] = 'IE'
    recipient: Literal['W_STRAT'] = 'W_STRAT'
    directive: StrategyDirective
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    token_budget: Annotated[int, Field(ge=0, le=1000000)]
    capabilities: tuple[Literal['S_ALLOC'], ...] = ('S_ALLOC',)
    seed: Annotated[int, Field(ge=0, lt=2**32)]
    max_context_requests: Literal[0, 1] = 1
    max_sandbox_calls: Literal[1] = 1
    max_runtime_seconds: Annotated[int, Field(ge=1, le=120)] = 60
    max_candidates: Annotated[int, Field(ge=1, le=200000)] = 50000
    bootstrap_samples: Annotated[int, Field(ge=20, le=500)] = 100
    authorization_ref: Name
    context: ContextIngestion | None = None

    @model_validator(mode='after')
    def scope(self):
        if (self.directive.tenant_id, self.directive.brand_id) != (self.tenant_id, self.brand_id):
            raise ValueError('directive scope mismatch')
        if self.expires_at <= self.issued_at or self.capabilities != ('S_ALLOC',):
            raise ValueError('invalid grant lifetime or capability set')
        if self.context is not None:
            validate_context(self, self.context, self.issued_at)
        return self


BoundedTaskGrant = TaskGrant


def validate_context(grant: TaskGrant, context: ContextIngestion, now: datetime) -> SpendConstraints:
    if (context.tenant_id, context.brand_id, context.task_id) != (grant.tenant_id, grant.brand_id, grant.task_id):
        raise ValueError('context scope mismatch')
    if not context.as_of <= now < context.valid_until:
        raise ValueError('context is stale or from the future')
    spend = context.narrowed_spend or grant.directive.spend
    if not spend.attenuates(grant.directive.spend):
        raise ValueError('context attempted to expand delegated authority')
    if context.currency != spend.currency or context.period_days != grant.directive.horizon_days:
        raise ValueError('currency or modeling period mismatch')
    if {x.channel for x in context.channels} != {x.channel for x in spend.channel_bounds}:
        raise ValueError('channel scope mismatch')
    return spend


class ContextRequest(Contract):
    tenant_id: UUID
    brand_id: UUID
    task_id: UUID
    grant_id: UUID
    fields: tuple[Literal['historical_performance', 'market_intel', 'brand_constraints'], ...] = (
        'historical_performance', 'market_intel', 'brand_constraints')
    access: Literal['read_only'] = 'read_only'


class AuthorizationReceipt(Contract):
    grant_hash: Digest
    tenant_id: UUID
    task_id: UUID
    valid_until: AwareDatetime
    decision: Literal['allow'] = 'allow'
    policy_version: Name


class SandboxPolicy(Contract):
    capability: Literal['S_ALLOC'] = 'S_ALLOC'
    egress: Literal['DENY_ALL'] = 'DENY_ALL'
    isolation: Literal['microvm'] = 'microvm'
    read_only_root: Literal[True] = True
    tmpfs_only: Literal[True] = True
    no_new_privileges: Literal[True] = True
    drop_all_capabilities: Literal[True] = True
    seccomp_required: Literal[True] = True
    no_host_mounts: Literal[True] = True
    no_credentials: Literal[True] = True
    destroy_after_run: Literal[True] = True
    memory_mb: Literal[256] = 256
    pids_limit: Literal[32] = 32
    timeout_seconds: Annotated[int, Field(ge=1, le=120)]
    max_output_bytes: Literal[262144] = 262144


class SandboxMandate(Contract):
    execution_id: UUID
    grant_id: UUID
    tenant_id: UUID
    brand_id: UUID
    task_id: UUID
    grant_hash: Digest
    context_hash: Digest
    seed: Annotated[int, Field(ge=0, lt=2**32)]
    directive: StrategyDirective
    context: ContextIngestion
    policy: SandboxPolicy
    max_candidates: Annotated[int, Field(ge=1, le=200000)]
    bootstrap_samples: Annotated[int, Field(ge=20, le=500)]
    delegated_token_budget: Literal[0] = 0
    operations: tuple[Literal['allocation', 'funnel', 'roadmap'], ...] = ('allocation', 'funnel', 'roadmap')

    @model_validator(mode='after')
    def scope(self):
        if (self.tenant_id, self.brand_id, self.task_id) != (
                self.context.tenant_id, self.context.brand_id, self.context.task_id):
            raise ValueError('mandate context scope mismatch')
        if (self.tenant_id, self.brand_id) != (self.directive.tenant_id, self.directive.brand_id):
            raise ValueError('mandate directive scope mismatch')
        if self.context_hash != digest(self.context):
            raise ValueError('context digest mismatch')
        if self.operations != ('allocation', 'funnel', 'roadmap'):
            raise ValueError('unsupported operation set')
        if (self.context.currency != self.directive.spend.currency or
                self.context.period_days != self.directive.horizon_days or
                {x.channel for x in self.context.channels} !=
                {x.channel for x in self.directive.spend.channel_bounds}):
            raise ValueError('mandate modeling scope mismatch')
        return self


class CurveAST(Contract):
    """Closed declarative AST: output = scale * spend / (half_saturation + spend)."""
    kind: Literal['saturation_v1'] = 'saturation_v1'
    channel: Channel
    half_saturation_minor: Annotated[float, Field(gt=0, le=10**12)]
    revenue_scale: Number
    conversion_scale: Number
    fit_rmse_minor: Number
    observations: Annotated[int, Field(ge=3, le=104)]


class ConfidenceInterval(Contract):
    metric: Literal['revenue_minor'] = 'revenue_minor'
    lower: Number
    upper: Number
    level: Literal[0.95] = 0.95
    method: Literal['conditional_bootstrap_percentile'] = 'conditional_bootstrap_percentile'
    samples: Annotated[int, Field(ge=20, le=500)]
    interpretation: Literal['observational_model_uncertainty_not_causal'] = 'observational_model_uncertainty_not_causal'

    @model_validator(mode='after')
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError('inverted confidence interval')
        return self


class ChannelAllocation(Contract):
    channel: Channel
    spend_minor: Money
    predicted_revenue_minor: Number
    predicted_conversions: Number


class AllocationPlan(Contract):
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    allocations: Annotated[tuple[ChannelAllocation, ...], Field(min_length=1, max_length=5)]
    total_spend_minor: PositiveMoney
    predicted_revenue_minor: Number
    predicted_conversions: Number
    constraints_satisfied: Literal[True] = True
    optimization_scope: Literal['global_optimum_on_declared_grid'] = 'global_optimum_on_declared_grid'

    @model_validator(mode='after')
    def totals(self):
        if len({x.channel for x in self.allocations}) != len(self.allocations):
            raise ValueError('duplicate allocation')
        if sum(x.spend_minor for x in self.allocations) != self.total_spend_minor:
            raise ValueError('allocation sum mismatch')
        for name in ('predicted_revenue_minor', 'predicted_conversions'):
            total = sum(getattr(x, name) for x in self.allocations)
            if abs(total - getattr(self, name)) > 1e-8 * max(1, total):
                raise ValueError('prediction sum mismatch')
        return self


class FunnelEstimate(Contract):
    channel: Channel
    click_through_rate: Probability
    click_to_conversion_rate: Probability
    click_drop_off_rate: Probability
    predicted_conversions: Number


class Milestone(Contract):
    phase: Literal['validate', 'learn', 'review']
    start_day: Annotated[int, Field(ge=1, le=366)]
    end_day: Annotated[int, Field(ge=1, le=366)]
    channel: Channel
    spend_minor: Money
    requires_hitl: Literal[True] = True


class SolverOutput(Contract):
    execution_id: UUID
    mandate_hash: Digest
    solver_version: Literal['s-alloc/1.0'] = 's-alloc/1.0'
    status: Literal['ok', 'infeasible', 'search_limit']
    plan: AllocationPlan | None
    curves: Annotated[tuple[CurveAST, ...], Field(max_length=5)]
    confidence_interval: ConfidenceInterval | None
    confidence_score: Probability
    funnels: Annotated[tuple[FunnelEstimate, ...], Field(max_length=5)]
    roadmap: Annotated[tuple[Milestone, ...], Field(max_length=15)]
    pareto_frontier: Annotated[tuple[AllocationPlan, ...], Field(max_length=32)]
    pareto_truncated: bool
    candidates_evaluated: Annotated[int, Field(ge=0, le=200000)]
    warnings: Annotated[tuple[Name, ...], Field(max_length=20)]

    @model_validator(mode='after')
    def outcome(self):
        if self.status == 'ok':
            if self.plan is None or self.confidence_interval is None or not self.curves:
                raise ValueError('successful result requires plan, curves and interval')
        elif self.plan is not None or self.confidence_interval is not None or self.funnels or self.roadmap or self.pareto_frontier:
            raise ValueError('incomplete search cannot publish a proposal')
        return self


class ExecutionAttestation(Contract):
    execution_id: UUID
    mandate_hash: Digest
    output_hash: Digest
    policy_hash: Digest
    image_digest: Annotated[str, Field(pattern=r'^sha256:[0-9a-f]{64}$')]
    runtime: Literal['kata', 'firecracker']
    instance_id: Name
    fresh_instance: Literal[True]
    destroyed: Literal[True]
    network_denied: Literal[True]
    tmpfs_verified: Literal[True]
    seccomp_verified: Literal[True]
    memory_limit_verified: Literal[True]
    trace_hash: Digest
    issuer: Name
    signature: Annotated[str, Field(min_length=32, max_length=4096)]


class SandboxResult(Contract):
    output: SolverOutput
    attestation: ExecutionAttestation


class StrategyPreview(Contract):
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    proposed_spend_minor: PositiveMoney
    channel_spend: tuple[ChannelAllocation, ...]
    brand_rules_for_review: tuple[Name, ...]
    review_reasons: tuple[Literal['spend', 'observational_model', 'brand_rules'], ...] = (
        'spend', 'observational_model', 'brand_rules')
    approved: Literal[False] = False
    outbound_authorized: Literal[False] = False


class StrategyData(Contract):
    result: SolverOutput
    preview: StrategyPreview | None
    proposed_state: Literal['AWAITING_REVIEW', 'NEEDS_REVISION']
    approval_required: Literal[True] = True
    tokens_consumed: Literal[0] = 0

    @model_validator(mode='after')
    def state(self):
        expected = 'AWAITING_REVIEW' if self.result.status == 'ok' else 'NEEDS_REVISION'
        if self.proposed_state != expected:
            raise ValueError('invalid proposed state for solver status')
        if self.result.plan is None:
            if self.preview is not None:
                raise ValueError('no spend preview without a feasible plan')
        elif (self.preview is None or self.preview.currency != self.result.plan.currency
              or self.preview.proposed_spend_minor != self.result.plan.total_spend_minor
              or self.preview.channel_spend != self.result.plan.allocations):
            raise ValueError('preview does not match allocation evidence')
        return self


class ProvEntity(Contract):
    id: Name
    sha256: Digest


class ProvAgent(Contract):
    id: Name
    acted_on_behalf_of: Name | None = None


class ProvActivity(Contract):
    id: Name
    activity_hash: Digest
    used: tuple[Name, ...]
    generated: tuple[Name, ...]
    was_associated_with: tuple[Name, ...]


class ProvMetadata(Contract):
    namespace: Literal['http://www.w3.org/ns/prov#'] = 'http://www.w3.org/ns/prov#'
    entities: tuple[ProvEntity, ...]
    activities: tuple[ProvActivity, ...]
    agents: tuple[ProvAgent, ...]
    seed: int
    grant_hash: Digest
    context_hash: Digest
    execution_hash: Digest

    @model_validator(mode='after')
    def references(self):
        entities = {x.id for x in self.entities}
        agents = {x.id for x in self.agents}
        ids = [x.id for x in (*self.entities, *self.activities, *self.agents)]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate PROV identifier')
        for x in self.activities:
            if not set(x.used + x.generated) <= entities or not set(x.was_associated_with) <= agents:
                raise ValueError('unresolved PROV relationship')
        if any(x.acted_on_behalf_of is not None and x.acted_on_behalf_of not in agents for x in self.agents):
            raise ValueError('unresolved delegation')
        return self


class EvidenceEnvelope(Contract):
    artifact_id: UUID
    tenant_id: UUID
    brand_id: UUID
    task_id: UUID
    grant_id: UUID
    data: StrategyData
    data_hash: Digest
    confidence_interval: ConfidenceInterval | None
    w3c_prov_metadata: ProvMetadata

    @model_validator(mode='after')
    def integrity(self):
        if digest(self.data) != self.data_hash or self.confidence_interval != self.data.result.confidence_interval:
            raise ValueError('evidence integrity mismatch')
        run_id = uuid5(NAMESPACE_URL, 'w-strat:v1:' + self.w3c_prov_metadata.grant_hash)
        if self.artifact_id != uuid5(run_id, self.data_hash):
            raise ValueError('artifact identity mismatch')
        if self.data.result.execution_id != uuid5(run_id, 'S_ALLOC'):
            raise ValueError('execution identity mismatch')
        hashes = {x.sha256 for x in self.w3c_prov_metadata.entities}
        if not {self.data_hash, digest(self.data.result), self.w3c_prov_metadata.grant_hash,
                self.w3c_prov_metadata.context_hash, self.data.result.mandate_hash} <= hashes:
            raise ValueError('evidence is not bound to provenance entities')
        if any(not x.id.startswith(f'urn:strategy:{self.tenant_id}:{run_id}:')
               for x in (*self.w3c_prov_metadata.entities, *self.w3c_prov_metadata.agents,
                         *self.w3c_prov_metadata.activities)):
            raise ValueError('provenance scope mismatch')
        return self


class FailureInfo(Contract):
    code: Literal['execution_failed', 'cancelled']


AuditPayload = TaskGrant | ContextRequest | ContextIngestion | SandboxMandate | SandboxResult | EvidenceEnvelope | FailureInfo


class AuditEvent(Contract):
    event_id: UUID
    run_id: UUID
    tenant_id: UUID
    brand_id: UUID
    task_id: UUID
    sequence: Annotated[int, Field(ge=0)]
    action: Literal['grant_received', 'context_requested', 'context_received', 'sandbox_dispatched',
                    'sandbox_received', 'proposal_created', 'submitted', 'failed']
    previous_hash: Digest | None
    payload: AuditPayload
    payload_hash: Digest
    agent: Literal['W_STRAT'] = 'W_STRAT'

    @model_validator(mode='after')
    def payload_integrity(self):
        if digest(self.payload) != self.payload_hash:
            raise ValueError('audit payload hash mismatch')
        expected = {'grant_received':TaskGrant, 'context_requested':ContextRequest,
            'context_received':ContextIngestion, 'sandbox_dispatched':SandboxMandate,
            'sandbox_received':SandboxResult, 'proposal_created':EvidenceEnvelope,
            'submitted':EvidenceEnvelope, 'failed':FailureInfo}
        if not isinstance(self.payload, expected[self.action]):
            raise ValueError('audit action/payload mismatch')
        if isinstance(self.payload, (TaskGrant, ContextRequest, ContextIngestion, SandboxMandate, EvidenceEnvelope)):
            if (self.payload.tenant_id, self.payload.brand_id, self.payload.task_id) != (self.tenant_id,self.brand_id,self.task_id):
                raise ValueError('audit payload scope mismatch')
        if self.event_id != uuid5(self.run_id, str(self.sequence)):
            raise ValueError('audit identity mismatch')
        return self

    def to_prov_jsonld(self) -> bytes:
        """Export standard PROV-O relationships; ledger stores event + this graph.

        Canonical event bytes remain the hash input. PROV describes provenance;
        append-only storage and signatures provide immutability, not PROV alone.
        """
        root = f'urn:strategy:{self.tenant_id}:{self.run_id}:'
        agent, parent = root+'W_STRAT', root+'IE'
        activity, payload = root+str(self.event_id), root+'payload:'+self.payload_hash
        graph = [
            {'@id':parent, '@type':'prov:SoftwareAgent'},
            {'@id':agent, '@type':'prov:SoftwareAgent', 'prov:actedOnBehalfOf':{'@id':parent}},
            {'@id':payload, '@type':'prov:Entity', 'ex:sha256':self.payload_hash},
            {'@id':activity, '@type':'prov:Activity', 'prov:used':{'@id':payload},
             'prov:wasAssociatedWith':[{'@id':agent},{'@id':parent}],
             'ex:action':self.action, 'ex:sha256':digest(self)},
            {'@id':root+'record-hash:'+digest(self), '@type':'prov:Entity',
             'prov:wasGeneratedBy':{'@id':activity}, 'ex:sha256':digest(self)},
        ]
        if self.previous_hash:
            graph[-1]['prov:wasDerivedFrom'] = {'@id':root+'record-hash:'+self.previous_hash}
            graph.append({'@id':root+'record-hash:'+self.previous_hash, '@type':'prov:Entity',
                          'ex:sha256':self.previous_hash})
        return json.dumps({'@context':{'prov':'http://www.w3.org/ns/prov#',
            'ex':'urn:enterprise-os:strategy:'}, '@graph':graph}, sort_keys=True,
            separators=(',', ':')).encode()


class AuditReceipt(Contract):
    event_id: UUID
    event_hash: Digest
    durable: Literal[True] = True


class SubmissionReceipt(Contract):
    artifact_id: UUID
    envelope_hash: Digest
    tenant_id: UUID
    task_id: UUID
    durable: Literal[True] = True
