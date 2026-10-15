"""Sandboxed file editing tool for internal sandbox operations."""

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, get_args

from .base import BaseAnthropicTool, BaseTool, CLIResult, ToolError, ToolResult
from .run import maybe_truncate, run

Command = Literal[
    "view",
    "create",
    "str_replace",
    "insert",
]
SNIPPET_LINES: int = 4


class EditTool(BaseTool):
    """
    A filesystem editor tool that allows the agent to view, create, and edit files inside the sandbox.
    """

    api_type: Literal["text_editor_20250728"] = "text_editor_20250728"
    name: str = "edit"

    _file_history: dict[Path, list[str]]

    def __init__(self):
        self._file_history = defaultdict(list)
        super().__init__()

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
                    "view_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Optional [start_line, end_line] range",
                    },
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
        _path = Path(path)
        self.validate_path(command, _path)
        if command == "view":
            return await self.view(_path, view_range)
        elif command == "create":
            if file_text is None:
                raise ToolError("Parameter `file_text` is required for command: create")
            self.write_file(_path, file_text)
            self._file_history[_path].append(file_text)
            return CLIResult(output=f"File created successfully at: {_path}")
        elif command == "str_replace":
            if old_str is None:
                raise ToolError("Parameter `old_str` is required for command: str_replace")
            return self.str_replace(_path, old_str, new_str)
        elif command == "insert":
            target_text = insert_text if insert_text is not None else new_str
            if insert_line is None:
                raise ToolError("Parameter `insert_line` is required for command: insert")
            if target_text is None:
                raise ToolError("Parameter `insert_text` is required for command: insert")
            return self.insert(_path, insert_line, target_text)
        raise ToolError(
            f"Unrecognized command {command}. The allowed commands for the {self.name} tool are: {', '.join(get_args(Command))}"
        )

    def validate_path(self, command: str, path: Path):
        """Checks path and command validity."""
        if not path.is_absolute():
            suggested_path = Path("/") / path
            raise ToolError(
                f"The path {path} is not an absolute path, it should start with `/`. Maybe you meant {suggested_path}?"
            )
        if not path.exists() and command != "create":
            raise ToolError(f"The path {path} does not exist. Please provide a valid path.")
        if path.exists() and command == "create":
            raise ToolError(f"File already exists at: {path}. Cannot overwrite files using command `create`.")
        if path.is_dir() and command != "view":
            raise ToolError(f"The path {path} is a directory and only the `view` command can be used on directories")

    async def view(self, path: Path, view_range: Optional[List[int]] = None) -> CLIResult:
        """Implements the view command."""
        if await asyncio.to_thread(path.is_dir):
            if view_range:
                raise ToolError("The `view_range` parameter is not allowed when `path` points to a directory.")
            entries = [f"{p.name}/" if p.is_dir() else p.name for p in path.iterdir()]
            stdout = "\n".join(sorted(entries))
            return CLIResult(output=f"Files and directories in {path}:\n{stdout}\n")

        file_content = self.read_file(path)
        init_line = 1
        if view_range:
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                raise ToolError("Invalid `view_range`. It should be a list of two integers.")
            file_lines = file_content.split("\n")
            n_lines_file = len(file_lines)
            init_line, final_line = view_range
            if init_line < 1 or init_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be within file lines: {[1, n_lines_file]}"
                )
            if final_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be <= lines in file: `{n_lines_file}`"
                )
            if final_line != -1 and final_line < init_line:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be >= first `{init_line}`"
                )

            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1 :])
            else:
                file_content = "\n".join(file_lines[init_line - 1 : final_line])

        return CLIResult(output=self._make_output(file_content, str(path), init_line=init_line))

    def str_replace(self, path: Path, old_str: str, new_str: Optional[str]) -> CLIResult:
        """Replaces unique occurrences of old_str with new_str."""
        file_content = self.read_file(path).expandtabs()
        old_str = old_str.expandtabs()
        new_str = new_str.expandtabs() if new_str is not None else ""

        occurrences = file_content.count(old_str)
        if occurrences == 0:
            raise ToolError(f"No replacement performed: old_str `{old_str}` did not appear verbatim in {path}.")
        elif occurrences > 1:
            file_content_lines = file_content.split("\n")
            lines = [idx + 1 for idx, line in enumerate(file_content_lines) if old_str in line]
            raise ToolError(
                f"No replacement performed: Multiple occurrences of old_str in lines {lines}. Please specify unique context."
            )

        new_file_content = file_content.replace(old_str, new_str)
        self.write_file(path, new_file_content)
        self._file_history[path].append(file_content)

        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

        success_msg = f"The file {path} has been edited. " + self._make_output(
            snippet, f"a snippet of {path}", start_line + 1
        )
        return CLIResult(output=success_msg)

    def insert(self, path: Path, insert_line: int, new_str: str) -> CLIResult:
        """Inserts new_str at the specified line in the file content."""
        file_text = self.read_file(path).expandtabs()
        new_str = new_str.expandtabs()
        file_text_lines = file_text.split("\n")
        n_lines_file = len(file_text_lines)

        if insert_line < 0 or insert_line > n_lines_file:
            raise ToolError(
                f"Invalid `insert_line` parameter: {insert_line}. It should be within file lines: {[0, n_lines_file]}"
            )

        new_str_lines = new_str.split("\n")
        new_file_text_lines = (
            file_text_lines[:insert_line]
            + new_str_lines
            + file_text_lines[insert_line:]
        )
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
            + new_str_lines
            + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
        )

        new_file_text = "\n".join(new_file_text_lines)
        snippet = "\n".join(snippet_lines)

        self.write_file(path, new_file_text)
        self._file_history[path].append(file_text)

        success_msg = f"The file {path} has been edited. " + self._make_output(
            snippet, "a snippet of the edited file", max(1, insert_line - SNIPPET_LINES + 1)
        )
        return CLIResult(output=success_msg)

    def read_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            raise ToolError(f"Ran into {e} while trying to read {path}") from None

    def write_file(self, path: Path, file: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file, encoding="utf-8")
        except Exception as e:
            raise ToolError(f"Ran into {e} while trying to write to {path}") from None

    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ) -> str:
        file_content = maybe_truncate(file_content)
        if expand_tabs:
            file_content = file_content.expandtabs()
        formatted = "\n".join(
            [f"{i + init_line:6}\t{line}" for i, line in enumerate(file_content.split("\n"))]
        )
        return f"Here's the result of running `cat -n` on {file_descriptor}:\n{formatted}\n"


class EditTool20250728(EditTool, BaseAnthropicTool):
    """Anthropic text_editor_20250728 version compatible subclass."""
    api_type: Literal["text_editor_20250728"] = "text_editor_20250728"
    name: Literal["str_replace_based_edit_tool"] = "str_replace_based_edit_tool"
