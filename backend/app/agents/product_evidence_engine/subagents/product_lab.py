"""w_prod.product_lab: Formulation and Laboratory Audit Specialist Sub-Agent.

Validates finished product formulation specifications, audits analytical lab certificates,
normalizes analytical measurements deterministically, and evaluates formulation evidence bridges.
Strictly offline execution under network_policy: DISABLED.
Zero direct access to database, CMS, RAG, or parent runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from app.agents.product_evidence_engine.product_evidence import (
    PRODUCT_LAB_PROFILE,
    SpecialistModelProfile,
    dispatch_specialist_s_val,
)
from app.schemas.agent_contracts import ProductSpecification
from app.schemas.product_evidence import (
    EvidenceRelevance,
    FormulationEvidenceBridge,
    LabValidation,
    NormalizedMeasurement,
    ProductEvidenceTask,
    SpecialistResult,
    SpecialistRole,
    SpecialistTask,
)


class ProductLabAgent:
    """Specialist sub-agent for formulation and lab verification (w_prod.product_lab).

    Implements PE-05: Deterministic measurement normalization, lab validation audits,
    and 10-dimension formulation comparability bridging under strict offline isolation.
    """

    SPECIALIST_ROLE = SpecialistRole.PRODUCT_LAB
    SPECIALIST_ID = "w_prod.product_lab"

    # Supported conversion units and their base ratios
    # Category: mass_fraction (base: % w/w = 1.0)
    MASS_FRACTION_BASES: dict[str, float] = {
        "%": 1.0,
        "wt%": 1.0,
        "w/w %": 1.0,
        "wt %": 1.0,
        "% w/w": 1.0,
        "ppm": 0.0001,
        "mg/kg": 0.0001,
        "ug/g": 0.0001,
        "mcg/g": 0.0001,
        "ppb": 0.0000001,
        "mg/g": 0.1,
        "g/kg": 0.1,
        "g/g": 100.0,
    }

    # Category: mass_volume (base: mg/mL = 1.0)
    MASS_VOLUME_BASES: dict[str, float] = {
        "mg/ml": 1.0,
        "mg/mL": 1.0,
        "g/l": 1.0,
        "g/L": 1.0,
        "% w/v": 10.0,
        "w/v %": 10.0,
        "ug/ml": 0.001,
        "ug/mL": 0.001,
        "mcg/ml": 0.001,
        "mcg/mL": 0.001,
        "mg/l": 0.001,
        "mg/L": 0.001,
        "ug/l": 0.000001,
        "ug/L": 0.000001,
    }

    # Category: pure_mass (base: g = 1.0)
    PURE_MASS_BASES: dict[str, float] = {
        "kg": 1000.0,
        "g": 1.0,
        "mg": 0.001,
        "ug": 0.000001,
        "mcg": 0.000001,
        "ng": 0.000000001,
    }

    # Category: pure_volume (base: mL = 1.0)
    PURE_VOLUME_BASES: dict[str, float] = {
        "l": 1000.0,
        "L": 1000.0,
        "ml": 1.0,
        "mL": 1.0,
        "ul": 0.001,
        "uL": 0.001,
    }

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any = None,
        sandbox_client: Any = None,
    ) -> None:
        self._profile = profile or PRODUCT_LAB_PROFILE
        self._llm_client = llm_client
        self._sandbox_client = sandbox_client

    @property
    def role(self) -> SpecialistRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def profile(self) -> SpecialistModelProfile:
        return self._profile

    @property
    def allowed_operations(self) -> tuple[str, ...]:
        return self._profile.allowed_operations

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return self._profile.allowed_tools

    @property
    def llm_client(self) -> Any:
        return self._llm_client

    @property
    def sandbox_client(self) -> Any:
        return self._sandbox_client

    @classmethod
    def normalize_measurement(
        cls,
        original_value: float | str,
        original_unit: str,
        target_unit: str,
        density: float | None = None,
        lod: float | None = None,
        loq: float | None = None,
        uncertainty: float | None = None,
        precision: int | None = None,
    ) -> NormalizedMeasurement:
        """Deterministically normalize analytical measurements while preserving raw values, units,

        assumptions, precision, uncertainty, and LOD/LOQ distinctions.
        Never treats 'not detected' as zero. Requires supplied density for density-dependent conversions.
        """
        orig_u = original_unit.strip()
        targ_u = target_unit.strip()
        assumptions: list[str] = []

        # 1. Non-detect & LOD/LOQ evaluation
        is_nondetect = False
        parsed_numeric_val: float | None = None
        extracted_bound: float | None = None

        if isinstance(original_value, str):
            clean_str = original_value.strip().lower()
            if clean_str in ("nd", "not detected", "nondetect", "not-detected", "none detected"):
                is_nondetect = True
            elif clean_str.startswith("<"):
                is_nondetect = True
                m = re.search(r"<\s*([0-9.]+)", clean_str)
                if m:
                    extracted_bound = float(m.group(1))
                    if lod is None:
                        lod = extracted_bound
            else:
                try:
                    parsed_numeric_val = float(clean_str)
                except ValueError:
                    pass
        else:
            parsed_numeric_val = float(original_value)

        # 2. Determine conversion factor
        orig_key = orig_u.lower()
        targ_key = targ_u.lower()

        # Find matching categories
        orig_cat = None
        orig_factor = 1.0
        targ_cat = None
        targ_factor = 1.0

        for cat_name, cat_dict in (
            ("mass_fraction", cls.MASS_FRACTION_BASES),
            ("mass_volume", cls.MASS_VOLUME_BASES),
            ("pure_mass", cls.PURE_MASS_BASES),
            ("pure_volume", cls.PURE_VOLUME_BASES),
        ):
            for k, f in cat_dict.items():
                if k.lower() == orig_key:
                    orig_cat = cat_name
                    orig_factor = f
                if k.lower() == targ_key:
                    targ_cat = cat_name
                    targ_factor = f

        if orig_cat is None:
            raise ValueError(f"Unsupported original unit '{original_unit}'.")
        if targ_cat is None:
            raise ValueError(f"Unsupported target unit '{target_unit}'.")

        conversion_factor: float
        formula_desc: str

        if orig_cat == targ_cat:
            conversion_factor = orig_factor / targ_factor
            formula_desc = f"1 {original_unit} = {conversion_factor:.6g} {target_unit} (within {orig_cat})"
        elif orig_cat == "mass_fraction" and targ_cat == "mass_volume":
            # mass fraction (% w/w) -> mass/volume (mg/mL): requires density (g/mL)
            if density is None or density <= 0.0:
                raise ValueError(
                    f"Density-dependent conversion from '{original_unit}' (mass fraction) to "
                    f"'{target_unit}' (mass concentration) requires supplied positive density."
                )
            # base: 1% w/w = 10 mg/g; (10 mg/g) * density (g/mL) = 10 * density mg/mL
            ratio_to_pct = orig_factor  # original -> % w/w
            mg_ml_per_pct = 10.0 * density  # 1% w/w in mg/mL
            target_from_mg_ml = 1.0 / targ_factor  # mg/mL -> target
            conversion_factor = ratio_to_pct * mg_ml_per_pct * target_from_mg_ml
            formula_desc = f"1 {original_unit} = ({ratio_to_pct} * 10 * {density} * {target_from_mg_ml:.6g}) {target_unit} (density={density} g/mL)"
            assumptions.append(f"Supplied density {density} g/mL applied for mass-to-volume basis conversion.")
        elif orig_cat == "mass_volume" and targ_cat == "mass_fraction":
            # mass/volume (mg/mL) -> mass fraction (% w/w): requires density (g/mL)
            if density is None or density <= 0.0:
                raise ValueError(
                    f"Density-dependent conversion from '{original_unit}' (mass concentration) to "
                    f"'{target_unit}' (mass fraction) requires supplied positive density."
                )
            # base: 1 mg/mL / density = 1/density mg/g = (0.1 / density) % w/w
            ratio_to_mg_ml = orig_factor  # original -> mg/mL
            pct_per_mg_ml = 0.1 / density  # 1 mg/mL in % w/w
            target_from_pct = 1.0 / targ_factor  # % w/w -> target
            conversion_factor = ratio_to_mg_ml * pct_per_mg_ml * target_from_pct
            formula_desc = f"1 {original_unit} = ({ratio_to_mg_ml} * (0.1 / {density}) * {target_from_pct:.6g}) {target_unit} (density={density} g/mL)"
            assumptions.append(f"Supplied density {density} g/mL applied for volume-to-mass basis conversion.")
        elif orig_cat == "pure_mass" and targ_cat == "pure_volume":
            if density is None or density <= 0.0:
                raise ValueError(
                    f"Density-dependent conversion from '{original_unit}' (mass) to "
                    f"'{target_unit}' (volume) requires supplied positive density."
                )
            # mass (g) / density (g/mL) = volume (mL)
            conversion_factor = (orig_factor / density) / targ_factor
            formula_desc = f"1 {original_unit} = ({orig_factor} / ({density} * {targ_factor})) {target_unit}"
            assumptions.append(f"Supplied density {density} g/mL applied for mass-to-volume conversion.")
        elif orig_cat == "pure_volume" and targ_cat == "pure_mass":
            if density is None or density <= 0.0:
                raise ValueError(
                    f"Density-dependent conversion from '{original_unit}' (volume) to "
                    f"'{target_unit}' (mass) requires supplied positive density."
                )
            # volume (mL) * density (g/mL) = mass (g)
            conversion_factor = (orig_factor * density) / targ_factor
            formula_desc = f"1 {original_unit} = ({orig_factor} * {density} / {targ_factor}) {target_unit}"
            assumptions.append(f"Supplied density {density} g/mL applied for volume-to-mass conversion.")
        else:
            raise ValueError(f"Incompatible unit conversion between '{original_unit}' and '{target_unit}'.")

        # 3. Handle LOD / LOQ conversions
        converted_lod: float | None = None
        converted_loq: float | None = None
        if lod is not None:
            converted_lod = lod * conversion_factor
            if precision is not None:
                converted_lod = round(converted_lod, precision)
        if loq is not None:
            converted_loq = loq * conversion_factor
            if precision is not None:
                converted_loq = round(converted_loq, precision)

        # 4. Handle Uncertainty conversion
        converted_uncertainty: float | None = None
        if uncertainty is not None:
            converted_uncertainty = uncertainty * conversion_factor
            if precision is not None:
                converted_uncertainty = round(converted_uncertainty, precision)

        # 5. Handle Final Normalized Value
        if is_nondetect:
            assumptions.append("Non-detect preserved: analytical measurement is below detection threshold; never treated as zero.")
            if converted_lod is not None:
                normalized_val = f"< {converted_lod:.4g}"
            elif converted_loq is not None:
                normalized_val = f"< {converted_loq:.4g}"
            else:
                normalized_val = "ND"
        else:
            if parsed_numeric_val is None:
                raise ValueError(f"Cannot parse analytical measurement value '{original_value}'.")
            converted_num = parsed_numeric_val * conversion_factor
            if precision is not None:
                converted_num = round(converted_num, precision)
            normalized_val = converted_num

        return NormalizedMeasurement(
            original_value=original_value,
            original_unit=original_unit,
            normalized_value=normalized_val,
            normalized_unit=target_unit,
            conversion_formula=formula_desc,
            assumptions=assumptions,
            precision=precision,
            uncertainty=converted_uncertainty,
            lod=converted_lod,
            loq=converted_loq,
            is_nondetect=is_nondetect,
        )

    @staticmethod
    def build_product_specification(
        product_id: str,
        product_name: str,
        tenant_id: str,
        formulation_id: str | None = None,
        version: str = "1.0",
        ingredients: list[dict[str, Any]] | None = None,
        process_context: dict[str, Any] | str | None = None,
        packaging_context: dict[str, Any] | str | None = None,
        intended_use_context: dict[str, Any] | str | None = None,
        supporting_evidence_references: list[str] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> ProductSpecification:
        """Construct a strongly typed ProductSpecification conforming to PE-02/PE-05 invariants.

        Tracks explicit ingredient status: supplied, normalized, proposed, or missing.
        Retains process, packaging, and intended-use context without data loss.
        """
        raw_ingredients = ingredients or []
        normalized_ingredients: list[dict[str, Any]] = []
        missing_attrs: list[str] = []
        compliance_findings: list[str] = []

        valid_statuses = {"supplied", "normalized", "proposed", "missing"}

        for idx, ing in enumerate(raw_ingredients):
            identity = ing.get("material_identity") or ing.get("identity") or ing.get("name")
            if not identity or not str(identity).strip():
                missing_attrs.append(f"ingredient[{idx}].material_identity")
                continue

            status = ing.get("status", "supplied")
            if status not in valid_statuses:
                status = "supplied" if ing.get("concentration") is not None else "missing"

            conc = ing.get("concentration")
            unit = ing.get("unit", "%")
            basis = ing.get("composition_basis", "w/w")
            supplier_ref = ing.get("supplier_reference") or ing.get("supplier_ref")
            spec_ref = ing.get("specification_reference") or ing.get("spec_ref")
            prov_ref = ing.get("provenance_ref")

            if conc is None and status != "missing":
                status = "missing"
                compliance_findings.append(f"Ingredient '{identity}' marked missing concentration.")

            normalized_ingredients.append({
                "material_identity": str(identity).strip(),
                "concentration": float(conc) if conc is not None else None,
                "unit": str(unit).strip(),
                "composition_basis": str(basis).strip(),
                "supplier_reference": str(supplier_ref) if supplier_ref else None,
                "specification_reference": str(spec_ref) if spec_ref else None,
                "status": status,
                "provenance_ref": str(prov_ref) if prov_ref else None,
            })

        # Process, packaging, intended use context
        norm_attributes: dict[str, Any] = {
            "process_context": process_context,
            "packaging_context": packaging_context,
            "intended_use_context": intended_use_context,
        }

        if process_context is None:
            missing_attrs.append("process_context")
        if packaging_context is None:
            missing_attrs.append("packaging_context")
        if intended_use_context is None:
            missing_attrs.append("intended_use_context")

        validation_status = "VALIDATED" if len(missing_attrs) == 0 else "NEEDS_REVIEW"

        return ProductSpecification(
            product_id=product_id,
            product_name=product_name,
            tenant_id=tenant_id,
            formulation_id=formulation_id or f"form-{product_id}-v{version}",
            version=version,
            normalized_attributes=norm_attributes,
            ingredients=normalized_ingredients,
            supporting_evidence_references=supporting_evidence_references or [],
            validation_status=validation_status,
            compliance_findings=compliance_findings,
            missing_attributes=missing_attrs,
            provenance=provenance or {"created_by": "w_prod.product_lab", "version": version},
        )

    @staticmethod
    def evaluate_formulation_bridge(
        studied_material: str,
        proposed_product: str,
        dimensions: dict[str, str],
        bridge_id: str | None = None,
        scientific_rationale: str = "",
        limits_and_conditions: list[str] | None = None,
        is_ingredient_to_finished_product: bool = False,
    ) -> FormulationEvidenceBridge:
        """Evaluate scientific comparability across 10 dimensions.

        Enforces that ingredient evidence cannot transfer to finished product without an explicit bridge.
        Surfaces all mismatches, supplier extract changes, concentration, vehicle, and batch discrepancies.
        """
        valid_comparability = {"match", "mismatch", "unknown", "not_applicable"}
        req_dimensions = (
            "identity",
            "concentration",
            "vehicle",
            "route",
            "exposure",
            "population",
            "duration",
            "endpoint",
            "manufacturing",
            "packaging",
        )

        dim_values: dict[str, str] = {}
        has_mismatch = False
        has_unknown = False

        for dim in req_dimensions:
            val = dimensions.get(dim, dimensions.get(f"{dim}_comparability", "unknown")).lower()
            if val not in valid_comparability:
                raise ValueError(
                    f"Invalid comparability value '{val}' for dimension '{dim}'. "
                    f"Must be one of {valid_comparability}."
                )
            dim_values[f"{dim}_comparability"] = val
            if val == "mismatch":
                has_mismatch = True
            elif val == "unknown":
                has_unknown = True

        requires_review = False
        overall_relevance: EvidenceRelevance

        if is_ingredient_to_finished_product:
            # Ingredient-to-finished-product requires explicit bridging; never direct
            if dim_values["endpoint_comparability"] == "mismatch":
                # e.g., in vitro cell assay offered for finished human clinical claim
                overall_relevance = EvidenceRelevance.NOT_APPLICABLE
                requires_review = True
            elif has_mismatch:
                overall_relevance = EvidenceRelevance.INDIRECT
                requires_review = True
            elif has_unknown:
                overall_relevance = EvidenceRelevance.BRIDGE_REQUIRED
                requires_review = True
            else:
                overall_relevance = EvidenceRelevance.BRIDGE_REQUIRED
                requires_review = False
        else:
            if has_mismatch:
                overall_relevance = EvidenceRelevance.INDIRECT
                requires_review = True
            elif has_unknown:
                overall_relevance = EvidenceRelevance.BRIDGE_REQUIRED
                requires_review = True
            else:
                overall_relevance = EvidenceRelevance.DIRECT
                requires_review = False

        b_id = bridge_id or f"bridge-{hashlib.sha256(f'{studied_material}:{proposed_product}'.encode()).hexdigest()[:12]}"

        rationale = scientific_rationale or (
            f"Comparability assessment between studied material '{studied_material}' and "
            f"proposed product '{proposed_product}'. "
            f"Status: {'mismatches noted' if has_mismatch else 'concordant'}."
        )

        return FormulationEvidenceBridge(
            bridge_id=b_id,
            studied_material=studied_material,
            proposed_product=proposed_product,
            identity_comparability=dim_values["identity_comparability"],  # type: ignore[arg-type]
            concentration_comparability=dim_values["concentration_comparability"],  # type: ignore[arg-type]
            vehicle_comparability=dim_values["vehicle_comparability"],  # type: ignore[arg-type]
            route_comparability=dim_values["route_comparability"],  # type: ignore[arg-type]
            exposure_comparability=dim_values["exposure_comparability"],  # type: ignore[arg-type]
            population_comparability=dim_values["population_comparability"],  # type: ignore[arg-type]
            duration_comparability=dim_values["duration_comparability"],  # type: ignore[arg-type]
            endpoint_comparability=dim_values["endpoint_comparability"],  # type: ignore[arg-type]
            manufacturing_comparability=dim_values["manufacturing_comparability"],  # type: ignore[arg-type]
            packaging_comparability=dim_values["packaging_comparability"],  # type: ignore[arg-type]
            overall_relevance=overall_relevance,
            scientific_rationale=rationale,
            limits_and_conditions=limits_and_conditions or [],
            requires_expert_review=requires_review,
        )

    @staticmethod
    def validate_lab_report(
        report_data: dict[str, Any],
        specification_limits: dict[str, Any] | None = None,
        expected_product_or_batch_id: str | None = None,
        default_decision_rule: str | None = None,
        default_limit_source: str | None = None,
    ) -> LabValidation:
        """Audit an analytical laboratory report / certificate of analysis.

        Verifies hash authenticity, accreditation validity & scope, batch linkage,
        chronology, LOD/LOQ preservation, and conformity against limits using explicit decision rules.
        Appearance of signatures, logos, or certificates alone cannot produce a validation pass.
        """
        deviations: list[str] = list(report_data.get("deviations", []))
        reviewer_reqs: list[str] = list(report_data.get("reviewer_requirements", []))

        report_id = str(report_data.get("report_id", "rep-unknown"))
        report_version = str(report_data.get("report_version", "1.0"))
        report_hash = str(report_data.get("report_hash", ""))
        issuer_lab = str(report_data.get("issuer_lab_name", "Unknown Laboratory"))
        test_method = str(report_data.get("test_method", "Standard Analytical Method"))
        sample_batch = str(report_data.get("sample_or_batch_id", ""))

        # 1. Authenticity & Integrity
        if not report_hash or report_data.get("hash_verified") is False:
            deviations.append("Report content hash is missing or fails verification.")

        has_visual_elements = bool(
            report_data.get("signatures") or report_data.get("has_logo_or_letterhead") or report_data.get("certificate_image")
        )
        signatures_verified = bool(report_data.get("signatures_verified", False))
        if has_visual_elements and not signatures_verified:
            deviations.append("Visual logos/signatures present but unverified against authorized credential registry.")
            reviewer_reqs.append("Verify report signature with laboratory quality assurance manager.")

        # 2. Accreditation Scope & Validity
        lab_accreditation = str(report_data.get("lab_accreditation", ""))
        accreditation_verified = bool(report_data.get("accreditation_verified", False))
        accreditation_scope_covers = bool(report_data.get("accreditation_scope_covers_test", False))
        expiry_date = report_data.get("accreditation_expiry_date")
        test_date = report_data.get("test_date")

        if lab_accreditation:
            if not accreditation_verified:
                deviations.append(
                    "Accreditation statement claimed by document appearance but unverified in national accreditation directory."
                )
                reviewer_reqs.append("Verify accreditation certificate on accreditation body portal.")
            elif not accreditation_scope_covers:
                deviations.append(
                    f"Test method '{test_method}' is outside verified laboratory accreditation scope."
                )
            if expiry_date and test_date and str(expiry_date) < str(test_date):
                deviations.append(
                    f"Laboratory accreditation expired ({expiry_date}) prior to test date ({test_date})."
                )

        # 3. Sample / Batch / Product Linkage
        product_linkage_verified = False
        if expected_product_or_batch_id:
            if sample_batch != expected_product_or_batch_id:
                deviations.append(
                    f"Sample/batch linkage mismatch: lab report tested '{sample_batch}' but product requires '{expected_product_or_batch_id}'."
                )
                product_linkage_verified = False
            else:
                product_linkage_verified = True
        else:
            product_linkage_verified = bool(report_data.get("product_linkage_verified", False))

        # 4. Chronology and Chain of Custody
        sampling_date = report_data.get("sampling_date")
        receipt_date = report_data.get("receipt_date")
        if sampling_date and test_date and str(test_date) < str(sampling_date):
            deviations.append("Chronological anomaly: test date precedes sampling date.")
        if receipt_date and sampling_date and str(receipt_date) < str(sampling_date):
            deviations.append("Chronological anomaly: receipt date precedes sampling date.")

        chain_of_custody_verified = bool(report_data.get("chain_of_custody_verified", False))
        if not chain_of_custody_verified:
            reviewer_reqs.append("Review sample chain of custody form and storage temperature log.")

        # 5. Conformity Against Specification Limits
        conformity_assessment: Literal["PASS", "FAIL", "UNKNOWN", "REVIEW_REQUIRED"] = "UNKNOWN"
        raw_results = report_data.get("raw_results", {})
        normalized_results = report_data.get("normalized_results", {})
        lod_loq = report_data.get("lod_loq", {})
        uncertainty = report_data.get("uncertainty", {})

        limits = specification_limits or report_data.get("specification_limits")
        decision_rule = (
            report_data.get("decision_rule")
            or default_decision_rule
            or "simple_acceptance"
        )
        limit_source = (
            report_data.get("specification_limit_source")
            or default_limit_source
            or ""
        )

        has_critical_deviation = any(
            "mismatch" in d.lower() or "outside" in d.lower() or "expired" in d.lower()
            for d in deviations
        )

        if not limits or not limit_source or not product_linkage_verified:
            conformity_assessment = "UNKNOWN" if not has_critical_deviation else "REVIEW_REQUIRED"
            if not limit_source and limits:
                deviations.append("Specification limits supplied without authoritative limit source; conformity cannot be verified.")
            if not product_linkage_verified and expected_product_or_batch_id:
                deviations.append("Batch linkage not established; limits cannot be evaluated for this product.")
        else:
            all_passed = True
            any_failed = False
            requires_guard_band_review = False

            for analyte, res_val in raw_results.items():
                if analyte not in limits:
                    continue
                spec = limits[analyte]
                max_lim = spec.get("max")
                min_lim = spec.get("min")
                u_val = float(uncertainty.get(analyte, 0.0))

                # Handle Non-detect
                is_nd = False
                lod_val = float(lod_loq.get(f"{analyte}_lod", lod_loq.get("lod", 0.0)))
                if isinstance(res_val, str) and (res_val.lower() in ("nd", "not detected") or res_val.startswith("<")):
                    is_nd = True

                if is_nd:
                    if max_lim is not None:
                        if lod_val > float(max_lim):
                            # LOD is higher than allowable limit; non-detect cannot prove compliance!
                            requires_guard_band_review = True
                            deviations.append(
                                f"LOD ({lod_val}) for '{analyte}' exceeds specification limit ({max_lim}); non-detect does not establish conformity."
                            )
                        # else: LOD <= max_lim, non-detect complies with limit
                    continue

                try:
                    num_val = float(res_val)
                except (ValueError, TypeError):
                    requires_guard_band_review = True
                    continue

                if max_lim is not None:
                    max_flt = float(max_lim)
                    if decision_rule in ("binary_guard_band", "ilac_g8", "guard_banded"):
                        acceptance_limit = max_flt - u_val
                        if num_val > max_flt:
                            any_failed = True
                        elif num_val > acceptance_limit:
                            requires_guard_band_review = True
                    else:
                        # simple acceptance
                        if num_val > max_flt:
                            any_failed = True

                if min_lim is not None:
                    min_flt = float(min_lim)
                    if decision_rule in ("binary_guard_band", "ilac_g8", "guard_banded"):
                        acceptance_limit = min_flt + u_val
                        if num_val < min_flt:
                            any_failed = True
                        elif num_val < acceptance_limit:
                            requires_guard_band_review = True
                    else:
                        if num_val < min_flt:
                            any_failed = True

            if any_failed:
                conformity_assessment = "FAIL"
            elif requires_guard_band_review:
                conformity_assessment = "REVIEW_REQUIRED"
            else:
                conformity_assessment = "PASS"

        # 6. Overall Validation Outcome
        validation_outcome: Literal["VALIDATED", "DEVIATIONS_NOTED", "REJECTED"]
        if has_critical_deviation or conformity_assessment == "FAIL":
            validation_outcome = "REJECTED"
        elif len(deviations) > 0 or conformity_assessment in ("REVIEW_REQUIRED", "UNKNOWN"):
            validation_outcome = "DEVIATIONS_NOTED"
        else:
            validation_outcome = "VALIDATED"

        return LabValidation(
            report_id=report_id,
            report_version=report_version,
            report_hash=report_hash,
            issuer_lab_name=issuer_lab,
            lab_accreditation=lab_accreditation,
            accreditation_verified=accreditation_verified,
            accreditation_scope_covers_test=accreditation_scope_covers,
            accreditation_expiry_date=expiry_date,
            test_method=test_method,
            method_version=str(report_data.get("method_version", "1.0")),
            sample_or_batch_id=sample_batch,
            product_linkage_verified=product_linkage_verified,
            sampling_date=sampling_date,
            receipt_date=receipt_date,
            test_date=test_date,
            chain_of_custody_verified=chain_of_custody_verified,
            analyte_or_endpoints=report_data.get("analyte_or_endpoints", list(raw_results.keys())),
            raw_results=raw_results,
            normalized_results=normalized_results or raw_results,
            units=str(report_data.get("units", "")),
            lod_loq=lod_loq,
            measurement_uncertainty=uncertainty,
            specification_limit_source=limit_source,
            decision_rule=decision_rule,
            deviations=deviations,
            reviewer_requirements=reviewer_reqs,
            validation_outcome=validation_outcome,
            conformity_assessment=conformity_assessment,
        )

    def build_task(
        self,
        task_id: str,
        tenant_id: str,
        parent_task_id: str,
        operation: str = "validate_formulation",
        context_slice: dict[str, Any] | None = None,
        input_manifest: list[str] | None = None,
        delegated_token_limit: int = 4000,
        policy_refs: list[str] | None = None,
        attempt_id: str = "1",
    ) -> SpecialistTask:
        """Construct strongly typed SpecialistTask for S_VAL execution."""
        return SpecialistTask(
            task_id=task_id,
            tenant_id=tenant_id,
            parent_task_id=parent_task_id,
            specialist_role=self.SPECIALIST_ROLE,
            operation=operation,
            input_manifest=input_manifest or [],
            context_slice=context_slice or {},
            profile_ref=self._profile.profile_id,
            profile_version=self._profile.profile_version,
            profile_digest=self._profile.compute_digest(),
            delegated_token_limit=min(delegated_token_limit, self._profile.budget_limit_tokens),
            policy_refs=policy_refs or [self._profile.endpoint_policy_ref],
            attempt_id=attempt_id,
        )

    def execute_lab_validation(
        self,
        specialist_task: SpecialistTask,
        parent_task: ProductEvidenceTask,
        report_data: dict[str, Any] | None = None,
        specification_limits: dict[str, Any] | None = None,
        expected_batch_id: str | None = None,
    ) -> SpecialistResult:
        """Dispatch formulation & laboratory validation via S_VAL runtime under least privilege."""
        if report_data is not None:
            lab_val = self.validate_lab_report(
                report_data,
                specification_limits=specification_limits,
                expected_product_or_batch_id=expected_batch_id,
            )
            specialist_task.context_slice["lab_validation"] = lab_val.model_dump(mode="json")
            specialist_task.context_slice["conformity_assessment"] = lab_val.conformity_assessment
            if lab_val.deviations:
                for dev in lab_val.deviations:
                    if "batch" in dev.lower():
                        specialist_task.context_slice["batch_mismatch"] = True
                    if "outside" in dev.lower():
                        specialist_task.context_slice["accreditation_out_of_scope"] = True
                    if "hash" in dev.lower():
                        specialist_task.context_slice["report_hash_missing"] = True
                    if "unverified" in dev.lower():
                        specialist_task.context_slice["unverified_visual_elements"] = True

        return dispatch_specialist_s_val(
            self._sandbox_client,
            specialist_task=specialist_task,
            parent_task=parent_task,
        )
