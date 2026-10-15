"""Internal sandboxed computer display, mouse, and keyboard interaction tool."""

import asyncio
import base64
from enum import StrEnum
import os
from pathlib import Path
import shlex
import shutil
from typing import Any, Dict, Literal, Optional, Tuple, TypedDict, Union, cast, get_args
from uuid import uuid4

from .base import BaseAnthropicTool, BaseTool, ToolError, ToolResult
from .run import run

OUTPUT_DIR = Path("/tmp/outputs")

TYPING_DELAY_MS = 12
TYPING_GROUP_SIZE = 50

Action_20241022 = Literal[
    "key",
    "type",
    "mouse_move",
    "left_click",
    "left_click_drag",
    "right_click",
    "middle_click",
    "double_click",
    "screenshot",
    "cursor_position",
]

Action_20250124 = (
    Action_20241022
    | Literal[
        "left_mouse_down",
        "left_mouse_up",
        "scroll",
        "hold_key",
        "wait",
        "triple_click",
    ]
)

Action_20251124 = Action_20250124 | Literal["zoom"]

ActionType = Action_20251124
ScrollDirection = Literal["up", "down", "left", "right"]


class Resolution(TypedDict):
    width: int
    height: int


MAX_SCALING_TARGETS: Dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),
    "WXGA": Resolution(width=1280, height=800),
    "FWXGA": Resolution(width=1366, height=768),
}

CLICK_BUTTONS = {
    "left_click": 1,
    "right_click": 3,
    "middle_click": 2,
    "double_click": "--repeat 2 --delay 10 1",
    "triple_click": "--repeat 3 --delay 10 1",
}


class ScalingSource(StrEnum):
    COMPUTER = "computer"
    API = "api"


class ComputerToolOptions(TypedDict):
    display_height_px: int
    display_width_px: int
    display_number: Optional[int]


def chunks(s: str, chunk_size: int) -> list[str]:
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]


class BaseComputerTool(BaseTool):
    """
    A tool that allows the agent to interact with the screen, keyboard, and mouse of the current computer.
    """

    name: str = "computer"
    width: int
    height: int
    display_num: Optional[int]

    _screenshot_delay = 2.0
    _scaling_enabled = True

    @property
    def options(self) -> ComputerToolOptions:
        width, height = self.scale_coordinates(ScalingSource.COMPUTER, self.width, self.height)
        return {
            "display_width_px": width,
            "display_height_px": height,
            "display_number": self.display_num,
        }

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        display_num: Optional[int] = 1,
    ):
        super().__init__()
        env_w = os.getenv("WIDTH")
        env_h = os.getenv("HEIGHT")
        self.width = int(env_w) if env_w else width
        self.height = int(env_h) if env_h else height
        env_disp = os.getenv("DISPLAY_NUM")
        self.display_num = int(env_disp) if env_disp is not None else display_num
        self.display_prefix = f"DISPLAY=:{self.display_num} " if self.display_num else ""
        self.xdotool = f"{self.display_prefix}xdotool"
        self._display_prefix = self.display_prefix
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def set_viewport(self, width: int, height: int) -> None:
        """Sets active viewport dimensions for coordinate scaling."""
        self.width = width
        self.height = height

    def scale_coordinates(
        self,
        source: Union[ScalingSource, str],
        x: int,
        y: int,
        target: Optional[str] = None,
    ) -> Tuple[int, int]:
        """Proportionally scales coordinates between API space and physical canvas."""
        if not self._scaling_enabled or self.width == 0 or self.height == 0:
            return x, y

        source_str = str(source).lower()
        if target and target in MAX_SCALING_TARGETS:
            t_res = MAX_SCALING_TARGETS[target]
            target_w, target_h = t_res["width"], t_res["height"]
        else:
            ratio = self.width / self.height
            target_dim: Optional[Resolution] = None
            for name, dim in MAX_SCALING_TARGETS.items():
                if abs(dim["width"] / dim["height"] - ratio) < 0.05 and dim["width"] < self.width:
                    target_dim = dim
                    break
            if target_dim is None:
                target_w, target_h = MAX_SCALING_TARGETS["XGA"]["width"], MAX_SCALING_TARGETS["XGA"]["height"]
            else:
                target_w, target_h = target_dim["width"], target_dim["height"]

        x_factor = target_w / self.width
        y_factor = target_h / self.height

        if source_str in ("api", "scalingsource.api"):
            return round(x / x_factor), round(y / y_factor)
        # source == "computer"
        return round(x * x_factor), round(y * y_factor)

    def validate_and_get_coordinates(
        self, coordinate: Union[Tuple[int, int], list[int], None] = None
    ) -> Tuple[int, int]:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
            raise ToolError(f"{coordinate} must be a tuple/list of length 2")
        if not all(isinstance(i, int) and i >= 0 for i in coordinate):
            raise ToolError(f"{coordinate} must be a tuple/list of non-negative ints")
        return self.scale_coordinates(ScalingSource.API, coordinate[0], coordinate[1])

    def screenshot_size(self) -> Tuple[int, int]:
        return self.scale_coordinates(ScalingSource.COMPUTER, self.width, self.height)

    async def _new_output_path(self, prefix: str) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return OUTPUT_DIR / f"{prefix}_{uuid4().hex}.png"

    async def _capture(self, path: Path) -> ToolResult:
        """Capture the display at physical resolution into `path`."""
        if shutil.which("gnome-screenshot"):
            screenshot_cmd = f"{self._display_prefix}gnome-screenshot -f {path} -p"
        elif shutil.which("scrot"):
            screenshot_cmd = f"{self._display_prefix}scrot -z -p {path}"
        else:
            screenshot_cmd = f"{self._display_prefix}scrot -z {path}"
        return await self.shell(screenshot_cmd, take_screenshot=False)

    async def screenshot(self) -> ToolResult:
        """Take a screenshot of the current screen and return the base64 encoded image."""
        path = await self._new_output_path("screenshot")
        result = await self._capture(path)

        if self._scaling_enabled and path.exists():
            x, y = self.screenshot_size()
            if shutil.which("convert"):
                await self.shell(f"convert {path} -resize {x}x{y}! {path}", take_screenshot=False)

        if path.exists():
            return result.replace(base64_image=base64.b64encode(path.read_bytes()).decode())

        # Fallback 1x1 transparent PNG if X server is offline
        fallback_png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        return ToolResult(
            base64_image=fallback_png,
            output="X11 display inactive; synthetic fallback screenshot returned.",
        )

    async def shell(self, command: str, take_screenshot: bool = False) -> ToolResult:
        """Run a shell command and return the output, error, and optionally a screenshot."""
        code, stdout, stderr = await run(command)
        base64_image = None
        if take_screenshot:
            await asyncio.sleep(self._screenshot_delay)
            base64_image = (await self.screenshot()).base64_image
        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)

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
                            "key", "type", "mouse_move", "left_click", "left_click_drag",
                            "right_click", "middle_click", "double_click", "triple_click",
                            "left_mouse_down", "left_mouse_up", "scroll", "hold_key",
                            "wait", "screenshot", "cursor_position", "zoom",
                        ],
                    },
                    "text": {"type": "string"},
                    "coordinate": {"type": "array", "items": {"type": "integer"}},
                    "start_coordinate": {"type": "array", "items": {"type": "integer"}},
                    "scroll_direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                    "scroll_amount": {"type": "integer"},
                    "duration": {"type": "number"},
                    "region": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["action"],
            },
        }

    async def __call__(
        self,
        *,
        action: ActionType,
        text: Optional[str] = None,
        coordinate: Optional[Tuple[int, int]] = None,
        start_coordinate: Optional[Tuple[int, int]] = None,
        scroll_direction: Optional[ScrollDirection] = None,
        scroll_amount: Optional[int] = None,
        duration: Optional[Union[int, float]] = None,
        key: Optional[str] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        **kwargs,
    ) -> ToolResult:
        if action in ("mouse_move", "left_click_drag"):
            if coordinate is None:
                raise ToolError(f"coordinate is required for {action}")
            if action == "left_click_drag":
                if start_coordinate is None:
                    raise ToolError(f"start_coordinate is required for {action}")
                start_x, start_y = self.validate_and_get_coordinates(start_coordinate)
                end_x, end_y = self.validate_and_get_coordinates(coordinate)
                command_parts = [
                    self.xdotool,
                    f"mousemove --sync {start_x} {start_y} mousedown 1 mousemove --sync {end_x} {end_y} mouseup 1",
                ]
                return await self.shell(" ".join(command_parts))
            elif action == "mouse_move":
                x, y = self.validate_and_get_coordinates(coordinate)
                command_parts = [self.xdotool, f"mousemove --sync {x} {y}"]
                return await self.shell(" ".join(command_parts))

        if action in ("key", "type"):
            if text is None:
                raise ToolError(f"text is required for {action}")
            if action == "key":
                command_parts = [self.xdotool, f"key -- {text}"]
                return await self.shell(" ".join(command_parts))
            elif action == "type":
                results: list[ToolResult] = []
                for chunk in chunks(text, TYPING_GROUP_SIZE):
                    command_parts = [
                        self.xdotool,
                        f"type --delay {TYPING_DELAY_MS} -- {shlex.quote(chunk)}",
                    ]
                    results.append(await self.shell(" ".join(command_parts), take_screenshot=False))
                screenshot_base64 = (await self.screenshot()).base64_image
                return ToolResult(
                    output="".join(r.output or "" for r in results),
                    error="".join(r.error or "" for r in results),
                    base64_image=screenshot_base64,
                )

        if action in ("left_mouse_down", "left_mouse_up"):
            btn = "mousedown 1" if action == "left_mouse_down" else "mouseup 1"
            return await self.shell(f"{self.xdotool} {btn}")

        if action == "scroll":
            direction = scroll_direction or kwargs.get("scroll_direction", "down")
            amount = scroll_amount or kwargs.get("scroll_amount", 2)
            scroll_button = {"up": 4, "down": 5, "left": 6, "right": 7}.get(str(direction), 5)
            mouse_move_part = ""
            if coordinate is not None:
                x, y = self.validate_and_get_coordinates(coordinate)
                mouse_move_part = f"mousemove --sync {x} {y} "
            cmd = f"{self.xdotool} {mouse_move_part}click --repeat {amount} {scroll_button}"
            return await self.shell(cmd)

        if action in ("hold_key", "wait"):
            dur = duration or kwargs.get("duration", 1.0)
            if action == "hold_key":
                if text is None:
                    raise ToolError("text is required for hold_key")
                escaped = shlex.quote(text)
                cmd = f"{self.xdotool} keydown {escaped} sleep {dur} keyup {escaped}"
                return await self.shell(cmd)
            if action == "wait":
                await asyncio.sleep(float(dur))
                return await self.screenshot()

        if action in ("left_click", "right_click", "double_click", "triple_click", "middle_click"):
            mouse_move_part = ""
            if coordinate is not None:
                x, y = self.validate_and_get_coordinates(coordinate)
                mouse_move_part = f"mousemove --sync {x} {y} "
            btn_str = CLICK_BUTTONS.get(action, 1)
            cmd = f"{self.xdotool} {mouse_move_part}click {btn_str}"
            return await self.shell(cmd)

        if action == "screenshot":
            return await self.screenshot()

        if action == "cursor_position":
            res = await self.shell(f"{self.xdotool} getmouselocation --shell", take_screenshot=False)
            output = res.output or ""
            if "X=" in output and "Y=" in output:
                x = int(output.split("X=")[1].split("\n")[0])
                y = int(output.split("Y=")[1].split("\n")[0])
                sx, sy = self.scale_coordinates(ScalingSource.COMPUTER, x, y)
                return res.replace(output=f"X={sx},Y={sy}")
            return res.replace(output="X=0,Y=0")

        if action == "zoom":
            reg = region or kwargs.get("region")
            if reg and len(reg) == 4:
                return await self.zoom((int(reg[0]), int(reg[1]), int(reg[2]), int(reg[3])))
            raise ToolError("region required for zoom")

        raise ToolError(f"Invalid computer action: {action}")

    async def zoom(self, region: Tuple[int, int, int, int]) -> ToolResult:
        """Return a magnified capture of region."""
        x0, y0 = self.scale_coordinates(ScalingSource.API, region[0], region[1])
        x1, y1 = self.scale_coordinates(ScalingSource.API, region[2], region[3])
        frame_w, frame_h = self.screenshot_size()

        raw_path = await self._new_output_path("zoom_raw")
        zoom_path = await self._new_output_path("zoom")
        await self._capture(raw_path)
        if not raw_path.exists():
            return await self.screenshot()
        try:
            if shutil.which("convert"):
                await run(
                    f"convert {raw_path} -crop {x1 - x0}x{y1 - y0}+{x0}+{y0} +repage "
                    f"-resize {frame_w}x{frame_h} {zoom_path}"
                )
                if zoom_path.exists():
                    return ToolResult(base64_image=base64.b64encode(zoom_path.read_bytes()).decode())
            return await self.screenshot()
        finally:
            raw_path.unlink(missing_ok=True)
            zoom_path.unlink(missing_ok=True)


class ComputerTool(BaseComputerTool):
    """Primary unified ComputerTool for VNC desktop interaction."""
    pass


class ComputerTool20241022(BaseComputerTool, BaseAnthropicTool):
    api_type: Literal["computer_20241022"] = "computer_20241022"


class ComputerTool20250124(BaseComputerTool, BaseAnthropicTool):
    api_type: Literal["computer_20250124"] = "computer_20250124"


class ComputerTool20251124(ComputerTool20250124):
    api_type: Literal["computer_20251124"] = "computer_20251124"  # pyright: ignore[reportIncompatibleVariableOverride]


class ComputerToolset20260801(ComputerTool20251124):
    api_type: Literal["computer_toolset_20260801"] = "computer_toolset_20260801"  # pyright: ignore[reportIncompatibleVariableOverride]
    toolset_name: Literal["computer"] = "computer"
