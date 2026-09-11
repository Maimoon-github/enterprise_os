"""Accepts owner objectives, scopes, budgets, and risk directives."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.governance import Directive
from app.services.policy_engine import PolicyEngine

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_directive(directive: Directive) -> dict[str, str]:
    envelope = PolicyEngine().compile_envelope(directive)
    return {"status": "accepted", "policy_id": envelope.policy_id}
