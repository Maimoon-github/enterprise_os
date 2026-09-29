"""Typed S_ALLOC adapter. Only validation and dispatch execute on the host."""
from app.integrations.sandbox.client import SandboxClient
from app.schemas.strategy import SandboxMandate, SandboxResult


def verify_output(mandate: SandboxMandate, result: SandboxResult) -> None:
    """Independent boundary checks; this is not a second optimizer."""
    o = result.output
    if o.candidates_evaluated > mandate.max_candidates:
        raise ValueError('candidate budget exceeded')
    if o.status != 'ok':
        return
    spend = mandate.directive.spend
    bounds = {x.channel: x for x in spend.channel_bounds}
    plans = (o.plan, *o.pareto_frontier)
    for plan in plans:
        if plan is None:
            raise ValueError('missing allocation plan')
        if plan.currency != spend.currency or plan.total_spend_minor != spend.spend_target_minor:
            raise ValueError('budget or currency mismatch')
        if plan.total_spend_minor > spend.total_cap_minor:
            raise ValueError('total cap exceeded')
        if {x.channel for x in plan.allocations} != set(bounds):
            raise ValueError('allocation channel mismatch')
        for x in plan.allocations:
            b = bounds[x.channel]
            if not b.minimum_minor <= x.spend_minor <= b.maximum_minor or x.spend_minor % spend.quantum_minor:
                raise ValueError('channel bound/grid violation')
            if b.maximum_cpa_minor is not None and x.spend_minor > x.predicted_conversions * b.maximum_cpa_minor + 1e-7:
                raise ValueError('channel CPA violation')
        if spend.target_roas is not None and plan.predicted_revenue_minor + 1e-7 < plan.total_spend_minor * spend.target_roas:
            raise ValueError('ROAS target violation')
        if spend.maximum_cpa_minor is not None and plan.total_spend_minor > plan.predicted_conversions * spend.maximum_cpa_minor + 1e-7:
            raise ValueError('global CPA violation')
    if ({x.channel for x in o.curves} != set(bounds) or len(o.curves) != len(bounds)
            or {x.channel for x in o.funnels} != set(bounds) or len(o.funnels) != len(bounds)):
        raise ValueError('curve/funnel channel mismatch')
    assert o.plan is not None and o.confidence_interval is not None
    if o.confidence_interval.samples != mandate.bootstrap_samples:
        raise ValueError('bootstrap budget mismatch')
    for allocation in o.plan.allocations:
        f = next(x for x in o.funnels if x.channel == allocation.channel)
        if f.predicted_conversions != allocation.predicted_conversions or abs(f.click_drop_off_rate + f.click_to_conversion_rate - 1) > 1e-9:
            raise ValueError('funnel result mismatch')
        milestones = [x for x in o.roadmap if x.channel == allocation.channel]
        if len(milestones) != 3 or tuple(x.phase for x in milestones) != ('validate', 'learn', 'review'):
            raise ValueError('roadmap phase mismatch')
        if sum(x.spend_minor for x in milestones) != allocation.spend_minor:
            raise ValueError('roadmap budget mismatch')
        day = 1
        for x in milestones:
            if x.start_day != day or x.end_day < x.start_day:
                raise ValueError('roadmap gaps or overlaps')
            day = x.end_day + 1
        if day != mandate.directive.horizon_days + 1:
            raise ValueError('roadmap horizon mismatch')
    if len(o.roadmap) != len(bounds) * 3:
        raise ValueError('unexpected roadmap channel')


class SAllocCore:
    def __init__(self, client: SandboxClient):
        self._client = client

    async def run(self, mandate: SandboxMandate) -> SandboxResult:
        result = await self._client.invoke_s_alloc(mandate)
        verify_output(mandate, result)
        return result
