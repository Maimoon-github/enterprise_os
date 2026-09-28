"""Builds policy-screened context slices for workers.

Context is assembled exclusively through the IE-exclusive RAG bridge and the
brand persona resolver, following a strict 9-stage deterministic precedence model:
1. Authority & tenant scope
2. CTS task state / holds / dependencies
3. Policy and risk constraints
4. Brand persona and brand rules (subordinate to policy)
5. Fresh RAG evidence + provenance
6. Task-specific instructions
7. Tool/capability allowlist
8. Token/context budget
9. Expected output schema
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
from typing import Any
import uuid

from app.core.exceptions import PolicyViolationError, RetrievalGovernanceError
from app.integrations.sandbox.capabilities import CAPABILITY_REGISTRY, WORKER_CAPABILITY_MAP
from app.orchestration.brand_persona import BrandPersona, BrandPersonaResolver
from app.orchestration.rag_query_dispatch import IntelligenceEngineToken, RagQueryDispatcher
from app.schemas.agent_contracts import ContextRequest
from app.schemas.task_state import CanonicalTaskState, TaskStatus


def _estimate_tokens(text: str) -> int:
    """Fast, deterministic token approximation (~4 chars per token)."""
    return max(1, len(text) // 4)


class ContextAssembler:
    """Assembles the bounded context payload handed to a worker with its grant."""

    def __init__(
        self,
        rag_dispatcher: RagQueryDispatcher,
        brand_persona_resolver: BrandPersonaResolver | None = None,
    ) -> None:
        self._rag_dispatcher = rag_dispatcher
        self._brand_persona_resolver = brand_persona_resolver or BrandPersonaResolver()

    async def assemble(
        self,
        token: IntelligenceEngineToken,
        *,
        tenant_id: str,
        request: ContextRequest,
        cts_state: CanonicalTaskState | None = None,
        policy_constraints: list[str] | None = None,
        risk_tier: str = "low",
        objective: str = "",
    ) -> dict[str, Any]:
        """Assemble bounded, budgeted context under strict deterministic precedence."""

        # Stage 1: Authority & Tenant Scope (Fail-closed)
        if not tenant_id:
            raise RetrievalGovernanceError("Context assembly requires an explicit tenant scope.")

        authority_scope = {
            "tenant_id": tenant_id,
            "brand_id": request.brand_id,
        }

        # Stage 2: CTS Task State, Holds & Dependencies
        cts_snapshot: dict[str, Any] = {}
        if cts_state is not None:
            if cts_state.status == TaskStatus.HELD or cts_state.hold_reason:
                raise PolicyViolationError(
                    f"Task {cts_state.task_id} is under an active hold: {cts_state.hold_reason or 'held'}"
                )
            if cts_state.status in (TaskStatus.FAILED, TaskStatus.COMPLETED):
                raise PolicyViolationError(
                    f"Task {cts_state.task_id} is in terminal state '{cts_state.status.value}'."
                )
            if cts_state.prerequisite_locks:
                raise PolicyViolationError(
                    f"Task {cts_state.task_id} has unresolved prerequisite locks: {sorted(cts_state.prerequisite_locks)}"
                )
            if not cts_state.governance_approved:
                raise PolicyViolationError(
                    f"Task {cts_state.task_id} has not received governance approval."
                )

            cts_snapshot = {
                "task_id": cts_state.task_id,
                "directive_id": cts_state.directive_id,
                "worker_role": cts_state.worker_role.value,
                "status": cts_state.status.value,
                "version": cts_state.version,
                "governance_approved": cts_state.governance_approved,
            }
            if hasattr(cts_state, "cts_state") and isinstance(cts_state.cts_state, dict):
                cts_snapshot.update(cts_state.cts_state)

        # Stage 3: Policy and Risk Constraints
        active_policy_constraints = list(policy_constraints or [])
        active_policy_constraints.append(f"risk_tier:{risk_tier}")

        # Stage 4: Brand Persona and Brand Rules (Subordinate to Policy)
        if hasattr(self._brand_persona_resolver, "resolve_with_memory"):
            raw_persona = await self._brand_persona_resolver.resolve_with_memory(
                tenant_id=tenant_id, brand_id=request.brand_id
            )
        else:
            raw_persona = self._brand_persona_resolver.resolve(
                tenant_id=tenant_id, brand_id=request.brand_id
            )

        # Ensure brand persona cannot override policy constraints
        persona = self._brand_persona_resolver.sanitize_against_policy(
            raw_persona, policy_prohibited_terms=active_policy_constraints
        )

        brand_rules = {
            "voice": persona.voice,
            "prohibited_terms": list(persona.prohibited_terms),
            "required_disclaimers": list(persona.required_disclaimers),
            "tone_attributes": list(persona.tone_attributes),
            "heuristics": list(persona.learned_heuristics),
        }

        # Stage 5: Fresh RAG Evidence + Provenance (IE-brokered)
        raw_documents = await self._rag_dispatcher.dispatch(
            token,
            tenant_id=tenant_id,
            query=request.query,
            top_k=request.max_items,
            purpose=request.purpose,
            freshness_target=request.freshness_target,
            provenance_required=request.provenance_required,
        )

        # Stage 6: Task-Specific Instructions
        instructions = {
            "query": request.query,
            "objective": objective or f"Execute {request.worker_role.value} operations",
            "task_id": request.task_id,
        }

        # Stage 7: Tool / Capability Allowlist
        capability = WORKER_CAPABILITY_MAP.get(request.worker_role)
        allowed_tools: list[str] = []
        if capability and capability in CAPABILITY_REGISTRY:
            allowed_tools = list(CAPABILITY_REGISTRY[capability].allowed_tools)

        tool_allowlist = {
            "capability": capability.value if capability else "none",
            "allowed_tools": allowed_tools,
        }

        # Stage 8: Token / Context Budgeting & Truncation Strategy
        # Explicit allocations
        budget_total = request.max_tokens
        reserved_output = min(2000, budget_total // 4)
        governance_budget = 400
        persona_budget = 600
        instruction_budget = 400
        tool_budget = 300
        evidence_budget = max(500, budget_total - (reserved_output + governance_budget + persona_budget + instruction_budget + tool_budget))

        budget_breakdown = {
            "total_budget": budget_total,
            "reserved_output": reserved_output,
            "governance_budget": governance_budget,
            "persona_budget": persona_budget,
            "instruction_budget": instruction_budget,
            "tool_budget": tool_budget,
            "evidence_budget": evidence_budget,
        }

        # Budget-constrained evidence processing:
        # filter -> rank -> deduplicate -> compress -> truncate
        processed_docs: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        provenance_references: list[str] = []
        timestamps: list[str] = []

        current_evidence_tokens = 0
        for doc in raw_documents:
            # Deduplicate by text hash or doc_id
            text = str(doc.get("text", "")).strip()
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            doc_copy = dict(doc)
            # Compress / summarize if text is verbose
            if len(text) > 300:
                doc_copy["text"] = text[:300] + "... [truncated]"

            doc_tokens = _estimate_tokens(doc_copy["text"])
            if current_evidence_tokens + doc_tokens > evidence_budget and processed_docs:
                # Evidence budget reached: stop adding lower-priority evidence
                break

            current_evidence_tokens += doc_tokens
            processed_docs.append(doc_copy)

            prov_hash = doc.get("provenance_hash")
            if prov_hash:
                provenance_references.append(str(prov_hash))
            retrieved_at = doc.get("retrieved_at")
            if retrieved_at:
                timestamps.append(str(retrieved_at))

        freshness_metadata = {
            "retrieved_count": len(processed_docs),
            "timestamps": sorted(timestamps),
        }

        # Stage 9: Expected Output Schema
        expected_output_schema = {
            "worker_role": request.worker_role.value,
            "requires_findings": True,
            "requires_confidence": True,
            "requires_provenance": True,
        }

        assembled = {
            "task_id": request.task_id,
            "worker_role": request.worker_role.value,
            "query": request.query,
            "authority_scope": authority_scope,
            "cts_state": cts_snapshot,
            "policy_constraints": active_policy_constraints,
            "brand_persona": persona,
            "brand_rules": brand_rules,
            "documents": processed_docs,
            "provenance_references": provenance_references,
            "freshness_metadata": freshness_metadata,
            "task_instructions": instructions,
            "tool_allowlist": tool_allowlist,
            "budget_breakdown": budget_breakdown,
            "expected_output_schema": expected_output_schema,
        }
        if cts_state is not None and hasattr(cts_state, "cts_state") and isinstance(cts_state.cts_state, dict):
            for k, v in cts_state.cts_state.items():
                if k not in assembled:
                    assembled[k] = v
        return assembled

    async def build_performance_context(
        self,
        token: IntelligenceEngineToken,
        *,
        tenant_id: str,
        brand_id: str = "default",
        time_window_start: datetime | None = None,
        time_window_end: datetime | None = None,
        requested_metrics: list[str] | None = None,
        channels: list[str] | None = None,
        purpose: str = "strategy_performance_evaluation",
        token_budget: int = 4000,
        raw_performance_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble governed, cited, bounded performance context envelope via IE-exclusive RAG bridge."""
        if not tenant_id or not tenant_id.strip():
            raise RetrievalGovernanceError("Performance context assembly requires an explicit tenant scope.")

        now = datetime.now(UTC)
        win_start = time_window_start or (now - timedelta(days=30))
        win_end = time_window_end or now

        query = f"performance metrics {brand_id} {' '.join(channels or [])}"
        raw_documents = await self._rag_dispatcher.dispatch(
            token,
            tenant_id=tenant_id,
            query=query,
            top_k=10,
            purpose=purpose,
            freshness_target=timedelta(hours=24),
            provenance_required=False,
        )

        dataset_ids: list[str] = []
        evidence_hashes: list[str] = []
        provenance_references: list[str] = []
        timestamps: list[str] = []

        for doc in raw_documents:
            doc_id = doc.get("doc_id") or doc.get("id")
            if doc_id:
                dataset_ids.append(str(doc_id))
            prov_hash = doc.get("provenance_hash")
            if prov_hash:
                evidence_hashes.append(str(prov_hash))
                provenance_references.append(str(prov_hash))
            retrieved_at = doc.get("retrieved_at")
            if retrieved_at:
                timestamps.append(str(retrieved_at))

        # Channel & metric coverage and quality calculation
        target_channels = [c.lower() for c in (channels or ["meta", "google", "tiktok", "linkedin"])]
        metrics_by_channel: dict[str, Any] = {}
        source_coverage: dict[str, float] = {}
        quality_flags: dict[str, Any] = {"is_complete": True, "has_suppression": False, "has_stale_data": False}
        suppression_flags: dict[str, Any] = {}
        freshness_flags: dict[str, Any] = {}

        perf_source = raw_performance_data or {}

        for ch in target_channels:
            ch_data = perf_source.get(ch)
            if ch_data is None:
                # Missing channel metrics: explicitly preserved as unavailable, never zeroed!
                metrics_by_channel[ch] = {
                    "status": "unavailable",
                    "value": None,
                    "reason": "no_active_source_or_data",
                }
                source_coverage[ch] = 0.0
                quality_flags["is_complete"] = False
                freshness_flags[ch] = "missing"
            elif isinstance(ch_data, dict) and ch_data.get("status") == "suppressed":
                metrics_by_channel[ch] = {
                    "status": "suppressed",
                    "value": None,
                    "reason": ch_data.get("reason", "privacy_threshold_suppressed"),
                }
                source_coverage[ch] = ch_data.get("coverage_ratio", 0.5)
                quality_flags["has_suppression"] = True
                suppression_flags[ch] = ch_data.get("reason", "privacy_threshold_suppressed")
                freshness_flags[ch] = "suppressed"
            elif isinstance(ch_data, dict) and ch_data.get("status") == "stale":
                metrics_by_channel[ch] = {
                    "status": "stale",
                    "value": ch_data.get("value"),
                    "staleness_seconds": ch_data.get("staleness_seconds", 100000),
                }
                source_coverage[ch] = ch_data.get("coverage_ratio", 1.0)
                quality_flags["has_stale_data"] = True
                freshness_flags[ch] = "stale"
            else:
                val = ch_data if not isinstance(ch_data, dict) else ch_data.get("value", ch_data)
                cov = ch_data.get("coverage_ratio", 1.0) if isinstance(ch_data, dict) else 1.0
                metrics_by_channel[ch] = {
                    "status": "valid",
                    "value": val,
                }
                source_coverage[ch] = cov
                freshness_flags[ch] = "fresh"

        context_id = f"perf_ctx_{uuid.uuid4().hex[:12]}"
        revalidation_conditions = ["freshness_expired", "channel_unlinked", "policy_updated"]

        is_valid = (
            quality_flags["is_complete"]
            and not quality_flags["has_stale_data"]
            and not quality_flags["has_suppression"]
        )
        blocking_reasons: list[str] = []
        if not quality_flags["is_complete"]:
            blocking_reasons.append("Missing required channel metrics")
        if quality_flags["has_stale_data"]:
            blocking_reasons.append("Stale performance metrics detected")
        if quality_flags["has_suppression"]:
            blocking_reasons.append("Suppressed metrics detected")

        return {
            "context_id": context_id,
            "tenant_id": tenant_id,
            "brand_id": brand_id,
            "dataset_ids": dataset_ids,
            "evidence_hashes": evidence_hashes,
            "schema_version": "1.0",
            "mapping_version": "1.0",
            "source_coverage": source_coverage,
            "window_start": win_start.isoformat(),
            "window_end": win_end.isoformat(),
            "as_of_time": now.isoformat(),
            "metric_definitions": {
                "roas": "Return on advertising spend (revenue / spend)",
                "cpa": "Cost per acquisition",
                "spend": "Advertising expenditure in currency",
            },
            "units": {"roas": "ratio", "cpa": "currency", "spend": "currency"},
            "currency": "USD",
            "attribution_assumptions": {"model": "last_touch_30d", "window_days": 30},
            "metrics": metrics_by_channel,
            "quality_flags": quality_flags,
            "suppression_flags": suppression_flags,
            "freshness_flags": freshness_flags,
            "learning_reference": {"model_id": "learn_decay_v1", "uncertainty": 0.05},
            "applicable_policy_version": "1.0",
            "budget_version": "1.0",
            "provenance_references": provenance_references,
            "expires_at": (now + timedelta(hours=24)).isoformat(),
            "revalidation_conditions": revalidation_conditions,
            "is_valid": is_valid,
            "blocking_reasons": blocking_reasons,
        }