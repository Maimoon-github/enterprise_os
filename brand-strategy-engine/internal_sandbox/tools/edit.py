"""Sandboxed file editing tool for internal sandbox operations."""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from .base import BaseTool, CLIResult, ToolError, ToolResult

Command = Literal["view", "create", "str_replace", "insert"]


class EditTool(BaseTool):
    """File buffer modification tool."""

    name: str = "edit"

    def to_params(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "View, create, and modify text files inside the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["view", "create", "str_replace", "insert"],
                        "description": "Command to perform",
                    },
                    "path": {"type": "string", "description": "Absolute path to file"},
                    "file_text": {"type": "string", "description": "Text content when creating"},
                    "old_str": {"type": "string", "description": "Exact text to replace"},
                    "new_str": {"type": "string", "description": "Replacement string"},
                    "insert_line": {"type": "integer", "description": "Line number to insert at"},
                    "insert_text": {"type": "string", "description": "Text to insert"},
                },
                "required": ["command", "path"],
            },
        }

    async def __call__(
        self,
        *,
        command: Command,
        path: str,
        file_text: Optional[str] = None,
        view_range: Optional[List[int]] = None,
        old_str: Optional[str] = None,
        new_str: Optional[str] = None,
        insert_line: Optional[int] = None,
        insert_text: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        file_path = Path(path)

        if command == "view":
            if not file_path.exists():
                raise ToolError(f"Path does not exist: {path}")
            if file_path.is_dir():
                entries = [f"{p.name}/" if p.is_dir() else p.name for p in file_path.iterdir()]
                return CLIResult(output="\n".join(sorted(entries)))
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            if view_range and len(view_range) == 2:
                start, end = view_range
                lines = lines[max(0, start - 1) : end]
            return CLIResult(output="\n".join(lines))

        elif command == "create":
            if file_path.exists():
                raise ToolError(f"File already exists: {path}")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file_text or "", encoding="utf-8")
            return CLIResult(output=f"Successfully created file: {path}")

        elif command == "str_replace":
            if not file_path.exists():
                raise ToolError(f"File not found: {path}")
            if not old_str:
                raise ToolError("Missing old_str for str_replace")
            content = file_path.read_text(encoding="utf-8")
            count = content.count(old_str)
            if count == 0:
                raise ToolError(f"Target string not found in {path}")
            if count > 1:
                raise ToolError(f"Target string occurs {count} times in {path}; specify unique context")
            replaced = content.replace(old_str, new_str or "")
            file_path.write_text(replaced, encoding="utf-8")
            return CLIResult(output=f"Successfully replaced string in {path}")

        elif command == "insert":
            if not file_path.exists():
                raise ToolError(f"File not found: {path}")
            if insert_line is None or insert_text is None:
                raise ToolError("insert requires insert_line and insert_text")
            lines = file_path.read_text(encoding="utf-8").splitlines()
            idx = max(0, min(insert_line, len(lines)))
            lines.insert(idx, insert_text)
            file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return CLIResult(output=f"Successfully inserted line into {path}")

        raise ToolError(f"Unsupported edit command: {command}")
