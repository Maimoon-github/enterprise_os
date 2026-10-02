"""In-process integration of real worker/solver and explicit host test doubles."""
import asyncio
import unittest
from tests.support import fixture, system


class StrategyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_brand_tasks_remain_separate(self):
        a=system(*fixture('alpha'))
        b=system(*fixture('beta'))
        ea,eb=await asyncio.gather(a[0].execute(a[-1]),b[0].execute(b[-1]))
        self.assertNotEqual(ea.artifact_id,eb.artifact_id)
        self.assertNotEqual(ea.tenant_id,eb.tenant_id)
        self.assertNotEqual(ea.w3c_prov_metadata.execution_hash,eb.w3c_prov_metadata.execution_hash)
        self.assertTrue(all(x.tenant_id==ea.tenant_id for x in a[2].events))
        self.assertTrue(all(x.tenant_id==eb.tenant_id for x in b[2].events))

    async def test_infeasible_strategy_returns_revision_with_audit(self):
        g,c=fixture()
        d=g.directive.model_copy(update={'spend':g.directive.spend.model_copy(update={'target_roas':9999.0})})
        g=g.model_copy(update={'directive':d})
        w,ie,ledger,controller,_=system(g,c)
        e=await w.execute(g)
        self.assertEqual(e.data.result.status,'infeasible')
        self.assertEqual(e.data.proposed_state,'NEEDS_REVISION')
        self.assertTrue(e.data.approval_required)
        self.assertIsNone(e.data.result.plan)
        self.assertEqual(ledger.events[-1].action,'submitted')
