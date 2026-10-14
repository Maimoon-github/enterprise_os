"""Agent 0: Master Supervisor coordinating multi-agent strategy pipeline execution."""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.agents.analyst_agent import AnalystAgent
from src.agents.audience_agent import AudienceAgent
from src.agents.base_agent import BaseAgent
from src.agents.brand_agent import BrandAgent
from src.agents.growth_agent import GrowthAgent
from src.agents.seo_content_agent import SEOContentAgent
from src.agents.validator_agent import ValidatorAgent
from src.memory.long_term import LongTermMemory
from src.memory.short_term import SessionNodeType, ShortTermMemory
from src.orchestrator.context_isolator import ContextIsolator
from src.orchestrator.state_machine import PipelineStage, StateMachine
from src.rag.chunker import DocumentChunker
from src.rag.parser import DocumentParser
from src.rag.store import VectorStore
from src.schemas.initiative import ApprovalStatus, StrategicInitiative
from src.schemas.state import (
    BrandProfile,
    MasterEngineState,
    OperationalMode,
    ResearchRepository,
    StrategicArtifacts,
)
from src.schemas.validation import ValidationReport
from src.tools.browser_bridge import BrowserBridge
from src.tools.rag_search import RAGSearchTool

logger = logging.getLogger(__name__)


class CapabilitiesConfig:
    """Antigravity SDK RBAC capabilities configuration."""

    def __init__(
        self,
        allow_vnc_sandbox: bool = False,
        allow_terminal_exec: bool = False,
        allow_filesystem_edit: bool = False,
        whitelisted_tools: Optional[List[str]] = None,
    ):
        self.allow_vnc_sandbox = allow_vnc_sandbox
        self.allow_terminal_exec = allow_terminal_exec
        self.allow_filesystem_edit = allow_filesystem_edit
        self.whitelisted_tools = whitelisted_tools or []


class LocalAgentConfig:
    """Antigravity SDK local agent configuration contract."""

    def __init__(
        self,
        system_instructions: str = "",
        model_name: str = "qwen2.5:14b-instruct-q4_K_M",
        context_window: int = 32768,
        temperature: float = 0.1,
        capabilities: Optional[CapabilitiesConfig] = None,
    ):
        self.system_instructions = system_instructions
        self.model_name = model_name
        self.context_window = context_window
        self.temperature = temperature
        self.capabilities = capabilities or CapabilitiesConfig()


class StrategyOrchestrator(BaseAgent):
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
        super().__init__(
            agent_id="Agent_0",
            name="Brand Strategy Orchestrator",
            model_name="qwen2.5:14b-instruct-q4_K_M",
            system_prompt=self.SYSTEM_PROMPT,
            context_window=32768,
            temperature=0.1,
            ollama_base_url=ollama_base_url,
        )
        self.whitelisted_tool_names = [
            "delegate_task",
            "merge_agent_payload",
            "route_revisions",
            "compile_strategy_dossier",
        ]
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

        # Register Agent 0 supervisory tools
        self.register_tool("delegate_task", self.delegate_task)
        self.register_tool("merge_agent_payload", self.merge_agent_payload)
        self.register_tool("route_revisions", self.route_revisions)
        self.register_tool("compile_strategy_dossier", self.compile_strategy_dossier)

    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        """Deterministic supervisor fallback."""
        return json.dumps({
            "status": "governed_execution",
            "supervisor": self.name,
            "role": "Central routing and state machine lifecycle coordinator",
        })

    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Executes supervisor orchestration check."""
        return {"supervisor_status": "ready"}

    async def delegate_task(self, agent_id: str, target_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches bounded context slice to a domain specialist subagent with schema validation."""
        agent_map = {
            "Agent_1": self.agent_1_analyst,
            "Agent_2": self.agent_2_audience,
            "Agent_3": self.agent_3_brand,
            "Agent_4": self.agent_4_seo,
            "Agent_5": self.agent_5_growth,
            "Agent_6": self.agent_6_validator,
        }
        target_agent = agent_map.get(agent_id)
        if not target_agent:
            raise ValueError(f"Unknown specialist subagent target: {agent_id}")

        logger.info("Supervisor delegating task to %s (%s)", agent_id, target_agent.name)
        payload = await target_agent.run(target_slice)
        return payload

    def merge_agent_payload(
        self,
        state: MasterEngineState,
        stage_name: str,
        payload: Dict[str, Any],
    ) -> MasterEngineState:
        """Merges validated subagent findings into MasterEngineState."""
        if stage_name in ("Analyst", PipelineStage.ANALYST.value):
            state.research_repository.dom_snapshots.update(payload.get("dom_snapshots", {}))
            state.research_repository.visual_evidence_vnc.extend(payload.get("visual_evidence_vnc", []))
            state.research_repository.competitor_profiles.extend(payload.get("competitors", []))
            if payload.get("context_gaps"):
                state.research_repository.context_gaps.extend(payload["context_gaps"])
        elif stage_name in ("Audience", PipelineStage.AUDIENCE.value):
            state.strategic_artifacts.audience_analysis = payload.get("audience_analysis", {})
            if payload.get("context_gaps"):
                state.research_repository.context_gaps.extend(payload["context_gaps"])
        elif stage_name in ("Brand", PipelineStage.BRAND.value):
            state.strategic_artifacts.brand_positioning = payload.get("brand_positioning", {})
            if payload.get("context_gaps"):
                state.research_repository.context_gaps.extend(payload["context_gaps"])
        elif stage_name in ("SEO", PipelineStage.SEO.value):
            state.strategic_artifacts.seo_and_content_plan = payload.get("seo_and_content_plan", {})
            if payload.get("context_gaps"):
                state.research_repository.context_gaps.extend(payload["context_gaps"])
        elif stage_name in ("Growth", PipelineStage.GROWTH.value):
            state.strategic_artifacts.growth_initiatives = payload.get("growth_initiatives", [])
        elif stage_name in ("Validator", PipelineStage.VALIDATOR.value):
            state.validation_report = payload["validation_report"]
            state.strategic_artifacts.growth_initiatives = payload["validated_initiatives"]
        return state

    def route_revisions(
        self,
        state: MasterEngineState,
        validation_report: Optional[ValidationReport] = None,
    ) -> Tuple[PipelineStage, List[StrategicInitiative], List[StrategicInitiative]]:
        """Processes adversarial audit verdict and enforces the 3-cycle revision loop ceiling."""
        return StateMachine.process_validation_verdict(state)

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
        """Executes full autonomous multi-agent audit lifecycle under Antigravity governance."""
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

        await self.short_term_memory.add_graph_node(
            session_id=session_id,
            agent_id="Supervisor",
            stage=PipelineStage.INITIALIZATION.value,
            node_type=SessionNodeType.INITIALIZATION,
            payload={"mode": mode.value, "brand_name": brand_profile.brand_name},
        )

        # Stage 1: Empirical VNC Reconnaissance (Agent 1)
        StateMachine.advance_stage(state)
        analyst_slice = ContextIsolator.get_analyst_slice(state)
        await self.react_step(
            step_number=1,
            thought="Inspecting initialization gate -> Stage 1 (Analyst). Delegating VNC reconnaissance.",
            action="delegate_task",
            action_args={"agent_id": "Agent_1", "target_slice": analyst_slice},
            reflection="Empirical VNC reconnaissance delegated to Agent 1; advancing state machine to Audience stage.",
        )
        analyst_out = await self.delegate_task("Agent_1", analyst_slice)
        self.merge_agent_payload(state, PipelineStage.ANALYST.value, analyst_out)
        await self.short_term_memory.save_stage_buffer(session_id, "analyst", analyst_out)
        await self.short_term_memory.add_graph_node(
            session_id=session_id,
            agent_id="Agent_1",
            stage=PipelineStage.ANALYST.value,
            node_type=SessionNodeType.STAGE_HANDOFF,
            payload={"output_keys": list(analyst_out.keys())},
        )

        # Stage 2: Audience & Friction Modeling (Agent 2)
        StateMachine.advance_stage(state)
        audience_slice = ContextIsolator.get_audience_slice(state)
        await self.react_step(
            step_number=2,
            thought="Advancing to Stage 2 (Audience). Delegating ICP and customer journey mapping.",
            action="delegate_task",
            action_args={"agent_id": "Agent_2", "target_slice": audience_slice},
            reflection="Audience ICP and user journey friction delegated to Agent 2; advancing state machine to Brand stage.",
        )
        audience_out = await self.delegate_task("Agent_2", audience_slice)
        self.merge_agent_payload(state, PipelineStage.AUDIENCE.value, audience_out)
        await self.short_term_memory.save_stage_buffer(session_id, "audience", audience_out)
        await self.short_term_memory.add_graph_node(
            session_id=session_id,
            agent_id="Agent_2",
            stage=PipelineStage.AUDIENCE.value,
            node_type=SessionNodeType.STAGE_HANDOFF,
            payload={"output_keys": list(audience_out.keys())},
        )

        # Stage 3: Brand Positioning & Category of One (Agent 3)
        StateMachine.advance_stage(state)
        brand_slice = ContextIsolator.get_brand_slice(state)
        await self.react_step(
            step_number=3,
            thought="Advancing to Stage 3 (Brand). Delegating Category of One differentiation analysis.",
            action="delegate_task",
            action_args={"agent_id": "Agent_3", "target_slice": brand_slice},
            reflection="Brand Category of One differentiation delegated to Agent 3; advancing state machine to SEO stage.",
        )
        brand_out = await self.delegate_task("Agent_3", brand_slice)
        self.merge_agent_payload(state, PipelineStage.BRAND.value, brand_out)
        await self.short_term_memory.save_stage_buffer(session_id, "brand", brand_out)
        await self.short_term_memory.add_graph_node(
            session_id=session_id,
            agent_id="Agent_3",
            stage=PipelineStage.BRAND.value,
            node_type=SessionNodeType.STAGE_HANDOFF,
            payload={"output_keys": list(brand_out.keys())},
        )

        # Stage 4: SEO & Content Gap Auditing (Agent 4)
        StateMachine.advance_stage(state)
        seo_slice = ContextIsolator.get_seo_slice(state)
        await self.react_step(
            step_number=4,
            thought="Advancing to Stage 4 (SEO). Delegating technical audit and commercial search mapping.",
            action="delegate_task",
            action_args={"agent_id": "Agent_4", "target_slice": seo_slice},
            reflection="Technical SEO and semantic gap audit delegated to Agent 4; advancing state machine to Growth stage.",
        )
        seo_out = await self.delegate_task("Agent_4", seo_slice)
        self.merge_agent_payload(state, PipelineStage.SEO.value, seo_out)
        await self.short_term_memory.save_stage_buffer(session_id, "seo", seo_out)
        await self.short_term_memory.add_graph_node(
            session_id=session_id,
            agent_id="Agent_4",
            stage=PipelineStage.SEO.value,
            node_type=SessionNodeType.STAGE_HANDOFF,
            payload={"output_keys": list(seo_out.keys())},
        )

        # Stage 5 & 6: Strategic Synthesis and Adversarial Revision Loop
        while state.iteration_counter <= StateMachine.MAX_REVISION_LOOPS:
            # Stage 5: Growth Strategist (Agent 5)
            state.current_stage = PipelineStage.GROWTH.value
            growth_slice = ContextIsolator.get_growth_slice(state)
            await self.react_step(
                step_number=5,
                thought=f"Executing Stage 5 (Growth) in cycle {state.iteration_counter}. Synthesizing ICE initiatives.",
                action="delegate_task",
                action_args={"agent_id": "Agent_5", "target_slice": growth_slice},
                reflection=f"Growth initiative synthesis delegated to Agent 5 in cycle {state.iteration_counter}; advancing to Validator.",
            )
            growth_out = await self.delegate_task("Agent_5", growth_slice)
            self.merge_agent_payload(state, PipelineStage.GROWTH.value, growth_out)
            await self.short_term_memory.save_stage_buffer(session_id, f"growth_cycle_{state.iteration_counter}", growth_out)
            await self.short_term_memory.add_graph_node(
                session_id=session_id,
                agent_id="Agent_5",
                stage=PipelineStage.GROWTH.value,
                node_type=SessionNodeType.STAGE_HANDOFF,
                payload={"cycle": state.iteration_counter},
            )

            # Stage 6: Strategy Validator (Agent 6)
            state.current_stage = PipelineStage.VALIDATOR.value
            validator_slice = ContextIsolator.get_validator_slice(state)
            await self.react_step(
                step_number=6,
                thought="Advancing to Stage 6 (Validator). Executing adversarial audit and provenance check.",
                action="delegate_task",
                action_args={"agent_id": "Agent_6", "target_slice": validator_slice},
                reflection="Adversarial audit and provenance verification delegated to Agent 6; awaiting verdict.",
            )
            validator_out = await self.delegate_task("Agent_6", validator_slice)
            self.merge_agent_payload(state, PipelineStage.VALIDATOR.value, validator_out)
            await self.short_term_memory.add_graph_node(
                session_id=session_id,
                agent_id="Agent_6",
                stage=PipelineStage.VALIDATOR.value,
                node_type=SessionNodeType.STAGE_HANDOFF,
                payload={"validation_status": str(validator_out.get("validation_report"))},
            )

            # Evaluate verdict
            next_stage, approved, purged = self.route_revisions(state)

            # Record audit logs in long-term memory
            for item in state.strategic_artifacts.growth_initiatives:
                await self.long_term_memory.save_audit_log(
                    session_id=session_id,
                    tenant_id=tid,
                    recommendation_id=item.recommendation_id,
                    status=item.approval_status.value,
                    audit_data=item.model_dump(),
                )

            # Snapshot session state
            await self.long_term_memory.save_session_state(
                session_id=session_id,
                tenant_id=tid,
                state_data=state.model_dump(),
            )

            if next_stage == PipelineStage.COMPLETED:
                break

        # Save brand profile, competitor footprints, and historical baselines
        await self.long_term_memory.save_brand_profile(
            tenant_id=tid,
            client_id="default_client",
            brand_name=brand_profile.brand_name,
            website_url=brand_profile.website_url,
            industry=brand_profile.industry,
            business_goals=brand_profile.business_goals,
            target_market=brand_profile.target_market,
        )
        for comp in state.research_repository.competitor_profiles:
            await self.long_term_memory.save_competitor_footprint(
                tenant_id=tid,
                client_id="default_client",
                competitor_name=comp.get("name", "Unknown"),
                domain=comp.get("domain", ""),
                positioning_summary=comp.get("positioning_summary", ""),
            )

        for init in state.strategic_artifacts.growth_initiatives:
            if init.approval_status == ApprovalStatus.APPROVED:
                await self.long_term_memory.save_baseline(
                    tenant_id=tid,
                    brand_name=brand_profile.brand_name,
                    website_url=brand_profile.website_url,
                    kpi=init.success_metric.kpi,
                    baseline=init.success_metric.baseline,
                )

        return state

    def compile_strategy_dossier(self, state: MasterEngineState) -> Dict[str, Any]:
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
            "target_url": state.brand_profile.website_url,
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

    # Backward-compatible alias
    compile_final_strategy_dossier = compile_strategy_dossier


class AntigravityRuntimeHarness:
    """Stateful runtime harness and multi-agent execution supervisor under Google Antigravity SDK."""

    def __init__(
        self,
        orchestrator: Optional[StrategyOrchestrator] = None,
        ollama_base_url: str = "http://localhost:11434",
    ):
        self.orchestrator = orchestrator or StrategyOrchestrator(ollama_base_url=ollama_base_url)

    async def execute_governed_pipeline(
        self,
        brand_profile: BrandProfile,
        mode: OperationalMode,
        docs_dir: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> MasterEngineState:
        """Executes full multi-agent workflow under Antigravity governance and lifecycle policies."""
        return await self.orchestrator.execute_audit(
            brand_profile=brand_profile,
            mode=mode,
            docs_dir=docs_dir,
            tenant_id=tenant_id,
        )
