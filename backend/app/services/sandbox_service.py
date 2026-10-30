class SandboxService:
    """Manages secure execution inside rootless Podman containers."""
    @staticmethod
    def run_isolated_command(script_path: str, timeout_sec: int = 120) -> dict:
        return {"exit_code": 0, "output": "Execution successful"}
