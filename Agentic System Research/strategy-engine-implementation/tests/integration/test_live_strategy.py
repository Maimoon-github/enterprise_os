"""Real environment acceptance gates; skips cannot satisfy production acceptance.

STRATEGY_LIVE_FACTORY=your_deployment_test_module:create_environment
The factory is async and returns tests.live_contract.LiveEnvironment. No default
or in-memory live fixture is provided; the host integration must supply one.
"""
import importlib
import os
import unittest
from tests.live_contract import DurableLedgerReport, IsolationReport

FACTORY = os.environ.get('STRATEGY_LIVE_FACTORY')


@unittest.skipUnless(FACTORY, 'Requires actual IE/PAB, agent_sandbox micro-VM controller and immutable ledger')
class LiveStrategyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        module, name = FACTORY.split(':', 1)
        if module.startswith('tests.support'):
            raise RuntimeError('test doubles are not a live deployment')
        self.env = await getattr(importlib.import_module(module), name)()

    async def asyncTearDown(self):
        await self.env.close()

    async def test_real_ie_sdk_ledger_roundtrip(self):
        envelope = await self.env.worker.execute(self.env.grant)
        self.assertTrue(await self.env.verify_stored_evidence(envelope))

    async def test_real_network_tmpfs_syscalls_and_microvm_teardown(self):
        IsolationReport.model_validate(await self.env.probe_isolation())

    async def test_real_immutable_ledger_replay_and_restart(self):
        DurableLedgerReport.model_validate(await self.env.verify_durable_ledger())
