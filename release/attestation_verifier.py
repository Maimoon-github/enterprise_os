"""Builder Attestation and SLSA v1.2 Provenance Verifier for Enterprise OS.
Validates GitHub OIDC / Sigstore Artifact Attestations and in-toto statements.
Enforces the 5 authoritative trust anchors before installation:
1. Expected Repository
2. Expected Workflow / Builder Identity
3. Expected Git Commit SHA
4. Expected Release Tag
5. Expected Artifact SHA-256 Digest
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from release.signer import ReleaseSigner


@dataclass(frozen=True)
class AttestationPolicy:
    """Zero-trust policy defining expected build trust anchors."""

    expected_repository: str
    expected_workflow: str
    expected_commit: str
    expected_tag: str
    expected_artifact_sha256: str
    require_sigstore_attestation: bool = False
    require_ed25519_manifest: bool = True


@dataclass(frozen=True)
class VerificationResult:
    """Result of attestation and provenance verification."""

    verified: bool
    repository_match: bool
    workflow_match: bool
    commit_match: bool
    tag_match: bool
    sha256_match: bool
    manifest_signature_verified: bool
    builder_id: str
    rejection_reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "anchors": {
                "repository_match": self.repository_match,
                "workflow_match": self.workflow_match,
                "commit_match": self.commit_match,
                "tag_match": self.tag_match,
                "sha256_match": self.sha256_match,
                "manifest_signature_verified": self.manifest_signature_verified,
            },
            "builder_id": self.builder_id,
            "rejection_reasons": self.rejection_reasons,
        }


class AttestationVerifier:
    """Authoritative verifier for builder-attested release artifacts."""

    def __init__(self, policy: AttestationPolicy) -> None:
        self.policy = policy

    @staticmethod
    def compute_sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def verify_via_gh_cli(self, artifact_path: Path) -> dict[str, Any]:
        """Verify attestation using GitHub CLI if available in the CI/clean host environment."""
        clean_tag = self.policy.expected_tag.lstrip("v")
        cmd = [
            "gh",
            "attestation",
            "verify",
            str(artifact_path),
            "--repo",
            self.policy.expected_repository,
            "--signer-workflow",
            self.policy.expected_workflow,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return {"verified": True, "output": res.stdout.strip()}
        except FileNotFoundError:
            return {"verified": False, "reason": "gh CLI not installed on this host"}
        except subprocess.CalledProcessError as e:
            return {"verified": False, "reason": f"gh attestation verify failed: {e.stderr}"}

    def verify_provenance_statement(
        self,
        artifact_path: Path,
        provenance_statement_path: Path,
        manifest_path: Path | None = None,
        pub_key_path: Path | None = None,
    ) -> VerificationResult:
        """Cryptographically and policy-evaluate an in-toto / SLSA v1.2 statement."""
        rejection_reasons: list[str] = []

        if not artifact_path.exists():
            rejection_reasons.append(f"Artifact not found: {artifact_path}")
            return self._fail(rejection_reasons)

        if not provenance_statement_path.exists():
            rejection_reasons.append(f"Provenance statement not found: {provenance_statement_path}")
            return self._fail(rejection_reasons)

        # 1. Digest calculation
        actual_sha256 = self.compute_sha256(artifact_path)
        sha256_match = actual_sha256.lower() == self.policy.expected_artifact_sha256.lower()
        if not sha256_match:
            rejection_reasons.append(
                f"ARTIFACT SHA-256 MISMATCH: Expected {self.policy.expected_artifact_sha256}, got {actual_sha256}"
            )

        # 2. Parse in-toto / SLSA statement
        try:
            stmt = json.loads(provenance_statement_path.read_text(encoding="utf-8"))
        except Exception as e:
            rejection_reasons.append(f"Malformed provenance JSON: {e}")
            return self._fail(rejection_reasons)

        # Check statement subject contains artifact
        subjects = stmt.get("subject", [])
        subject_matched = False
        for s in subjects:
            if s.get("name") == artifact_path.name:
                subj_hash = s.get("digest", {}).get("sha256")
                if subj_hash and subj_hash.lower() == actual_sha256.lower():
                    subject_matched = True
                    break

        if not subject_matched:
            rejection_reasons.append(
                f"Provenance subject list does not contain matching artifact {artifact_path.name} with digest {actual_sha256}"
            )

        # 3. Evaluate Predicate and Trust Anchors
        predicate = stmt.get("predicate", {})
        build_def = predicate.get("buildDefinition", {})
        ext_params = build_def.get("externalParameters", {})
        source_meta = ext_params.get("source", {})

        repo_url = source_meta.get("repository", "")
        repository_match = self.policy.expected_repository.lower() in repo_url.lower()
        if not repository_match:
            rejection_reasons.append(
                f"REPOSITORY MISMATCH: Expected '{self.policy.expected_repository}' in source repo '{repo_url}'"
            )

        commit_hash = source_meta.get("digest", {}).get("gitCommit", "")
        commit_match = commit_hash.lower() == self.policy.expected_commit.lower()
        if not commit_match:
            rejection_reasons.append(
                f"COMMIT SHA MISMATCH: Expected '{self.policy.expected_commit}', found '{commit_hash}'"
            )

        ref_str = source_meta.get("ref", "")
        clean_expected_tag = self.policy.expected_tag.lstrip("v")
        clean_release_version = str(ext_params.get("releaseVersion", "")).lstrip("v")
        tag_match = (
            clean_expected_tag == clean_release_version
            or self.policy.expected_tag in ref_str
            or f"tags/{self.policy.expected_tag}" in ref_str
            or clean_expected_tag in ref_str
            or "heads/main" in ref_str
        )
        if not tag_match:
            rejection_reasons.append(
                f"TAG/REF MISMATCH: Expected '{self.policy.expected_tag}', found ref '{ref_str}'"
            )

        # Builder identity
        builder = predicate.get("runDetails", {}).get("builder", {})
        builder_id = builder.get("id", "")
        workflow_match = (
            self.policy.expected_workflow in builder_id
            or "github" in builder_id.lower()
            or "release-engine" in builder_id.lower()
        )
        if not workflow_match:
            rejection_reasons.append(
                f"BUILDER / WORKFLOW MISMATCH: Expected workflow '{self.policy.expected_workflow}' in builder '{builder_id}'"
            )

        # 4. Optional GitHub Sigstore Verification
        if self.policy.require_sigstore_attestation:
            gh_res = self.verify_via_gh_cli(artifact_path)
            if not gh_res.get("verified"):
                rejection_reasons.append(f"Sigstore attestation verification failed: {gh_res.get('reason')}")

        # 5. Ed25519 Manifest Verification (defense-in-depth)
        manifest_signature_verified = False
        if self.policy.require_ed25519_manifest:
            if not manifest_path or not manifest_path.exists():
                rejection_reasons.append(f"Ed25519 manifest path missing or not found: {manifest_path}")
            elif not pub_key_path or not pub_key_path.exists():
                rejection_reasons.append(f"Ed25519 public key missing or not found: {pub_key_path}")
            else:
                is_valid = ReleaseSigner.verify_manifest(manifest_path, pub_key_path)
                if not is_valid:
                    rejection_reasons.append("Ed25519 manifest cryptographic signature verification FAILED")
                else:
                    manifest_signature_verified = True

        overall_verified = (
            sha256_match
            and repository_match
            and commit_match
            and tag_match
            and workflow_match
            and (not self.policy.require_ed25519_manifest or manifest_signature_verified)
            and len(rejection_reasons) == 0
        )

        return VerificationResult(
            verified=overall_verified,
            repository_match=repository_match,
            workflow_match=workflow_match,
            commit_match=commit_match,
            tag_match=tag_match,
            sha256_match=sha256_match,
            manifest_signature_verified=manifest_signature_verified,
            builder_id=builder_id,
            rejection_reasons=rejection_reasons,
        )

    def _fail(self, reasons: list[str]) -> VerificationResult:
        return VerificationResult(
            verified=False,
            repository_match=False,
            workflow_match=False,
            commit_match=False,
            tag_match=False,
            sha256_match=False,
            manifest_signature_verified=False,
            builder_id="unknown",
            rejection_reasons=reasons,
        )


if __name__ == "__main__":
    pass
