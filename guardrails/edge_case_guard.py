# pyright: reportMissingImports=false
"""Edge Case Resilience and Historical Defect Guard (TSK-09).
Mitigates undo_edit file retention leaks, browser_evaluate JavaScript syntax errors,
execution timeouts, and token boundary blowups.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, Field


class EdgeCaseGuardResult(BaseModel):
    """Result from edge case sanitization or interception."""

    success: bool
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    sanitized_output: Optional[str] = None


class EdgeCaseGuard:
    """Provides defensive resilience against documented sandbox runtime edge cases."""

    @staticmethod
    def handle_undo_edit_cleanup(
        file_path: str,
        created_in_session: bool = True,
        sandbox_client: Optional[Any] = None,
    ) -> EdgeCaseGuardResult:
        """Handle undo_edit defect: when undoing creation of a new file, ensure file is deleted."""
        if not created_in_session:
            return EdgeCaseGuardResult(
                success=True,
                action="REVERT_CONTENT",
                details={"file_path": file_path, "deleted": False},
            )

        deleted = False
        error_msg = None

        # 1. Attempt removal via sandbox client if provided
        if sandbox_client is not None and hasattr(sandbox_client, "file"):
            try:
                if hasattr(sandbox_client.file, "delete_file"):
                    res = sandbox_client.file.delete_file(file=file_path)
                    deleted = getattr(res, "success", True)
                elif hasattr(sandbox_client.file, "write_file"):
                    # Fallback command execution to remove
                    cmd_res = sandbox_client.command.execute_command(command=f"rm -f '{file_path}'")
                    deleted = getattr(cmd_res, "success", True)
            except Exception as e:
                error_msg = str(e)

        # 2. Local fallback if file exists locally
        if not deleted and os.path.exists(file_path):
            try:
                os.remove(file_path)
                deleted = True
            except Exception as e:
                error_msg = str(e)

        return EdgeCaseGuardResult(
            success=True,
            action="FILE_UNLINKED",
            details={
                "file_path": file_path,
                "deleted": deleted or not os.path.exists(file_path),
                "error": error_msg,
            },
        )

    @staticmethod
    def normalize_browser_evaluate_script(script: str) -> str:
        """Normalize raw JavaScript statements into self-executing expressions for browser_evaluate.
        Historical defect: LLMs often submit raw multi-line statements without return values or
        proper arrow wrappers, causing syntax errors in CDP.
        """
        trimmed = script.strip()
        if not trimmed:
            return "(() => { return null; })()"

        # Already an IIFE or arrow function
        if (trimmed.startswith("(() =>") or trimmed.startswith("(function")) and trimmed.endswith(")()"):
            return trimmed

        # If it's a simple expression without semicolons or keywords, return it directly inside IIFE
        has_statements = ";" in trimmed or any(kw in trimmed for kw in ["let ", "const ", "var ", "if ", "for "])
        if has_statements:
            # Wrap in try-catch IIFE with clean execution
            if "return " not in trimmed:
                # Add return to last expression if feasible
                lines = trimmed.strip().split("\n")
                last_line = lines[-1].strip()
                if not last_line.startswith("return "):
                    if last_line.endswith(";"):
                        last_line = last_line[:-1]
                    lines[-1] = f"return {last_line};"
                body = "\n".join(lines)
            else:
                body = trimmed
            return f"(() => {{\n    try {{\n        {body}\n    }} catch (e) {{\n        return String(e);\n    }}\n}})()"
        else:
            return f"(() => {{\n    try {{\n        return {trimmed};\n    }} catch (e) {{\n        return null;\n    }}\n}})()"

    @staticmethod
    def sanitize_output_tokens(output: str, max_chars: int = 12000) -> str:
        """Enforces token boundaries to prevent context blowup in agent reasoning loops."""
        if len(output) <= max_chars:
            return output
        truncated_msg = f"\n\n[... Truncated {len(output) - max_chars} characters to preserve context limit ...]"
        return output[:max_chars] + truncated_msg

    @staticmethod
    async def execute_with_timeout(
        coro: Any,
        timeout_seconds: float = 15.0,
        fallback_value: Any = None,
    ) -> Any:
        """Asynchronously executes a coroutine bounded by a strict timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return fallback_value
