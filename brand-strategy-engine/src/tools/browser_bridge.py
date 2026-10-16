"""Public tool bridge for Agent 1 providing VNC sandbox access and evidence capture."""

import base64
import os
from pathlib import Path
import uuid
from typing import Any, Dict, Optional, Tuple
import httpx

from internal_sandbox.tools.vnc_client import VNCClient
from src.schemas.evidence import EvidenceReference


class BrowserBridge:
    """Agent 1 interface for headless desktop browser interaction."""

    def __init__(self, vnc_client: Optional[VNCClient] = None):
        self.vnc_client = vnc_client or VNCClient()
        self._current_url: str = ""

    async def vnc_navigate(
        self,
        url: str,
        viewport_size: Tuple[int, int] = (1920, 1080),
    ) -> Dict[str, Any]:
        """Directs the sandboxed browser to visit the target URL."""
        self._current_url = url
        screenshot_result = await self.vnc_client.navigate_browser(url, viewport_size=viewport_size)
        return {
            "status": "success",
            "url": url,
            "viewport": viewport_size,
            "screenshot_base64": screenshot_result.base64_image,
        }

    async def vnc_interact(
        self,
        action_type: str,
        coordinate: Optional[Tuple[int, int]] = None,
        text: Optional[str] = None,
        scroll_direction: str = "down",
        scroll_amount: int = 2,
    ) -> Dict[str, Any]:
        """Performs mouse, keyboard, or scroll interaction in the sandbox."""
        if action_type in ("left_click", "right_click", "click") and coordinate:
            btn = 3 if action_type == "right_click" else 1
            result = await self.vnc_client.send_click(coordinate[0], coordinate[1], button=btn)
        elif action_type == "scroll":
            result = await self.vnc_client.send_scroll(
                direction=scroll_direction,
                amount=scroll_amount,
                coordinate=coordinate,
            )
        elif action_type == "type" and text:
            result = await self.vnc_client.send_keys(text)
        else:
            result = await self.vnc_client.capture_screen()

        return {
            "status": "success",
            "action": action_type,
            "output": result.output,
            "screenshot_base64": result.base64_image,
        }

    def scale_coordinates(
        self,
        source: str,
        x: int,
        y: int,
        target: Optional[str] = None,
    ) -> Tuple[int, int]:
        """Maps coordinates proportionally between vision model coordinates and display canvas."""
        return self.vnc_client.scale_coordinates(source, x, y, target=target)

    async def capture_visual_evidence(
        self,
        source_url: str,
        dataset_reference: str,
        observation_notes: str,
        bounding_box: Optional[Tuple[int, int, int, int]] = None,
    ) -> EvidenceReference:
        """Captures a verifiable visual frame and persists screenshot blob to disk."""
        ev_id = f"ev_vnc_{uuid.uuid4().hex[:8]}"
        res = await self.vnc_client.capture_screen()

        # Determine target directory: prefer /app/evidence_blobs, fallback to ./evidence_blobs
        storage_dir = Path("/app/evidence_blobs")
        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            storage_dir = Path("evidence_blobs")
            storage_dir.mkdir(parents=True, exist_ok=True)

        blob_path = storage_dir / f"{ev_id}.png"
        screenshot_uri = str(blob_path)
        sha256_hex = None
        if res.base64_image:
            try:
                import hashlib
                img_bytes = base64.b64decode(res.base64_image)
                blob_path.write_bytes(img_bytes)
                sha256_hex = hashlib.sha256(img_bytes).hexdigest()
            except Exception:
                pass

        return EvidenceReference(
            evidence_id=ev_id,
            source_url=source_url or self._current_url or "https://unknown.target",
            source_type="vnc_screenshot",
            dataset_reference=dataset_reference,
            observation_notes=observation_notes,
            screenshot_uri=screenshot_uri,
            bounding_box=bounding_box,
            sha256_hash=sha256_hex,
        )

    async def fetch_page_response(self, url: str) -> Tuple[str, int]:
        """Fetches page content and returns (html, status_code)."""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Antigravity-Brand-Auditor/2.4"})
                return resp.text, resp.status_code
        except Exception as e:
            return f"<html><body><p>Failed to retrieve {url}: {e}</p></body></html>", 500

    async def fetch_page_html(self, url: str) -> str:
        """Fetches raw HTML directly via HTTP for DOM parsing."""
        html, _ = await self.fetch_page_response(url)
        return html
