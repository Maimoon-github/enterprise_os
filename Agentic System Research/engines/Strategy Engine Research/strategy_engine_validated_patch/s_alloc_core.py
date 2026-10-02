from __future__ import annotations
import json, math
from typing import Any


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def execute_s_alloc(payload: dict[str, Any]) -> dict[str, str]:
    task_id = str(payload.get('task_id', 'unknown'))
    tenant_id = str(payload.get('tenant_id', 'default'))
    brand_id = str(payload.get('brand_id', 'default'))
    time_horizon = str(payload.get('time_horizon', '90_days'))
    objective = str(payload.get('objective', 'balanced omnichannel planning'))

    requested_budget = max(0.0, _float(payload.get('budget', payload.get('budget_cap')), 10000.0))
    ceiling = max(0.0, _float(payload.get('budget_ceiling'), requested_budget))
    budget_total = min(requested_budget, ceiling)

    raw_channels = payload.get('channels', 'meta,google,tiktok,linkedin')
    if isinstance(raw_channels, list):
        channels = [str(x).strip().lower() for x in raw_channels if str(x).strip()]
    else:
        channels = [x.strip().lower() for x in str(raw_channels).split(',') if x.strip()]
    if not channels:
        channels = ['meta', 'google', 'tiktok']
    channels = list(dict.fromkeys(channels))

    defaults = {'meta':3.2,'google':3.8,'tiktok':2.6,'linkedin':2.1,'youtube':2.9,'email':4.5}
    media_history = _json(payload.get('media_history') or payload.get('performance_telemetry'), {})
    if not isinstance(media_history, dict):
        media_history = {}
    constraints = _json(payload.get('channel_constraints'), {})
    if not isinstance(constraints, dict):
        constraints = {}
    incrementality = _json(payload.get('incrementality_evidence'), {})
    reasoning = _json(payload.get('s_alloc_reasoning'), {})

    applied_claims = []
    claims = _json(payload.get('t16_claims') or payload.get('approved_claims'), [])
    if isinstance(claims, list):
        for item in claims:
            if isinstance(item, dict):
                text = item.get('text') or item.get('claim_text') or item.get('id')
                if text:
                    applied_claims.append(str(text))
            elif item:
                applied_claims.append(str(item))

    addressed_objections = []
    objections = _json(payload.get('t17_objections') or payload.get('objections'), [])
    if isinstance(objections, list):
        for item in objections:
            if isinstance(item, dict):
                text = item.get('theme') or item.get('objection_type') or item.get('objection_id')
                if text:
                    addressed_objections.append(str(text))
            elif item:
                addressed_objections.append(str(item))

    factored_competitor_signals = []
    comp = _json(payload.get('t18_competitor') or payload.get('competitor_signals'), {})
    competitor_threat_elevated = False
    if isinstance(comp, dict) and comp:
        name = comp.get('competitor', 'Competitor')
        threat = str(comp.get('threat_level', 'medium')).lower()
        sig = f'{name} threat: {threat}'
        if comp.get('benchmark_price') is not None:
            sig += f", benchmark price: ${comp.get('benchmark_price')}"
        factored_competitor_signals.append(sig)
        competitor_threat_elevated = threat in {'high','critical'} or comp.get('pricing_trajectory') == 'discounting_aggressive'

    priors: dict[str,float] = {}
    uncertainty: dict[str,float] = {}
    saturation: dict[str,float] = {}
    reference_spend: dict[str,float] = {}
    evidence_factor: dict[str,float] = {c:1.0 for c in channels}

    for ch in channels:
        hist = media_history.get(ch, {}) if isinstance(media_history.get(ch, {}), dict) else {}
        prior = _float(payload.get(f'prior_roas_{ch}', hist.get('roi', defaults.get(ch,2.5))), defaults.get(ch,2.5))
        priors[ch] = max(0.01, prior)
        uncertainty[ch] = max(0.0, _float(payload.get(f'prior_roas_sd_{ch}', hist.get('roas_sd', prior*0.25)), prior*0.25))
        reference_spend[ch] = max(0.0, _float(hist.get('spend'), budget_total/max(len(channels),1)))
        saturation[ch] = max(1.0, _float(payload.get(f'saturation_spend_{ch}', hist.get('saturation_spend')), max(reference_spend[ch], budget_total/max(len(channels),1), 1.0)))

    if applied_claims:
        if 'meta' in evidence_factor: evidence_factor['meta'] *= 1.10
        if 'tiktok' in evidence_factor: evidence_factor['tiktok'] *= 1.05
    if addressed_objections and 'google' in evidence_factor:
        evidence_factor['google'] *= 1.15
    if competitor_threat_elevated and 'google' in evidence_factor:
        evidence_factor['google'] *= 1.10

    def response(ch: str, spend: float) -> float:
        # Saturating planning response proxy. This is not a fitted causal MMM.
        return priors[ch] * evidence_factor[ch] * spend / (1.0 + spend / saturation[ch])

    def mroi(ch: str, spend: float) -> float:
        return priors[ch] * evidence_factor[ch] / ((1.0 + spend / saturation[ch]) ** 2)

    min_spend: dict[str,float] = {}
    max_spend: dict[str,float] = {}
    for ch in channels:
        c = constraints.get(ch, {}) if isinstance(constraints.get(ch, {}), dict) else {}
        mn = max(0.0, _float(c.get('min_spend'), 0.0))
        mx = max(0.0, _float(c.get('max_spend'), budget_total))
        if c.get('min_share') is not None:
            mn = max(mn, budget_total * max(0.0, min(1.0, _float(c.get('min_share'), 0.0))))
        if c.get('max_share') is not None:
            mx = min(mx, budget_total * max(0.0, min(1.0, _float(c.get('max_share'), 1.0))))
        max_spend[ch] = max(mn, mx)
        min_spend[ch] = min(mn, max_spend[ch])

    allocations = dict(min_spend)
    min_total = sum(allocations.values())
    warnings: list[str] = []
    if min_total > budget_total and min_total > 0:
        warnings.append('Channel minimums exceed the authorized budget; minimums were proportionally scaled to the ceiling.')
        scale = budget_total / min_total
        allocations = {ch: amount * scale for ch, amount in allocations.items()}

    remaining = max(0.0, budget_total - sum(allocations.values()))
    quantum = max(budget_total / 100.0, 0.01) if budget_total else 0.0
    while remaining > 0.005 and quantum > 0:
        eligible = [ch for ch in channels if allocations.get(ch, 0.0) + 0.005 < max_spend[ch]]
        if not eligible:
            break
        ch = max(
            eligible,
            key=lambda c: max(0.01, mroi(c, allocations.get(c, 0.0)) - 0.25 * uncertainty[c]),
        )
        room = max_spend[ch] - allocations.get(ch, 0.0)
        delta = min(remaining, quantum, room)
        if delta <= 0:
            break
        allocations[ch] = allocations.get(ch, 0.0) + delta
        remaining -= delta

    allocations = {ch: round(allocations.get(ch,0.0),2) for ch in channels}
    allocated_total = round(sum(allocations.values()),2)
    if allocated_total > budget_total and allocations:
        ch = max(allocations, key=allocations.get)
        allocations[ch] = round(max(0.0, allocations[ch] - (allocated_total-budget_total)),2)
        allocated_total = round(sum(allocations.values()),2)

    def blended_roi(allocs: dict[str,float]) -> float:
        spend = sum(allocs.values())
        return 0.0 if spend <= 0 else sum(response(ch, amount) for ch,amount in allocs.items()) / spend

    expected_blended_roas = blended_roi(allocations)
    marginal = {ch: round(mroi(ch, allocations[ch]),4) for ch in channels}
    curves = {}
    for ch in channels:
        top = max(max_spend[ch], allocations[ch], saturation[ch])
        points=[]
        for frac in (0.0,0.25,0.5,0.75,1.0):
            spend = round(top*frac,2)
            points.append({'spend':spend,'expected_incremental_kpi':round(response(ch,spend),4),'mroi':round(mroi(ch,spend),4)})
        curves[ch]=points

    roles_map = {
        'meta':'Top-of-funnel acquisition, discovery, and retargeting',
        'google':'High-intent capture and competitor defense',
        'tiktok':'Short-form discovery and social proof',
        'linkedin':'B2B consideration and authority',
        'youtube':'Video education and brand building',
        'email':'Retention and lifecycle re-engagement',
    }
    channel_objs=[]
    for ch in channels:
        pct = allocations[ch]/budget_total*100 if budget_total else 0.0
        channel_objs.append({
            'channel':ch,'allocated_amount':allocations[ch],'percentage_of_total':round(pct,1),
            'role':roles_map.get(ch,f'Omnichannel activation on {ch}'),
            'primary_kpi':'mROI / incremental KPI', 'prior_roas':priors[ch],
            'target_roas_range':[round(max(0.0,priors[ch]-uncertainty[ch]),2),round(priors[ch]+uncertainty[ch],2)],
            'constraints':[f"min=${min_spend[ch]:.2f}",f"max=${max_spend[ch]:.2f}",f"saturation=${saturation[ch]:.2f}"],
        })

    tofu_pct,mofu_pct,bofu_pct,ret_pct=(0.40,0.30,0.20,0.10) if addressed_objections else (0.45,0.25,0.20,0.10)
    stage_pcts=[('TOFU',tofu_pct),('MOFU',mofu_pct),('BOFU',bofu_pct),('RETENTION',ret_pct)]
    stage_amounts={name:round(budget_total*pct,2) for name,pct in stage_pcts}
    stage_amounts['RETENTION']=round(max(0.0,budget_total-stage_amounts['TOFU']-stage_amounts['MOFU']-stage_amounts['BOFU']),2)
    funnel=[]
    for name,pct in stage_pcts:
        mapping={'TOFU':['meta','tiktok','youtube'],'MOFU':['meta','youtube','linkedin'],'BOFU':['google','meta'],'RETENTION':['email','meta']}
        chs=[c for c in channels if c in mapping[name]] or channels[:1]
        funnel.append({'stage':name,'stage_name':name,'allocated_amount':stage_amounts[name], 'percentage_of_total':round(pct*100,1),'channels':chs,
                       'objective':{'TOFU':'Awareness and discovery','MOFU':'Consideration and education','BOFU':'Conversion and intent capture','RETENTION':'Lifecycle retention'}[name],
                       'transition_hypothesis':'Planning hypothesis; validate against observed funnel telemetry.','target_metrics':{}})

    def normalize(weights: dict[str,float]) -> dict[str,float]:
        total=sum(weights.values()) or 1.0
        return {c:round(budget_total*v/total,2) for c,v in weights.items()}
    aggressive=normalize({c:allocations[c]*(1.25 if c in {'meta','tiktok','youtube'} else 0.75) for c in channels})
    conservative=normalize({c:allocations[c]*(1.35 if c in {'google','email'} else 0.70) for c in channels})

    pref = str(reasoning.get('scenario_emphasis','')).lower() if isinstance(reasoning,dict) else ''
    if pref not in {'balanced','aggressive','conservative'}:
        low=objective.lower()
        pref='conservative' if any(x in low for x in ('efficiency','profit','roas','margin')) else ('aggressive' if any(x in low for x in ('awareness','reach','scale','growth')) else 'balanced')
    rec_id=f'scenario_{pref}'
    scenarios=[
        {'scenario_id':'scenario_balanced','scenario_name':'Balanced Omnichannel Growth','description':'Marginal-return-aware constrained allocation.','is_recommended':rec_id=='scenario_balanced','allocations_by_channel':allocations,'allocations_by_stage':stage_amounts,'expected_blended_roas':round(blended_roi(allocations),2),'risk_level':'medium','key_assumptions':['Planning response curves are proxies unless calibrated by experiments or a fitted MMM.']},
        {'scenario_id':'scenario_aggressive','scenario_name':'Aggressive Audience Scale','description':'Tilts spend toward discovery/upper-funnel channels.','is_recommended':rec_id=='scenario_aggressive','allocations_by_channel':aggressive,'allocations_by_stage':{'TOFU':round(budget_total*.60,2),'MOFU':round(budget_total*.20,2),'BOFU':round(budget_total*.15,2),'RETENTION':round(budget_total*.05,2)},'expected_blended_roas':round(blended_roi(aggressive),2),'risk_level':'high','key_assumptions':['Higher reach may encounter faster saturation and creative fatigue.']},
        {'scenario_id':'scenario_conservative','scenario_name':'Conservative Efficiency','description':'Tilts spend toward intent and retention.','is_recommended':rec_id=='scenario_conservative','allocations_by_channel':conservative,'allocations_by_stage':{'TOFU':round(budget_total*.30,2),'MOFU':round(budget_total*.25,2),'BOFU':round(budget_total*.30,2),'RETENTION':round(budget_total*.15,2)},'expected_blended_roas':round(blended_roi(conservative),2),'risk_level':'low','key_assumptions':['Lower reach is acceptable in exchange for near-term efficiency.']},
    ]

    health_reasons=['Current implementation is a deterministic response-curve planning proxy, not a fitted causal MMM.']
    if not media_history:
        health_reasons.append('No media-history/performance series supplied.')
    if not incrementality:
        health_reasons.append('No incrementality calibration supplied.')
    model_diagnostics={'measurement_mode':'deterministic_response_curve_proxy','causal_mmm':False,'health_status':'REVIEW','health_reasons':health_reasons,'incrementality_calibrated':bool(incrementality),'marginal_roas':marginal,'warnings':warnings}

    conf=0.65 + (0.05 if applied_claims else 0)+(0.05 if addressed_objections else 0)+(0.05 if factored_competitor_signals else 0)+(0.05 if media_history else 0)+(0.05 if incrementality else 0)
    conf=min(0.85,conf)
    assumptions=['Response curves use a saturating planning proxy and must not be represented as causal MMM estimates.','All budget shifts are constrained by the authorized ceiling and channel bounds.']
    if isinstance(reasoning,dict):
        assumptions.extend(str(x) for x in reasoning.get('modeling_assumptions',[]) if x)
    caveats=list(health_reasons)+['Projected ROI/mROI values are planning estimates, not guaranteed financial results.']
    constraints_text=[f'Total budget capped at ${ceiling:.2f}.',f"Channels restricted to: {', '.join(channels)}.",'No external campaign publication or spend mutation without IE/HITL authorization.']
    plan={
        'plan_id':f'strat-{task_id}','tenant_id':tenant_id,'brand_id':brand_id,'time_horizon':time_horizon,'budget_ceiling':ceiling,'total_allocated':allocated_total,'unallocated_contingency':round(max(0.0,ceiling-allocated_total),2),
        'channel_allocations':channel_objs,'funnel_stages':funnel,'scenarios':scenarios,'recommended_scenario':rec_id,
        'approved_claims_applied':applied_claims,'objections_addressed':addressed_objections,'competitor_signals_factored':factored_competitor_signals,
        'assumptions':assumptions,'constraints':constraints_text,'unsupported_estimates_or_caveats':caveats,
        'provenance':{'modeled_by':'S_ALLOC','task_id':task_id,'tenant_id':tenant_id,'model_diagnostics':model_diagnostics},
        'confidence':{'point_estimate':round(conf,2),'lower_bound':round(max(0.0,conf-.15),2),'upper_bound':round(min(1.0,conf+.10),2)},
    }
    primary=max(allocations,key=allocations.get) if allocations else 'none'
    return {'status':'success','task_id':task_id,'budget_total':str(budget_total),'allocated_total':str(allocated_total),'allocations':json.dumps(allocations),'expected_blended_roas':f'{expected_blended_roas:.2f}','primary_channel':primary,'marginal_roas':json.dumps(marginal),'response_curves':json.dumps(curves),'model_diagnostics':json.dumps(model_diagnostics),'funnel_model':json.dumps(funnel),'scenarios':json.dumps(scenarios),'strategy_plan':json.dumps(plan)}
