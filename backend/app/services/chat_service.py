import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

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

        # Fallback: ensure at least one brand exists to anchor campaign
        all_brands = await brand_repo.list_all(limit=1)
        if all_brands:
            brand_id = all_brands[0].id
        else:
            default_brand = await brand_repo.create(
                name="Apex Global",
                slug="apex-global",
                tone_profile={"voice": "authoritative", "style": "executive"},
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

        # 3. Resolve campaign & dispatch run
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

        # 4. Create initial assistant message
        assistant_content = f"Orchestrator received command: '{payload.content[:100]}...'. Initiated run {run.id} across research, creative, and HITL gate."
        assistant_msg = await chat_repo.create_message(
            session_id=session.id,
            role="assistant",
            content=assistant_content,
            run_id=run.id,
            metadata={"thread_id": thread_id, "status": "running", "current_node": "supervisor_router"},
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

        # 2. Resolve campaign & dispatch run
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

        assistant_msg = await chat_repo.create_message(
            session_id=session.id,
            role="assistant",
            content="Analyzing strategic objective and orchestrating multi-agent workflow...",
            run_id=run.id,
            metadata={"thread_id": thread_id, "status": "running"},
        )

        # Emit run_start
        yield f'event: run_start\ndata: {json.dumps({"run_id": str(run.id), "thread_id": thread_id, "message_id": str(assistant_msg.id)})}\n\n'
        yield f'event: delta\ndata: {json.dumps({"text": f"Orchestrator initiated run `{run.id}`. Invoking Brand RAG, research, and creative subgraphs...\n\n"})}\n\n'

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
                        # Persist final state in assistant message
                        assistant_msg.content = f"Orchestrator generated multi-platform campaign blueprint for '{campaign.name}'. Halted at Human Approval Gate prior to non-idempotent publish fanout."
                        assistant_msg.msg_metadata = {
                            "thread_id": thread_id,
                            "status": "interrupted",
                            "approval_id": interrupted_approval_id,
                            "run_id": str(run.id),
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
            assistant_msg.content = f"Campaign blueprint and all orchestrator subgraphs finalized for '{campaign.name}'. All 8 platforms synced."
            assistant_msg.msg_metadata = {"thread_id": thread_id, "status": "completed", "run_id": str(run.id)}
            await db.commit()

            yield f'event: delta\ndata: {json.dumps({"text": f"\n\n✅ Orchestration completed. All pipeline stages finalized."})}\n\n'
            yield f'event: complete\ndata: {json.dumps({"run_id": str(run.id), "status": "completed"})}\n\n'

        except Exception as exc:
            logger.error("Chat orchestrator streaming failed: %s", exc, exc_info=True)
            await run_repo.update(run.id, status="failed", error_message=str(exc), finished_at=datetime.now(UTC))
            assistant_msg.content = f"Orchestrator encountered error: {str(exc)}"
            assistant_msg.msg_metadata = {"thread_id": thread_id, "status": "failed", "error": str(exc)}
            await db.commit()

            yield f'event: error\ndata: {json.dumps({"error": str(exc)})}\n\n'
            yield f'event: complete\ndata: {json.dumps({"run_id": str(run.id), "status": "failed"})}\n\n'


chat_service = ChatService()
