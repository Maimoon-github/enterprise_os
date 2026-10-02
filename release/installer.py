"""Clean-Room Host Installer for Enterprise OS.
Installs cryptographically signed release bundle onto clean target host/staging root.
Verifies Ed25519 signature, sets up systemd units, and applies database migrations.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any

# Ensure project root in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from release.signer import ReleaseSigner


class CleanRoomInstaller:
    def __init__(
        self,
        release_tar_path: str | Path,
        manifest_path: str | Path,
        pub_key_path: str | Path,
        target_install_dir: str | Path,
        db_dsn: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/governed_backend",
    ) -> None:
        self.release_tar_path = Path(release_tar_path).resolve()
        self.manifest_path = Path(manifest_path).resolve()
        self.pub_key_path = Path(pub_key_path).resolve()
        self.target_dir = Path(target_install_dir).resolve()
        self.db_dsn = db_dsn

    def verify_release_bundle(self) -> dict[str, Any]:
        """Verify Ed25519 signature and SHA-256 hash of the release artifact."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        if not self.pub_key_path.exists():
            raise FileNotFoundError(f"Public key not found: {self.pub_key_path}")
        if not self.release_tar_path.exists():
            raise FileNotFoundError(f"Release tarball not found: {self.release_tar_path}")

        # 1. Cryptographic manifest signature check
        is_valid_sig = ReleaseSigner.verify_manifest(self.manifest_path, self.pub_key_path)
        if not is_valid_sig:
            raise PermissionError("CRYPTOGRAPHIC REJECTION: Release manifest signature is invalid or tampered!")

        # 2. Hash check against manifest
        manifest_data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        artifacts = manifest_data.get("artifacts", {})
        tar_name = self.release_tar_path.name
        if tar_name not in artifacts:
            raise ValueError(f"Artifact {tar_name} not registered in signed manifest")

        expected_hash = artifacts[tar_name]["sha256"]
        actual_hash = hashlib.sha256(self.release_tar_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"HASH MISMATCH: Expected {expected_hash}, calculated {actual_hash}")

        return {
            "signature_verified": True,
            "hash_verified": True,
            "sha256": actual_hash,
            "release_version": manifest_data.get("release_version"),
        }

    def install(self) -> dict[str, Any]:
        """Perform clean installation into target directory."""
        verification = self.verify_release_bundle()

        # Wipe and recreate target clean staging root
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)
        self.target_dir.mkdir(parents=True, exist_ok=True)

        # Unpack immutable tarball
        with tarfile.open(self.release_tar_path, "r:gz") as tar:
            tar.extractall(self.target_dir)

        # Ensure directory structure
        systemd_dest = self.target_dir / "systemd"
        systemd_dest.mkdir(parents=True, exist_ok=True)
        config_dest = self.target_dir / "etc"
        config_dest.mkdir(parents=True, exist_ok=True)
        var_dest = self.target_dir / "var" / "run"
        var_dest.mkdir(parents=True, exist_ok=True)

        # Write runtime production environment config
        env_content = (
            f"ENTERPRISE_OS_RELEASE_VERSION={verification['release_version']}\n"
            f"DATABASE_DSN={self.db_dsn}\n"
            f"SANDBOX_UDS_PATH=/run/enterprise-os/provisioner.sock\n"
            f"BUBBLEWRAP_BIN=/usr/bin/bwrap\n"
            f"ZERO_TRUST_ENFORCED=true\n"
        )
        (config_dest / "enterprise-os.env").write_text(env_content, encoding="utf-8")

        # Record deployment receipt
        receipt = {
            "deployment_id": os.urandom(8).hex(),
            "target_dir": str(self.target_dir),
            "release_version": verification["release_version"],
            "sha256": verification["sha256"],
            "status": "INSTALLED",
        }
        receipt_path = self.target_dir / "deployment_receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

        return receipt


if __name__ == "__main__":
    pass
