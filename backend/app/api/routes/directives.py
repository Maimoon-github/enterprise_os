"""Accepts owner objectives, scopes, budgets, and risk directives."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.governance import Directive

router = APIRouter()


@router.post("", response_model=Directive, status_code=201)
async def create_directive(directive: Directive, request: Request) -> Directive:
    """Accept and persist a new owner-issued directive."""

    operational_repository = request.app.state.operational_repository
    await operational_repository.save_directive(directive)
    return directive


@router.get("/{directive_id}", response_model=Directive)
async def get_directive(directive_id: str, request: Request) -> Directive:
    """Return a previously accepted directive."""

    operational_repository = request.app.state.operational_repository
    return await operational_repository.require(directive_id)