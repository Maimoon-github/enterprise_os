"""Application entrypoint and backend composition root."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

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
from app.agents.strategy_engine.profiles import S_ALLOC_PROFILE
from app.agents.strategy_engine.subagents import StrategyAllocationAgent
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
from app.integrations.llm.client import (
    DEFAULT_OLLAMA_CODER_MODEL,
    DEFAULT_OLLAMA_INTELLIGENCE_MODEL,
    LlmClient,
)
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


def _build_workers(
    sandbox_client: SandboxClient,
    llm_client: LlmClient | None = None,
    creative_workflow: Any = None,
    voice_specialists: dict[str, Any] | None = None,
    voice_llm_client: LlmClient | None = None,
    worker_llm_clients: dict[WorkerRole, LlmClient] | None = None,
    specialist_llm_clients_by_worker: dict[WorkerRole, dict[str, LlmClient]] | None = None,
) -> dict[WorkerRole, BoundedWorkerAgent]:
    """Instantiate all seven bounded worker agents with sandbox adapter and dedicated LLM clients."""

    workers: dict[WorkerRole, BoundedWorkerAgent] = {}
    worker_llms = worker_llm_clients or {}
    specialist_llms = specialist_llm_clients_by_worker or {}

    for role, agent_class in _AGENT_CLASSES_BY_ROLE.items():
        role_llm = worker_llms.get(role)
        if role_llm is None and llm_client is not None:
            expected_role_ident = {
                WorkerRole.DEVELOPMENT: "W_DEV",
                WorkerRole.STRATEGY: "W_STRAT",
                WorkerRole.CREATIVE_CONTENT: "W_CREAT",
                WorkerRole.PRODUCT_EVIDENCE: "W_PROD",
                WorkerRole.COMPETITOR_INTEL: "W_COMP",
                WorkerRole.CUSTOMER_VOICE: "W_VOICE",
                WorkerRole.LEARNING_PERFORMANCE: "W_LEARN",
            }.get(role, role.value)
            if getattr(llm_client, "agent_identity", None) == expected_role_ident:
                role_llm = llm_client
            elif isinstance(llm_client, LlmClient):
                role_llm = LlmClient(
                    llm_client.settings,
                    agent_identity=expected_role_ident,
                    model_identity=llm_client.model_identity,
                    default_temperature=llm_client.default_temperature,
                    default_max_output_tokens=llm_client.default_max_output_tokens,
                )
            else:
                role_llm = llm_client
        role_specialists = specialist_llms.get(role)

        if role == WorkerRole.CREATIVE_CONTENT:
            workers[role] = CreativeContentAgent(
                llm_client=role_llm,
                workflow=creative_workflow,
            )
            continue
        if role == WorkerRole.CUSTOMER_VOICE:
            workers[role] = CustomerVoiceAgent(
                llm_client=voice_llm_client or role_llm,
                specialist_llm_clients=role_specialists,
                discovery_agent=voice_specialists.get("discovery") if voice_specialists else None,
                themes_agent=voice_specialists.get("themes") if voice_specialists else None,
                sentiment_agent=voice_specialists.get("sentiment") if voice_specialists else None,
                needs_agent=voice_specialists.get("needs") if voice_specialists else None,
                journey_agent=voice_specialists.get("journey") if voice_specialists else None,
                qa_agent=voice_specialists.get("qa") if voice_specialists else None,
            )
            continue
        assert get_capability_for_role(role) == agent_class.capability
        if role == WorkerRole.STRATEGY:
            alloc_llm = (role_specialists or {}).get("STRAT-ALLOC") if role_specialists else None
            allocation_agent = StrategyAllocationAgent(
                profile=S_ALLOC_PROFILE,
                llm_client=alloc_llm,
            )
            workers[role] = StrategyAgent(
                sandbox_client,
                llm_client=role_llm,
                allocation_agent=allocation_agent,
                allocation_llm_client=alloc_llm,
            )
        elif role == WorkerRole.DEVELOPMENT:
            workers[role] = DevelopmentAgent(
                sandbox_client,
                llm_client=role_llm,
                subagent_llm_clients=role_specialists,
            )
        elif role == WorkerRole.PRODUCT_EVIDENCE:
            workers[role] = ProductEvidenceAgent(
                sandbox_client,
                llm_client=role_llm,
                specialist_llm_clients=role_specialists,
            )
        elif role == WorkerRole.COMPETITOR_INTEL:
            workers[role] = CompetitorIntelAgent(
                sandbox_client,
                llm_client=role_llm,
                specialist_llm_clients=role_specialists,
            )
        elif role == WorkerRole.LEARNING_PERFORMANCE:
            workers[role] = LearningPerformanceAgent(
                sandbox_client,
                llm_client=role_llm,
                specialist_llm_clients=role_specialists,
            )
        else:
            workers[role] = agent_class(sandbox_client, llm_client=role_llm)
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

    provenance_recorder = ProvenanceRecorder(provenance_repository)
    task_state_service = TaskStateService(
        task_state_repository, TaskStateMachine(), provenance_recorder
    )
    memory_promotion_service = MemoryPromotionService(memory_repository)

    cms_client = CmsClient(settings.cms.base_url, settings.cms.api_key)
    data_gateway = DataGateway(
        vector_repository,
        AuthorizationBoundary(ScopeEvaluator()),
        operational_repository=operational_repository,
        memory_repository=memory_repository,
        artifact_repository=artifact_repository,
        cms_client=cms_client,
        telemetry_repository=telemetry_repository,
        provenance_recorder=provenance_recorder,
    )

    hybrid_retriever = HybridRetriever(data_gateway=data_gateway)
    rag_controller = RagController(
        hybrid_retriever, FreshnessPolicy(), SchemaValidator(), data_gateway=data_gateway
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    ie_llm: LlmClient | None = None
    llm_client: LlmClient | None = None
    worker_llm_clients: dict[WorkerRole, LlmClient] = {}
    specialist_llm_clients_by_worker: dict[WorkerRole, dict[str, LlmClient]] = {}
    all_llm_clients: list[LlmClient] = []

    creative_llm_clients: list[LlmClient] = []
    creative_workflow = None
    voice_llm_clients: list[LlmClient] = []
    voice_specialists: dict[str, Any] = {}
    w_voice_llm = None
    sandbox_client = SandboxClient(settings.sandbox, provenance_recorder=provenance_recorder)

    if settings.llm.provider != "unset":
        # Architectural multi-model Ollama isolation:
        # - Intelligence Engine (Orchestrator Layer 2): qwen2.5:7b (general reasoning and strategic synthesis)
        # - Development Worker & Sub-agents: qwen2.5-coder:7b (code synthesis, execution, and verification)
        # - Other Workers & Sub-agents: general intelligence model
        # Guarantees that every single invoke uses exactly one deterministic model per role.
        ie_model = (
            settings.llm.intelligence_model_name
            or (
                settings.llm.model_name
                if settings.llm.model_name != "unset" and settings.llm.model_name != DEFAULT_OLLAMA_CODER_MODEL
                else DEFAULT_OLLAMA_INTELLIGENCE_MODEL
            )
        )
        coder_model = settings.llm.coder_model_name or DEFAULT_OLLAMA_CODER_MODEL
        general_model = (
            settings.llm.model_name
            if settings.llm.model_name != "unset"
            else DEFAULT_OLLAMA_INTELLIGENCE_MODEL
        )

        # Helper factories ensuring deterministic model identity per agent role
        def _coder_llm(ident: str) -> LlmClient:
            return LlmClient(settings.llm, agent_identity=ident, model_identity=coder_model)

        def _gen_llm(ident: str) -> LlmClient:
            return LlmClient(settings.llm, agent_identity=ident, model_identity=general_model)

        # 1. Intelligence Engine (Orchestrator Layer 2) isolated cognitive client
        ie_llm = LlmClient(
            settings.llm, agent_identity="INTELLIGENCE_ENGINE", model_identity=ie_model
        )
        llm_client = ie_llm
        all_llm_clients.append(ie_llm)

        # 2. Worker Agents (Layer 5) isolated cognitive clients
        from app.agents.customer_voice_engine.profiles import (
            COORDINATOR_PROFILE,
            DISCOVERY_PROFILE,
            JOURNEY_PROFILE,
            NEEDS_PROFILE,
            QA_PROFILE,
            SENTIMENT_PROFILE,
            THEMES_PROFILE,
            create_voice_llm_client,
        )

        w_dev_llm = _coder_llm("W_DEV")
        w_strat_llm = _gen_llm("W_STRAT")
        w_creat_llm = _gen_llm("W_CREAT")
        w_prod_llm = _gen_llm("W_PROD")
        w_comp_llm = _gen_llm("W_COMP")
        w_voice_llm = create_voice_llm_client(
            COORDINATOR_PROFILE, base_settings=settings.llm, model_identity=general_model
        )
        w_learn_llm = _gen_llm("W_LEARN")

        worker_llm_clients = {
            WorkerRole.DEVELOPMENT: w_dev_llm,
            WorkerRole.STRATEGY: w_strat_llm,
            WorkerRole.CREATIVE_CONTENT: w_creat_llm,
            WorkerRole.PRODUCT_EVIDENCE: w_prod_llm,
            WorkerRole.COMPETITOR_INTEL: w_comp_llm,
            WorkerRole.CUSTOMER_VOICE: w_voice_llm,
            WorkerRole.LEARNING_PERFORMANCE: w_learn_llm,
        }
        all_llm_clients.extend(worker_llm_clients.values())

        # 3. Specialist Sub-Agents (Layer 6) isolated cognitive clients (38 sub-agents)
        specialist_llm_clients_by_worker = {
            WorkerRole.DEVELOPMENT: {
                "DEV-PLAN": _coder_llm("DEV-PLAN"),
                "DEV-CMS": _coder_llm("DEV-CMS"),
                "DEV-UI": _coder_llm("DEV-UI"),
                "DEV-CODE": _coder_llm("DEV-CODE"),
                "DEV-VERIFY": _coder_llm("DEV-VERIFY"),
                "DEV-SEC": _coder_llm("DEV-SEC"),
                "DEV-REL": _coder_llm("DEV-REL"),
            },
            WorkerRole.STRATEGY: {
                "STRAT-ALLOC": _gen_llm("STRAT-ALLOC"),
            },
            WorkerRole.CREATIVE_CONTENT: {
                "CREAT-RESEARCH": _gen_llm("CREAT-RESEARCH"),
                "CREAT-CONCEPT": _gen_llm("CREAT-CONCEPT"),
                "CREAT-COPY": _gen_llm("CREAT-COPY"),
                "CREAT-VISUAL": _gen_llm("CREAT-VISUAL"),
                "CREAT-ADAPT": _gen_llm("CREAT-ADAPT"),
                "CREAT-QA": _gen_llm("CREAT-QA"),
            },
            WorkerRole.PRODUCT_EVIDENCE: {
                "PROD-DISCOVERY": _gen_llm("PROD-DISCOVERY"),
                "PROD-APPRAISAL": _gen_llm("PROD-APPRAISAL"),
                "PROD-CLAIMS": _gen_llm("PROD-CLAIMS"),
                "PROD-LAB": _gen_llm("PROD-LAB"),
                "PROD-REGULATORY": _gen_llm("PROD-REGULATORY"),
                "PROD-SAFETY": _gen_llm("PROD-SAFETY"),
            },
            WorkerRole.COMPETITOR_INTEL: {
                "COMP-DISCOVERY": _gen_llm("COMP-DISCOVERY"),
                "COMP-ADS": _gen_llm("COMP-ADS"),
                "COMP-PRICING": _gen_llm("COMP-PRICING"),
                "COMP-SEARCH": _gen_llm("COMP-SEARCH"),
                "COMP-POSITIONING": _gen_llm("COMP-POSITIONING"),
                "COMP-SYNTHESIS": _gen_llm("COMP-SYNTHESIS"),
            },
            WorkerRole.CUSTOMER_VOICE: {
                "VOICE-DISCOVERY": create_voice_llm_client(
                    DISCOVERY_PROFILE, base_settings=settings.llm, model_identity=general_model
                ),
                "VOICE-THEMES": create_voice_llm_client(
                    THEMES_PROFILE, base_settings=settings.llm, model_identity=general_model
                ),
                "VOICE-SENTIMENT": create_voice_llm_client(
                    SENTIMENT_PROFILE, base_settings=settings.llm, model_identity=general_model
                ),
                "VOICE-NEEDS": create_voice_llm_client(
                    NEEDS_PROFILE, base_settings=settings.llm, model_identity=general_model
                ),
                "VOICE-JOURNEY": create_voice_llm_client(
                    JOURNEY_PROFILE, base_settings=settings.llm, model_identity=general_model
                ),
                "VOICE-QA": create_voice_llm_client(
                    QA_PROFILE, base_settings=settings.llm, model_identity=general_model
                ),
            },
            WorkerRole.LEARNING_PERFORMANCE: {
                "LEARN-TELEMETRY": _gen_llm("LEARN-TELEMETRY"),
                "LEARN-ATTRIBUTION": _gen_llm("LEARN-ATTRIBUTION"),
                "LEARN-INCREMENTALITY": _gen_llm("LEARN-INCREMENTALITY"),
                "LEARN-FATIGUE": _gen_llm("LEARN-FATIGUE"),
                "LEARN-DECAY": _gen_llm("LEARN-DECAY"),
                "LEARN-QA": _gen_llm("LEARN-QA"),
            },
        }
        for sub_map in specialist_llm_clients_by_worker.values():
            all_llm_clients.extend(sub_map.values())

        # Creative workflow wiring
        from app.agents.creative_content_engine.subagents.adaptation import CreativeAdaptationAgent
        from app.agents.creative_content_engine.subagents.concept import CreativeConceptAgent
        from app.agents.creative_content_engine.subagents.copy import CreativeCopyAgent
        from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent
        from app.agents.creative_content_engine.subagents.research import CreativeResearchAgent
        from app.agents.creative_content_engine.subagents.visual import CreativeVisualAgent
        from app.orchestration.creative_content_workflow import CreativeContentWorkflow

        creat_subs = specialist_llm_clients_by_worker[WorkerRole.CREATIVE_CONTENT]
        creative_llm_clients = [w_creat_llm, *creat_subs.values()]
        creative_workflow = CreativeContentWorkflow(
            research_agent=CreativeResearchAgent(
                llm_client=creat_subs["CREAT-RESEARCH"], sandbox_client=sandbox_client
            ),
            concept_agent=CreativeConceptAgent(llm_client=creat_subs["CREAT-CONCEPT"]),
            copy_agent=CreativeCopyAgent(llm_client=creat_subs["CREAT-COPY"], sandbox_client=sandbox_client),
            visual_agent=CreativeVisualAgent(llm_client=creat_subs["CREAT-VISUAL"]),
            adaptation_agent=CreativeAdaptationAgent(llm_client=creat_subs["CREAT-ADAPT"]),
            qa_agent=CreativeQualityAgent(llm_client=creat_subs["CREAT-QA"]),
        )

        # Voice specialists wiring
        from app.agents.customer_voice_engine.subagents import (
            VoiceDiscoveryAgent,
            VoiceJourneyAgent,
            VoiceNeedsAgent,
            VoiceQualityAgent,
            VoiceSentimentAgent,
            VoiceThemesAgent,
        )

        voice_subs = specialist_llm_clients_by_worker[WorkerRole.CUSTOMER_VOICE]
        voice_llm_clients = [w_voice_llm, *voice_subs.values()]
        voice_specialists = {
            "discovery": VoiceDiscoveryAgent(llm_client=voice_subs["VOICE-DISCOVERY"], profile=DISCOVERY_PROFILE),
            "themes": VoiceThemesAgent(llm_client=voice_subs["VOICE-THEMES"], profile=THEMES_PROFILE),
            "sentiment": VoiceSentimentAgent(llm_client=voice_subs["VOICE-SENTIMENT"], profile=SENTIMENT_PROFILE),
            "needs": VoiceNeedsAgent(llm_client=voice_subs["VOICE-NEEDS"], profile=NEEDS_PROFILE),
            "journey": VoiceJourneyAgent(llm_client=voice_subs["VOICE-JOURNEY"], profile=JOURNEY_PROFILE),
            "qa": VoiceQualityAgent(llm_client=voice_subs["VOICE-QA"], profile=QA_PROFILE),
        }

    workers = _build_workers(
        sandbox_client,
        llm_client=ie_llm,
        creative_workflow=creative_workflow,
        voice_specialists=voice_specialists,
        voice_llm_client=w_voice_llm,
        worker_llm_clients=worker_llm_clients,
        specialist_llm_clients_by_worker=specialist_llm_clients_by_worker,
    )

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
    outbound_gateway = OutboundGateway(
        hitl_coordinator,
        crypto_validator,
        ads_adapters=ads_adapters,
        social_adapters=social_adapters,
        cms_client=cms_client,
        require_signature=settings.security.require_signed_dispatch,
    )
    mcp_host = McpHost(data_gateway, outbound_gateway)

    telemetry_normalizer = TelemetryNormalizer(telemetry_repository, data_gateway=data_gateway)
    telemetry_engine = OmnichannelTelemetryEngine(
        webhook_signing_secret=settings.telemetry.webhook_signing_secret,
        max_payload_bytes=settings.telemetry.max_payload_bytes,
        freshness_window_seconds=settings.telemetry.freshness_window_seconds,
        max_future_skew_seconds=settings.telemetry.max_future_skew_seconds,
        task_state_service=task_state_service,
        provenance_recorder=provenance_recorder,
        telemetry_repository=telemetry_repository,
        telemetry_normalizer=telemetry_normalizer,
        data_gateway=data_gateway,
    )

    brand_persona_resolver = BrandPersonaResolver(
        memory_repository=memory_repository,
        data_gateway=data_gateway,
    )

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
        llm_client=ie_llm,
    )

    from app.services.attribution_coordinator import AttributionCoordinator
    attribution_coordinator = AttributionCoordinator(
        telemetry_repository=telemetry_repository,
        agent=workers[WorkerRole.LEARNING_PERFORMANCE],  # type: ignore[arg-type]
        task_state_service=task_state_service,
        provenance_recorder=provenance_recorder,
        data_gateway=data_gateway,
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
    app.state.attribution_coordinator = attribution_coordinator
    app.state.llm_client = ie_llm
    app.state.worker_llm_clients = worker_llm_clients
    app.state.specialist_llm_clients_by_worker = specialist_llm_clients_by_worker
    app.state.all_llm_clients = all_llm_clients
    app.state.creative_workflow = creative_workflow
    app.state.creative_llm_clients = creative_llm_clients
    app.state.voice_llm_clients = voice_llm_clients
    app.state.cryptographic_validator = crypto_validator

    try:
        yield
    finally:
        closed_clients: set[Any] = set()
        for client in all_llm_clients:
            if client is not None and client not in closed_clients:
                await client.aclose()
                closed_clients.add(client)
        if ie_llm is not None and ie_llm not in closed_clients:
            await ie_llm.aclose()
            closed_clients.add(ie_llm)
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