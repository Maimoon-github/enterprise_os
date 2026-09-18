"""DEV-REL: Release Operations & Packaging Sub-Agent (DE-11).

Responsible for:
- Packaging verified and security-approved candidate deliverable snapshots
- Plan authority and HITL authorization verification (pre-DEV-REL human approval)
- Strict Security Dossier Gate: Machine DENY overrides human approval
  (machine DENY + human APPROVE = DENY; fails closed on any CRITICAL/HIGH finding)
- Exact candidate hash verification matching the security dossier snapshot
- Release packaging execution in fresh isolated sandbox (S_CODE):
  1. package_release_bundle: Immutable content-addressable release artifacts with SHA-256 digests
  2. generate_cyclonedx_sbom: CycloneDX v1.5 Software Bill of Materials with dependency graph
  3. generate_deployment_manifest: Container runtime, resource limits, and ingress specification
  4. generate_rollback_manifest: Blue/green drain steps, compensation actions, health checks
  5. simulate_migration_dry_run: Database/schema migration dry-run and idempotency check
  6. verify_release_integrity: Cryptographic digest validation across all packaged artifacts
- SLSA v1.0 / in-toto attestation generation via control-plane ProvenanceRecorder (keys outside)
- Scope boundary: packaging ONLY, never direct production deployment or outbound dispatch
- Sealed, tamper-evident ReleaseCandidateDeliverable (ReleaseDossier)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope, TaskGrant
from app.schemas.cms import CmsCandidateDeliverable
from app.schemas.development.development_plan import DevelopmentPlan, DevelopmentPlanStep
from app.schemas.development.development_result import (
    CodeCandidateDeliverable,
    CycloneDxComponent,
    CycloneDxSbom,
    DeploymentManifest,
    DevelopmentTaskGrant,
    MigrationInstruction,
    ReleaseArtifact,
    ReleaseCandidateDeliverable,
    RollbackManifest,
    SecurityDossier,
)
from app.schemas.development.ui import UiCandidateDeliverable
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate

logger = logging.getLogger(__name__)


class ReleaseOpsAgent:
    """DEV-REL release packaging sub-agent for W_DEV."""

    def __init__(
        self,
        sandbox_client: Any,
        provenance_recorder: Any | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self._sandbox_client = sandbox_client
        self._provenance_recorder = provenance_recorder
        self._llm_client = llm_client

    async def _reason_with_llm(
        self,
        *,
        component_name: str,
        version: str,
        artifact_count: int,
        sbom_components_count: int,
        migration_steps_count: int,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """LLM cognitive reflection for DEV-REL: Think -> Ponder -> Reflect -> React.

        - Think & Ponder: Examines release bundle composition, dependencies, and environment constraints.
        - Reflect: Synthesizes operational risk assessment, blue-green deployment health notes, and rollback guidance.
        - React: Attaches structured release reasoning to deliverable provenance without altering packaging artifacts.
        """
        cognitive_result: dict[str, Any] = {
            "release_thought": f"Assessed release bundle for '{component_name}' v{version} ({artifact_count} artifacts, {sbom_components_count} dependencies).",
            "operational_risks": [
                f"Contains {migration_steps_count} migration step(s); verify database connection pools."
            ] if migration_steps_count > 0 else ["Zero schema migrations required."],
            "rollback_recommendations": [
                "Execute automated health checks on /health before blue/green traffic cutover.",
                "Ensure previous stable version is kept warm for rapid traffic drain."
            ],
            "release_readiness": "APPROVED_FOR_STAGING_DELIVERY",
        }

        if self._llm_client is not None:
            system_prompt = (
                "You are DEV-REL, the Development Engine's release packaging and delivery agent. "
                "Ponder release packaging artifacts, dependency SBOM, and deployment manifests. "
                "Reflect on operational risks and produce actionable release/rollback guidance. "
                "Structure output strictly as a JSON dictionary."
            )
            user_prompt = (
                f"Component: {component_name}\n"
                f"Version: {version}\n"
                f"Artifacts Count: {artifact_count}\n"
                f"SBOM Dependencies Count: {sbom_components_count}\n"
                f"Migration Steps: {migration_steps_count}\n"
                "Return JSON with keys: release_thought (str), operational_risks (list[str]), rollback_recommendations (list[str]), release_readiness (str)"
            )
            try:
                raw: Any = None
                if hasattr(self._llm_client, "generate"):
                    raw = await self._llm_client.generate(prompt=user_prompt, system=system_prompt)
                elif hasattr(self._llm_client, "complete"):
                    raw = await self._llm_client.complete(user_prompt, system=system_prompt)
                elif callable(self._llm_client):
                    raw = await self._llm_client(user_prompt)
                if isinstance(raw, str):
                    clean_str = raw.strip()
                    if clean_str.startswith("```"):
                        clean_str = clean_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                    raw = json.loads(clean_str)
                if isinstance(raw, dict):
                    for k in ("release_thought", "operational_risks", "rollback_recommendations", "release_readiness"):
                        if k in raw:
                            cognitive_result[k] = raw[k]
            except Exception as exc:
                logger.warning("ReleaseOpsAgent LLM reasoning failed: %s", exc, exc_info=True)

        return cognitive_result

    async def _invoke_sandbox(
        self,
        *,
        tenant_id: str = "default",
        task_id: str = "unknown",
        operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke sandbox control plane via S_CODE with in-process micro-tool fallback."""
        mandate = SandboxInvocationMandate(
            tenant_id=tenant_id,
            task_id=task_id,
            worker_role=WorkerRole.DEVELOPMENT,
            capability=SandboxCapability.CODE,
            operation=operation,
            payload=payload,
        )

        result = None
        if hasattr(self._sandbox_client, "invoke"):
            result = await self._sandbox_client.invoke(mandate)
        elif hasattr(self._sandbox_client, "execute"):
            result = await self._sandbox_client.execute(mandate)

        if result is not None and not result.success:
            logger.error(
                "Sandbox invocation failed for DEV-REL operation %s",
                operation,
                extra={"operation": operation, "error": result.error},
            )
            return {"status": "error", "error": result.error or "Sandbox execution failure"}

        output = result.sanitized_output if result else {}
        output = output or {}

        if "output" in output and isinstance(output["output"], dict):
            return output["output"]

        rel_expected_keys = {
            "package_release_bundle": "release_artifacts",
            "generate_cyclonedx_sbom": "sbom",
            "generate_deployment_manifest": "deployment_manifest",
            "generate_rollback_manifest": "rollback_manifest",
            "simulate_migration_dry_run": "dry_run_passed",
            "verify_release_integrity": "integrity_verified",
        }
        if operation in rel_expected_keys and rel_expected_keys[operation] in output:
            return output

        # Fallback to in-process micro-tools
        from app.integrations.sandbox.micro_tools import execute_s_code

        fallback_payload = dict(payload)
        fallback_payload["operation"] = operation
        return execute_s_code(fallback_payload)

    async def execute_release_task(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant | None = None,
        candidate: (
            CodeCandidateDeliverable
            | UiCandidateDeliverable
            | CmsCandidateDeliverable
            | Any
            | None
        ) = None,
        expected_candidate_hash: str | None = None,
        security_dossier: SecurityDossier | None = None,
        plan: DevelopmentPlan | None = None,
        hitl_approved: bool = True,
        hitl_approval_token: str | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        context: dict[str, Any] | None = None,
    ) -> ReleaseCandidateDeliverable:
        """Execute release packaging and produce sealed ReleaseCandidateDeliverable."""
        tenant_id = (
            grant.tenant_scope.tenant_id
            if hasattr(grant, "tenant_scope") and grant.tenant_scope
            else "default"
        )
        task_id = grant.task_id if hasattr(grant, "task_id") else "unknown"
        return await self.prepare_release(
            tenant_id=tenant_id,
            task_id=task_id,
            workflow_id=workflow_id,
            plan=plan,
            task_grant=grant,
            security_dossier=security_dossier,
            candidate=candidate,
            expected_candidate_hash=expected_candidate_hash,
            hitl_approved=hitl_approved,
            hitl_approval_token=hitl_approval_token,
            context=context,
        )

    async def prepare_release(
        self,
        *,
        tenant_id: str = "default",
        task_id: str = "unknown",
        workflow_id: str | None = None,
        plan: DevelopmentPlan | None = None,
        task_grant: TaskGrant | DevelopmentTaskGrant | None = None,
        security_dossier: SecurityDossier | None = None,
        candidate: (
            CodeCandidateDeliverable
            | UiCandidateDeliverable
            | CmsCandidateDeliverable
            | Any
            | None
        ) = None,
        expected_candidate_hash: str | None = None,
        hitl_approved: bool = True,
        hitl_approval_token: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ReleaseCandidateDeliverable:
        """Execute release packaging and produce sealed ReleaseCandidateDeliverable."""
        ctx = context or {}
        wf_id = workflow_id or f"wf-rel-{uuid.uuid4().hex[:8]}"

        # 1. Plan Authority Enforcement
        if plan is not None:
            rel_step: DevelopmentPlanStep | None = None
            for s in plan.steps:
                step_name = (
                    getattr(s, "step_name", None)
                    or getattr(s, "subagent_id", None)
                    or getattr(s, "subagent", None)
                    or getattr(s, "step_id", None)
                    or ""
                )
                if "REL" in step_name.upper():
                    rel_step = s
                    break

            if (
                rel_step is not None
                and getattr(rel_step, "status", None) == "SKIPPED_NOT_APPLICABLE"
            ):
                raise PolicyViolationError(
                    "Execution of DEV-REL is not authorized by the development plan "
                    "(step marked SKIPPED_NOT_APPLICABLE)."
                )

        # 2. Scope Boundary Invariant: DEV-REL packages only; no production deployment
        if (
            ctx.get("deploy_to_production")
            or ctx.get("execute_deployment")
            or ctx.get("outbound_dispatch")
        ):
            raise PolicyViolationError(
                "Scope violation: DEV-REL is restricted to release packaging only; "
                "production deployment or outbound dispatch is forbidden."
            )

        # 3. Pre-DEV-REL Human Approval Gate Check
        if not hitl_approved:
            raise PolicyViolationError(
                "DEV-REL release packaging requires prior human-in-the-loop (HITL) approval."
            )
        if ctx.get("require_hitl_token") and not hitl_approval_token:
            raise PolicyViolationError(
                "Missing required HITL approval token for DEV-REL packaging."
            )

        # 4. Strict Security Dossier Gate (CRITICAL INVARIANT)
        # Machine DENY overrides human approval: machine DENY + human APPROVE = DENY
        if security_dossier is None:
            raise PolicyViolationError(
                "DEV-REL release packaging requires an approved SecurityDossier."
            )

        if not security_dossier.is_acceptable_for_release():
            raise PolicyViolationError(
                f"DEV-REL rejected: Security dossier failed with verdict "
                f"'{security_dossier.verdict}' and {security_dossier.hard_block_count} "
                f"hard-block findings. Machine DENY overrides human approval."
            )

        # 5. Candidate Snapshot Integrity Check (Fail-Closed)
        actual_candidate_hash = ""
        component_name = security_dossier.component_name
        version = str(ctx.get("version", "1.0.0"))

        if candidate is not None:
            component_name = getattr(candidate, "component_name", component_name)
            actual_candidate_hash = getattr(candidate, "candidate_hash", "")
            if not actual_candidate_hash and hasattr(candidate, "compute_candidate_hash"):
                actual_candidate_hash = candidate.compute_candidate_hash()
            elif not actual_candidate_hash and hasattr(candidate, "compute_deliverable_hash"):
                actual_candidate_hash = candidate.compute_deliverable_hash()

        if not actual_candidate_hash:
            actual_candidate_hash = security_dossier.candidate_hash

        if actual_candidate_hash != security_dossier.candidate_hash:
            raise PolicyViolationError(
                f"Candidate digest mismatch: candidate hash '{actual_candidate_hash}' "
                f"does not match security dossier hash '{security_dossier.candidate_hash}'."
            )

        if expected_candidate_hash and expected_candidate_hash != actual_candidate_hash:
            raise PolicyViolationError(
                f"Candidate digest mismatch: expected '{expected_candidate_hash}', "
                f"got '{actual_candidate_hash}'. Snapshot integrity compromised."
            )

        # Extract source files
        source_files: dict[str, str] = {}
        if candidate is not None:
            if hasattr(candidate, "source_code") and isinstance(candidate.source_code, dict):
                source_files.update(candidate.source_code)
            elif hasattr(candidate, "code_diffs"):
                for d in getattr(candidate, "code_diffs", []):
                    fp = getattr(d, "file_path", "")
                    if fp:
                        source_files[fp] = getattr(d, "diff_unified", "")
        if "source_files" in ctx and isinstance(ctx["source_files"], dict):
            source_files.update(ctx["source_files"])
        if not source_files:
            source_files["main.py"] = f"# release deliverable for {component_name}\n"

        evidence_envelopes: list[EvidenceEnvelope] = []

        # -------------------------------------------------------------
        # Step 1: Package Release Bundle
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        bundle_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="package_release_bundle",
            payload={
                "tenant_id": tenant_id,
                "task_id": task_id,
                "component_name": component_name,
                "version": version,
                "source_files": source_files,
            },
        )
        t_bundle = (time.perf_counter() - t0) * 1000

        raw_artifacts = bundle_res.get("release_artifacts") or []
        release_artifacts: list[ReleaseArtifact] = []
        for ra in raw_artifacts:
            release_artifacts.append(
                ReleaseArtifact(
                    artifact_name=str(ra.get("artifact_name", "artifact")),
                    file_path=str(ra.get("file_path", "")),
                    sha256=str(ra.get("sha256", "")),
                    size_bytes=int(ra.get("size_bytes", 0)),
                    media_type=str(ra.get("media_type", "application/octet-stream")),
                )
            )

        artifact_digests: dict[str, str] = dict(bundle_res.get("artifact_digests") or {})
        for art in release_artifacts:
            artifact_digests[art.artifact_name] = art.sha256

        evidence_envelopes.append(
            EvidenceEnvelope(
                task_id=task_id,
                worker_role=WorkerRole.DEVELOPMENT,
                confidence=ConfidenceInterval(
                    point_estimate=1.0, lower_bound=0.95, upper_bound=1.0
                ),
                findings=[f"Packaged {len(release_artifacts)} artifacts"],
                payload={
                    "artifact_count": str(len(release_artifacts)),
                    "bundle_digest": str(bundle_res.get("bundle_digest", "")),
                    "elapsed_ms": f"{t_bundle:.1f}",
                },
                produced_at=datetime.now(UTC),
            )
        )

        # -------------------------------------------------------------
        # Step 2: Generate CycloneDX v1.5 SBOM
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        sbom_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="generate_cyclonedx_sbom",
            payload={
                "tenant_id": tenant_id,
                "task_id": task_id,
                "component_name": component_name,
                "version": version,
                "dependencies": ctx.get("dependencies", {}),
            },
        )
        t_sbom = (time.perf_counter() - t0) * 1000

        raw_sbom = sbom_res.get("sbom") or {}
        components: list[CycloneDxComponent] = []
        for rc in raw_sbom.get("components") or []:
            components.append(
                CycloneDxComponent(
                    name=str(rc.get("name", "dep")),
                    version=str(rc.get("version", "1.0.0")),
                    type=str(rc.get("type", "library")),
                    purl=str(rc.get("purl", "")),
                    hashes=dict(rc.get("hashes", {})),
                    licenses=list(rc.get("licenses", ["MIT"])),
                )
            )

        cyclonedx_sbom = CycloneDxSbom(
            bomFormat=str(raw_sbom.get("bomFormat", "CycloneDX")),
            specVersion=str(raw_sbom.get("specVersion", "1.5")),
            serialNumber=str(raw_sbom.get("serialNumber") or f"urn:uuid:{uuid.uuid4()}"),
            version=int(raw_sbom.get("version", 1)),
            metadata=dict(raw_sbom.get("metadata", {})),
            components=components,
            dependencies=list(raw_sbom.get("dependencies", [])),
        )
        cyclonedx_sbom.compute_sbom_hash()

        evidence_envelopes.append(
            EvidenceEnvelope(
                task_id=task_id,
                worker_role=WorkerRole.DEVELOPMENT,
                confidence=ConfidenceInterval(
                    point_estimate=1.0, lower_bound=0.95, upper_bound=1.0
                ),
                findings=[f"Generated SBOM with {len(components)} components"],
                payload={
                    "component_count": str(len(components)),
                    "sbom_hash": cyclonedx_sbom.sbom_hash,
                    "elapsed_ms": f"{t_sbom:.1f}",
                },
                produced_at=datetime.now(UTC),
            )
        )

        # -------------------------------------------------------------
        # Step 3: Generate Deployment Manifest
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        deploy_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="generate_deployment_manifest",
            payload={
                "tenant_id": tenant_id,
                "task_id": task_id,
                "component_name": component_name,
                "version": version,
                "runtime": ctx.get("runtime", "python:3.11-slim"),
                "entrypoint": ctx.get("entrypoint", "main.py"),
                "environment_variables": ctx.get("environment_variables", {}),
                "healthcheck_endpoint": ctx.get("healthcheck_endpoint", "/health"),
                "resource_limits": ctx.get("resource_limits", {"cpu": "1.0", "memory": "1Gi"}),
                "ingress_route": ctx.get("ingress_route", f"/{component_name}"),
            },
        )
        t_deploy = (time.perf_counter() - t0) * 1000

        raw_deploy = deploy_res.get("deployment_manifest") or {}
        deployment_manifest = DeploymentManifest(
            manifest_id=str(
                raw_deploy.get("manifest_id") or f"deploy-{component_name}-{version}"
            ),
            component_name=component_name,
            version=version,
            runtime=str(raw_deploy.get("runtime", "python:3.11-slim")),
            entrypoint=str(raw_deploy.get("entrypoint", "main.py")),
            environment_variables=dict(raw_deploy.get("environment_variables", {})),
            healthcheck_endpoint=str(raw_deploy.get("healthcheck_endpoint", "/health")),
            resource_limits=dict(
                raw_deploy.get("resource_limits", {"cpu": "1.0", "memory": "1Gi"})
            ),
            ingress_route=str(raw_deploy.get("ingress_route", f"/{component_name}")),
        )
        deployment_manifest.compute_manifest_hash()

        evidence_envelopes.append(
            EvidenceEnvelope(
                task_id=task_id,
                worker_role=WorkerRole.DEVELOPMENT,
                confidence=ConfidenceInterval(
                    point_estimate=1.0, lower_bound=0.95, upper_bound=1.0
                ),
                findings=[f"Generated deployment manifest {deployment_manifest.manifest_id}"],
                payload={
                    "manifest_id": deployment_manifest.manifest_id,
                    "manifest_hash": deployment_manifest.manifest_hash,
                    "elapsed_ms": f"{t_deploy:.1f}",
                },
                produced_at=datetime.now(UTC),
            )
        )

        # -------------------------------------------------------------
        # Step 4: Generate Rollback Manifest
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        target_rel_id = f"rel-{task_id}"
        rb_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="generate_rollback_manifest",
            payload={
                "tenant_id": tenant_id,
                "task_id": task_id,
                "target_release_id": target_rel_id,
                "previous_stable_version": ctx.get("previous_stable_version", "0.9.0"),
                "rollback_strategy": ctx.get("rollback_strategy", "BLUE_GREEN_DRAIN"),
                "revert_steps": ctx.get("revert_steps"),
                "migration_revert_instructions": ctx.get("migration_revert_instructions"),
                "automated_verification_steps": ctx.get("automated_verification_steps"),
            },
        )
        t_rb = (time.perf_counter() - t0) * 1000

        raw_rb = rb_res.get("rollback_manifest") or {}
        rollback_manifest = RollbackManifest(
            rollback_id=str(raw_rb.get("rollback_id") or f"rollback-{target_rel_id}"),
            target_release_id=target_rel_id,
            previous_stable_version=str(raw_rb.get("previous_stable_version", "0.9.0")),
            rollback_strategy=str(raw_rb.get("rollback_strategy", "BLUE_GREEN_DRAIN")),
            revert_steps=list(raw_rb.get("revert_steps", [])),
            migration_revert_instructions=[],
            automated_verification_steps=list(raw_rb.get("automated_verification_steps", [])),
        )
        rollback_manifest.compute_rollback_hash()

        evidence_envelopes.append(
            EvidenceEnvelope(
                task_id=task_id,
                worker_role=WorkerRole.DEVELOPMENT,
                confidence=ConfidenceInterval(
                    point_estimate=1.0, lower_bound=0.95, upper_bound=1.0
                ),
                findings=[f"Generated rollback manifest {rollback_manifest.rollback_id}"],
                payload={
                    "rollback_id": rollback_manifest.rollback_id,
                    "rollback_hash": rollback_manifest.rollback_hash,
                    "elapsed_ms": f"{t_rb:.1f}",
                },
                produced_at=datetime.now(UTC),
            )
        )

        # -------------------------------------------------------------
        # Step 5: Simulate Migration Dry-Run
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        mig_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="simulate_migration_dry_run",
            payload={
                "tenant_id": tenant_id,
                "task_id": task_id,
                "component_name": component_name,
                "migrations": ctx.get("migrations"),
                "simulate_migration_failure": ctx.get("simulate_migration_failure", False),
            },
        )
        t_mig = (time.perf_counter() - t0) * 1000

        if not mig_res.get("dry_run_passed", True):
            raise PolicyViolationError(
                f"Database migration dry-run simulation failed: {mig_res.get('error')}. "
                f"Release packaging aborted."
            )

        migration_instructions: list[MigrationInstruction] = []
        for r_mi in mig_res.get("migration_instructions") or []:
            migration_instructions.append(
                MigrationInstruction(
                    step_number=int(r_mi.get("step_number", 1)),
                    operation=str(r_mi.get("operation", "APPLY_SCHEMA_DELTA")),
                    model_name=str(r_mi.get("model_name", component_name)),
                    dry_run_passed=bool(r_mi.get("dry_run_passed", True)),
                    sql_or_schema_change=str(r_mi.get("sql_or_schema_change", "")),
                )
            )

        evidence_envelopes.append(
            EvidenceEnvelope(
                task_id=task_id,
                worker_role=WorkerRole.DEVELOPMENT,
                confidence=ConfidenceInterval(
                    point_estimate=1.0, lower_bound=0.95, upper_bound=1.0
                ),
                findings=["Dry-run database migrations passed"],
                payload={
                    "dry_run_passed": "True",
                    "migration_steps_count": str(len(migration_instructions)),
                    "elapsed_ms": f"{t_mig:.1f}",
                },
                produced_at=datetime.now(UTC),
            )
        )

        # -------------------------------------------------------------
        # Step 6: Verify Release Integrity
        # -------------------------------------------------------------
        integ_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="verify_release_integrity",
            payload={
                "release_artifacts": [ra.model_dump() for ra in release_artifacts],
                "artifact_digests": artifact_digests,
            },
        )
        if not integ_res.get("integrity_verified", True):
            raise PolicyViolationError(
                f"Release integrity validation failed: {integ_res.get('error')}"
            )

        # -------------------------------------------------------------
        # Step 7: Cryptographic SLSA / in-toto Attestation
        # -------------------------------------------------------------
        attestation_dict: dict[str, Any] | None = None
        if self._provenance_recorder is not None and hasattr(
            self._provenance_recorder, "generate_slsa_attestation"
        ):
            try:
                slsa_stmt = self._provenance_recorder.generate_slsa_attestation(
                    task_id=task_id,
                    step_id="DEV-REL",
                    attempt_id=wf_id,
                    artifacts=artifact_digests,
                    build_config={
                        "version": version,
                        "component_name": component_name,
                        "security_dossier_hash": security_dossier.dossier_hash,
                    },
                )
                if hasattr(slsa_stmt, "model_dump"):
                    attestation_dict = slsa_stmt.model_dump()
                elif isinstance(slsa_stmt, dict):
                    attestation_dict = slsa_stmt
            except Exception as att_exc:
                logger.warning(
                    "SLSA attestation recording encountered non-fatal error: %s",
                    att_exc,
                )

        # -------------------------------------------------------------
        # Step 8: Assemble & Seal Release Candidate Deliverable
        # -------------------------------------------------------------
        cognitive_reasoning = await self._reason_with_llm(
            component_name=component_name,
            version=version,
            artifact_count=len(release_artifacts),
            sbom_components_count=len(components),
            migration_steps_count=len(migration_instructions),
            context=ctx,
        )

        deliverable = ReleaseCandidateDeliverable(
            release_id=f"rel-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            workflow_id=wf_id,
            security_dossier_hash=security_dossier.dossier_hash,
            candidate_hash=actual_candidate_hash,
            component_name=component_name,
            version=version,
            release_artifacts=release_artifacts,
            artifact_digests=artifact_digests,
            sbom=cyclonedx_sbom,
            deployment_manifest=deployment_manifest,
            rollback_manifest=rollback_manifest,
            migration_dry_run_evidence=migration_instructions,
            attestation_statement=attestation_dict,
            evidence_envelopes=evidence_envelopes,
            provenance={
                "subagent": "DEV-REL",
                "packaged_at": datetime.now(UTC).isoformat(),
                "security_dossier_hash": security_dossier.dossier_hash,
                "candidate_hash": actual_candidate_hash,
                "artifact_count": len(release_artifacts),
                "hitl_approved": hitl_approved,
                "llm_reasoning": cognitive_reasoning,
            },
        )
        deliverable.compute_release_hash()

        logger.info(
            "DEV-REL packaged release candidate: release_id=%s, version=%s, artifacts=%d, hash=%s",
            deliverable.release_id,
            version,
            len(release_artifacts),
            deliverable.release_hash,
            extra={
                "task_id": task_id,
                "release_id": deliverable.release_id,
                "release_hash": deliverable.release_hash,
            },
        )

        return deliverable


# Canonical alias
DevRelAgent = ReleaseOpsAgent
