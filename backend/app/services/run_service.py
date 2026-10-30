import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from app.core.exceptions import EntityNotFoundError
from app.db.models.run import Run
from app.db.repositories.approval_repo import ApprovalRepository
from app.db.repositories.run_repo import RunRepository
from app.orchestrator.graph import DEFAULT_RECURSION_LIMIT, master_orchestrator_graph
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("services.run")


class RunService:
    async def dispatch_orchestrator(
        self,
        campaign_id: uuid.UUID,
        db: AsyncSession,
        user_command: str | None = None,
        skills_override: list[str] | None = None,
    ) -> Run:
        """Create and persist a new graph run with a unique thread identifier."""
        thread_id = f"thread_{uuid.uuid4().hex[:16]}"
        repo = RunRepository(db)
        run = await repo.create(
            campaign_id=campaign_id,
            thread_id=thread_id,
            status="running",
            trigger_type="manual",
            current_node="supervisor_router",
            token_usage={"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
        )
        return run

    async def stream_run_execution(
        self,
        run_id: str,
        db: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        """Stream real-time LangGraph execution events via SSE.

        Emits node_start, node_transition, tool_call, interrupt, node_finish, and complete events.
        Synchronizes Run and Approval database records across the interrupt/resume lifecycle.
        """
        run_repo = RunRepository(db)
        approval_repo = ApprovalRepository(db)

        try:
            run_uuid = uuid.UUID(run_id)
            run = await run_repo.get(run_uuid)
        except (ValueError, TypeError):
            run = await run_repo.get_by_thread_id(run_id)

        if not run:
            raise EntityNotFoundError("Run", run_id)

        thread_id = run.thread_id
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": DEFAULT_RECURSION_LIMIT,
        }
        initial_input = {
            "thread_id": thread_id,
            "campaign_id": str(run.campaign_id),
            "approval_status": "pending",
        }

        step_idx = 0
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
                        if isinstance(interrupt_val, dict):
                            interrupt_payload = interrupt_val
                        else:
                            interrupt_payload = {"message": str(interrupt_val)}

                        # Create pending approval record in DB
                        existing = await approval_repo.get_by_thread(thread_id)
                        if not existing or existing.status != "pending":
                            await approval_repo.create(
                                run_id=run.id,
                                thread_id=thread_id,
                                status="pending",
                                step_name="human_approval_gate_node",
                                payload=interrupt_payload,
                            )

                        await run_repo.update(
                            run.id,
                            status="interrupted",
                            current_node="human_approval_gate_node",
                        )

                        interrupt_event = {
                            "run_id": str(run.id),
                            "thread_id": thread_id,
                            "node": "human_approval_gate_node",
                            "step": step_idx,
                            "status": "interrupted",
                            "payload": interrupt_payload,
                        }
                        yield f"event: interrupt\ndata: {json.dumps(interrupt_event)}\n\n"
                        yield f'event: complete\ndata: {json.dumps({"run_id": str(run.id), "status": "interrupted", "reason": "human_approval_required"})}\n\n'
                        return

                    # Normal node execution
                    await run_repo.update(
                        run.id,
                        status="running",
                        current_node=node_name,
                    )

                    start_event = {
                        "run_id": str(run.id),
                        "node": node_name,
                        "step": step_idx,
                        "status": "executing",
                    }
                    yield f"event: node_start\ndata: {json.dumps(start_event)}\n\n"
                    yield f"event: node_transition\ndata: {json.dumps(start_event)}\n\n"

                    # If the node produced mock or actual tool invocations
                    if "active_skills" in node_update:
                        tool_event = {
                            "run_id": str(run.id),
                            "tool": f"{node_name}_tool",
                            "args": {"skills": node_update.get("active_skills")},
                        }
                        yield f"event: tool_call\ndata: {json.dumps(tool_event)}\n\n"

                    finish_event = {
                        "run_id": str(run.id),
                        "node": node_name,
                        "step": step_idx,
                        "status": "completed",
                    }
                    yield f"event: node_finish\ndata: {json.dumps(finish_event)}\n\n"

            # Graph finished successfully
            await run_repo.update(
                run.id,
                status="completed",
                finished_at=datetime.now(UTC),
            )
            complete_event = {
                "run_id": str(run.id),
                "status": "completed",
                "thread_id": thread_id,
            }
            yield f"event: complete\ndata: {json.dumps(complete_event)}\n\n"

        except Exception as exc:
            logger.error("Run stream execution failed: %s", exc, exc_info=True)
            await run_repo.update(
                run.id,
                status="failed",
                error_message=str(exc),
                finished_at=datetime.now(UTC),
            )
            error_event = {
                "run_id": str(run.id),
                "status": "failed",
                "error": str(exc),
            }
            yield f"event: complete\ndata: {json.dumps(error_event)}\n\n"
