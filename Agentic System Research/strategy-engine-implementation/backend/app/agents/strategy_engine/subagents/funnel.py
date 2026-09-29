"""Typed projection of the funnel specialist's sandbox-produced evidence."""
from app.schemas.strategy import FunnelEstimate, SolverOutput


class FunnelSpecialist:
    @staticmethod
    def receive(output: SolverOutput) -> tuple[FunnelEstimate, ...]:
        return output.funnels
