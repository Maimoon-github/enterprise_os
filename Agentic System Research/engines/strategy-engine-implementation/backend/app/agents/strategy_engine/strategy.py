"""W_STRAT worker interface: IE -> bounded sandbox -> evidence -> IE.

Canonical state, auth, persistence, retries/leases and HITL remain with IE.
An instance holds no per-task mutable state, so tenant executions can overlap.
"""
import asyncio
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.agents.strategy_engine.ports import AuditPort, Clock, IntelligenceEnginePort
from app.agents.strategy_engine.subagents.allocation import AllocationSpecialist
from app.agents.strategy_engine.subagents.funnel import FunnelSpecialist
from app.agents.strategy_engine.subagents.roadmap import RoadmapSpecialist
from app.integrations.sandbox.capabilities import s_alloc_policy
from app.schemas.strategy import (AuditEvent, AuditPayload, AuditReceipt, AuthorizationReceipt,
    ContextIngestion, ContextRequest, EvidenceEnvelope, FailureInfo, ProvActivity, ProvAgent,
    ProvEntity, ProvMetadata, SandboxMandate, StrategyData, StrategyPreview, SubmissionReceipt, TaskGrant,
    digest, validate_context)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StrategyEngine:
    worker_id = 'W_STRAT'

    def __init__(self, ie: IntelligenceEnginePort, audit: AuditPort,
                 allocation: AllocationSpecialist, *, clock: Clock = utcnow):
        self._ie, self._audit, self._allocation, self._clock = ie, audit, allocation, clock

    async def _authorize(self, grant: TaskGrant) -> None:
        now = self._clock()
        if not grant.issued_at <= now < grant.expires_at:
            raise PermissionError('grant expired or not yet active')
        receipt = AuthorizationReceipt.model_validate(await self._ie.authorize(grant))
        now = self._clock()
        if (receipt.grant_hash != digest(grant) or receipt.tenant_id != grant.tenant_id
                or receipt.task_id != grant.task_id or not now < receipt.valid_until <= grant.expires_at):
            raise PermissionError('IE authorization receipt mismatch')

    async def execute(self, grant: TaskGrant) -> EvidenceEnvelope:
        grant = TaskGrant.model_validate(grant)
        remaining = (grant.expires_at - self._clock()).total_seconds()
        if remaining <= 0:
            raise PermissionError('grant expired')
        async with asyncio.timeout(remaining):
            return await self._execute(grant)

    async def _execute(self, grant: TaskGrant) -> EvidenceEnvelope:
        await self._authorize(grant)
        run_id = uuid5(NAMESPACE_URL, 'w-strat:v1:' + digest(grant))
        sequence = 0
        previous_hash = None

        async def record(action: str, payload: AuditPayload) -> None:
            nonlocal sequence, previous_hash
            event = AuditEvent(event_id=uuid5(run_id, str(sequence)), run_id=run_id,
                tenant_id=grant.tenant_id, brand_id=grant.brand_id, task_id=grant.task_id,
                sequence=sequence, action=action, previous_hash=previous_hash,
                payload=payload, payload_hash=digest(payload))
            receipt = AuditReceipt.model_validate(await self._audit.append(event))
            if receipt.event_id != event.event_id or receipt.event_hash != digest(event):
                raise ValueError('audit receipt binding mismatch')
            previous_hash, sequence = digest(event), sequence + 1

        await record('grant_received', grant)
        try:
            context = grant.context
            if context is None:
                if grant.max_context_requests == 0:
                    raise PermissionError('context request budget exhausted')
                request = ContextRequest(tenant_id=grant.tenant_id, brand_id=grant.brand_id,
                                         task_id=grant.task_id, grant_id=grant.grant_id)
                await record('context_requested', request)
                context = ContextIngestion.model_validate(await self._ie.request_context(request))
            spend = validate_context(grant, context, self._clock())
            await record('context_received', context)
            await self._authorize(grant)  # revocation/TOCTOU check before dispatch
            directive = grant.directive.model_copy(update={'spend': spend})
            remaining = int((grant.expires_at - self._clock()).total_seconds())
            if remaining < 1:
                raise PermissionError('grant has insufficient runtime left')
            # Fixed granted timeout keeps request hashes stable on retries. Reject
            # near-expiry dispatch rather than silently changing mandate identity.
            if remaining < grant.max_runtime_seconds:
                raise PermissionError('grant expires before execution deadline')
            mandate = SandboxMandate(execution_id=uuid5(run_id, 'S_ALLOC'), grant_id=grant.grant_id,
                tenant_id=grant.tenant_id, brand_id=grant.brand_id, task_id=grant.task_id,
                grant_hash=digest(grant), context_hash=digest(context), seed=grant.seed,
                directive=directive, context=context, policy=s_alloc_policy(grant.max_runtime_seconds),
                max_candidates=grant.max_candidates, bootstrap_samples=grant.bootstrap_samples)
            await record('sandbox_dispatched', mandate)
            result = await self._allocation.execute(mandate)
            await record('sandbox_received', result)
            validate_context(grant, context, self._clock())
            await self._authorize(grant)
            FunnelSpecialist.receive(result.output)
            RoadmapSpecialist.receive(result.output)
            plan = result.output.plan
            preview = StrategyPreview(currency=plan.currency, proposed_spend_minor=plan.total_spend_minor,
                channel_spend=plan.allocations, brand_rules_for_review=context.brand_constraints) if plan else None
            data = StrategyData(result=result.output, preview=preview,
                proposed_state='AWAITING_REVIEW' if result.output.status == 'ok' else 'NEEDS_REVISION')
            artifact_id = uuid5(run_id, digest(data))
            prefix = f'urn:strategy:{grant.tenant_id}:{run_id}:'
            e_grant, e_context, e_mandate, e_output, e_data = (
                prefix + x for x in ('grant', 'context', 'mandate', 'output', str(artifact_id)))
            owner, ie, worker, specialist = (prefix + x for x in ('owner', 'IE', 'W_STRAT', 'S_ALLOC'))
            metadata = ProvMetadata(
                entities=(ProvEntity(id=e_grant, sha256=digest(grant)),
                    ProvEntity(id=e_context, sha256=digest(context)),
                    ProvEntity(id=e_mandate, sha256=digest(mandate)),
                    ProvEntity(id=e_output, sha256=digest(result.output)),
                    ProvEntity(id=e_data, sha256=digest(data))),
                activities=(
                    ProvActivity(id=prefix+'delegate', activity_hash=digest(mandate),
                        used=(e_grant, e_context), generated=(e_mandate,), was_associated_with=(owner, ie, worker)),
                    ProvActivity(id=prefix+'execute', activity_hash=digest(result),
                        used=(e_mandate,), generated=(e_output,), was_associated_with=(worker, specialist)),
                    ProvActivity(id=prefix+'synthesize', activity_hash=digest(data),
                        used=(e_output,), generated=(e_data,), was_associated_with=(ie, worker))),
                agents=(ProvAgent(id=owner), ProvAgent(id=ie, acted_on_behalf_of=owner),
                    ProvAgent(id=worker, acted_on_behalf_of=ie), ProvAgent(id=specialist, acted_on_behalf_of=worker)),
                seed=grant.seed, grant_hash=digest(grant), context_hash=digest(context), execution_hash=digest(result))
            envelope = EvidenceEnvelope(artifact_id=artifact_id, tenant_id=grant.tenant_id,
                brand_id=grant.brand_id, task_id=grant.task_id, grant_id=grant.grant_id,
                data=data, data_hash=digest(data), confidence_interval=result.output.confidence_interval,
                w3c_prov_metadata=metadata)
            await record('proposal_created', envelope)
            await self._authorize(grant)  # audit latency must not bypass revocation
            receipt = SubmissionReceipt.model_validate(await self._ie.submit(envelope))
            if (receipt.artifact_id != artifact_id or receipt.envelope_hash != digest(envelope)
                    or receipt.tenant_id != grant.tenant_id or receipt.task_id != grant.task_id):
                raise ValueError('IE submission receipt mismatch')
            await record('submitted', envelope)
            return envelope
        except BaseException as exc:
            # Cancellation is recorded without leaking exception text/data. The
            # controller owns teardown and execution traces even if this process dies.
            if isinstance(exc, (Exception, asyncio.CancelledError)):
                try:
                    async with asyncio.timeout(5):
                        await record('failed', FailureInfo(code='cancelled' if isinstance(exc, asyncio.CancelledError) else 'execution_failed'))
                except Exception as audit_error:
                    exc.add_note('Failure audit append was not acknowledged: ' + type(audit_error).__name__)
            raise


W_STRAT = StrategyEngine
