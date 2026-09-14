"""Application entrypoint and backend composition root."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.agents.base import BoundedWorkerAgent
from app.agents.competitor_intel import CompetitorIntelAgent
from app.agents.creative_content import CreativeContentAgent
from app.agents.customer_voice import CustomerVoiceAgent
from app.agents.development import DevelopmentAgent
from app.agents.learning_performance import LearningPerformanceAgent
from app.agents.product_evidence import ProductEvidenceAgent
from app.agents.strategy import StrategyAgent
from app.api.router import api_router
from app.core.exceptions import (
    ApprovalRequiredError,
    AuthorizationError,
    ConfigurationError,
    GovernedBackendError,
    InvalidTransitionError,
    PolicyViolationError,
    RateLimitExceededError,
    RepositoryError,
    RetrievalGovernanceError,
    SandboxInvocationError,
    SignatureVerificationError,
)
from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings
from app.integrations.ads.base import AdsAdapter
from app.integrations.ads.google import GoogleAdsAdapter
from app.integrations.ads.linkedin import LinkedInAdsAdapter
from app.integrations.ads.meta import MetaAdsAdapter
from app.integrations.ads.tiktok import TikTokAdsAdapter
from app.integrations.cms.client import CmsClient
from app.integrations.sandbox.capabilities import get_capability_for_role
from app.integrations.sandbox.client import SandboxClient
from app.integrations.social.base import SocialAdapter
from app.integrations.social.instagram import InstagramAdapter
from app.integrations.social.tiktok import TikTokSocialAdapter
from app.integrations.social.x import XAdapter
from app.integrations.social.youtube import YouTubeAdapter
from app.mcp.data_gateway import DataGateway
from app.mcp.host import McpHost
from app.mcp.outbound_gateway import OutboundGateway
from app.orchestration.brand_persona import BrandPersonaResolver
from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.persistence.database import Database
from app.persistence.repositories.artifact import ArtifactRepository
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.operational import OperationalRepository
from app.persistence.repositories.provenance import ProvenanceRepository
from app.persistence.repositories.task_state import TaskStateRepository
from app.persistence.repositories.telemetry import TelemetryRepository
from app.persistence.repositories.vector import VectorRepository
from app.schemas.governance import WorkerRole
from app.security.authorization_boundary import AuthorizationBoundary
from app.security.cryptographic_validator import CryptographicValidator
from app.security.scope_evaluator import ScopeEvaluator
from app.services.hitl import HitlCoordinator
from app.services.memory_promotion import MemoryPromotionService
from app.services.policy_engine import PolicyEngine
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from app.services.telemetry import TelemetryNormalizer
from app.services.telemetry_engine import OmnichannelTelemetryEngine

_AGENT_CLASSES_BY_ROLE: dict[WorkerRole, type[BoundedWorkerAgent]] = {
    WorkerRole.DEVELOPMENT: DevelopmentAgent,
    WorkerRole.STRATEGY: StrategyAgent,
    WorkerRole.CREATIVE_CONTENT: CreativeContentAgent,
    WorkerRole.PRODUCT_EVIDENCE: ProductEvidenceAgent,
    WorkerRole.COMPETITOR_INTEL: CompetitorIntelAgent,
    WorkerRole.CUSTOMER_VOICE: CustomerVoiceAgent,
    WorkerRole.LEARNING_PERFORMANCE: LearningPerformanceAgent,
}

logger = get_logger(__name__)


def _build_workers(sandbox_client: SandboxClient) -> dict[WorkerRole, BoundedWorkerAgent]:
    """Instantiate all seven bounded worker agents against one sandbox client."""

    workers: dict[WorkerRole, BoundedWorkerAgent] = {}
    for role, agent_class in _AGENT_CLASSES_BY_ROLE.items():
        assert get_capability_for_role(role) == agent_class.capability
        workers[role] = agent_class(sandbox_client)
    return workers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Compose every backend dependency once at startup and dispose at shutdown."""

    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting governed backend in '%s' environment", settings.environment)

    database = Database(settings.database)
    await database.create_all()

    operational_repository = OperationalRepository(database.session_factory)
    task_state_repository = TaskStateRepository(database.session_factory)
    vector_repository = VectorRepository(database.session_factory)
    telemetry_repository = TelemetryRepository(database.session_factory)
    memory_repository = MemoryRepository(database.session_factory)
    artifact_repository = ArtifactRepository(database.session_factory)
    provenance_repository = ProvenanceRepository(database.session_factory)

    from app.services.task_state import TaskStateService

    telemetry_normalizer = TelemetryNormalizer(telemetry_repository)
    telemetry_engine = OmnichannelTelemetryEngine(
        webhook_signing_secret=settings.telemetry.webhook_signing_secret,
        max_payload_bytes=settings.telemetry.max_payload_bytes,
        freshness_window_seconds=settings.telemetry.freshness_window_seconds,
        max_future_skew_seconds=settings.telemetry.max_future_skew_seconds,
        task_state_service=task_state_service,
        provenance_recorder=provenance_recorder,
    )
    memory_promotion_service = MemoryPromotionService(memory_repository)
    provenance_recorder = ProvenanceRecorder(provenance_repository)
    task_state_service = TaskStateService(
        task_state_repository, TaskStateMachine(), provenance_recorder
    )

    hybrid_retriever = HybridRetriever(vector_repository)
    rag_controller = RagController(hybrid_retriever, FreshnessPolicy(), SchemaValidator())
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    sandbox_client = SandboxClient(settings.sandbox)
    workers = _build_workers(sandbox_client)

    hitl_coordinator = HitlCoordinator()
    crypto_validator = CryptographicValidator(settings.security.signing_public_key_pem)

    ads_adapters: dict[str, AdsAdapter] = {
        "meta": MetaAdsAdapter(settings.ads.meta_access_token),
        "google": GoogleAdsAdapter(settings.ads.google_access_token),
        "tiktok": TikTokAdsAdapter(settings.ads.tiktok_access_token),
        "linkedin": LinkedInAdsAdapter(settings.ads.linkedin_access_token),
    }
    social_adapters: dict[str, SocialAdapter] = {
        "instagram": InstagramAdapter(settings.social.instagram_access_token),
        "x": XAdapter(settings.social.x_access_token),
        "tiktok_social": TikTokSocialAdapter(settings.social.tiktok_access_token),
        "youtube": YouTubeAdapter(settings.social.youtube_access_token),
    }
    cms_client = CmsClient(settings.cms.base_url, settings.cms.api_key)

    outbound_gateway = OutboundGateway(
        hitl_coordinator,
        crypto_validator,
        ads_adapters=ads_adapters,
        social_adapters=social_adapters,
        cms_client=cms_client,
        require_signature=settings.security.require_signed_dispatch,
    )
    data_gateway = DataGateway(
        vector_repository,
        AuthorizationBoundary(ScopeEvaluator()),
        operational_repository=operational_repository,
        memory_repository=memory_repository,
        artifact_repository=artifact_repository,
        cms_client=cms_client,
    )
    mcp_host = McpHost(data_gateway, outbound_gateway)

    brand_persona_resolver = BrandPersonaResolver(memory_repository=memory_repository)

    intelligence_engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(PolicyEngine()),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(rag_dispatcher, brand_persona_resolver),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl_coordinator,
        mcp_host=mcp_host,
        provenance_recorder=provenance_recorder,
        workers=workers,
    )

    app.state.database = database
    app.state.operational_repository = operational_repository
    app.state.task_state_repository = task_state_repository
    app.state.task_state_service = task_state_service
    app.state.artifact_repository = artifact_repository
    app.state.telemetry_normalizer = telemetry_normalizer
    app.state.telemetry_engine = telemetry_engine
    app.state.memory_promotion_service = memory_promotion_service
    app.state.provenance_recorder = provenance_recorder
    app.state.hitl_coordinator = hitl_coordinator
    app.state.mcp_host = mcp_host
    app.state.intelligence_engine = intelligence_engine

    try:
        yield
    finally:
        for ads_adapter in ads_adapters.values():
            await ads_adapter.aclose()
        for social_adapter in social_adapters.values():
            await social_adapter.aclose()
        await cms_client.aclose()
        await database.dispose()
        logger.info("Governed backend shutdown complete")


def _error_response(status_code: int, error: GovernedBackendError) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": str(error)})


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""

    app = FastAPI(title="Governed Backend", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)

    @app.exception_handler(RepositoryError)
    async def _repository_error_handler(_: Request, exc: RepositoryError) -> JSONResponse:
        return _error_response(404, exc)

    @app.exception_handler(AuthorizationError)
    async def _authorization_error_handler(_: Request, exc: AuthorizationError) -> JSONResponse:
        return _error_response(403, exc)

    @app.exception_handler(RetrievalGovernanceError)
    async def _retrieval_governance_error_handler(
        _: Request, exc: RetrievalGovernanceError
    ) -> JSONResponse:
        return _error_response(403, exc)

    @app.exception_handler(PolicyViolationError)
    async def _policy_violation_error_handler(
        _: Request, exc: PolicyViolationError
    ) -> JSONResponse:
        return _error_response(422, exc)

    @app.exception_handler(InvalidTransitionError)
    async def _invalid_transition_error_handler(
        _: Request, exc: InvalidTransitionError
    ) -> JSONResponse:
        return _error_response(409, exc)

    @app.exception_handler(ApprovalRequiredError)
    async def _approval_required_error_handler(
        _: Request, exc: ApprovalRequiredError
    ) -> JSONResponse:
        return _error_response(409, exc)

    @app.exception_handler(SignatureVerificationError)
    async def _signature_verification_error_handler(
        _: Request, exc: SignatureVerificationError
    ) -> JSONResponse:
        return _error_response(401, exc)

    @app.exception_handler(RateLimitExceededError)
    async def _rate_limit_error_handler(_: Request, exc: RateLimitExceededError) -> JSONResponse:
        return _error_response(429, exc)

    @app.exception_handler(SandboxInvocationError)
    async def _sandbox_invocation_error_handler(
        _: Request, exc: SandboxInvocationError
    ) -> JSONResponse:
        return _error_response(502, exc)

    @app.exception_handler(ConfigurationError)
    async def _configuration_error_handler(_: Request, exc: ConfigurationError) -> JSONResponse:
        return _error_response(500, exc)

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()