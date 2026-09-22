"""W_VOICE: tickets, reviews, sentiment, and objection analysis."""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import BoundedWorkerAgent, WorkerReasoningOutput
from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    AnonymizedSentimentVector,
    ConfidenceInterval,
    CustomerVoiceAnalysisResult,
    EvidenceEnvelope,
    ObjectionProfile,
    TaskGrant,
)
from app.schemas.customer_voice import (
    CustomerVoicePayload,
    CustomerVoiceTask,
    VoiceWorkflowStage,
)
from app.schemas.sandbox import SandboxCapability


class CustomerVoiceAgent(BoundedWorkerAgent):
    """W_VOICE Customer Voice Engine.

    Operates as a Layer-5 coordinator with zero direct sandbox capability.
    Validates bounded TaskGrant and context, enforces tenant isolation, rejects
    missing feedback without fabricating fallback data, and coordinates the
    Customer Voice pipeline.
    """

    capability = None

    def __init__(
        self,
        sandbox_client: Any = None,
        llm_client: Any = None,
    ) -> None:
        if sandbox_client is not None:
            raise PolicyViolationError(
                "W_VOICE coordinator is zero-sandbox and must not receive a SandboxClient."
            )
        super().__init__(sandbox_client=None, llm_client=llm_client)

    def build_payload(self, grant: TaskGrant, context: dict[str, Any]) -> dict[str, str]:
        """Reject sandbox payload construction: W_VOICE has zero sandbox capability."""
        raise PolicyViolationError(
            f"Worker {grant.worker_role.value if grant.worker_role else 'W_VOICE'} "
            "has zero sandbox capability and must not formulate sandbox payloads."
        )

    def _normalize_context(
        self, grant: TaskGrant, context: dict[str, object]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Normalize authorized customer voice items from grant and context.

        Preserves tenant, source, channel, timestamp, and provenance metadata.
        Enforces tenant isolation by failing closed on off-tenant customer items.
        Never fabricates fallback feedback when customer evidence is missing.
        """
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        product_id = str(context.get("product_id", grant.cts_state.get("product_id", "")))

        # 1. Gather raw customer voice inputs
        raw_items = (
            context.get("items")
            or context.get("feedback_items")
            or context.get("support_tickets")
            or context.get("reviews")
            or context.get("surveys")
            or grant.cts_state.get("feedback_items")
            or grant.cts_state.get("support_tickets")
        )

        normalized_items: list[dict[str, Any]] = []

        if raw_items:
            if isinstance(raw_items, list):
                for idx, item in enumerate(raw_items):
                    if isinstance(item, dict):
                        item_tenant = item.get("tenant_id")
                        if item_tenant and item_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in customer voice context: item tenant '{item_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        normalized_items.append({
                            "item_id": str(item.get("item_id", item.get("ticket_id", item.get("id", f"item-{idx + 1}")))),
                            "source_type": str(item.get("source_type", item.get("type", "feedback"))),
                            "text": str(item.get("text", item.get("content", item.get("body", "")))),
                            "product_id": str(item.get("product_id", product_id)),
                            "channel": item.get("channel"),
                            "tenant_id": grant_tenant,
                            "timestamp": str(item.get("timestamp", "")),
                        })
                    elif isinstance(item, str):
                        normalized_items.append({
                            "item_id": f"item-{idx + 1}",
                            "source_type": "feedback",
                            "text": item,
                            "product_id": product_id,
                            "tenant_id": grant_tenant,
                        })
            elif isinstance(raw_items, str):
                try:
                    parsed = json.loads(raw_items)
                    if isinstance(parsed, list):
                        for idx, p in enumerate(parsed):
                            if isinstance(p, dict):
                                item_tenant = p.get("tenant_id")
                                if item_tenant and item_tenant != grant_tenant:
                                    raise ValueError(
                                        f"Tenant isolation breach in customer voice context: item tenant '{item_tenant}' "
                                        f"does not match grant tenant '{grant_tenant}'."
                                    )
                                normalized_items.append({
                                    "item_id": str(p.get("item_id", f"item-{idx + 1}")),
                                    "source_type": str(p.get("source_type", "feedback")),
                                    "text": str(p.get("text", "")),
                                    "product_id": str(p.get("product_id", product_id)),
                                    "tenant_id": grant_tenant,
                                })
                            else:
                                normalized_items.append({
                                    "item_id": f"item-{idx + 1}",
                                    "source_type": "feedback",
                                    "text": str(p),
                                    "product_id": product_id,
                                    "tenant_id": grant_tenant,
                                })
                except Exception:
                    normalized_items.append({
                        "item_id": "item-1",
                        "source_type": "feedback",
                        "text": raw_items,
                        "product_id": product_id,
                        "tenant_id": grant_tenant,
                    })

        # Also check validated evidence in grant for customer sentiment texts
        if grant.validated_evidence:
            for idx, ev in enumerate(grant.validated_evidence):
                if isinstance(ev, dict):
                    ev_tenant = ev.get("tenant_id")
                    if ev_tenant and ev_tenant != grant_tenant:
                        raise ValueError(
                            f"Tenant isolation breach in customer voice context: evidence tenant '{ev_tenant}' "
                            f"does not match grant tenant '{grant_tenant}'."
                        )
                    ev_src = str(ev.get("source", "")).lower()
                    if any(k in ev_src for k in ("review", "ticket", "feedback", "survey", "voice")):
                        normalized_items.append({
                            "item_id": str(ev.get("doc_id", f"ev-voice-{idx}")),
                            "source_type": "review" if "review" in ev_src else "support_ticket",
                            "text": str(ev.get("text", ev.get("content", ""))),
                            "product_id": product_id,
                            "tenant_id": grant_tenant,
                        })

        # Check explicit single feedback text (no synthetic default fallback)
        if not normalized_items:
            single_text = context.get("feedback_text") or grant.cts_state.get("feedback_text")
            if single_text:
                normalized_items.append({
                    "item_id": "item-1",
                    "source_type": str(context.get("source_type", "feedback")),
                    "text": str(single_text),
                    "product_id": product_id,
                    "tenant_id": grant_tenant,
                })

        return product_id, normalized_items

    async def run(self, grant: TaskGrant, context: dict[str, Any]) -> EvidenceEnvelope:
        """Execute W_VOICE coordinator workflow over bounded grant and context.

        W_VOICE has zero sandbox capability and operates strictly as a Layer-5 coordinator.
        Rejects missing feedback evidence without fabricating default inputs.
        """
        # Validate tenant and gather authorized feedback items
        product_id, items = self._normalize_context(grant, context)

        if not items:
            # Explicit incomplete/needs-context result when customer evidence is missing
            return EvidenceEnvelope(
                task_id=grant.task_id,
                worker_role=grant.worker_role,
                confidence=ConfidenceInterval(point_estimate=0.0, lower_bound=0.0, upper_bound=0.0),
                evidence=["Missing customer voice evidence: no feedback items, support tickets, reviews, or surveys provided."],
                payload={"status": "incomplete", "reason": "missing_feedback_evidence"},
                findings=[],
                generated_artifacts=[],
                supporting_evidence=[],
                provenance={
                    "agent": grant.worker_role.value if grant.worker_role else "W_VOICE",
                    "task_id": grant.task_id,
                    "capability": "NONE",
                    "status": "incomplete",
                },
                proposed_state_changes={
                    "status": "needs_context",
                },
                unresolved_risks_or_assumptions=[
                    "Missing customer voice evidence: cannot perform customer voice analysis without authorized feedback inputs."
                ],
            )

        reasoning_output: WorkerReasoningOutput | None = None
        llm_metadata: dict[str, Any] = {}
        if self._llm_client is not None:
            reasoning_output, llm_metadata = await self._reason_domain(grant, context)

        # Freeze CustomerVoiceTask contract
        task_contract = CustomerVoiceTask(
            task_id=grant.task_id,
            tenant_id=grant.tenant_scope.tenant_id if grant.tenant_scope else "default",
            brand_id=grant.brand_id,
            product_ref=product_id or None,
            objective=grant.objective or "analyze_customer_voice",
            source_refs=[it["item_id"] for it in items],
            workflow_stage=VoiceWorkflowStage.DISCOVERY,
        )

        findings: list[str] = [f"Customer Voice Analysis: {len(items)} items authorized for analysis."]
        risks: list[str] = []
        if reasoning_output:
            findings.extend(reasoning_output.preliminary_findings)
            risks.extend(reasoning_output.identified_risks)

        findings = sorted(list(set(findings)))
        artifacts = [f"voice:{grant.task_id}", f"sentiment:{grant.task_id}"]

        provenance: dict[str, Any] = {
            "agent": grant.worker_role.value if grant.worker_role else "W_VOICE",
            "capability": "NONE",
            "task_id": grant.task_id,
            "status": "completed",
            "workflow_stage": VoiceWorkflowStage.SYNTHESIS.value,
        }
        if llm_metadata:
            provenance.update({
                "llm_reasoning_used": "true",
                "llm_provider": str(llm_metadata.get("provider", "unset")),
                "llm_model": str(llm_metadata.get("actual_model", "unset")),
                "prompt_tokens": str(llm_metadata.get("prompt_tokens", 0)),
                "completion_tokens": str(llm_metadata.get("completion_tokens", 0)),
                "total_tokens": str(llm_metadata.get("total_tokens", 0)),
            })

        confidence = ConfidenceInterval(point_estimate=0.85, lower_bound=0.75, upper_bound=0.95)

        voice_payload = CustomerVoicePayload(
            task_id=grant.task_id,
            tenant_id=grant.tenant_scope.tenant_id if grant.tenant_scope else "default",
            product_ref=product_id or None,
            records_analyzed=len(items),
            inference_scope="observed_feedback_only",
            population_representativeness="not_established",
            provenance=provenance,
        )

        analysis_result = CustomerVoiceAnalysisResult(
            analysis_id=f"cva-{grant.task_id}",
            tenant_id=grant.tenant_scope.tenant_id if grant.tenant_scope else "default",
            product_id=product_id or None,
            total_items_analyzed=len(items),
            provenance=provenance,
        )

        return EvidenceEnvelope(
            task_id=grant.task_id,
            worker_role=grant.worker_role,
            confidence=confidence,
            evidence=[f"Customer Voice Analysis: {len(items)} items analyzed."],
            payload={
                "customer_voice_task": task_contract.model_dump_json(),
                "customer_voice_payload": voice_payload.model_dump_json(),
                "customer_voice_analysis": analysis_result.model_dump_json(),
                "total_items_analyzed": str(len(items)),
                "product_id": product_id,
            },
            findings=findings,
            generated_artifacts=artifacts,
            supporting_evidence=[f"items_count:{len(items)}"],
            provenance=provenance,
            proposed_state_changes={
                "status": "completed",
                "capability": "NONE",
            },
            unresolved_risks_or_assumptions=risks,
        )

    def interpret_result(
        self, sanitized_output: dict[str, str]
    ) -> tuple[list[str], ConfidenceInterval]:
        """Interpret S_PARSE sanitized output into structured findings and confidence interval."""
        evidence: list[str] = []

        # 1. Parse Customer Voice Analysis Result if present
        analysis_data: dict[str, Any] = {}
        if "customer_voice_analysis" in sanitized_output:
            try:
                analysis_data = json.loads(sanitized_output["customer_voice_analysis"])
            except Exception:
                pass

        if analysis_data:
            total_items = analysis_data.get("total_items_analyzed", 0)
            avg_polarity = analysis_data.get("average_polarity", 0.0)
            breakdown = analysis_data.get("sentiment_breakdown", {})
            pos = breakdown.get("POSITIVE", 0)
            neg = breakdown.get("NEGATIVE", 0)
            neu = breakdown.get("NEUTRAL", 0)
            mix = breakdown.get("MIXED", 0)

            evidence.append(
                f"Customer Voice Analysis: {total_items} items analyzed | Avg Polarity: {avg_polarity:.2f} | "
                f"Breakdown: Positive={pos}, Negative={neg}, Neutral={neu}, Mixed={mix}"
            )

            # Redactions note
            anonymization_stats = analysis_data.get("anonymization_stats", {})
            redactions = anonymization_stats.get("total_redactions", 0)
            evidence.append(f"Privacy & Anonymization: {redactions} sensitive identifiers redacted | Source IDs tokenized")

            # Top objection profiles
            profiles = analysis_data.get("objection_profiles", [])
            for p in profiles:
                theme = p.get("normalized_theme", "")
                freq = p.get("frequency", 0)
                sev = p.get("severity", "low")
                trend = p.get("trend", "stable")
                evidence.append(f"[OBJECTION: {theme}] Frequency: {freq} | Severity: {sev} | Trend: {trend}")

            # Warnings if any
            for w in analysis_data.get("warnings", []):
                evidence.append(f"Notice: {w}")

        elif "feedback_summary" in sanitized_output:
            evidence.append(sanitized_output["feedback_summary"])

        if "objections" in sanitized_output and not analysis_data:
            evidence.append(f"Objections: {sanitized_output['objections']}")

        # 2. Compute Confidence Interval
        try:
            polarity_val = float(sanitized_output.get("sentiment_polarity", "0.0"))
        except (ValueError, TypeError):
            polarity_val = 0.0

        total_analyzed = analysis_data.get("total_items_analyzed", 1)

        if total_analyzed == 0:
            point = 0.0
            lower = 0.0
            upper = 0.1
        elif abs(polarity_val) > 0.3:
            # Decisive sentiment
            point = min(0.95, 0.80 + min(total_analyzed * 0.03, 0.15))
            lower = max(0.65, point - 0.1)
            upper = min(0.98, point + 0.05)
        elif abs(polarity_val) <= 0.15:
            # Ambiguous or balanced neutral feedback
            point = 0.60
            lower = 0.45
            upper = 0.75
        else:
            point = 0.75
            lower = 0.60
            upper = 0.85

        confidence = ConfidenceInterval(
            point_estimate=round(point, 2),
            lower_bound=round(lower, 2),
            upper_bound=round(upper, 2),
        )

        return evidence, confidence

    @staticmethod
    def extract_customer_voice_payload(envelope: EvidenceEnvelope) -> CustomerVoicePayload | None:
        """Helper to extract strongly typed CustomerVoicePayload from an EvidenceEnvelope."""
        raw = envelope.payload.get("customer_voice_payload")
        if raw:
            try:
                if isinstance(raw, str):
                    return CustomerVoicePayload.model_validate_json(raw)
                return CustomerVoicePayload.model_validate(raw)
            except Exception:
                return None
        return None

    @staticmethod
    def extract_customer_voice_analysis(envelope: EvidenceEnvelope) -> CustomerVoiceAnalysisResult | None:
        """Helper to extract strongly typed CustomerVoiceAnalysisResult from an EvidenceEnvelope."""
        raw = envelope.payload.get("customer_voice_analysis")
        if raw:
            try:
                return CustomerVoiceAnalysisResult.model_validate_json(raw)
            except Exception:
                return None
        return None

    @staticmethod
    def extract_objection_profiles(envelope: EvidenceEnvelope) -> list[ObjectionProfile]:
        """Helper to extract strongly typed ObjectionProfile list from an EvidenceEnvelope."""
        raw = envelope.payload.get("objection_profiles")
        if raw:
            try:
                parsed = json.loads(raw)
                return [ObjectionProfile.model_validate(p) for p in parsed]
            except Exception:
                return []
        return []

    @staticmethod
    def extract_sentiment_vectors(envelope: EvidenceEnvelope) -> list[AnonymizedSentimentVector]:
        """Helper to extract strongly typed AnonymizedSentimentVector list from an EvidenceEnvelope."""
        raw = envelope.payload.get("sentiment_vectors")
        if raw:
            try:
                parsed = json.loads(raw)
                return [AnonymizedSentimentVector.model_validate(v) for v in parsed]
            except Exception:
                return []
        return []