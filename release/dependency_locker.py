"""Dependency Locking Module for Enterprise OS.
Produces deterministic, hashed dependency locks for Python and Node.js environments.
NIST SSDF PW.4 / SLSA v1.2 resolvedDependencies compliance.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class DependencyLocker:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.backend_dir = self.root_dir / "backend"
        self.frontend_dir = self.root_dir / "frontend"
        self.dist_dir = self.root_dir / "dist"
        self.dist_dir.mkdir(parents=True, exist_ok=True)

    def lock_python_dependencies(self) -> dict[str, Any]:
        """Generate deterministic, sorted requirements.lock for backend runtime."""
        res = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
        installed_packages = json.loads(res.stdout)
        # Sort alphabetically for reproducible lock output
        installed_packages.sort(key=lambda p: p["name"].lower())

        lock_path = self.dist_dir / "requirements.lock"
        lines = [
            "# Auto-generated deterministic lock by Enterprise OS Release Pipeline",
            "# Adheres to NIST SSDF PW.4 / SLSA v1.2",
            "",
        ]
        for pkg in installed_packages:
            name = pkg["name"]
            version = pkg["version"]
            lines.append(f"{name}=={version}")

        lock_content = "\n".join(lines) + "\n"
        lock_path.write_text(lock_content, encoding="utf-8")

        sha256 = hashlib.sha256(lock_content.encode("utf-8")).hexdigest()
        return {
            "lock_file": str(lock_path.relative_to(self.root_dir)),
            "package_count": len(installed_packages),
            "sha256": sha256,
            "packages": installed_packages,
        }

    def lock_node_dependencies(self) -> dict[str, Any]:
        """Verify and record hash of frontend/package-lock.json."""
        lock_file = self.frontend_dir / "package-lock.json"
        if not lock_file.exists():
            raise FileNotFoundError(f"Frontend package-lock.json not found at {lock_file}")

        content = lock_file.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        data = json.loads(content.decode("utf-8"))

        summary_path = self.dist_dir / "node_lock_summary.json"
        summary = {
            "lock_file": "frontend/package-lock.json",
            "lockfile_version": data.get("lockfileVersion", 3),
            "packages_count": len(data.get("packages", {})),
            "sha256": sha256,
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    def lock_all(self) -> dict[str, Any]:
        python_lock = self.lock_python_dependencies()
        node_lock = self.lock_node_dependencies()
        return {
            "python": python_lock,
            "node": node_lock,
            "status": "locked",
        }


if __name__ == "__main__":
    locker = DependencyLocker(Path(__file__).resolve().parent.parent)
    result = locker.lock_all()
    print(json.dumps(result, indent=2))
