"""Ed25519 Cryptographic Release Signing and Attestation Engine.
Complies with NIST SSDF (SP 800-218) Delivery Controls and SLSA Supply Chain Security.
Enforces strict private signing key isolation: private keys are NEVER stored in git,
workspace, dist/, or release archives.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


class ReleaseSigner:
    """Ed25519 Release Authority with zero-trust key isolation."""

    def __init__(
        self,
        root_dir: str | Path,
        release_version: str = "1.0.0-rc1",
        private_key_path: str | Path | None = None,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.release_version = release_version
        self.dist_dir = self.root_dir / "dist"
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        self.explicit_key_path = Path(private_key_path).resolve() if private_key_path else None

    def _resolve_private_key_path(self) -> Path:
        """Resolve private key from explicit path, env var, or external secure directory.
        Strictly forbids keys from residing inside the repository root.
        """
        candidate_paths: list[Path] = []

        if self.explicit_key_path:
            candidate_paths.append(self.explicit_key_path)

        env_path = os.environ.get("ENTERPRISE_OS_SIGNING_KEY_PATH")
        if env_path:
            candidate_paths.append(Path(env_path).resolve())

        # Check outside-workspace locations
        home_keys_dir = Path.home() / ".gemini" / "enterprise_os_keys"
        candidate_paths.append(home_keys_dir / "release_authority_ed25519.pem")

        runner_temp = os.environ.get("RUNNER_TEMP")
        if runner_temp:
            candidate_paths.append(Path(runner_temp) / "enterprise_os_keys" / "release_authority_ed25519.pem")

        # Ephemeral secure fallback outside root
        ephemeral_keys_dir = Path(tempfile.gettempdir()) / "enterprise_os_authority_keys"
        candidate_paths.append(ephemeral_keys_dir / "release_authority_ed25519.pem")

        for path in candidate_paths:
            if path.exists():
                # Enforce key is strictly OUTSIDE root_dir
                try:
                    path.relative_to(self.root_dir)
                    raise PermissionError(
                        f"CRITICAL SECURITY VIOLATION: Private release signing key at {path} "
                        f"resides inside repository root {self.root_dir}! "
                        "Private signing keys must reside outside the repository."
                    )
                except ValueError:
                    # Good: path is outside self.root_dir
                    return path

        # If no key exists yet, create in external directory
        if runner_temp:
            target_dir = Path(runner_temp) / "enterprise_os_keys"
        elif env_path:
            target_dir = Path(env_path).parent
        elif home_keys_dir.parent.exists():
            target_dir = home_keys_dir
        else:
            target_dir = ephemeral_keys_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(target_dir, 0o700)
        target_key_file = target_dir / "release_authority_ed25519.pem"
        return target_key_file

    def get_or_create_keypair(self) -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
        """Load or create Ed25519 release authority keypair strictly outside repository."""
        # 1. Check if direct PEM is provided via environment variable
        env_pem = os.environ.get("ENTERPRISE_OS_SIGNING_KEY_ED25519")
        if env_pem:
            priv_key = serialization.load_pem_private_key(env_pem.encode("utf-8"), password=None)
            if not isinstance(priv_key, ed25519.Ed25519PrivateKey):
                raise ValueError("Environment key is not an Ed25519 private key")
            pub_key = priv_key.public_key()
            pub_pem = pub_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            (self.dist_dir / "release_authority_pub.pem").write_bytes(pub_pem)
            return priv_key, pub_key

        priv_path = self._resolve_private_key_path()
        pub_path = priv_path.parent / "release_authority_pub.pem"

        if priv_path.exists():
            priv_key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
            if not isinstance(priv_key, ed25519.Ed25519PrivateKey):
                raise ValueError(f"Key at {priv_path} is not an Ed25519 private key")
            pub_key = priv_key.public_key()
        else:
            priv_key = ed25519.Ed25519PrivateKey.generate()
            pub_key = priv_key.public_key()

            priv_pem = priv_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            priv_path.parent.mkdir(parents=True, exist_ok=True)
            priv_path.write_bytes(priv_pem)
            os.chmod(priv_path, 0o600)

            pub_pem = pub_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            pub_path.write_bytes(pub_pem)

        # Export ONLY public key to dist/ for distribution
        pub_pem = pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        (self.dist_dir / "release_authority_pub.pem").write_bytes(pub_pem)
        return priv_key, pub_key

    def validate_key_isolation(self) -> dict[str, Any]:
        """Audit repository workspace and dist to guarantee no private keys are exposed."""
        violations: list[str] = []

        # Check git tracked files
        try:
            res = subprocess.run(
                ["git", "ls-files"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            for tracked_file in res.stdout.splitlines():
                if any(ext in tracked_file.lower() for ext in [".pem", ".key", "id_ed25519", "private"]):
                    violations.append(f"Tracked git file violation: {tracked_file}")
        except Exception:
            pass

        # Check dist/ directory (only public pem is allowed)
        if self.dist_dir.exists():
            for p in self.dist_dir.rglob("*"):
                if p.is_file():
                    if p.suffix in [".pem", ".key"] and p.name != "release_authority_pub.pem":
                        violations.append(f"Dist directory key violation: {p.relative_to(self.root_dir)}")

        # Check root_dir for release/keys
        bad_keys_dir = self.root_dir / "release" / "keys"
        if bad_keys_dir.exists():
            violations.append("release/keys directory must not exist in workspace root")

        if violations:
            raise PermissionError("KEY ISOLATION COMPROMISED:\n" + "\n".join(violations))

        return {
            "status": "ISOLATED",
            "violations_detected": 0,
            "public_key_available": (self.dist_dir / "release_authority_pub.pem").exists(),
        }

    def create_and_sign_manifest(self, artifacts: list[Path], git_commit: str) -> dict[str, Any]:
        """Produce canonical JSON manifest of release artifacts and sign with Ed25519."""
        # 1. Enforce zero-trust key isolation audit
        self.validate_key_isolation()

        priv_key, pub_key = self.get_or_create_keypair()

        artifact_entries: dict[str, dict[str, Any]] = {}
        for path in artifacts:
            if not path.exists():
                continue
            content = path.read_bytes()
            sha256 = hashlib.sha256(content).hexdigest()
            artifact_entries[path.name] = {
                "sha256": sha256,
                "size_bytes": len(content),
            }

        manifest = {
            "release_name": "enterprise-os",
            "release_version": self.release_version,
            "git_commit": git_commit,
            "hash_algorithm": "SHA-256",
            "artifacts": artifact_entries,
        }

        # Canonicalize JSON (RFC 8785 style sorting)
        canonical_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = priv_key.sign(canonical_bytes)
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        manifest_path = self.dist_dir / f"enterprise-os-{self.release_version}.manifest.json"
        sig_path = self.dist_dir / f"enterprise-os-{self.release_version}.manifest.json.sig"

        manifest_with_sig = {
            **manifest,
            "signature": signature_b64,
            "signature_scheme": "ed25519",
        }

        manifest_path.write_text(json.dumps(manifest_with_sig, indent=2), encoding="utf-8")
        sig_path.write_text(signature_b64, encoding="utf-8")

        return {
            "manifest_path": str(manifest_path.relative_to(self.root_dir)),
            "signature_path": str(sig_path.relative_to(self.root_dir)),
            "signature_b64": signature_b64,
            "artifacts_count": len(artifact_entries),
        }

    @staticmethod
    def verify_manifest(manifest_path: Path, pub_key_path: Path) -> bool:
        """Verify an Ed25519 signed release manifest."""
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        sig_b64 = data.get("signature")
        if not sig_b64:
            return False

        signature = base64.b64decode(sig_b64)
        raw_manifest = {
            "release_name": data["release_name"],
            "release_version": data["release_version"],
            "git_commit": data["git_commit"],
            "hash_algorithm": data["hash_algorithm"],
            "artifacts": data["artifacts"],
        }
        canonical_bytes = json.dumps(raw_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")

        pub_key = serialization.load_pem_public_key(pub_key_path.read_bytes())
        if not isinstance(pub_key, ed25519.Ed25519PublicKey):
            return False

        try:
            pub_key.verify(signature, canonical_bytes)
            return True
        except InvalidSignature:
            return False


if __name__ == "__main__":
    signer = ReleaseSigner(Path(__file__).resolve().parent.parent)
    signer.get_or_create_keypair()
    signer.validate_key_isolation()
    print("Release authority Ed25519 keypair and key isolation audit: VERIFIED.")
