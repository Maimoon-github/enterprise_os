import asyncio
from datetime import timedelta
import unittest
from app.agents.strategy_engine.strategy import StrategyEngine
from app.agents.strategy_engine.subagents.allocation import AllocationSpecialist
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.s_alloc_core import SAllocCore
from app.schemas.strategy import *
from tests.support import fixture, system, NOW, IMAGE, uid


class RoundtripTests(unittest.IsolatedAsyncioTestCase):
    async def test_ie_grant_context_dispatch_evidence(self):
        worker,ie,ledger,controller,g=system()
        e=await worker.execute(g)
        self.assertEqual(e.data.proposed_state,'AWAITING_REVIEW')
        self.assertEqual(len(ie.requests),1)
        self.assertEqual(ie.requests[0].access,'read_only')
        self.assertEqual(len(controller.calls),1)
        self.assertEqual(controller.calls[0].policy.capability,'S_ALLOC')
        self.assertEqual(controller.calls[0].policy.egress,'DENY_ALL')
        self.assertEqual(ie.envelopes,[e])
        self.assertEqual([x.action for x in ledger.events],['grant_received','context_requested','context_received',
            'sandbox_dispatched','sandbox_received','proposal_created','submitted'])
        self.assertEqual(EvidenceEnvelope.model_validate_json(e.model_dump_json()),e)

    async def test_injected_context_no_fetch(self):
        g,c=fixture(injected=True)
        worker,ie,_,controller,_=system(g,c)
        await worker.execute(g)
        self.assertEqual(ie.requests,[])
        self.assertEqual(len(controller.calls),1)

    async def test_zero_token_budget_is_allowed_no_llm_used(self):
        g,c=fixture()
        g=g.model_copy(update={'token_budget':0})
        worker,*_=system(g,c)
        e=await worker.execute(g)
        self.assertEqual(e.data.tokens_consumed,0)

    async def test_no_context_budget_stops_before_dispatch(self):
        g,c=fixture()
        g=g.model_copy(update={'max_context_requests':0})
        w,ie,ledger,controller,_=system(g,c)
        with self.assertRaises(PermissionError): await w.execute(g)
        self.assertFalse(controller.calls)
        self.assertFalse(ie.requests)
        self.assertEqual(ledger.events[-1].action,'failed')

    async def test_wrong_tenant_context_stops_before_dispatch(self):
        w,ie,ledger,controller,g=system()
        ie.context=ie.context.model_copy(update={'tenant_id':uid('attacker')})
        with self.assertRaises(ValueError): await w.execute(g)
        self.assertFalse(controller.calls)
        self.assertFalse(ie.envelopes)

    async def test_expired_grant_or_revocation(self):
        g,c=fixture()
        g=g.model_copy(update={'issued_at':NOW-timedelta(hours=2),'expires_at':NOW-timedelta(hours=1)})
        w,ie,ledger,controller,_=system(g,c)
        with self.assertRaises(PermissionError): await w.execute(g)
        self.assertFalse(controller.calls)
        w,ie,_,controller,g=system()
        ie.revoke=True
        with self.assertRaises(PermissionError): await w.execute(g)
        self.assertFalse(controller.calls)

    async def test_revocation_after_context(self):
        w,ie,ledger,controller,g=system()
        original=ie.request_context
        async def revoke(request):
            c=await original(request)
            ie.revoke=True
            return c
        ie.request_context=revoke
        with self.assertRaises(PermissionError): await w.execute(g)
        self.assertFalse(controller.calls)

    async def test_budget_narrowing(self):
        w,ie,_,controller,g=system()
        narrow=g.directive.spend.model_copy(update={'spend_target_minor':8000,'total_cap_minor':8000})
        ie.context=ie.context.model_copy(update={'narrowed_spend':narrow})
        e=await w.execute(g)
        self.assertEqual(e.data.result.plan.total_spend_minor,8000)

    async def test_audit_failure_prevents_dispatch(self):
        w,ie,ledger,controller,g=system()
        ledger.fail_action='sandbox_dispatched'
        with self.assertRaises(OSError): await w.execute(g)
        self.assertFalse(controller.calls)
        self.assertFalse(ie.envelopes)

    async def test_proposal_audit_failure_prevents_submission(self):
        w,ie,ledger,controller,g=system()
        ledger.fail_action='proposal_created'
        with self.assertRaises(OSError): await w.execute(g)
        self.assertFalse(ie.envelopes)

    async def test_replay_deduplicates_artifacts_and_events(self):
        w,ie,ledger,controller,g=system()
        a=await w.execute(g)
        count=len(ledger.events)
        b=await w.execute(g)
        self.assertEqual(a,b)
        self.assertEqual(len(ledger.events),count)
        self.assertEqual(len(ie.envelopes),1)
        self.assertEqual(len(controller.cache),1)

    async def test_search_limit_is_upward_revision_not_plan(self):
        g,c=fixture()
        g=g.model_copy(update={'max_candidates':1})
        w,*_=system(g,c)
        e=await w.execute(g)
        self.assertEqual(e.data.proposed_state,'NEEDS_REVISION')
        self.assertIsNone(e.confidence_interval)
        self.assertIsNone(e.data.result.plan)

    async def test_cancellation_records_failure(self):
        w,ie,ledger,controller,g=system()
        controller.delay=1
        task=asyncio.create_task(w.execute(g))
        for _ in range(100):
            if controller.calls: break
            await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(ledger.events[-1].payload.code,'cancelled')
        self.assertFalse(ie.envelopes)

    async def test_changed_retry_context_is_immutable_conflict(self):
        w,ie,ledger,controller,g=system()
        await w.execute(g)
        ie.context=ie.context.model_copy(update={'snapshot_id':uid('changed')})
        with self.assertRaises(ValueError): await w.execute(g)
        self.assertEqual(len(controller.calls),1)

    async def test_invalid_receipt_not_accepted(self):
        w,ie,ledger,controller,g=system()
        async def wrong(e):
            return SubmissionReceipt(artifact_id=e.artifact_id,envelope_hash='a'*64,
                                     tenant_id=e.tenant_id,task_id=e.task_id)
        ie.submit=wrong
        with self.assertRaises(ValueError): await w.execute(g)

    async def test_expiry_budget_is_not_silently_extended(self):
        g,c=fixture()
        g=g.model_copy(update={'expires_at':NOW+timedelta(seconds=20)})
        w,ie,_,controller,_=system(g,c)
        with self.assertRaises(PermissionError): await w.execute(g)
        self.assertFalse(controller.calls)

    async def test_revocation_during_audit_blocks_submission(self):
        w,ie,ledger,_,g=system()
        append=ledger.append
        async def revoke(event):
            receipt=await append(event)
            if event.action=='proposal_created': ie.revoke=True
            return receipt
        ledger.append=revoke
        with self.assertRaises(PermissionError): await w.execute(g)
        self.assertFalse(ie.envelopes)

    async def test_preview_never_authorizes_spend(self):
        w,ie,_,_,g=system()
        e=await w.execute(g)
        self.assertFalse(e.data.preview.approved)
        self.assertFalse(e.data.preview.outbound_authorized)
        self.assertEqual(e.data.preview.brand_rules_for_review,ie.context.brand_constraints)
