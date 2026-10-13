# pyright: reportMissingImports=false
"""Perception and storefront audit node for LangGraph workflow (TSK-04).
Integrates headless browser inspection, network telemetry, and Baymard CRO heuristics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage

from audit.storefront_auditor import StorefrontAuditor
from core.state import AgentState, AuditMetrics


def perception_and_audit_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node executing storefront, Core Web Vitals, and network analytics audit.

    Extracts target storefront configuration from state metadata or brand profile,
    executes browser automation via AIO Sandbox, detects Baymard friction points,
    and transitions phase to 'reasoning'.
    """
    metadata: Dict[str, Any] = state.get("metadata") or {}
    brand = state.get("brand_profile")

    # Determine target URL or test markup
    target_url = (
        metadata.get("target_url")
        or metadata.get("storefront_url")
        or (brand.guidelines.get("storefront_url") if brand and hasattr(brand, "guidelines") else None)
        or "http://127.0.0.1:8080"
    )
    custom_html = metadata.get("custom_html")

    sandbox_url = metadata.get("sandbox_base_url")
    sandbox_key = metadata.get("sandbox_api_key")

    auditor = StorefrontAuditor(base_url=sandbox_url, api_key=sandbox_key)

    try:
        audit_result = auditor.audit_storefront(
            target_url=target_url,
            custom_html=custom_html,
        )

        audit_metrics = audit_result.audit_metrics
        baymard_summary = (
            f"Identified {len(audit_result.baymard_issues)} Baymard friction points. "
            if audit_result.baymard_issues
            else "Storefront meets baseline Baymard checkout standards. "
        )
        telemetry_summary = (
            f"Telemetry: GA4={'Detected' if audit_result.ga4_detected else 'Missing'}, "
            f"Meta Pixel={'Detected' if audit_result.meta_pixel_detected else 'Missing'}."
        )

        message_content = (
            f"[Perception & Storefront Audit Complete]\n"
            f"URL: {target_url}\n"
            f"Load Time: {audit_result.load_time_ms:.1f}ms\n"
            f"{telemetry_summary}\n"
            f"{baymard_summary}\n"
            f"Artifacts saved: Screenshot -> {audit_result.screenshot_path}, HAR -> {audit_result.har_path}"
        )

        artifacts: List[str] = [audit_result.screenshot_path, audit_result.har_path]

        return {
            "audit_metrics": audit_metrics,
            "phase": "reasoning",
            "artifacts": artifacts,
            "messages": [AIMessage(content=message_content)],
        }

    except Exception as exc:
        fallback_metrics = AuditMetrics(
            reach=50000,
            traffic=10000,
            conversions=150,
            cac=40.0,
            clv=100.0,
            roas=2.5,
            health_ratio=2.5,
            baymard_issues=[f"Audit execution interrupted: {str(exc)}"],
        )
        return {
            "audit_metrics": fallback_metrics,
            "phase": "reasoning",
            "errors": [f"Storefront audit failed: {str(exc)}"],
            "messages": [AIMessage(content=f"Perception audit encountered error: {str(exc)}")],
        }
