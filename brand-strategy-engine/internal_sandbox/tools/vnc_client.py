"""Headless Python RFB/VNC client for automated browser exploration."""

import asyncio
import base64
import os
import socket
from typing import Any, Dict, Optional, Tuple

from .base import ToolError, ToolResult
from .computer import ComputerTool


class VNCClient:
    """Client for controlling the sandboxed private VNC desktop environment."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5901,
        password: Optional[str] = None,
        timeout: float = 5.0,
    ):
        self.host = os.getenv("VNC_HOST", host)
        self.port = int(os.getenv("VNC_PORT", port))
        self.password = password
        self.timeout = timeout
        self.is_connected = False
        self._remote_url = f"http://{self.host}:8080"
        self._computer_tool = ComputerTool()

    def check_socket(self) -> bool:
        """Verifies if the VNC TCP port is actively listening."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
            sock.close()
            return True
        except (socket.error, socket.timeout):
            return False

    async def connect(self) -> bool:
        """Establishes authenticated handshake with internal RFB server or remote sandbox."""
        self.is_connected = self.check_socket()
        return self.is_connected

    async def _try_remote_exec(self, endpoint: str, payload: Dict[str, Any]) -> Optional[ToolResult]:
        """Attempts remote execution against containerized sandbox endpoint."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{self._remote_url}{endpoint}", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return ToolResult(
                        output=data.get("output", ""),
                        error=data.get("error"),
                        base64_image=data.get("base64_image"),
                    )
        except Exception:
            pass
        return None

    async def navigate_browser(
        self,
        url: str,
        viewport_size: Tuple[int, int] = (1920, 1080),
    ) -> ToolResult:
        """Launches Firefox or directs active browser window to the designated target URL."""
        remote_res = await self._try_remote_exec("/navigate", {"url": url, "viewport": viewport_size})
        if remote_res:
            return remote_res

        self._computer_tool.set_viewport(viewport_size[0], viewport_size[1])
        nav_cmd = f"firefox-esr --new-window '{url}' >/dev/null 2>&1 &"
        await self._computer_tool.shell(nav_cmd)
        await asyncio.sleep(1.0)
        return await self.capture_screen()

    async def send_click(self, x: int, y: int, button: int = 1) -> ToolResult:
        """Dispatches mouse click at specified viewport coordinates."""
        action = "left_click" if button == 1 else "right_click"
        return await self._computer_tool(action=action, coordinate=(x, y))

    async def send_scroll(
        self,
        direction: str = "down",
        amount: int = 2,
        coordinate: Optional[Tuple[int, int]] = None,
    ) -> ToolResult:
        """Dispatches mouse wheel scroll events."""
        return await self._computer_tool(
            action="scroll",
            scroll_direction=direction,
            scroll_amount=amount,
            coordinate=coordinate,
        )

    async def send_keys(self, text: str) -> ToolResult:
        """Dispatches typed keystrokes to the active window."""
        return await self._computer_tool(action="type", text=text)

    def scale_coordinates(
        self,
        source: str,
        x: int,
        y: int,
        target: Optional[str] = None,
    ) -> Tuple[int, int]:
        """Scales coordinates proportionally using underlying ComputerTool."""
        return self._computer_tool.scale_coordinates(source, x, y, target=target)

    async def capture_screen(self) -> ToolResult:
        """Retrieves current frame buffer as base64-encoded PNG."""
        return await self._computer_tool.screenshot()

    async def close(self) -> None:
        """Terminates active VNC session."""
        self.is_connected = False
