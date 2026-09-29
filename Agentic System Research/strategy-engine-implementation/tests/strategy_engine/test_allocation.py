import itertools
import random
import unittest
from app.schemas.strategy import *
from app.integrations.sandbox.s_alloc_core import verify_output
from tests.support import fixture, mandate, solver


class AllocationTests(unittest.TestCase):
    def test_grid_global_optimum_against_independent_oracle(self):
        m = mandate()
        o = solver.solve(m)
        self.assertEqual(o.status, 'ok')
        # Independent exhaustive reference over the two-channel lattice.
        curves = {c.channel:c for c in o.curves}
        scored = []
        for meta in range(1000,8001,1000):
            google = 10000-meta
            if 1000 <= google <= 8000:
                value = sum(curves[ch].revenue_scale*s/(curves[ch].half_saturation_minor+s)
                            for ch,s in (('Meta',meta),('Google',google)))
                scored.append(value)
        self.assertAlmostEqual(o.plan.predicted_revenue_minor, max(scored))
        self.assertEqual(o.plan.total_spend_minor,10000)

    def test_five_channel_bounds_and_exact_money(self):
        g,c = fixture()
        channels = ('Meta','Google','TikTok','LinkedIn','Programmatic')
        spend = g.directive.spend.model_copy(update={'channel_bounds':tuple(
            ChannelBound(channel=x,minimum_minor=1000,maximum_minor=4000) for x in channels)})
        g=g.model_copy(update={'directive':g.directive.model_copy(update={'spend':spend})})
        c=c.model_copy(update={'channels':tuple(c.channels[0].model_copy(update={'channel':x}) for x in channels)})
        o=solver.solve(mandate(g,c))
        self.assertEqual(o.status,'ok')
        self.assertEqual(sum(x.spend_minor for x in o.plan.allocations),10000)
        self.assertTrue(all(1000<=x.spend_minor<=4000 for x in o.plan.allocations))

    def test_seeded_determinism_and_seed_sensitivity(self):
        m=mandate()
        first=solver.solve(m)
        self.assertEqual(canonical(first),canonical(solver.solve(m)))
        changed=solver.solve(m.model_copy(update={'seed':43}))
        self.assertEqual(first.plan,changed.plan)
        self.assertNotEqual(first.confidence_interval,changed.confidence_interval)

    def test_performance_infeasibility_and_search_limit(self):
        m=mandate()
        for change in ({'target_roas':10000.0}, {'maximum_cpa_minor':1},
                       {'channel_bounds':tuple(x.model_copy(update={'maximum_cpa_minor':1}) for x in m.directive.spend.channel_bounds)}):
            d=m.directive.model_copy(update={'spend':m.directive.spend.model_copy(update=change)})
            o=solver.solve(m.model_copy(update={'directive':d}))
            self.assertEqual(o.status,'infeasible')
            self.assertIsNone(o.plan)
        o=solver.solve(m.model_copy(update={'max_candidates':1}))
        self.assertEqual(o.status,'search_limit')
        self.assertEqual(o.candidates_evaluated,1)
        self.assertIsNone(o.plan)

    def test_limit_exactly_at_search_size_is_success(self):
        m=mandate()
        n=solver.solve(m).candidates_evaluated
        self.assertEqual(solver.solve(m.model_copy(update={'max_candidates':n})).status,'ok')

    def test_grid_rounds_inward_not_past_bounds(self):
        m=mandate()
        b=(ChannelBound(channel='Meta',minimum_minor=1100,maximum_minor=7900),
           ChannelBound(channel='Google',minimum_minor=1100,maximum_minor=7900))
        d=m.directive.model_copy(update={'spend':m.directive.spend.model_copy(update={'channel_bounds':b})})
        o=solver.solve(m.model_copy(update={'directive':d}))
        self.assertTrue(all(2000<=x.spend_minor<=7000 for x in o.plan.allocations))

    def test_randomized_spend_invariants(self):
        rng=random.Random(731)
        for _ in range(40):
            m=mandate()
            low=rng.randrange(0,5)*1000
            b=tuple(ChannelBound(channel=x,minimum_minor=low,maximum_minor=10000-low) for x in ('Meta','Google'))
            d=m.directive.model_copy(update={'spend':m.directive.spend.model_copy(update={'channel_bounds':b})})
            o=solver.solve(m.model_copy(update={'directive':d,'bootstrap_samples':20}))
            self.assertEqual(o.status,'ok')
            self.assertEqual(sum(x.spend_minor for x in o.plan.allocations),10000)
            self.assertTrue(all(low<=x.spend_minor<=10000-low for x in o.plan.allocations))

    def test_zero_conversion_is_not_division_by_zero(self):
        g,c=fixture()
        channels=tuple(x.model_copy(update={'observations':tuple(y.model_copy(update={'conversions':0,'clicks':0,'impressions':0}) for y in x.observations)}) for x in c.channels)
        c=c.model_copy(update={'channels':channels})
        o=solver.solve(mandate(g,c))
        self.assertEqual(o.plan.predicted_conversions,0.0)
        self.assertTrue(all(x.click_through_rate==0.0 for x in o.funnels))

    def test_roadmap_budget_and_contiguity(self):
        m=mandate()
        for days in (3,4,30,31,366):
            c=m.context.model_copy(update={'period_days':days})
            d=m.directive.model_copy(update={'horizon_days':days})
            o=solver.solve(m.model_copy(update={'directive':d,'context':c,'context_hash':digest(c)}))
            for a in o.plan.allocations:
                rows=[x for x in o.roadmap if x.channel==a.channel]
                self.assertEqual(sum(x.spend_minor for x in rows),a.spend_minor)
                self.assertEqual(rows[0].start_day,1)
                self.assertEqual(rows[-1].end_day,days)
                self.assertTrue(all(a.end_day+1==b.start_day for a,b in zip(rows,rows[1:])))

    def test_pareto_points_are_nondominated(self):
        o=solver.solve(mandate())
        for a,b in itertools.permutations(o.pareto_frontier,2):
            self.assertFalse(a.predicted_revenue_minor>=b.predicted_revenue_minor and
                             a.predicted_conversions>=b.predicted_conversions)
