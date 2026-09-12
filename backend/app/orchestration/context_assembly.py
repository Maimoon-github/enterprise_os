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

import hashlib
from typing import Any

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
    ) -> dict[str, object]:
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

        return {
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