import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import EntityNotFoundError
from app.db.repositories.approval_repo import ApprovalRepository
from app.db.repositories.run_repo import RunRepository
from app.orchestrator.graph import DEFAULT_RECURSION_LIMIT, master_orchestrator_graph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("services.approval")


class ApprovalService:
    async def process_decision(
        self,
        approval_id: uuid.UUID,
        approved: bool,
        db: AsyncSession,
        notes: str | None = None,
        modifications: dict[str, Any] | None = None,
        reviewer_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Process human operator decision, update DB records, and resume the paused LangGraph thread

        using LangGraph Command(resume=payload) with recursion_limit: 25.
        """
        approval_repo = ApprovalRepository(db)
        run_repo = RunRepository(db)

        approval = await approval_repo.get(approval_id)
        if not approval:
            raise EntityNotFoundError("Approval", str(approval_id))

        new_status = "approved" if approved else "rejected"
        resolved_at = datetime.now(UTC)

        await approval_repo.update(
            approval_id,
            status=new_status,
            decision_notes=notes,
            reviewed_by=reviewer_id,
            resolved_at=resolved_at,
        )

        config = {
            "configurable": {"thread_id": approval.thread_id},
            "recursion_limit": DEFAULT_RECURSION_LIMIT,
        }
        resume_payload = {
            "approved": approved,
            "notes": notes,
            "modifications": modifications or {},
        }

        # Resume the paused thread
        try:
            resume_result = await master_orchestrator_graph.ainvoke(
                Command(resume=resume_payload),
                config=config,
            )

            # Check if execution encountered a subsequent interrupt (e.g. following revision)
            if resume_result.get("__interrupt__"):
                interrupt_obj = resume_result["__interrupt__"][0]
                interrupt_val = getattr(interrupt_obj, "value", interrupt_obj)
                interrupt_payload = (
                    interrupt_val if isinstance(interrupt_val, dict) else {"message": str(interrupt_val)}
                )

                step_name = interrupt_payload.get("step_name", "human_approval_gate_node")

                # Create subsequent approval gate record
                await approval_repo.create(
                    run_id=approval.run_id,
                    thread_id=approval.thread_id,
                    status="pending",
                    step_name=step_name,
                    payload=interrupt_payload,
                )
                await run_repo.update(
                    approval.run_id,
                    status="interrupted",
                    current_node=step_name,
                )
                graph_status = "interrupted"
            else:
                await run_repo.update(
                    approval.run_id,
                    status="completed",
                    current_node="closed_loop_eval",
                    finished_at=datetime.now(UTC),
                )
                graph_status = "completed"

        except Exception as exc:
            logger.error("Error resuming LangGraph thread %s: %s", approval.thread_id, exc, exc_info=True)
            await run_repo.update(
                approval.run_id,
                status="failed",
                error_message=str(exc),
                finished_at=datetime.now(UTC),
            )
            graph_status = "failed"

        return {
            "status": "resumed",
            "approval_id": str(approval_id),
            "thread_id": approval.thread_id,
            "decision": new_status,
            "resolved_at": resolved_at.isoformat(),
            "graph_status": graph_status,
        }
