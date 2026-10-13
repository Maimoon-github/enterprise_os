"""Agent 0: Master Supervisor coordinating multi-agent strategy pipeline execution."""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agents.analyst_agent import AnalystAgent
from src.agents.audience_agent import AudienceAgent
from src.agents.brand_agent import BrandAgent
from src.agents.growth_agent import GrowthAgent
from src.agents.seo_content_agent import SEOContentAgent
from src.agents.validator_agent import ValidatorAgent
from src.memory.long_term import LongTermMemory
from src.memory.short_term import ShortTermMemory
from src.orchestrator.context_isolator import ContextIsolator
from src.orchestrator.state_machine import PipelineStage, StateMachine
from src.rag.chunker import DocumentChunker
from src.rag.parser import DocumentParser
from src.rag.store import VectorStore
from src.schemas.initiative import ApprovalStatus
from src.schemas.state import (
    BrandProfile,
    MasterEngineState,
    OperationalMode,
    ResearchRepository,
    StrategicArtifacts,
)
from src.tools.browser_bridge import BrowserBridge
from src.tools.rag_search import RAGSearchTool

logger = logging.getLogger(__name__)


class StrategyOrchestrator:
    """Central supervisor (Agent 0) maintaining MasterEngineState and orchestrating specialist agents."""

    SYSTEM_PROMPT = """You are the Brand Strategy Orchestrator, the central supervisory engine for the Universal AI Brand Strategy Engine.
Responsibilities:
1. State Management: Maintain the MasterEngineState and coordinate specialist agents in strict sequence: Analyst -> Audience -> Brand -> SEO/Content -> Growth -> Validator.
2. Context Isolation: Provide each downstream specialist ONLY with its required slice of state to prevent context dilution.
3. Revision Control: When Agent 6 (Strategy Validator) issues a veto, extract the failed initiatives and audit logs, increment the iteration counter, and route the items back to the initiating agent.
4. Hard Revision Ceiling: If an initiative fails verification 3 times, purge it permanently from the final strategic dossier.
5. Non-Interference: Never invent findings or strategy recommendations directly."""

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        browser_bridge: Optional[BrowserBridge] = None,
    ):
        self.ollama_base_url = ollama_base_url
        self.short_term_memory = ShortTermMemory()
        self.long_term_memory = LongTermMemory()
        self.vector_store = VectorStore()
        self.rag_tool = RAGSearchTool(vector_store=self.vector_store)

        # Initialize domain specialists
        self.browser_bridge = browser_bridge or BrowserBridge()
        self.agent_1_analyst = AnalystAgent(
            browser_bridge=self.browser_bridge, ollama_base_url=ollama_base_url
        )
        self.agent_2_audience = AudienceAgent(
            rag_tool=self.rag_tool, ollama_base_url=ollama_base_url
        )
        self.agent_3_brand = BrandAgent(
            rag_tool=self.rag_tool, ollama_base_url=ollama_base_url
        )
        self.agent_4_seo = SEOContentAgent(
            rag_tool=self.rag_tool, ollama_base_url=ollama_base_url
        )
        self.agent_5_growth = GrowthAgent(
            rag_tool=self.rag_tool, ollama_base_url=ollama_base_url
        )
        self.agent_6_validator = ValidatorAgent(ollama_base_url=ollama_base_url)

    async def ingest_user_documents(self, docs_dir: str, tenant_id: str) -> int:
        """Ingests client pitch decks and internal brand guidelines into the RAG vector store."""
        path = Path(docs_dir)
        if not path.exists():
            return 0

        chunker = DocumentChunker()
        total_chunks = 0
        for doc_file in path.iterdir():
            if doc_file.is_file() and not doc_file.name.startswith("."):
                try:
                    sections = DocumentParser.parse_file(str(doc_file))
                    chunks = chunker.chunk_document(sections, document_id=doc_file.stem)
                    indexed = await self.vector_store.add_chunks(chunks, tenant_id=tenant_id)
                    total_chunks += indexed
                except Exception as e:
                    logger.warning("Failed to parse doc %s: %s", doc_file, e)
        return total_chunks

    async def execute_audit(
        self,
        brand_profile: BrandProfile,
        mode: OperationalMode,
        docs_dir: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> MasterEngineState:
        """Executes full autonomous multi-agent audit lifecycle."""
        session_id = str(uuid.uuid4())
        tid = tenant_id or f"tenant_{uuid.uuid4().hex[:8]}"

        # Initialize long term memory connection
        await self.long_term_memory.connect()

        # Ingest documents if provided
        if docs_dir:
            chunks_count = await self.ingest_user_documents(docs_dir, tenant_id=tid)
            logger.info("Ingested %d document chunks for tenant %s", chunks_count, tid)

        # Initialize Master State
        state = MasterEngineState(
            session_id=session_id,
            mode=mode,
            brand_profile=brand_profile,
            current_stage=PipelineStage.INITIALIZATION.value,
        )

        # Stage 1: Empirical VNC Reconnaissance (Agent 1)
        StateMachine.advance_stage(state)
        analyst_slice = ContextIsolator.get_analyst_slice(state)
        analyst_out = await self.agent_1_analyst.run(analyst_slice)
        state.research_repository.dom_snapshots.update(analyst_out.get("dom_snapshots", {}))
        state.research_repository.visual_evidence_vnc.extend(analyst_out.get("visual_evidence_vnc", []))
        state.research_repository.competitor_profiles.extend(analyst_out.get("competitors", []))
        await self.short_term_memory.save_stage_buffer(session_id, "analyst", analyst_out)

        # Stage 2: Audience & Friction Modeling (Agent 2)
        StateMachine.advance_stage(state)
        audience_slice = ContextIsolator.get_audience_slice(state)
        audience_out = await self.agent_2_audience.run(audience_slice)
        state.strategic_artifacts.audience_analysis = audience_out.get("audience_analysis", {})
        await self.short_term_memory.save_stage_buffer(session_id, "audience", audience_out)

        # Stage 3: Brand Positioning & Category of One (Agent 3)
        StateMachine.advance_stage(state)
        brand_slice = ContextIsolator.get_brand_slice(state)
        brand_out = await self.agent_3_brand.run(brand_slice)
        state.strategic_artifacts.brand_positioning = brand_out.get("brand_positioning", {})
        await self.short_term_memory.save_stage_buffer(session_id, "brand", brand_out)

        # Stage 4: SEO & Content Gap Auditing (Agent 4)
        StateMachine.advance_stage(state)
        seo_slice = ContextIsolator.get_seo_slice(state)
        seo_out = await self.agent_4_seo.run(seo_slice)
        state.strategic_artifacts.seo_and_content_plan = seo_out.get("seo_and_content_plan", {})
        await self.short_term_memory.save_stage_buffer(session_id, "seo", seo_out)

        # Stage 5 & 6: Strategic Synthesis and Adversarial Revision Loop
        while state.iteration_counter <= StateMachine.MAX_REVISION_LOOPS:
            # Stage 5: Growth Strategist (Agent 5)
            state.current_stage = PipelineStage.GROWTH.value
            growth_slice = ContextIsolator.get_growth_slice(state)
            growth_out = await self.agent_5_growth.run(growth_slice)
            state.strategic_artifacts.growth_initiatives = growth_out.get("growth_initiatives", [])
            await self.short_term_memory.save_stage_buffer(session_id, f"growth_cycle_{state.iteration_counter}", growth_out)

            # Stage 6: Strategy Validator (Agent 6)
            state.current_stage = PipelineStage.VALIDATOR.value
            validator_slice = ContextIsolator.get_validator_slice(state)
            validator_out = await self.agent_6_validator.run(validator_slice)
            state.validation_report = validator_out["validation_report"]
            state.strategic_artifacts.growth_initiatives = validator_out["validated_initiatives"]

            # Evaluate verdict
            next_stage, approved, purged = StateMachine.process_validation_verdict(state)

            # Record audit logs in long-term memory
            for item in state.strategic_artifacts.growth_initiatives:
                await self.long_term_memory.save_audit_log(
                    session_id=session_id,
                    tenant_id=tid,
                    recommendation_id=item.recommendation_id,
                    status=item.approval_status.value,
                    audit_data=item.model_dump(),
                )

            if next_stage == PipelineStage.COMPLETED:
                break

        # Save historical baseline
        for init in state.strategic_artifacts.growth_initiatives:
            if init.approval_status == ApprovalStatus.APPROVED:
                await self.long_term_memory.save_baseline(
                    tenant_id=tid,
                    brand_name=brand_profile.brand_name,
                    website_url=str(brand_profile.website_url),
                    kpi=init.success_metric.kpi,
                    baseline=init.success_metric.baseline,
                )

        return state

    def compile_final_strategy_dossier(self, state: MasterEngineState) -> Dict[str, Any]:
        """Compiles clean, executive-ready strategy report."""
        approved = [
            init.model_dump()
            for init in state.strategic_artifacts.growth_initiatives
            if init.approval_status == ApprovalStatus.APPROVED
        ]

        return {
            "session_id": state.session_id,
            "mode": state.mode.value,
            "brand_name": state.brand_profile.brand_name,
            "target_url": str(state.brand_profile.website_url),
            "validation_status": state.validation_report.status,
            "total_initiatives": len(approved),
            "approved_initiatives": approved,
            "strategic_artifacts": {
                "audience_analysis": state.strategic_artifacts.audience_analysis,
                "brand_positioning": state.strategic_artifacts.brand_positioning,
                "seo_and_content_plan": state.strategic_artifacts.seo_and_content_plan,
            },
            "validation_report": state.validation_report.model_dump(),
        }
