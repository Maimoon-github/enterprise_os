"""Persists enterprise directives and generated operational records."""
from __future__ import annotations

from app.schemas.governance import Directive


class OperationalRepository:
    def __init__(self) -> None:
        self._directives: dict[str, Directive] = {}

    def save_directive(self, directive: Directive) -> None:
        self._directives[directive.directive_id] = directive

    def get_directive(self, directive_id: str) -> Directive | None:
        return self._directives.get(directive_id)
