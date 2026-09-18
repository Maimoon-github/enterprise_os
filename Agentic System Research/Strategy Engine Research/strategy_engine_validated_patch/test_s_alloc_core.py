import json
from s_alloc_core import execute_s_alloc


def test_budget_ceiling_and_constraints():
    out = execute_s_alloc({
        'budget': 20000,
        'budget_ceiling': 15000,
        'channels': 'meta,google',
        'channel_constraints': json.dumps({
            'meta': {'max_share': 0.20},
            'google': {'max_share': 0.70},
        }),
    })
    assert float(out['budget_total']) == 15000.0
    alloc = json.loads(out['allocations'])
    assert alloc['meta'] <= 3000.0
    assert alloc['google'] <= 10500.0
    assert float(out['allocated_total']) <= 15000.0


def test_saturation_changes_marginal_allocation():
    out = execute_s_alloc({
        'budget': 20000,
        'channels': 'meta,google',
        'prior_roas_meta': 3.2,
        'prior_roas_google': 4.0,
        'media_history': json.dumps({
            'google': {'spend': 20000, 'saturation_spend': 5000},
            'meta': {'spend': 1000, 'saturation_spend': 15000},
        }),
    })
    alloc = json.loads(out['allocations'])
    assert alloc['meta'] > alloc['google']
    curves = json.loads(out['response_curves'])
    assert curves['google'][0]['mroi'] > curves['google'][-1]['mroi']


def test_model_diagnostics_are_explicit():
    out = execute_s_alloc({'budget': 10000, 'channels': 'meta,google'})
    diag = json.loads(out['model_diagnostics'])
    assert diag['causal_mmm'] is False
    assert diag['health_status'] == 'REVIEW'
    assert any('not a fitted causal MMM' in item for item in diag['health_reasons'])


def test_llm_scenario_emphasis_is_advisory_but_bounded():
    out = execute_s_alloc({
        'budget': 10000,
        'channels': 'meta,google',
        's_alloc_reasoning': json.dumps({'scenario_emphasis': 'conservative'}),
    })
    plan = json.loads(out['strategy_plan'])
    assert plan['recommended_scenario'] == 'scenario_conservative'
    assert plan['total_allocated'] <= plan['budget_ceiling']


def test_no_fabricated_claim_or_competitor_evidence():
    out = execute_s_alloc({'budget': 10000, 'channels': 'meta,google'})
    plan = json.loads(out['strategy_plan'])
    assert plan['approved_claims_applied'] == []
    assert plan['competitor_signals_factored'] == []
