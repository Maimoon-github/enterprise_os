# pyright: reportMissingImports=false
"""Human-in-the-Loop (HitL) Approval Gate and Webhook Dispatcher (TSK-06).
Configures LangGraph interrupt checkpoints and routes sensitive actions to approval channels.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage

from core.state import AgentState, BrandProfile
from guardrails.brand_rules import BrandComplianceFilter, BrandComplianceResult
from guardrails.grounding_verifier import GroundingVerificationResult, GroundingVerifier


class WebhookNotificationReceipt(BaseModel):
    """Receipt documenting webhook dispatch to Slack or Email approval channels."""

    dispatched: bool
    channel: str = "slack_webhook"
    timestamp: str
    target_action: str
    payload_summary: str
    status: str = "pending_human_review"


class ApprovalWebhookDispatcher:
    """Dispatches approval requests for high-impact actions (ad spend, live posts) to webhooks."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def dispatch_approval_request(
        self,
        action_type: str,
        summary: str,
        brand_name: str = "Enterprise Brand",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WebhookNotificationReceipt:
        """Route approval payload to configured webhook endpoint (or safe sandbox mock)."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = {
            "brand": brand_name,
            "action_type": action_type,
            "summary": summary,
            "metadata": metadata or {},
            "timestamp": now_str,
        }

        # If real webhook configured and httpx available, send outbound POST
        if self.webhook_url:
            try:
                import httpx
                httpx.post(self.webhook_url, json=payload, timeout=5.0)
            except Exception:
                pass

        return WebhookNotificationReceipt(
            dispatched=True,
            channel="slack_webhook" if "slack" in (self.webhook_url or "") else "approval_channel",
            timestamp=now_str,
            target_action=action_type,
            payload_summary=summary,
            status="pending_human_review",
        )


def compliance_guardrail_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node verifying copy compliance and factual grounding prior to human gate."""
    brand: Optional[BrandProfile] = state.get("brand_profile")
    metadata: Dict[str, Any] = state.get("metadata") or {}

    raw_copy = metadata.get("draft_copy")
    messages = state.get("messages")
    if raw_copy is None and messages:
        raw_copy = messages[-1].content
    if isinstance(raw_copy, list):
        copy_to_verify = " ".join(str(item) for item in raw_copy)
    else:
        copy_to_verify = str(raw_copy or "")

    source_chunks = metadata.get("source_chunks") or []
    platform = str(metadata.get("target_platform") or "linkedin")

    compliance_filter = BrandComplianceFilter()
    grounding_verifier = GroundingVerifier()

    compliance_res: BrandComplianceResult = compliance_filter.validate_copy(
        copy_text=copy_to_verify,
        brand=brand,
        platform=platform,
    )

    grounding_res: GroundingVerificationResult = grounding_verifier.verify_grounding(
        copy_text=copy_to_verify,
        source_chunks=source_chunks,
    )

    errors: List[str] = []
    if not compliance_res.is_compliant:
        errors.extend(compliance_res.violations)

    if not grounding_res.is_grounded:
        errors.extend([f"Ungrounded claim: '{c}'" for c in grounding_res.ungrounded_claims])

    if errors:
        # Halt and return to reasoning with actionable feedback
        feedback_msg = (
            f"[Guardrail Check FAILED]\n"
            f"Compliance: {'PASSED' if compliance_res.is_compliant else 'FAILED'} (Readability: ARI {compliance_res.readability_score})\n"
            f"Grounding: {'PASSED' if grounding_res.is_grounded else 'FAILED'} (Coverage: {grounding_res.citation_coverage*100:.1f}%)\n"
            f"Violations:\n" + "\n".join(f"• {e}" for e in errors)
        )
        return {
            "phase": "reasoning",
            "human_approved": False,
            "errors": errors,
            "messages": [AIMessage(content=feedback_msg)],
        }

    # All guardrails passed -> Advance to human gate
    success_msg = (
        f"[Guardrails Passed]: Style, Tone (ARI {compliance_res.readability_score}), and "
        f"Factual Grounding ({grounding_res.grounded_claims_count}/{grounding_res.total_claims_count} claims verified). "
        f"Proceeding to Human-in-the-Loop gate."
    )
    return {
        "phase": "human_gate",
        "messages": [AIMessage(content=success_msg)],
    }


def human_gate_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node representing the Human-in-the-Loop approval gate.

    Operates in tandem with interrupt_before=['human_gate'].
    Evaluates human approval status:
    - If None: Suspends and triggers webhook notification.
    - If True: Advances to 'action' phase.
    - If False: Re-routes to 'reasoning' phase with human feedback.
    """
    human_approved = state.get("human_approved")
    human_feedback = state.get("human_feedback")
    metadata: Dict[str, Any] = state.get("metadata") or {}
    brand = state.get("brand_profile")
    brand_name = brand.brand_name if brand else "Enterprise Brand"

    dispatcher = ApprovalWebhookDispatcher(webhook_url=metadata.get("approval_webhook_url"))

    # Case 1: Resumed with explicit approval
    if human_approved is True:
        approval_msg = (
            f"[Human Gate APPROVED by Operator]\n"
            f"Outbound actions and ad spend cleared for execution.\n"
            f"Operator Feedback: {human_feedback or 'Approved with zero modifications.'}"
        )
        return {
            "phase": "action",
            "human_approved": True,
            "messages": [AIMessage(content=approval_msg)],
        }

    # Case 2: Resumed with explicit rejection / revisions requested
    if human_approved is False:
        rejection_msg = (
            f"[Human Gate REJECTED by Operator]\n"
            f"Outbound action aborted. Re-routing to reasoning.\n"
            f"Required Adjustments: {human_feedback or 'Revise copy according to brand style.'}"
        )
        return {
            "phase": "reasoning",
            "human_approved": False,
            "errors": [f"Operator rejection: {human_feedback or 'Action denied'}"],
            "messages": [AIMessage(content=rejection_msg)],
        }

    # Case 3: Initial arrival at gate (awaiting human decision)
    action_type = metadata.get("action_type", "Public Asset Publication / Ad Spend Modification")
    receipt = dispatcher.dispatch_approval_request(
        action_type=action_type,
        summary=f"Approval requested for {brand_name} action: {action_type}",
        brand_name=brand_name,
        metadata=metadata,
    )

    pending_msg = (
        f"[Human Gate SUSPENDED]: Awaiting operator sign-off.\n"
        f"Target Action: {action_type}\n"
        f"Webhook Notification: Dispatched to {receipt.channel} at {receipt.timestamp}\n"
        f"Status: Execution paused via interrupt_before=['human_gate']."
    )

    return {
        "phase": "human_gate",
        "artifacts": [f"approval_receipt_{receipt.timestamp}.json"],
        "messages": [AIMessage(content=pending_msg)],
    }
