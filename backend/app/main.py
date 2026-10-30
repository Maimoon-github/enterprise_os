from contextlib import asynccontextmanager

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.models import (  # noqa: F401
    analytics_event,
    approval,
    brand,
    campaign,
    chat,
    media_asset,
    platform_connection,
    run,
    schedule,
    user,
)
from app.db.session import engine
from app.observability.otel import get_tracer, setup_telemetry
from app.orchestrator.checkpointer import close_checkpointer, init_checkpointer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

tracer = get_tracer("marketing-os-backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    setup_telemetry()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_checkpointer()
    yield
    await close_checkpointer()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Control Plane API for Agentic Brand Marketing Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")

@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["System"])
async def health_check():
    with tracer.start_as_current_span("health_smoke_trace") as span:
        span.set_attribute("service.name", settings.PROJECT_NAME)
        span.set_attribute("environment", settings.ENVIRONMENT)
        span.set_attribute("health.status", "healthy")
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "environment": settings.ENVIRONMENT,
        }

@app.get("/ready", tags=["System"])
async def ready_check():
    return {
        "status": "ready",
        "service": settings.PROJECT_NAME,
    }
