"""Ed25519 Cryptographic Release Signing and Attestation Engine.
Complies with NIST SSDF (Secure Software Development Framework) Delivery Controls.
Ensures non-repudiation, tamper-evidence, and authoritative provenance.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


class ReleaseSigner:
    def __init__(self, root_dir: str | Path, release_version: str = "1.0.0-rc1") -> None:
        self.root_dir = Path(root_dir).resolve()
        self.release_version = release_version
        self.dist_dir = self.root_dir / "dist"
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir = self.root_dir / "release" / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_keypair(self) -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
        priv_path = self.keys_dir / "release_authority_ed25519.pem"
        pub_path = self.keys_dir / "release_authority_pub.pem"

        if priv_path.exists() and pub_path.exists():
            priv_key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
            pub_key = serialization.load_pem_public_key(pub_path.read_bytes())
            if not isinstance(priv_key, ed25519.Ed25519PrivateKey) or not isinstance(pub_key, ed25519.Ed25519PublicKey):
                raise ValueError("Keys are not Ed25519 keypair")
            return priv_key, pub_key

        priv_key = ed25519.Ed25519PrivateKey.generate()
        pub_key = priv_key.public_key()

        priv_pem = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        priv_path.write_bytes(priv_pem)
        pub_path.write_bytes(pub_pem)
        # Copy public key to dist for release consumer distribution
        (self.dist_dir / "release_authority_pub.pem").write_bytes(pub_pem)
        return priv_key, pub_key

    def create_and_sign_manifest(self, artifacts: list[Path], git_commit: str) -> dict[str, Any]:
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
    print("Release authority Ed25519 keypair ready.")
