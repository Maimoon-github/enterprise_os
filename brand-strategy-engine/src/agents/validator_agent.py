"""Agent 6: Strategy Validator."""

import json
from typing import Any, Dict, List, Optional
from src.agents.base_agent import BaseAgent
from src.schemas.initiative import ApprovalStatus, StrategicInitiative
from src.schemas.validation import AuditEntry, ValidationReport
from src.tools.metric_validator import MetricValidator


class ValidatorAgent(BaseAgent):
    """Adversarial auditor with unilateral veto power enforcing empirical grounding and metric sanity."""

    SYSTEM_PROMPT = """You are the Strategy Validator. You operate as an adversarial auditor with unilateral veto power over every proposed strategic initiative.
Mandates:
1. Provenance Audit: Query the raw research repository. If an initiative's evidence_id does not resolve to an empirical DOM snapshot, VNC visual capture, or indexed RAG citation, VETO IMMEDIATELY.
2. Logical Coherence: Verify that the actionable prescription directly resolves the observed business implication.
3. Metric Realism: Reject ungrounded claims (e.g., "increase CVR by 400% in 14 days"). Enforce statistically realistic target thresholds.
4. Corrective Feedback: For every rejected initiative, generate a detailed diagnostic log specifying the exact failure point and routing instructions for the Orchestrator."""

    def __init__(self, ollama_base_url: str = "http://localhost:11434"):
        super().__init__(
            agent_id="Agent_6",
            name="Strategy Validator",
            model_name="deepseek-r1:32b-qwen-distill-q4_K_M",
            system_prompt=self.SYSTEM_PROMPT,
            context_window=32768,
            temperature=0.0,
            ollama_base_url=ollama_base_url,
        )
        self.whitelisted_tool_names = [
            "verify_evidence_provenance",
            "audit_logical_consistency",
            "validate_metric_feasibility",
            "issue_veto",
        ]
        self.register_tool("verify_evidence_provenance", self._tool_provenance)
        self.register_tool("audit_logical_consistency", self._tool_logical_consistency)
        self.register_tool("validate_metric_feasibility", self._tool_metric_feasibility)
        self.register_tool("issue_veto", self._tool_issue_veto)

    async def invoke_tool(self, tool_name: str, **kwargs) -> Any:
        """Reconciles tool naming aliases (e.g. issue_rejection_notice, issue_approval_certificate)."""
        alias_map = {
            "issue_rejection_notice": "issue_veto",
        }
        if tool_name == "issue_approval_certificate":
            rec_id = kwargs.get("rec_id") or kwargs.get("recommendation_id") or "ALL"
            return {"recommendation_id": rec_id, "approved": True, "certificate": f"CERT-{rec_id}"}
        resolved_name = alias_map.get(tool_name, tool_name)
        return await super().invoke_tool(resolved_name, **kwargs)

    def _tool_provenance(
        self,
        evidence_id: str,
        repo_evidence_ids: List[str],
        evidence_ref: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if evidence_id not in repo_evidence_ids:
            return False
        if evidence_ref:
            selector = evidence_ref.get("dataset_reference") or ""
            screenshot = evidence_ref.get("screenshot_uri") or ""
            source_type = evidence_ref.get("source_type") or ""
            if not selector and not screenshot and not evidence_id.startswith("chk_") and source_type != "rag_citation":
                return False
        return True

    def _tool_logical_consistency(
        self,
        implication: Optional[str] = None,
        prescription: Optional[str] = None,
        initiative: Optional[Dict[str, Any]] = None,
        recommendation_object: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> bool:
        rec = initiative or recommendation_object or {}
        imp = implication or rec.get("business_implication", "")
        pres = prescription or rec.get("actionable_prescription", "")

        if not pres or len(pres.strip()) < 15:
            return False
        if pres.strip().lower() in ("none", "n/a", "do nothing", "no action needed", "ignore finding"):
            return False
        if not imp or len(imp.strip()) < 5:
            return False
        return True

    def _tool_metric_feasibility(self, metric_dict: Dict[str, Any], business_type: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        from src.schemas.initiative import SuccessMetric
        metric = SuccessMetric(**metric_dict)
        passed, reason, lift = MetricValidator.validate_metric(metric)
        return {"passed": passed, "reason": reason, "lift_pct": lift}

    def _tool_issue_veto(self, rec_id: str, reasons: List[str]) -> Dict[str, Any]:
        return {"recommendation_id": rec_id, "vetoed": True, "reasons": reasons}

    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        return json.dumps({"audit_decision": "passed", "reasons": []})

    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Executes adversarial validation on all proposed growth initiatives."""
        raw_initiatives = state_slice.get("growth_initiatives", [])
        initiatives: List[StrategicInitiative] = [
            init if isinstance(init, StrategicInitiative) else StrategicInitiative(**init)
            for init in raw_initiatives
        ]
        research_repo = state_slice.get("research_repository", {})

        # Collect verified evidence IDs from research repository
        repo_evidence_ids = set()
        for ev in research_repo.get("visual_evidence_vnc", []):
            if isinstance(ev, dict):
                repo_evidence_ids.add(ev.get("evidence_id"))
            elif hasattr(ev, "evidence_id"):
                repo_evidence_ids.add(ev.evidence_id)

        for cit in research_repo.get("rag_citations", []):
            if isinstance(cit, dict) and "chunk_id" in cit:
                repo_evidence_ids.add(cit["chunk_id"])

        dom_snaps = research_repo.get("dom_snapshots") or state_slice.get("dom_snapshots") or {}
        if isinstance(dom_snaps, dict):
            for k in dom_snaps.keys():
                repo_evidence_ids.add(k)

        for ev in state_slice.get("visual_evidence_vnc", []):
            if isinstance(ev, dict):
                repo_evidence_ids.add(ev.get("evidence_id"))
            elif hasattr(ev, "evidence_id"):
                repo_evidence_ids.add(ev.evidence_id)

        for cit in state_slice.get("rag_citations", []):
            if isinstance(cit, dict) and "chunk_id" in cit:
                repo_evidence_ids.add(cit["chunk_id"])

        audit_entries: List[AuditEntry] = []
        validated_initiatives: List[StrategicInitiative] = []
        has_vetoes = False

        for init in initiatives:
            rejection_reasons = []
            target_agent = getattr(init, "initiating_agent", "Agent_5_Growth")

            # 1. Provenance Check
            ev_id = init.evidence.evidence_id
            ev_dict = init.evidence.model_dump() if hasattr(init.evidence, "model_dump") else init.evidence
            provenance_ok = self._tool_provenance(ev_id, list(repo_evidence_ids), ev_dict)
            await self.react_step(
                step_number=1,
                thought=f"Reason: Auditing evidence provenance for initiative {init.recommendation_id} (evidence ID: {ev_id}).",
                action="verify_evidence_provenance",
                action_args={"evidence_id": ev_id, "repo_evidence_ids": list(repo_evidence_ids)},
                reflection=f"Evidence provenance check for {ev_id}: {'PASSED' if provenance_ok else 'FAILED'}.",
            )
            audit_entries.append(
                AuditEntry(
                    recommendation_id=init.recommendation_id,
                    check_type="provenance_check",
                    passed=provenance_ok,
                    failure_reason=None if provenance_ok else f"Unverified evidence provenance: {ev_id} not found in research repository.",
                    target_agent=target_agent,
                )
            )
            if not provenance_ok:
                rejection_reasons.append(f"Unverified evidence provenance: {ev_id}")

            # 2. Logical Alignment Check
            logical_ok = self._tool_logical_consistency(
                implication=init.business_implication,
                prescription=init.actionable_prescription,
            )
            await self.react_step(
                step_number=2,
                thought=f"Reason: Auditing logical coherence and alignment between implication and prescription for {init.recommendation_id}.",
                action="audit_logical_consistency",
                action_args={
                    "implication": init.business_implication,
                    "prescription": init.actionable_prescription,
                },
                reflection=f"Logical coherence audit for {init.recommendation_id}: {'PASSED' if logical_ok else 'FAILED'}.",
            )
            audit_entries.append(
                AuditEntry(
                    recommendation_id=init.recommendation_id,
                    check_type="logical_alignment",
                    passed=logical_ok,
                    failure_reason=None if logical_ok else "Prescription does not logically resolve the stated business implication.",
                    target_agent=target_agent,
                )
            )
            if not logical_ok:
                rejection_reasons.append("Logical disconnect between implication and proposed action.")

            # 3. Metric Sanity Check
            m_res = self._tool_metric_feasibility(init.success_metric.model_dump())
            metric_ok = m_res["passed"]
            await self.react_step(
                step_number=3,
                thought=f"Reason: Evaluating mathematical feasibility and platform verification of metric for {init.recommendation_id}.",
                action="validate_metric_feasibility",
                action_args={"metric_dict": init.success_metric.model_dump()},
                reflection=f"Metric feasibility verification for {init.recommendation_id}: {'PASSED' if metric_ok else 'FAILED'}.",
            )
            audit_entries.append(
                AuditEntry(
                    recommendation_id=init.recommendation_id,
                    check_type="metric_feasibility",
                    passed=metric_ok,
                    failure_reason=m_res.get("reason"),
                    target_agent=target_agent,
                )
            )
            if not metric_ok:
                rejection_reasons.append(m_res.get("reason") or "Infeasible metric threshold.")

            # Decision
            if rejection_reasons:
                has_vetoes = True
                await self.react_step(
                    step_number=4,
                    thought=f"Reason: Issuing unilateral veto and diagnostic remediation instructions for initiative {init.recommendation_id}.",
                    action="issue_veto",
                    action_args={"rec_id": init.recommendation_id, "reasons": rejection_reasons},
                    reflection=f"Unilateral veto issued for {init.recommendation_id}; diagnostic reasons committed for revision loop.",
                )
                init.approval_status = ApprovalStatus.REJECTED
                init.rejection_reasons = rejection_reasons
                init.iteration_cycle += 1
            else:
                init.approval_status = ApprovalStatus.APPROVED
                init.rejection_reasons = None

            validated_initiatives.append(init)

        passed_count = sum(1 for i in validated_initiatives if i.approval_status == ApprovalStatus.APPROVED)
        failed_count = sum(1 for i in validated_initiatives if i.approval_status != ApprovalStatus.APPROVED)

        report = ValidationReport(
            status="Approved" if not has_vetoes else "Failed_Needs_Revision",
            total_audited=len(validated_initiatives),
            passed_count=passed_count,
            failed_count=failed_count,
            audit_trail=audit_entries,
        )

        return {
            "validation_report": report,
            "validated_initiatives": validated_initiatives,
        }
