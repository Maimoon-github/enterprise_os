import json
import unittest
from datetime import timedelta
from pydantic import ValidationError
from app.schemas.strategy import *
from tests.support import fixture, mandate, NOW, uid


class ContractTests(unittest.TestCase):
    def test_roundtrip(self):
        grant, _ = fixture(injected=True)
        self.assertEqual(TaskGrant.model_validate_json(grant.model_dump_json()), grant)
        self.assertEqual(SandboxMandate.model_validate_json(mandate().model_dump_json()), mandate())

    def test_unknown_fields_and_numeric_coercion(self):
        grant, _ = fixture()
        for change in ({'token_budget': '100'}, {'seed': True}, {'db_url': 'postgres://secret'}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                TaskGrant.model_validate(grant.model_dump() | change)

    def test_frozen_and_nested_revalidation(self):
        grant, _ = fixture()
        with self.assertRaises(ValidationError):
            grant.seed = 99
        bad = grant.model_copy(update={'seed': -1})
        with self.assertRaises(ValidationError):
            TaskGrant.model_validate(bad)

    def test_scope_and_freshness(self):
        grant, context = fixture()
        for change in ({'tenant_id':uid('evil')}, {'brand_id':uid('evil')}, {'task_id':uid('evil')},
                       {'currency':'USD'}, {'period_days':7}, {'valid_until':NOW},
                       {'as_of':NOW+timedelta(minutes=1)}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_context(grant, context.model_copy(update=change), NOW)

    def test_nonfinite_and_negative(self):
        grant, _ = fixture()
        for bad in (float('nan'), float('inf'), -1.0):
            with self.assertRaises(ValidationError):
                SpendConstraints.model_validate(grant.directive.spend.model_dump() | {'target_roas':bad})

    def test_duplicate_channels(self):
        grant, _ = fixture()
        b = grant.directive.spend.channel_bounds[0]
        with self.assertRaises(ValidationError):
            SpendConstraints.model_validate(grant.directive.spend.model_dump() | {'channel_bounds':(b,b)})

    def test_lattice_infeasible(self):
        grant, _ = fixture()
        for change in ({'spend_target_minor':10001}, {'total_cap_minor':5000},
                       {'channel_bounds':(ChannelBound(channel='Meta', minimum_minor=101,maximum_minor=999),)}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                SpendConstraints.model_validate(grant.directive.spend.model_dump() | change)

    def test_attenuation(self):
        grant, context = fixture()
        parent = grant.directive.spend
        child = parent.model_copy(update={'total_cap_minor':10000})
        self.assertTrue(child.attenuates(parent))
        for change in ({'total_cap_minor':15000}, {'currency':'USD'}, {'quantum_minor':100},
                       {'channel_bounds':(ChannelBound(channel='TikTok',minimum_minor=0,maximum_minor=20000),)}):
            self.assertFalse(parent.model_copy(update=change).attenuates(parent))

    def test_removed_required_channel_and_relaxed_performance(self):
        grant, _ = fixture()
        parent = grant.directive.spend.model_copy(update={'target_roas':2.0,'maximum_cpa_minor':500})
        self.assertFalse(parent.model_copy(update={'target_roas':None}).attenuates(parent))
        self.assertFalse(parent.model_copy(update={'maximum_cpa_minor':501}).attenuates(parent))
        self.assertFalse(parent.model_copy(update={'channel_bounds':parent.channel_bounds[:1]}).attenuates(parent))

    def test_context_duplicate_period_and_impossible_funnel(self):
        _, c = fixture()
        row = c.channels[0].observations[0]
        with self.assertRaises(ValidationError):
            Observation.model_validate(row.model_dump() | {'conversions':1001})
        with self.assertRaises(ValidationError):
            ChannelData(channel='Meta', observations=(row,row,row))

    def test_no_code_or_open_ast(self):
        with self.assertRaises(ValidationError):
            SandboxMandate.model_validate(mandate().model_dump() | {'loss_function':'eval(input())'})
        with self.assertRaises(ValidationError):
            CurveAST(kind='python', channel='Meta', half_saturation_minor=2.0, revenue_scale=1.0,
                     conversion_scale=1.0, fit_rmse_minor=1.0, observations=3)
