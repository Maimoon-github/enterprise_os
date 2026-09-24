"""Accepts owner objectives, scopes, budgets, and risk directives."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.exceptions import AuthorizationError, PolicyViolationError
from app.schemas.governance import Directive

router = APIRouter()


@router.post("", response_model=Directive, status_code=201)
async def create_directive(directive: Directive, request: Request) -> Directive:
    """Accept and persist a new owner-issued directive with tenant authority validation."""

    if not directive.validate_tenant_consistency():
        raise PolicyViolationError(
            f"Directive tenant_id '{directive.tenant_id}' does not match scope tenant_id '{directive.scope.tenant_id}'."
        )

    auth_tenant = getattr(request.state, "tenant_id", None) or request.headers.get("x-tenant-id")
    if auth_tenant and auth_tenant not in ("*", "default", "global"):
        if directive.tenant_id != auth_tenant:
            raise AuthorizationError(
                f"Tenant authority mismatch: authenticated tenant '{auth_tenant}' "
                f"cannot issue directive for tenant '{directive.tenant_id}'."
            )

    operational_repository = request.app.state.operational_repository
    await operational_repository.save_directive(directive)
    return directive


@router.get("/{directive_id}", response_model=Directive)
async def get_directive(directive_id: str, request: Request) -> Directive:
    """Return a previously accepted directive."""

    operational_repository = request.app.state.operational_repository
    return await operational_repository.require(directive_id)