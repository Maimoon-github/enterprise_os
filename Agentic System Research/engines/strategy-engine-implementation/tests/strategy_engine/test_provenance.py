import json
import unittest
from app.schemas.strategy import *
from tests.support import system, uid


class ProvenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_entity_activity_agent_lineage(self):
        w,ie,ledger,controller,g=system()
        e=await w.execute(g)
        p=e.w3c_prov_metadata
        self.assertEqual(len(p.entities),5)
        self.assertEqual(len(p.activities),3)
        self.assertEqual(len(p.agents),4)
        self.assertEqual(p.grant_hash,digest(g))
        self.assertEqual(p.context_hash,digest(ie.context))
        self.assertEqual(p.seed,g.seed)
        self.assertTrue(all(x.activity_hash for x in p.activities))
        self.assertEqual([x.acted_on_behalf_of is not None for x in p.agents],[False,True,True,True])

    async def test_append_chain_and_prov_export_for_every_action(self):
        w,ie,ledger,_,g=system()
        await w.execute(g)
        previous=None
        for i,event in enumerate(ledger.events):
            self.assertEqual(event.previous_hash,previous)
            self.assertEqual(event.sequence,i)
            self.assertEqual(event.payload_hash,digest(event.payload))
            graph=json.loads(event.to_prov_jsonld())['@graph']
            self.assertTrue(any(x.get('@type')=='prov:Activity' for x in graph))
            self.assertTrue(any('prov:wasGeneratedBy' in x for x in graph))
            self.assertTrue(any('prov:actedOnBehalfOf' in x for x in graph))
            previous=digest(event)

    async def test_tamper_same_event_id_rejected(self):
        w,_,ledger,_,g=system()
        await w.execute(g)
        old=ledger.events[0]
        with self.assertRaises(ValueError):
            await ledger.append(old.model_copy(update={'brand_id':uid('tamper')}))

    async def test_unresolved_provenance_reference_rejected(self):
        w,*rest=system()
        e=await w.execute(rest[-1])
        p=e.w3c_prov_metadata
        with self.assertRaises(ValueError):
            ProvMetadata.model_validate(p.model_dump() | {'agents':p.agents[:1]})

    async def test_envelope_integrity(self):
        w,*rest=system()
        e=await w.execute(rest[-1])
        with self.assertRaises(ValueError):
            EvidenceEnvelope.model_validate(e.model_copy(update={'data_hash':'0'*64}))
