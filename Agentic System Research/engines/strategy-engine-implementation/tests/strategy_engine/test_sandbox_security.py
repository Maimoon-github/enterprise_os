import ast
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from app.integrations.sandbox.client import SandboxClient
from app.schemas.strategy import *
from tests.support import ROOT, system, mandate, TestController, IMAGE


def forbidden_dependencies(source):
    allowed=('app.schemas.strategy','app.agents.strategy_engine',
             'app.integrations.sandbox.s_alloc_core','app.integrations.sandbox.capabilities',
             'asyncio','datetime','uuid','typing')
    failures=[]
    for node in ast.walk(ast.parse(source)):
        modules=[]
        if isinstance(node,ast.Import): modules=[x.name for x in node.names]
        if isinstance(node,ast.ImportFrom):
            if node.level: failures.append('relative-import')
            modules=[node.module or '']
        failures.extend(x for x in modules if not any(x==a or x.startswith(a+'.') for a in allowed))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('eval','exec','compile','__import__','open'):
            failures.append(node.func.id)
    return failures


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    def test_worker_import_allowlist_model_a(self):
        for p in (ROOT/'backend/app/agents/strategy_engine').rglob('*.py'):
            self.assertEqual(forbidden_dependencies(p.read_text()),[],str(p))

    def test_static_guard_detects_forbidden_examples(self):
        for source in ('import app.persistence.repositories','from app.services.rag import controller',
                       'import socket','import httpx','from app.integrations.cms.client import Client',
                       'import subprocess','import importlib',"__import__('socket')",'eval("1+1")',
                       'from .. import persistence'):
            self.assertTrue(forbidden_dependencies(source),source)

    def test_wrapper_has_no_local_execution_fallback(self):
        for filename in ('client.py','s_alloc_core.py'):
            source=(ROOT/'backend/app/integrations/sandbox'/filename).read_text()
            tree=ast.parse(source)
            names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
            self.assertFalse(names & {'eval','exec','subprocess','importlib','solve','runpy'})
            self.assertNotIn('scripts/run.py',source)

    async def test_worker_roundtrip_attempts_no_external_network(self):
        w,*rest=system()
        # Application-level tripwire, not proof of kernel containment.
        with patch('socket.socket.connect',side_effect=AssertionError('network attempted')), \
             patch('socket.getaddrinfo',side_effect=AssertionError('DNS attempted')):
            await w.execute(rest[-1])

    def test_policy_cannot_relax_containment(self):
        p=mandate().policy
        for change in ({'egress':'ALLOW_ALL'},{'isolation':'container'},{'tmpfs_only':False},
                       {'seccomp_required':False},{'destroy_after_run':False},{'no_host_mounts':False},
                       {'read_only_root':False},{'no_credentials':False}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                SandboxPolicy.model_validate(p.model_dump() | change)

    async def test_invalid_signature_blocks_upward_evidence(self):
        w,ie,_,controller,g=system()
        controller.fail_signature=True
        with self.assertRaises(PermissionError): await w.execute(g)
        self.assertFalse(ie.envelopes)

    async def test_oversized_and_malformed_result(self):
        c=TestController()
        client=SandboxClient(c,image_digest=IMAGE)
        for value in (b'x'*262145,b'{"data":"bogus"}',b'null'):
            async def execute(_): return value
            c.execute_s_alloc=execute
            with self.assertRaises(ValueError): await client.invoke_s_alloc(mandate())

    async def test_wrong_pinned_image(self):
        c=TestController()
        client=SandboxClient(c,image_digest='sha256:'+'f'*64)
        with self.assertRaises(ValueError): await client.invoke_s_alloc(mandate())

    async def test_signed_but_overspending_result_rejected(self):
        w,ie,_,controller,g=system()
        def bad(o):
            plan=o.plan
            rows=tuple(x.model_copy(update={'spend_minor':x.spend_minor+10000}) for x in plan.allocations)
            plan=plan.model_copy(update={'allocations':rows,'total_spend_minor':30000})
            return o.model_copy(update={'plan':plan})
        controller.mutate=bad
        with self.assertRaises(ValueError): await w.execute(g)
        self.assertFalse(ie.envelopes)

    async def test_signed_roadmap_budget_tamper(self):
        w,ie,_,controller,g=system()
        controller.mutate=lambda o:o.model_copy(update={'roadmap':o.roadmap[1:]})
        with self.assertRaises(ValueError): await w.execute(g)
        self.assertFalse(ie.envelopes)

    async def test_execution_id_reuse_with_changed_seed_rejected(self):
        c=TestController()
        client=SandboxClient(c,image_digest=IMAGE)
        m=mandate()
        await client.invoke_s_alloc(m)
        with self.assertRaises(ValueError):
            await client.invoke_s_alloc(m.model_copy(update={'seed':m.seed+1}))

    async def test_timeout_rejects_late_output(self):
        c=TestController()
        c.delay=2
        client=SandboxClient(c,image_digest=IMAGE)
        m=mandate().model_copy(update={'policy':SandboxPolicy(timeout_seconds=1)})
        with self.assertRaises(TimeoutError): await client.invoke_s_alloc(m)
        self.assertFalse(c.cache)
