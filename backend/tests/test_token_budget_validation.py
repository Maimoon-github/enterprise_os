import pytest
from app.agents.base import BoundedWorkerAgent, WorkerReasoningOutput
from app.schemas.agent_contracts import TaskGrant
from app.schemas.task_state import WorkerRole
from app.schemas.governance import TenantScope
from app.schemas.sandbox import SandboxCapability
from app.core.exceptions import PolicyViolationError
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

class DummyWorker(BoundedWorkerAgent):
    capability = SandboxCapability.CODE

    def build_payload(self, grant: TaskGrant, context: dict[str, Any]) -> dict[str, str]:
        return {"operation": "run"}

@pytest.mark.asyncio
async def test_token_budget_numeric_coercion_and_fail_closed() -> None:
    mock_llm = MagicMock()
    worker = DummyWorker(llm_client=mock_llm)

    grant = TaskGrant(
        task_id="test-budget-task",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-test"),
        brand_id="test-brand",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        token_budget=1000,
    )

    output = WorkerReasoningOutput(
        domain_interpretation="test",
        rationale_summary="ok",
        estimated_confidence=0.8,
    )

    # 1. Valid string int coerced to int within budget (500 <= 1000)
    mock_llm.generate_structured_with_metadata = AsyncMock(return_value=(output, {"total_tokens": "500"}))
    reasoning, meta = await worker._reason_domain(grant, {})
    assert reasoning.domain_interpretation == "test"
    assert meta["total_tokens"] == "500"

    # 2. String int exceeding budget (1500 > 1000) raises PolicyViolationError
    mock_llm.generate_structured_with_metadata = AsyncMock(return_value=(output, {"total_tokens": "1500"}))
    with pytest.raises(PolicyViolationError) as exc_info:
        await worker._reason_domain(grant, {})
    assert "exceeded token budget" in str(exc_info.value).lower()

    # 3. Non-numeric token count fails closed with PolicyViolationError
    mock_llm.generate_structured_with_metadata = AsyncMock(return_value=(output, {"total_tokens": "malformed_string_tokens"}))
    with pytest.raises(PolicyViolationError) as exc_info:
        await worker._reason_domain(grant, {})
    assert "malformed non-numeric token usage" in str(exc_info.value).lower()
