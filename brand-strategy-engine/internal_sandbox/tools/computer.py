"""Internal sandboxed computer display, mouse, and keyboard interaction tool."""

import asyncio
import base64
import os
import shlex
import shutil
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

from internal_sandbox.tools.base import BaseTool, ToolError, ToolResult

ActionType = Literal[
    "key",
    "type",
    "mouse_move",
    "left_click",
    "left_click_drag",
    "right_click",
    "double_click",
    "middle_click",
    "screenshot",
    "cursor_position",
]

OUTPUT_DIR = Path("/tmp/outputs")


class ComputerTool(BaseTool):
    """Low-level OS input and display controller."""

    name: str = "computer"

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        display_num: Optional[int] = 1,
    ):
        self.width = int(os.getenv("WIDTH") or width)
        self.height = int(os.getenv("HEIGHT") or height)
        env_disp = os.getenv("DISPLAY_NUM")
        self.display_num = int(env_disp) if env_disp is not None else display_num
        self.display_prefix = f"DISPLAY=:{self.display_num} " if self.display_num else ""
        self.xdotool = f"{self.display_prefix}xdotool"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def to_params(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Send keyboard events, mouse clicks, movements, and take screenshots in the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "key",
                            "type",
                            "mouse_move",
                            "left_click",
                            "left_click_drag",
                            "right_click",
                            "double_click",
                            "middle_click",
                            "screenshot",
                            "cursor_position",
                        ],
                    },
                    "text": {"type": "string", "description": "Text to type or key combinations"},
                    "coordinate": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[x, y] coordinates",
                    },
                },
                "required": ["action"],
            },
        }

    async def shell(self, cmd: str) -> Tuple[str, str, int]:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            stdout.decode(errors="replace").strip(),
            stderr.decode(errors="replace").strip(),
            proc.returncode or 0,
        )

    async def screenshot(self) -> ToolResult:
        """Captures a screenshot using scrot or fallback 1x1 base64 transparent PNG."""
        target_path = OUTPUT_DIR / "screenshot.png"
        if target_path.exists():
            target_path.unlink()

        scrot_cmd = f"{self.display_prefix}scrot -z {target_path}"
        stdout, stderr, code = await self.shell(scrot_cmd)

        if code == 0 and target_path.exists():
            raw_bytes = target_path.read_bytes()
            encoded = base64.b64encode(raw_bytes).decode("ascii")
            return ToolResult(base64_image=encoded, output="Screenshot captured successfully")

        # Fallback 1x1 transparent PNG if X server is offline (e.g. running outside X11)
        fallback_png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        return ToolResult(
            base64_image=fallback_png,
            output="X11 display inactive; synthetic fallback screenshot returned.",
        )

    async def __call__(
        self,
        *,
        action: ActionType,
        text: Optional[str] = None,
        coordinate: Optional[Tuple[int, int]] = None,
        **kwargs,
    ) -> ToolResult:
        if action == "screenshot":
            return await self.screenshot()

        elif action == "mouse_move":
            if not coordinate:
                raise ToolError("coordinate required for mouse_move")
            x, y = coordinate
            cmd = f"{self.xdotool} mousemove --sync {x} {y}"
            out, err, _ = await self.shell(cmd)
            return ToolResult(output=f"Mouse moved to {x}, {y}")

        elif action in ("left_click", "right_click", "middle_click", "double_click"):
            btn_map = {
                "left_click": "1",
                "right_click": "3",
                "middle_click": "2",
                "double_click": "--repeat 2 --delay 10 1",
            }
            if coordinate:
                x, y = coordinate
                await self.shell(f"{self.xdotool} mousemove --sync {x} {y}")
            cmd = f"{self.xdotool} click {btn_map[action]}"
            await self.shell(cmd)
            return ToolResult(output=f"Performed {action}")

        elif action == "type":
            if text is None:
                raise ToolError("text is required for action 'type'")
            cmd = f"{self.xdotool} type --delay 12 -- {shlex.quote(text)}"
            await self.shell(cmd)
            return ToolResult(output=f"Typed text: {text}")

        elif action == "key":
            if text is None:
                raise ToolError("text is required for action 'key'")
            cmd = f"{self.xdotool} key -- {shlex.quote(text)}"
            await self.shell(cmd)
            return ToolResult(output=f"Sent key: {text}")

        elif action == "cursor_position":
            cmd = f"{self.xdotool} getmouselocation --shell"
            out, _, _ = await self.shell(cmd)
            return ToolResult(output=out or "X=0\nY=0")

        raise ToolError(f"Unsupported computer action: {action}")
