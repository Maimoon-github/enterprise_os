"""Authoritative Enterprise OS Release Pipeline & Clean-Room Production Certification.
Enforces NIST SSDF (SP 800-218), SLSA Provenance v1.2, and CISA SBOM Guidelines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure project root in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from release.attestation_verifier import AttestationPolicy, AttestationVerifier
from release.dependency_locker import DependencyLocker
from release.installer import CleanRoomInstaller
from release.provenance import SlsaProvenanceGenerator
from release.rollback import ReleaseRollbackManager
from release.sbom_generator import SbomGenerator
from release.signer import ReleaseSigner
from release.smoke_test import run_clean_room_smoke_test


class EnterpriseOsReleasePipeline:
    def __init__(
        self,
        root_dir: str | Path,
        release_version: str = "1.0.0-rc1",
        staging_dir: str | Path | None = None,
        allow_dirty: bool = False,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.release_version = release_version
        self.dist_dir = self.root_dir / "dist"
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir = Path(staging_dir).resolve() if staging_dir else (self.root_dir / "dist" / "staging_target")
        self.allow_dirty = allow_dirty

    def run_cmd(self, cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        target_cwd = cwd or self.root_dir
        res = subprocess.run(cmd, cwd=str(target_cwd), capture_output=True, text=True)
        if check and res.returncode != 0:
            raise RuntimeError(
                f"Command failed (exit {res.returncode}): {' '.join(cmd)}\n"
                f"STDOUT:\n{res.stdout[-1000:]}\nSTDERR:\n{res.stderr[-1000:]}"
            )
        return res

    def validate_clean_checkout(self) -> dict[str, str]:
        """Verify git status is clean and return commit metadata."""
        status_proc = self.run_cmd(["git", "status", "--porcelain"])
        dirty_lines = [l for l in status_proc.stdout.splitlines() if not l.startswith("?? dist")]
        if dirty_lines:
            if self.allow_dirty:
                print(f"[WARNING] Building release with dirty tree (allowed via --allow-dirty):\n" + "\n".join(dirty_lines[:5]))
            else:
                raise RuntimeError(f"Cannot build release from dirty git tree:\n" + "\n".join(dirty_lines))

        commit_sha = self.run_cmd(["git", "rev-parse", "HEAD"]).stdout.strip()
        return {
            "status": "DIRTY_DEV_BUILD" if dirty_lines else "CLEAN",
            "commit_sha": commit_sha,
            "version": self.release_version,
        }

    def lock_dependencies(self) -> dict[str, Any]:
        """Lock Python and Node dependencies deterministically."""
        locker = DependencyLocker(self.root_dir)
        return locker.lock_all()

    def run_quality_gates(self) -> dict[str, Any]:
        """Run complete authoritative quality gate."""
        results: dict[str, Any] = {}

        # 1. Full Backend Tests
        print("--> Running full backend test tree (pytest backend/tests)...")
        t0 = datetime.now(UTC)
        test_proc = self.run_cmd([sys.executable, "-m", "pytest", "backend/tests", "-q"])
        results["backend_pytest"] = {
            "passed": test_proc.returncode == 0,
            "duration_s": (datetime.now(UTC) - t0).total_seconds(),
            "summary": test_proc.stdout.strip().splitlines()[-1] if test_proc.stdout else "Passed",
        }

        # 2. Ruff Linter
        print("--> Running Python linter (ruff check backend)...")
        ruff_proc = self.run_cmd([sys.executable, "-m", "ruff", "check", "backend"])
        results["ruff"] = {"passed": ruff_proc.returncode == 0}

        # 3. Pyright Type Checking
        print("--> Running static typing (pyright)...")
        pyright_proc = self.run_cmd(["npx", "--no-install", "pyright"])
        results["pyright"] = {"passed": pyright_proc.returncode == 0}

        # 4. Frontend Lint
        print("--> Running frontend lint (npm run lint)...")
        fe_lint = self.run_cmd(["npm", "run", "lint"], cwd=self.root_dir / "frontend")
        results["frontend_lint"] = {"passed": fe_lint.returncode == 0}

        # 5. Frontend Production Build
        print("--> Building Next.js production artifact (npm run build)...")
        fe_build = self.run_cmd(["npm", "run", "build"], cwd=self.root_dir / "frontend")
        results["frontend_build"] = {"passed": fe_build.returncode == 0}

        # 6. Playwright Browser E2E
        print("--> Running browser Playwright E2E suite...")
        playwright_proc = self.run_cmd(["npx", "playwright", "test"], cwd=self.root_dir / "frontend")
        results["playwright_e2e"] = {"passed": playwright_proc.returncode == 0}

        # 7. Migration Verification (Empty DB + Upgrade Replay)
        print("--> Validating PostgreSQL migrations from scratch and upgrade replay...")
        mig_code = """
import asyncio, asyncpg
from app.persistence.database import Database
from app.core.settings import DatabaseSettings

async def verify():
    sys_conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/postgres")
    await sys_conn.execute("DROP DATABASE IF EXISTS release_pipeline_mig_test")
    await sys_conn.execute("CREATE DATABASE release_pipeline_mig_test")
    await sys_conn.close()

    db = Database(DatabaseSettings(dsn="postgresql+asyncpg://postgres:postgres@localhost:5432/release_pipeline_mig_test"))
    applied = await db.apply_migrations()
    assert len(applied) == 7, f"Expected 7 migrations, applied {len(applied)}"

    applied_again = await db.apply_migrations()
    assert len(applied_again) == 0, f"Expected 0 migrations on replay, applied {len(applied_again)}"

    test_conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/release_pipeline_mig_test")
    tables = await test_conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    table_names = {r["table_name"] for r in tables}
    assert "schema_migrations" in table_names
    assert "operational_directives" in table_names
    assert "institutional_memory" in table_names
    await test_conn.close()
    await db.dispose()

    sys_conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/postgres")
    await sys_conn.execute("DROP DATABASE release_pipeline_mig_test")
    await sys_conn.close()

asyncio.run(verify())
"""
        mig_proc = self.run_cmd([sys.executable, "-c", mig_code])
        results["migration_verification"] = {"passed": mig_proc.returncode == 0}

        # 8. Systemd Service/Socket Units Validation
        print("--> Validating systemd service and socket units...")
        sysd_proc = self.run_cmd([
            "systemd-analyze",
            "verify",
            "sandbox/systemd/enterprise-os-provisioner.service",
            "sandbox/systemd/enterprise-os-provisioner.socket",
        ])
        results["systemd_units"] = {"passed": sysd_proc.returncode == 0}

        return results

    def build_immutable_release_tarball(self) -> Path:
        """Package immutable release archive containing backend, frontend, systemd, migrations."""
        tar_name = f"enterprise-os-{self.release_version}.tar.gz"
        tar_path = self.dist_dir / tar_name

        print(f"--> Building immutable release archive: {tar_path.name}...")
        with tarfile.open(tar_path, "w:gz") as tar:
            # Add backend
            tar.add(self.root_dir / "backend", arcname="backend", filter=lambda ti: None if "__pycache__" in ti.name or ".pytest_cache" in ti.name else ti)
            # Add frontend production build assets
            tar.add(self.root_dir / "frontend" / "package.json", arcname="frontend/package.json")
            tar.add(self.root_dir / "frontend" / "package-lock.json", arcname="frontend/package-lock.json")
            tar.add(self.root_dir / "frontend" / ".next", arcname="frontend/.next", filter=lambda ti: None if "cache" in ti.name else ti)
            # Add systemd definitions
            tar.add(self.root_dir / "sandbox" / "systemd", arcname="systemd")
            # Add lockfiles
            tar.add(self.dist_dir / "requirements.lock", arcname="requirements.lock")

        return tar_path

    def run_full_pipeline(self) -> dict[str, Any]:
        """Execute complete release pipeline end-to-end."""
        pipeline_started = datetime.now(UTC)

        # 1. Clean checkout check
        checkout_info = self.validate_clean_checkout()

        # 2. Lock dependencies
        print("--> Locking dependencies...")
        locks = self.lock_dependencies()

        # 3. Quality Gate
        print("--> Running Quality Gates...")
        quality_gates = self.run_quality_gates()

        # 4. Package Artifacts
        tar_path = self.build_immutable_release_tarball()

        # 5. Generate CISA SBOM
        print("--> Generating CISA-compliant CycloneDX v1.5 SBOM...")
        sbom_gen = SbomGenerator(self.root_dir, self.release_version)
        sbom_res = sbom_gen.generate()
        sbom_path = self.dist_dir / f"enterprise-os-{self.release_version}.sbom.json"

        # 6. Generate SLSA Provenance
        print("--> Generating SLSA v1.2 Build Provenance...")
        pipeline_finished = datetime.now(UTC)
        prov_gen = SlsaProvenanceGenerator(self.root_dir, self.release_version)
        resolved_deps = [
            {"purl": "pkg:generic/requirements.lock", "digest": {"sha256": locks["python"]["sha256"]}},
            {"purl": "pkg:generic/package-lock.json", "digest": {"sha256": locks["node"]["sha256"]}},
        ]
        prov_res = prov_gen.generate(
            artifact_paths=[tar_path, sbom_path],
            resolved_deps=resolved_deps,
            started_on=pipeline_started,
            finished_on=pipeline_finished,
        )
        prov_path = self.dist_dir / f"enterprise-os-{self.release_version}.provenance.json"

        # 7. Sign Release Manifest with Strict Key Isolation
        print("--> Auditing key isolation and cryptographically signing release manifest (Ed25519)...")
        signer = ReleaseSigner(self.root_dir, self.release_version)
        key_audit = signer.validate_key_isolation()
        sign_res = signer.create_and_sign_manifest(
            artifacts=[tar_path, sbom_path, prov_path],
            git_commit=checkout_info["commit_sha"],
        )
        manifest_path = self.dist_dir / f"enterprise-os-{self.release_version}.manifest.json"
        pub_key_path = self.dist_dir / "release_authority_pub.pem"

        # 8. Clean-Room Staging Installation with Builder Attestation Enforcement
        print(f"--> Verifying builder attestation and installing into staging target ({self.staging_dir})...")
        tar_sha256 = hashlib.sha256(tar_path.read_bytes()).hexdigest()
        policy = AttestationPolicy(
            expected_repository=os.environ.get("GITHUB_REPOSITORY", "Maimoon-github/enterprise_os"),
            expected_workflow=".github/workflows/enterprise_os_release.yml",
            expected_commit=checkout_info["commit_sha"],
            expected_tag=f"v{self.release_version.lstrip('v')}",
            expected_artifact_sha256=tar_sha256,
            require_sigstore_attestation=False,
            require_ed25519_manifest=True,
        )
        installer = CleanRoomInstaller(
            release_tar_path=tar_path,
            manifest_path=manifest_path,
            pub_key_path=pub_key_path,
            provenance_path=prov_path,
            attestation_policy=policy,
            target_install_dir=self.staging_dir,
        )
        install_receipt = installer.install()

        # 9. Clean-Room Smoke Test
        print("--> Running complete end-to-end smoke test against installed artifact...")
        smoke_res = run_clean_room_smoke_test(self.staging_dir)
        if smoke_res["status"] != "PASSED":
            raise RuntimeError(f"Installed smoke test failed: {smoke_res}")

        # 10. Prove Rollback
        print("--> Proving atomic rollback to prior release baseline...")
        rollback_mgr = ReleaseRollbackManager(self.staging_dir, previous_release_version="1.0.0-rc0")
        rollback_receipt = rollback_mgr.execute_rollback()

        # Compile Release Certification Report
        report = {
            "pipeline_status": "CERTIFIED",
            "release_version": self.release_version,
            "git_commit": checkout_info["commit_sha"],
            "started_at": pipeline_started.isoformat(),
            "finished_at": pipeline_finished.isoformat(),
            "artifacts": {
                "tarball": str(tar_path.relative_to(self.root_dir)),
                "sbom": str(sbom_path.relative_to(self.root_dir)),
                "provenance": str(prov_path.relative_to(self.root_dir)),
                "manifest": sign_res["manifest_path"],
                "signature": sign_res["signature_path"],
            },
            "quality_gates": quality_gates,
            "key_isolation": key_audit,
            "installation": install_receipt,
            "smoke_test": smoke_res,
            "rollback_proof": rollback_receipt,
        }

        report_path = self.dist_dir / f"enterprise-os-{self.release_version}.certification_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"--> Certification report saved to {report_path}")
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise OS Release Pipeline")
    parser.add_argument("--version", default="1.0.0-rc1", help="Release version")
    parser.add_argument("--staging-dir", default=None, help="Target staging directory")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow building from dirty git tree (development only)")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    pipeline = EnterpriseOsReleasePipeline(
        root_dir,
        release_version=args.version,
        staging_dir=args.staging_dir,
        allow_dirty=args.allow_dirty,
    )
    report = pipeline.run_full_pipeline()
    print("\n" + "=" * 80)
    print(f"ENTERPRISE OS {args.version} PRODUCTION RELEASE PIPELINE: CERTIFIED")
    print("=" * 80)


if __name__ == "__main__":
    main()
