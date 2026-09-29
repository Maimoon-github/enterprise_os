"""Typed projection of the roadmap specialist's sandbox-produced evidence."""
from app.schemas.strategy import Milestone, SolverOutput


class RoadmapSpecialist:
    @staticmethod
    def receive(output: SolverOutput) -> tuple[Milestone, ...]:
        return output.roadmap
