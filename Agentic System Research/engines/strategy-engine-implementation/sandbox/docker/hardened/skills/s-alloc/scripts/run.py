#!/usr/bin/env python3
"""S_ALLOC pure deterministic numerical runtime, installed only in the VM image.

Production imports/calls to this module from worker code are prohibited. The CLI
reads one size-bounded JSON mandate and emits one typed result; no code strings,
files, URLs, credentials, eval, subprocesses or external models are accepted.
"""
from __future__ import annotations

import math
import random
import statistics
import sys

from app.schemas.strategy import (AllocationPlan, ChannelAllocation, ChannelData,
    ConfidenceInterval, CurveAST, FunnelEstimate, Milestone, SandboxMandate,
    SolverOutput, canonical, digest)

VERSION = 's-alloc/1.0'
MAX_INPUT_BYTES = 524288
WARNINGS = (
    'Observational saturation model; no causal or incremental ROAS claims.',
    '95% interval is conditional model uncertainty; excludes causal, time-trend and model-selection uncertainty.',
    'Confidence score is a sample-support heuristic, not a probability of success.',
    'Roadmap is a three-phase planning template requiring human approval.',
)


def fit(channel: ChannelData, half: float | None = None) -> CurveAST:
    rows = channel.observations
    half = float(statistics.median(x.spend_minor for x in rows)) if half is None else half
    features = [x.spend_minor / (half + x.spend_minor) for x in rows]
    denominator = sum(x*x for x in features)
    revenue = sum(x.revenue_minor * f for x, f in zip(rows, features)) / denominator
    conversions = sum(x.conversions * f for x, f in zip(rows, features)) / denominator
    rmse = math.sqrt(sum((x.revenue_minor - revenue*f)**2 for x, f in zip(rows, features)) / len(rows))
    return CurveAST(channel=channel.channel, half_saturation_minor=half,
                    revenue_scale=revenue, conversion_scale=conversions,
                    fit_rmse_minor=rmse, observations=len(rows))


def predict(curve: CurveAST, spend: int) -> tuple[float, float]:
    feature = spend / (curve.half_saturation_minor + spend)
    return curve.revenue_scale * feature, curve.conversion_scale * feature


def make_plan(m: SandboxMandate, curves: tuple[CurveAST, ...], amounts: tuple[int, ...]) -> AllocationPlan:
    allocations = tuple(ChannelAllocation(channel=c.channel, spend_minor=amount,
        predicted_revenue_minor=predict(c, amount)[0], predicted_conversions=predict(c, amount)[1])
        for c, amount in zip(curves, amounts))
    return AllocationPlan(currency=m.directive.spend.currency, allocations=allocations,
        total_spend_minor=sum(amounts), predicted_revenue_minor=sum(x.predicted_revenue_minor for x in allocations),
        predicted_conversions=sum(x.predicted_conversions for x in allocations))


def allocations(total: int, lows: tuple[int, ...], highs: tuple[int, ...], prefix: tuple[int, ...] = ()):
    """Enumerate only lattice points with exact total, in stable lexical order."""
    if len(lows) == 1:
        if lows[0] <= total <= highs[0]:
            yield prefix + (total,)
        return
    low = max(lows[0], total - sum(highs[1:]))
    high = min(highs[0], total - sum(lows[1:]))
    for amount in range(low, high + 1):
        yield from allocations(total-amount, lows[1:], highs[1:], prefix+(amount,))


def admissible(m: SandboxMandate, plan: AllocationPlan) -> bool:
    spend = m.directive.spend
    if spend.target_roas is not None and plan.predicted_revenue_minor + 1e-7 < plan.total_spend_minor * spend.target_roas:
        return False
    if spend.maximum_cpa_minor is not None and plan.total_spend_minor > plan.predicted_conversions * spend.maximum_cpa_minor + 1e-7:
        return False
    bounds = {x.channel: x for x in spend.channel_bounds}
    return all(bounds[x.channel].maximum_cpa_minor is None or
               x.spend_minor <= x.predicted_conversions * bounds[x.channel].maximum_cpa_minor + 1e-7
               for x in plan.allocations)


def interval(m: SandboxMandate, plan: AllocationPlan, curves: tuple[CurveAST, ...]) -> ConfidenceInterval:
    rng = random.Random(m.seed)
    channels = {x.channel: x for x in m.context.channels}
    draws = []
    for _ in range(m.bootstrap_samples):
        prediction = 0.0
        for c, allocation in zip(curves, plan.allocations):
            rows = channels[c.channel].observations
            sampled = tuple(rows[rng.randrange(len(rows))] for _ in rows)
            # Repeated bootstrap observations are expected. Do not construct a
            # ChannelData (whose wire validator rejects duplicate periods).
            features = [x.spend_minor / (c.half_saturation_minor + x.spend_minor) for x in sampled]
            scale = sum(x.revenue_minor*f for x, f in zip(sampled, features)) / sum(f*f for f in features)
            prediction += scale * allocation.spend_minor / (c.half_saturation_minor + allocation.spend_minor)
        draws.append(prediction)
    draws.sort()

    def quantile(p: float) -> float:
        index = (len(draws)-1)*p
        low, high = math.floor(index), math.ceil(index)
        return draws[low] + (draws[high]-draws[low])*(index-low)

    return ConfidenceInterval(lower=quantile(0.025), upper=quantile(0.975), samples=m.bootstrap_samples)


def funnel(m: SandboxMandate, plan: AllocationPlan) -> tuple[FunnelEstimate, ...]:
    channels = {x.channel: x for x in m.context.channels}
    result = []
    for a in plan.allocations:
        rows = channels[a.channel].observations
        impressions = sum(x.impressions for x in rows)
        clicks = sum(x.clicks for x in rows)
        conversions = sum(x.conversions for x in rows)
        ctr = clicks/impressions if impressions else 0.0
        cvr = conversions/clicks if clicks else 0.0
        result.append(FunnelEstimate(channel=a.channel, click_through_rate=ctr,
            click_to_conversion_rate=cvr, click_drop_off_rate=1-cvr,
            predicted_conversions=a.predicted_conversions))
    return tuple(result)


def roadmap(m: SandboxMandate, plan: AllocationPlan) -> tuple[Milestone, ...]:
    days = m.directive.horizon_days
    cut1, cut2 = max(1, days//3), max(2, 2*days//3)
    result = []
    for a in plan.allocations:
        # A neutral duration-weighted schedule; not an inferred marketing optimum.
        first = a.spend_minor * cut1 // days
        second = a.spend_minor * (cut2-cut1) // days
        for phase, start, end, amount in (
            ('validate', 1, cut1, first), ('learn', cut1+1, cut2, second),
            ('review', cut2+1, days, a.spend_minor-first-second)):
            result.append(Milestone(phase=phase, start_day=start, end_day=end,
                                    channel=a.channel, spend_minor=amount))
    return tuple(result)


def solve(m: SandboxMandate) -> SolverOutput:
    m = SandboxMandate.model_validate(m)
    spend = m.directive.spend
    bounds = sorted(spend.channel_bounds, key=lambda x: x.channel)
    channels = {x.channel: x for x in m.context.channels}
    curves = tuple(fit(channels[x.channel]) for x in bounds)
    q = spend.quantum_minor
    lows = tuple((x.minimum_minor+q-1)//q for x in bounds)
    highs = tuple(x.maximum_minor//q for x in bounds)
    best = None
    frontier: list[AllocationPlan] = []
    count = 0

    def output(status: str, plan: AllocationPlan | None = None) -> SolverOutput:
        extra_warnings = ()
        if plan and any(not min(x.spend_minor for x in channels[a.channel].observations)
                        <= a.spend_minor <= max(x.spend_minor for x in channels[a.channel].observations)
                        for a in plan.allocations):
            extra_warnings = ('One or more allocations extrapolate beyond observed channel spend; review before approval.',)
        return SolverOutput(execution_id=m.execution_id, mandate_hash=digest(m), status=status,
            plan=plan, curves=curves, confidence_interval=interval(m, plan, curves) if plan else None,
            confidence_score=min(1.0, min(x.observations for x in curves)/30) if plan else 0.0,
            funnels=funnel(m, plan) if plan else (), roadmap=roadmap(m, plan) if plan else (),
            pareto_frontier=tuple(frontier[:32]) if plan else (), pareto_truncated=len(frontier)>32 if plan else False,
            candidates_evaluated=count, warnings=WARNINGS + extra_warnings)

    def score(p: AllocationPlan):
        primary, secondary = (p.predicted_revenue_minor, p.predicted_conversions) if m.directive.objective == 'maximize_revenue' else (p.predicted_conversions, p.predicted_revenue_minor)
        return primary, secondary

    def dominates(a: AllocationPlan, b: AllocationPlan):
        return a.predicted_revenue_minor >= b.predicted_revenue_minor and a.predicted_conversions >= b.predicted_conversions

    for units in allocations(spend.spend_target_minor//q, lows, highs):
        if count == m.max_candidates:
            return output('search_limit')
        count += 1
        plan = make_plan(m, curves, tuple(x*q for x in units))
        if not admissible(m, plan):
            continue
        if best is None or score(plan) > score(best):
            best = plan
        if not any(dominates(x, plan) for x in frontier):
            frontier = [x for x in frontier if not dominates(plan, x)]
            frontier.append(plan)
        # Prevent quadratic Pareto growth from becoming an unbounded search.
        # This is a work-limit outcome, never a false infeasibility claim.
        if len(frontier) > 512:
            return output('search_limit')
    if best is None:
        return output('infeasible')
    frontier.sort(key=score, reverse=True)
    return output('ok', best)


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    try:
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError('input limit')
        mandate = SandboxMandate.model_validate_json(raw)
        result = canonical(solve(mandate))
        if len(result) > mandate.policy.max_output_bytes:
            raise ValueError('output limit')
        sys.stdout.buffer.write(result + b'\n')
        return 0
    except Exception:
        # No payload/validation trace is reflected to logs or stdout. Controller
        # records the exit code and hashes; invalid input produces no evidence.
        sys.stderr.write('S_ALLOC_INVALID_OR_FAILED\n')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
