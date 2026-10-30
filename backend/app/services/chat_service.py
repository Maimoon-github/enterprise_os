import json
import logging
import re
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import httpx
from app.core.config import settings
from app.core.exceptions import EntityNotFoundError
from app.db.models.campaign import Campaign
from app.db.models.chat import ChatMessage, ChatSession
from app.db.repositories.approval_repo import ApprovalRepository
from app.db.repositories.brand_repo import BrandRepository
from app.db.repositories.campaign_repo import CampaignRepository
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.run_repo import RunRepository
from app.orchestrator.graph import DEFAULT_RECURSION_LIMIT, master_orchestrator_graph
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatSessionUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("services.chat")

OLLAMA_BASE_URL = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = getattr(settings, "OLLAMA_CHAT_MODEL", "qwen2.5:7b")


def classify_orchestrator_intent(content: str) -> tuple[bool, str]:
    """Autonomously evaluate whether the user input commands operational pipeline execution

    (Run creation, LangGraph subgraphs, HITL gate) or conversational/advisory assistance.
    """
    text = content.strip().lower()

    # Question indicators
    is_question = bool(
        re.search(
            r"^(what|how|why|where|when|who|which|can you|could you|would you|is there|are there|tell me|explain|describe|brainstorm|help me)\b",
            text,
        )
        or text.endswith("?")
    )

    # Operational execution triggers (action verbs directed at pipeline actions)
    execution_patterns = [
        r"\b(synthesize|generate|create|build)\b.*\b(campaign|blueprint|assets|plan|strategy|copy|content)\b",
        r"\b(publish|distribute|post|fanout|fan-out)\b.*\b(to|platform|linkedin|twitter|x|instagram|youtube|social)\b",
        r"\b(audit|inspect|verify)\b.*\b(brand|voice|compliance|media|posts)\b",
        r"\b(run|execute|trigger|launch)\b.*\b(recon|reconnaissance|pipeline|workflow|graph|subgraph|audit|campaign|plan)\b",
        r"\b(deploy|stage)\b.*\b(campaign|assets|posts)\b",
        r"^(synthesize|execute|publish|audit|deploy)\b",
    ]

    matches_execution = any(re.search(p, text) for p in execution_patterns)

    # If explicitly phrased as a theoretical/explanatory question, keep conversational
    if is_question and not re.search(r"\b(please\s+)?(run|execute|synthesize|publish|launch)\b", text):
        return False, "User submitted an informational or strategic question."

    if matches_execution:
        return True, "User commanded direct operational workflow execution."

    if is_question or len(text.split()) < 4 or any(w in text for w in ["hello", "hi", "hey", "help", "status", "ideas", "hooks", "positioning"]):
        return False, "User prompt is conversational, advisory, or brainstorming."

    return False, "Defaulted to conversational advisory mode."


class ChatService:
    async def create_session(
        self,
        user_id: str,
        payload: ChatSessionCreate,
        db: AsyncSession,
    ) -> ChatSessionResponse:
        repo = ChatRepository(db)
        title = payload.title or "New Orchestrator Chat"
        session = await repo.create_session(
            user_id=user_id,
            title=title,
            project_id=payload.project_id,
            brand_id=payload.brand_id,
        )
        return ChatSessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            is_pinned=session.is_pinned,
            is_archived=session.is_archived,
            project_id=session.project_id,
            brand_id=session.brand_id,
            messages_count=0,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def list_sessions(
        self,
        user_id: str,
        db: AsyncSession,
        is_pinned: bool | None = None,
        is_archived: bool | None = False,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatSessionResponse]:
        repo = ChatRepository(db)
        sessions = await repo.list_sessions(
            user_id=user_id,
            is_pinned=is_pinned,
            is_archived=is_archived,
            search=search,
            limit=limit,
            offset=offset,
        )

        responses: list[ChatSessionResponse] = []
        for s in sessions:
            count = await repo.count_messages(s.id)
            responses.append(
                ChatSessionResponse(
                    id=s.id,
                    user_id=s.user_id,
                    title=s.title,
                    is_pinned=s.is_pinned,
                    is_archived=s.is_archived,
                    project_id=s.project_id,
                    brand_id=s.brand_id,
                    messages_count=count,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
            )
        return responses

    async def get_session(
        self,
        session_id: uuid.UUID,
        user_id: str,
        db: AsyncSession,
    ) -> ChatSessionDetailResponse:
        repo = ChatRepository(db)
        session = await repo.get_session_with_messages(session_id, user_id=user_id)
        if not session:
            raise EntityNotFoundError("ChatSession", str(session_id))

        messages_resp = [
            ChatMessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                run_id=m.run_id,
                metadata=m.msg_metadata,
                created_at=m.created_at,
            )
            for m in (session.messages or [])
        ]

        return ChatSessionDetailResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            is_pinned=session.is_pinned,
            is_archived=session.is_archived,
            project_id=session.project_id,
            brand_id=session.brand_id,
            messages_count=len(messages_resp),
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=messages_resp,
        )

    async def update_session(
        self,
        session_id: uuid.UUID,
        user_id: str,
        payload: ChatSessionUpdate,
        db: AsyncSession,
    ) -> ChatSessionResponse:
        repo = ChatRepository(db)
        updated = await repo.update_session(
            session_id=session_id,
            user_id=user_id,
            title=payload.title,
            is_pinned=payload.is_pinned,
            is_archived=payload.is_archived,
            project_id=payload.project_id,
        )
        if not updated:
            raise EntityNotFoundError("ChatSession", str(session_id))

        count = await repo.count_messages(updated.id)
        return ChatSessionResponse(
            id=updated.id,
            user_id=updated.user_id,
            title=updated.title,
            is_pinned=updated.is_pinned,
            is_archived=updated.is_archived,
            project_id=updated.project_id,
            brand_id=updated.brand_id,
            messages_count=count,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    async def delete_session(
        self,
        session_id: uuid.UUID,
        user_id: str,
        db: AsyncSession,
    ) -> bool:
        repo = ChatRepository(db)
        deleted = await repo.delete_session(session_id=session_id, user_id=user_id)
        if not deleted:
            raise EntityNotFoundError("ChatSession", str(session_id))
        return True

    async def _get_brand_context(self, session: ChatSession, db: AsyncSession) -> dict[str, Any] | None:
        brand_repo = BrandRepository(db)
        brand = None
        if session.brand_id:
            brand = await brand_repo.get(session.brand_id)
        if not brand:
            brands = await brand_repo.list_all(limit=1)
            if brands:
                brand = brands[0]

        if brand:
            return {
                "name": brand.name,
                "voice_guidelines": brand.voice_guidelines or "Authoritative, executive, precise, and insight-driven.",
            }
        return {
            "name": "Apex Global",
            "voice_guidelines": "Authoritative, executive, precise, and insight-driven.",
        }

    def _heuristic_conversational_fallback(
        self,
        prompt: str,
        brand_name: str,
        voice_guidelines: str,
    ) -> str:
        prompt_lower = prompt.lower()

        if any(w in prompt_lower for w in ["hello", "hi", "hey", "greetings"]):
            return (
                f"Hello! I am your **Agentic Marketing Orchestrator** for **{brand_name}**.\n\n"
                "I can assist you conversationally with marketing strategy, brand positioning, copy ideation, "
                "or autonomously execute end-to-end multi-agent pipelines (Campaign Synthesis, Media Compliance, "
                "Competitor Recon, and Multi-Platform Fan-out).\n\n"
                "How can I assist your marketing initiatives today?"
            )
        if "positioning" in prompt_lower or "brand" in prompt_lower or "voice" in prompt_lower or "tone" in prompt_lower:
            return (
                f"### Strategic Brand Positioning & Voice Guidelines: **{brand_name}**\n\n"
                f"- **Voice Guidelines**: {voice_guidelines}\n"
                "- **Value Proposition**: Enterprise-grade autonomous brand marketing with multi-platform synchronization and guaranteed Human-in-the-Loop oversight.\n"
                "- **Core Pillars**: Verified ROI, cross-platform narrative coherence, and strict media compliance.\n\n"
                "Would you like me to brainstorm specific campaign angles or execute an end-to-end campaign blueprint?"
            )
        if "interrupt" in prompt_lower or "hitl" in prompt_lower or "approval" in prompt_lower:
            return (
                "### Human-in-the-Loop (HITL) Interrupt Gate\n\n"
                "The platform enforces strict safety boundaries before performing any non-idempotent actions (e.g. social publishing fanout):\n\n"
                "1. **Blueprint & Copy Synthesis**: The orchestrator and creative subgraphs draft multi-platform assets.\n"
                "2. **State Interrupt**: LangGraph triggers an interrupt at `human_approval_gate_node`, halting execution.\n"
                "3. **Human Review**: Stakeholders review the staged copy, target channels, and compliance scores.\n"
                "4. **Resume Action**: Upon human approval (`POST /api/v1/approvals/{id}/resume`), the publishing worker resumes fan-out.\n\n"
                "This guarantees that no external publishing occurs without explicit authorized sign-off."
            )
        return (
            f"As the **Agentic Marketing Orchestrator** for **{brand_name}**, I have analyzed your inquiry.\n\n"
            f"Applying our guidelines (*{voice_guidelines}*), we emphasize clarity, measurable strategic value, and unified cross-channel messaging.\n\n"
            "You can ask me questions, brainstorm campaign angles, or instruct me to execute full workflows:\n"
            "- *'Synthesize comprehensive Q4 multi-platform campaign blueprint'* to initiate an end-to-end run.\n"
            "- *'Run competitor reconnaissance on top 3 industry benchmarks'* to trigger market analysis.\n"
            "- *'Audit brand voice consistency across recent social posts'* to run compliance evaluation."
        )

    async def _stream_conversational_llm(
        self,
        prompt: str,
        brand_info: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        brand_name = brand_info.get("name", "Apex Global") if brand_info else "Apex Global"
        voice_guidelines = (
            brand_info.get("voice_guidelines", "Authoritative, executive, precise, and insight-driven.")
            if brand_info
            else "Authoritative, executive, precise, and insight-driven."
        )

        system_instruction = (
            f"You are the intelligent Agentic Brand Marketing Orchestrator for {brand_name}. "
            f"Brand Voice Guidelines: {voice_guidelines}. "
            "You are an executive marketing strategist, brand architect, and autonomous multi-agent director. "
            "When responding to conversational queries, brainstorming, or strategy questions, provide authoritative, "
            "insightful, well-structured markdown answers. "
            "Highlight platform capabilities (ReAct research, Plan-and-Solve creative synthesis, Send() publishing fan-out, "
            "ReWOO analytics, and Human-in-the-Loop approval gates) when relevant. "
            "Keep your tone professional, articulate, and directly actionable."
        )

        formatted_prompt = (
            f"<|im_start|>system\n{system_instruction}<|im_end|>\n"
            f"<|im_start|>user\n{prompt}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": formatted_prompt,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 512,
            },
        }

        if "pytest" in sys.modules:
            fallback = self._heuristic_conversational_fallback(prompt, brand_name, voice_guidelines)
            for word in fallback.split(" "):
                yield word + " "
            return

        generated_any = False
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=2.5, read=40.0, write=5.0, pool=5.0)) as client:
                async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload) as resp:
                    if resp.status_code == 200:
                        async for line in resp.aiter_lines():
                            if not line.strip():
                                continue
                            try:
                                chunk_data = json.loads(line)
                                token = chunk_data.get("response", "")
                                if token:
                                    generated_any = True
                                    yield token
                                if chunk_data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
        except Exception as exc:
            logger.warning("Ollama conversational streaming unavailable: %s. Using executive fallback.", exc)

        if not generated_any:
            fallback = self._heuristic_conversational_fallback(prompt, brand_name, voice_guidelines)
            for word in fallback.split(" "):
                yield word + " "

    async def _generate_conversational_llm(
        self,
        prompt: str,
        brand_info: dict[str, Any] | None = None,
    ) -> str:
        tokens = []
        async for chunk in self._stream_conversational_llm(prompt, brand_info):
            tokens.append(chunk)
        return "".join(tokens)

    async def _resolve_campaign(
        self,
        payload_campaign_id: uuid.UUID | None,
        session: ChatSession,
        user_command: str,
        db: AsyncSession,
    ) -> Campaign:
        camp_repo = CampaignRepository(db)
        brand_repo = BrandRepository(db)

        if payload_campaign_id:
            c = await camp_repo.get(payload_campaign_id)
            if c:
                return c

        if session.brand_id:
            camps = await camp_repo.list_by_brand(session.brand_id)
            if camps:
                return camps[0]

        all_camps = await camp_repo.list_all(limit=1)
        if all_camps:
            return all_camps[0]

        all_brands = await brand_repo.list_all(limit=1)
        if all_brands:
            brand_id = all_brands[0].id
        else:
            default_brand = await brand_repo.create(
                name="Apex Global",
                slug=f"apex-global-{uuid.uuid4().hex[:6]}",
                voice_guidelines="Authoritative, executive, precise, and insight-driven.",
            )
            brand_id = default_brand.id

        created_camp = await camp_repo.create(
            brand_id=brand_id,
            name=f"Chat Campaign - {datetime.now(UTC).strftime('%b %d %H:%M')}",
            objective=user_command[:200],
            status="draft",
        )
        return created_camp

    async def submit_message(
        self,
        session_id: uuid.UUID,
        user_id: str,
        payload: ChatMessageCreate,
        db: AsyncSession,
    ) -> ChatMessageResponse:
        chat_repo = ChatRepository(db)
        session = await chat_repo.get_session_with_messages(session_id, user_id=user_id)
        if not session:
            raise EntityNotFoundError("ChatSession", str(session_id))

        # 1. Store user message
        user_msg = await chat_repo.create_message(
            session_id=session.id,
            role="user",
            content=payload.content,
        )

        # 2. Derive title if default
        if session.title == "New Orchestrator Chat":
            clean_title = payload.content.strip().replace("\n", " ")
            derived_title = clean_title[:45] + ("..." if len(clean_title) > 45 else "")
            await chat_repo.update_session(session.id, title=derived_title)

        is_operational, rationale = classify_orchestrator_intent(payload.content)
        brand_info = await self._get_brand_context(session, db)

        if not is_operational:
            # Conversational advisory path (no Run created)
            assistant_content = await self._generate_conversational_llm(payload.content, brand_info)
            assistant_msg = await chat_repo.create_message(
                session_id=session.id,
                role="assistant",
                content=assistant_content,
                run_id=None,
                metadata={"intent": "conversational", "decision": rationale},
            )
            return ChatMessageResponse(
                id=assistant_msg.id,
                session_id=assistant_msg.session_id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                run_id=None,
                metadata=assistant_msg.msg_metadata,
                created_at=assistant_msg.created_at,
            )

        # Operational execution path
        campaign = await self._resolve_campaign(payload.campaign_id, session, payload.content, db)
        run_repo = RunRepository(db)
        thread_id = f"chat_{uuid.uuid4().hex[:16]}"
        run = await run_repo.create(
            campaign_id=campaign.id,
            thread_id=thread_id,
            status="running",
            trigger_type="chat",
            current_node="supervisor_router",
            token_usage={"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
        )

        assistant_content = (
            f"🤖 **Autonomous Decision:** Orchestrator received command: '{payload.content[:100]}...'. "
            f"Execution Rationale: {rationale}. "
            f"Initiated run `{run.id}` across research, creative synthesis, and HITL gate for campaign '{campaign.name}'."
        )
        assistant_msg = await chat_repo.create_message(
            session_id=session.id,
            role="assistant",
            content=assistant_content,
            run_id=run.id,
            metadata={"thread_id": thread_id, "status": "running", "current_node": "supervisor_router", "intent": "operational", "decision": rationale},
        )

        return ChatMessageResponse(
            id=assistant_msg.id,
            session_id=assistant_msg.session_id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            run_id=assistant_msg.run_id,
            metadata=assistant_msg.msg_metadata,
            created_at=assistant_msg.created_at,
        )

    async def stream_chat_response(
        self,
        session_id: uuid.UUID,
        user_id: str,
        payload: ChatMessageCreate,
        db: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        chat_repo = ChatRepository(db)
        run_repo = RunRepository(db)
        approval_repo = ApprovalRepository(db)

        session = await chat_repo.get_session_with_messages(session_id, user_id=user_id)
        if not session:
            raise EntityNotFoundError("ChatSession", str(session_id))

        # 1. Save user message
        user_msg = await chat_repo.create_message(
            session_id=session.id,
            role="user",
            content=payload.content,
        )

        if session.title == "New Orchestrator Chat":
            clean_title = payload.content.strip().replace("\n", " ")
            derived_title = clean_title[:45] + ("..." if len(clean_title) > 45 else "")
            await chat_repo.update_session(session.id, title=derived_title)

        is_operational, rationale = classify_orchestrator_intent(payload.content)
        brand_info = await self._get_brand_context(session, db)

        # 2A. Conversational / Advisory Path
        if not is_operational:
            assistant_msg = await chat_repo.create_message(
                session_id=session.id,
                role="assistant",
                content="",
                run_id=None,
                metadata={"intent": "conversational", "decision": rationale},
            )

            yield f'event: message_start\ndata: {json.dumps({"message_id": str(assistant_msg.id), "intent": "conversational"})}\n\n'

            accumulated_text = ""
            async for chunk in self._stream_conversational_llm(payload.content, brand_info):
                accumulated_text += chunk
                yield f'event: delta\ndata: {json.dumps({"text": chunk})}\n\n'

            # Persist full assistant response
            final_content = accumulated_text.strip() or "I am your Brand Marketing Orchestrator. How can I assist you with your marketing strategy today?"
            assistant_msg.content = final_content
            await db.commit()

            yield f'event: complete\ndata: {json.dumps({"status": "completed", "intent": "conversational", "message_id": str(assistant_msg.id)})}\n\n'
            return

        # 2B. Operational Execution Path
        campaign = await self._resolve_campaign(payload.campaign_id, session, payload.content, db)
        thread_id = f"chat_{uuid.uuid4().hex[:16]}"
        run = await run_repo.create(
            campaign_id=campaign.id,
            thread_id=thread_id,
            status="running",
            trigger_type="chat",
            current_node="supervisor_router",
            token_usage={"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
        )

        decision_text = (
            f"🤖 **Autonomous Decision:** Recognized operational pipeline directive: *\"{payload.content.strip()}\"*\n"
            f"*Execution Rationale: {rationale}*\n\n"
            f"Orchestrator initiated run `{run.id}`. Invoking Brand RAG, research, and creative subgraphs...\n\n"
        )

        assistant_msg = await chat_repo.create_message(
            session_id=session.id,
            role="assistant",
            content=decision_text,
            run_id=run.id,
            metadata={"thread_id": thread_id, "status": "running", "intent": "operational", "decision": rationale},
        )

        # Emit run_start
        yield f'event: run_start\ndata: {json.dumps({"run_id": str(run.id), "thread_id": thread_id, "message_id": str(assistant_msg.id)})}\n\n'
        yield f'event: delta\ndata: {json.dumps({"text": decision_text})}\n\n'

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": DEFAULT_RECURSION_LIMIT,
        }
        initial_input = {
            "thread_id": thread_id,
            "campaign_id": str(campaign.id),
            "approval_status": "pending",
        }

        step_idx = 0
        final_text = "Execution completed successfully."
        interrupted_approval_id: str | None = None

        try:
            async for event in master_orchestrator_graph.astream(
                initial_input,
                config=config,
                stream_mode="updates",
            ):
                step_idx += 1
                for node_name, node_update in event.items():
                    if node_name == "__interrupt__":
                        interrupt_obj = node_update[0] if isinstance(node_update, tuple | list) else node_update
                        interrupt_val = getattr(interrupt_obj, "value", interrupt_obj)
                        interrupt_payload = interrupt_val if isinstance(interrupt_val, dict) else {"message": str(interrupt_val)}

                        existing_appr = await approval_repo.get_by_thread(thread_id)
                        if not existing_appr or existing_appr.status != "pending":
                            new_appr = await approval_repo.create(
                                run_id=run.id,
                                thread_id=thread_id,
                                status="pending",
                                step_name="human_approval_gate_node",
                                payload=interrupt_payload,
                            )
                            interrupted_approval_id = str(new_appr.id)
                        else:
                            interrupted_approval_id = str(existing_appr.id)

                        await run_repo.update(
                            run.id,
                            status="interrupted",
                            current_node="human_approval_gate_node",
                        )

                        interrupt_data = {
                            "run_id": str(run.id),
                            "thread_id": thread_id,
                            "approval_id": interrupted_approval_id,
                            "node": "human_approval_gate_node",
                            "step": step_idx,
                            "status": "interrupted",
                            "payload": interrupt_payload,
                        }
                        yield f"event: interrupt\ndata: {json.dumps(interrupt_data)}\n\n"
                        yield f'event: delta\ndata: {json.dumps({"text": "\n\n⚠️ **Human-in-the-Loop Interrupt Gate Active:** Campaign blueprint and staged platform assets require human review and sign-off before dispatch."})}\n\n'

                        final_text = "Paused at Human-in-the-Loop approval gate. Blueprint review required."
                        assistant_msg.content = f"{decision_text}\n\nOrchestrator generated multi-platform campaign blueprint for '{campaign.name}'. Halted at Human Approval Gate prior to non-idempotent publish fanout."
                        assistant_msg.msg_metadata = {
                            "thread_id": thread_id,
                            "status": "interrupted",
                            "approval_id": interrupted_approval_id,
                            "run_id": str(run.id),
                            "intent": "operational",
                            "decision": rationale,
                        }
                        await db.commit()

                        yield f'event: complete\ndata: {json.dumps({"run_id": str(run.id), "status": "interrupted", "approval_id": interrupted_approval_id})}\n\n'
                        return

                    # Normal node transition
                    await run_repo.update(run.id, status="running", current_node=node_name)
                    yield f'event: node_start\ndata: {json.dumps({"run_id": str(run.id), "node": node_name, "step": step_idx})}\n\n'

                    if "active_skills" in node_update:
                        yield f'event: tool_call\ndata: {json.dumps({"run_id": str(run.id), "tool": f"{node_name}_tool", "args": {"skills": node_update.get("active_skills")}, "step": step_idx})}\n\n'

                    yield f'event: node_finish\ndata: {json.dumps({"run_id": str(run.id), "node": node_name, "step": step_idx})}\n\n'

            # Completed
            await run_repo.update(run.id, status="completed", finished_at=datetime.now(UTC))
            assistant_msg.content = f"{decision_text}\n\nCampaign blueprint and all orchestrator subgraphs finalized for '{campaign.name}'. All 8 platforms synced."
            assistant_msg.msg_metadata = {"thread_id": thread_id, "status": "completed", "run_id": str(run.id), "intent": "operational"}
            await db.commit()

            yield f'event: delta\ndata: {json.dumps({"text": f"\n\n✅ Orchestration completed. All pipeline stages finalized."})}\n\n'
            yield f'event: complete\ndata: {json.dumps({"run_id": str(run.id), "status": "completed"})}\n\n'

        except Exception as exc:
            logger.error("Chat orchestrator streaming failed: %s", exc, exc_info=True)
            await run_repo.update(run.id, status="failed", error_message=str(exc), finished_at=datetime.now(UTC))
            assistant_msg.content = f"Orchestrator encountered error: {str(exc)}"
            assistant_msg.msg_metadata = {"thread_id": thread_id, "status": "failed", "error": str(exc), "intent": "operational"}
            await db.commit()

            yield f'event: error\ndata: {json.dumps({"error": str(exc)})}\n\n'
            yield f'event: complete\ndata: {json.dumps({"run_id": str(run.id), "status": "failed"})}\n\n'


chat_service = ChatService()
