"""Aggregates backend API routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import approvals, directives, tasks, telemetry

api_router = APIRouter()
api_router.include_router(directives.router, prefix="/directives", tags=["directives"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])