"""W_PROD: product specifications, evidence, claims, and compliance dossiers."""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import (
    ClaimsDossier,
    ConfidenceInterval,
    EvidenceEnvelope,
    ProductSpecification,
    TaskGrant,
)
from app.schemas.sandbox import SandboxCapability


class ProductEvidenceAgent(BoundedWorkerAgent):
    """W_PROD Product / Evidence Engine.

    Ingests authorized product evidence, formulations, test results, and compliance
    rules through the Intelligence Engine bounded grant, formulates the S_VAL
    mandate payload, invokes S_VAL within the sandbox, and interprets the sanitized
    output into verified Product Specifications and Claims Dossiers.
    """

    capability = SandboxCapability.VAL

    def _normalize_context(
        self, grant: TaskGrant, context: dict[str, object]
    ) -> tuple[str, str, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], str, list[str]]:
        """Normalize authorized product information from grant and context.

        Preserves tenant, product, source, version, freshness, and provenance metadata.
        Enforces tenant isolation by failing closed on off-tenant evidence.
        """
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"

        # Product & formulation identity
        product_id = str(context.get("product_id", grant.cts_state.get("product_id", f"prod-{grant.brand_id}")))
        product_name = str(context.get("product_name", grant.cts_state.get("product_name", grant.brand_id)))

        # Formulation and specifications
        raw_form = (
            context.get("formulation")
            or context.get("specifications")
            or context.get("product_specification")
            or grant.cts_state.get("formulation")
            or grant.cts_state.get("specifications")
            or {}
        )
        formulation: dict[str, Any] = {}
        if isinstance(raw_form, dict):
            formulation = dict(raw_form)
        elif isinstance(raw_form, str):
            try:
                formulation = json.loads(raw_form)
            except Exception:
                formulation = {"notes": raw_form}

        # Normalize Claims
        claims: list[dict[str, Any]] = []
        raw_claims = (
            context.get("claims")
            or context.get("proposed_claims")
            or grant.cts_state.get("claims")
            or grant.cts_state.get("proposed_claims")
        )
        if raw_claims:
            if isinstance(raw_claims, list):
                for idx, c in enumerate(raw_claims):
                    if isinstance(c, dict):
                        claims.append(c)
                    else:
                        claims.append({"id": f"claim-{idx + 1}", "text": str(c)})
            elif isinstance(raw_claims, str):
                try:
                    parsed = json.loads(raw_claims)
                    claims = parsed if isinstance(parsed, list) else [{"id": "claim-1", "text": str(parsed)}]
                except Exception:
                    claims = [{"id": "claim-1", "text": raw_claims}]
        else:
            claim_text = str(
                context.get(
                    "claim",
                    grant.cts_state.get(
                        "claim",
                        context.get(
                            "statement",
                            grant.cts_state.get(
                                "statement",
                                "Clinically tested to improve performance by 40%. *Results may vary based on usage.",
                            ),
                        ),
                    ),
                )
            )
            claims = [{"id": "claim-1", "text": claim_text, "category": "performance"}]

        # Normalize Evidence Pool (with tenant isolation and freshness checks)
        evidence_pool: list[dict[str, Any]] = []
        raw_evidence: list[Any] = list(grant.validated_evidence)
        for key in ("evidence", "laboratory_reports", "certificates"):
            val = context.get(key)
            if isinstance(val, list):
                raw_evidence.extend(val)

        freshness_meta = grant.freshness_metadata or {}

        for idx, ev in enumerate(raw_evidence):
            if isinstance(ev, dict):
                ev_tenant = ev.get("tenant_id")
                if ev_tenant and ev_tenant != grant_tenant:
                    # Off-tenant evidence detected: fail closed under tenant isolation
                    raise ValueError(
                        f"Tenant isolation breach in evidence context: evidence tenant '{ev_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )

                doc_id = str(ev.get("doc_id", ev.get("evidence_id", ev.get("id", f"ev-{idx}"))))
                is_stale = bool(ev.get("is_stale", ev.get("stale", False)))
                if doc_id in freshness_meta and freshness_meta[doc_id].get("is_fresh") is False:
                    is_stale = True

                evidence_pool.append({
                    "doc_id": doc_id,
                    "text": str(ev.get("text", ev.get("content", ""))),
                    "source": str(ev.get("source", ev.get("source_uri", "authorized_rag"))),
                    "version": str(ev.get("version", "1.0")),
                    "is_stale": is_stale,
                    "provenance_hash": str(ev.get("provenance_hash", "")),
                    "contradicts": bool(ev.get("contradicts", False)),
                })

        # Disclaimers and compliance rules
        persona = context.get("brand_persona")
        disclaimers = getattr(persona, "required_disclaimers", ())
        disclaimer = disclaimers[0] if disclaimers else "*Results may vary based on usage."
        if "required_disclaimer" in context:
            disclaimer = str(context["required_disclaimer"])

        rules: list[str] = list(grant.policy_constraints)
        if grant.brand_rules:
            rules.extend(f"{k}:{v}" for k, v in grant.brand_rules.items())
        raw_rules = context.get("compliance_rules")
        if isinstance(raw_rules, list):
            rules.extend(str(r) for r in raw_rules)

        return product_id, product_name, formulation, claims, evidence_pool, disclaimer, rules

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        """Formulate deterministic S_VAL execution payload."""
        product_id, product_name, formulation, claims, evidence_pool, disclaimer, rules = self._normalize_context(grant, context)

        operation = "validate_product_dossier" if len(claims) > 1 or formulation or evidence_pool else "validate_claim"

        primary_claim = claims[0]["text"] if claims else "Clinically tested to improve performance by 40%."

        return {
            "task_id": grant.task_id,
            "tenant_id": grant.tenant_scope.tenant_id if grant.tenant_scope else "default",
            "operation": operation,
            "objective": grant.objective or "validate_product_claims",
            "product_id": product_id,
            "product_name": product_name,
            "claim": primary_claim,
            "required_disclaimer": disclaimer,
            "claims": json.dumps(claims),
            "evidence": json.dumps(evidence_pool),
            "formulation": json.dumps(formulation),
            "compliance_rules": json.dumps(rules),
        }

    def interpret_result(
        self, sanitized_output: dict[str, str]
    ) -> tuple[list[str], ConfidenceInterval]:
        """Interpret S_VAL sanitized output into structured findings and confidence interval."""
        evidence: list[str] = []

        # Parse Claims Dossier if present
        dossier_data: dict[str, Any] = {}
        if "claims_dossier" in sanitized_output:
            try:
                dossier_data = json.loads(sanitized_output["claims_dossier"])
            except Exception:
                pass

        # Parse Product Specification if present
        spec_data: dict[str, Any] = {}
        if "product_specification" in sanitized_output:
            try:
                spec_data = json.loads(sanitized_output["product_specification"])
            except Exception:
                pass

        if spec_data:
            spec_status = spec_data.get("validation_status", "VALIDATED")
            prod_name = spec_data.get("product_name", "Product")
            prod_id = spec_data.get("product_id", "")
            evidence.append(f"Product Specification: {prod_name} ({prod_id}) - Status: {spec_status}")
            for finding in spec_data.get("compliance_findings", []):
                evidence.append(f"Specification Finding: {finding}")

        if dossier_data:
            claims_entries = dossier_data.get("claims", [])
            total = dossier_data.get("total_claims", len(claims_entries))
            supported = dossier_data.get("supported_claims", 0)
            rejected = dossier_data.get("rejected_claims", 0)
            insufficient = dossier_data.get("insufficient_claims", 0)
            conflicting = dossier_data.get("conflicting_claims", 0)
            review = dossier_data.get("requires_review_claims", 0)

            evidence.append(
                f"Claims Dossier: {total} claims evaluated | Supported: {supported} | "
                f"Rejected: {rejected} | Insufficient: {insufficient} | Conflicting: {conflicting} | "
                f"Requires Review: {review}"
            )

            for entry in claims_entries:
                cid = entry.get("claim_id", "")
                text = entry.get("claim_text", "")
                st = entry.get("validation_status", "UNKNOWN")
                conf = entry.get("confidence", 0.0)
                ev_refs = entry.get("evidence_references", [])
                ev_str = f" [Evidence: {', '.join(ev_refs)}]" if ev_refs else ""
                contra_refs = entry.get("contradicting_evidence_references", [])
                contra_str = f" [Contradicted by: {', '.join(contra_refs)}]" if contra_refs else ""
                evidence.append(f"[{st}] {cid}: {text} (conf: {conf:.2f}){ev_str}{contra_str}")

        if "verified_dossier" in sanitized_output and not dossier_data:
            evidence.append(sanitized_output["verified_dossier"])

        # Add violations if present
        if "violations" in sanitized_output:
            try:
                viols = json.loads(sanitized_output["violations"])
                for v in viols:
                    evidence.append(f"Violation: {v}")
            except Exception:
                pass

        # Compute Confidence Interval
        try:
            compliance_score = float(sanitized_output.get("compliance_score", "0.6"))
        except (ValueError, TypeError):
            compliance_score = 0.6

        rejected_count = dossier_data.get("rejected_claims", 0)
        conflicting_count = dossier_data.get("conflicting_claims", 0)
        insufficient_count = dossier_data.get("insufficient_claims", 0)

        if rejected_count > 0:
            point = 0.0
            lower = 0.0
            upper = 0.1
        elif conflicting_count > 0:
            point = 0.2
            lower = 0.1
            upper = 0.3
        elif insufficient_count > 0:
            point = 0.55
            lower = 0.4
            upper = 0.7
        elif compliance_score >= 0.8:
            point = min(0.95, compliance_score)
            lower = max(0.7, point - 0.1)
            upper = min(1.0, point + 0.05)
        else:
            point = max(0.1, compliance_score)
            lower = max(0.0, point - 0.15)
            upper = min(0.8, point + 0.15)

        confidence = ConfidenceInterval(
            point_estimate=round(point, 2),
            lower_bound=round(lower, 2),
            upper_bound=round(upper, 2),
        )

        return evidence, confidence

    @staticmethod
    def extract_product_specification(envelope: EvidenceEnvelope) -> ProductSpecification | None:
        """Helper to extract strongly typed ProductSpecification from an EvidenceEnvelope."""
        raw = envelope.payload.get("product_specification")
        if raw:
            try:
                return ProductSpecification.model_validate_json(raw)
            except Exception:
                return None
        return None

    @staticmethod
    def extract_claims_dossier(envelope: EvidenceEnvelope) -> ClaimsDossier | None:
        """Helper to extract strongly typed ClaimsDossier from an EvidenceEnvelope."""
        raw = envelope.payload.get("claims_dossier")
        if raw:
            try:
                return ClaimsDossier.model_validate_json(raw)
            except Exception:
                return None
        return None