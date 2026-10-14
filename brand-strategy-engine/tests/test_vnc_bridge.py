"""Tests for VNC sandbox tools, browser bridge, DOM parser, and metric feasibility validator."""

import pytest
from src.schemas.initiative import SuccessMetric
from src.tools.browser_bridge import BrowserBridge
from src.tools.dom_parser import DOMParser
from src.tools.metric_validator import MetricValidator
from internal_sandbox.tools.computer import ComputerTool
from internal_sandbox.tools.vnc_client import VNCClient


@pytest.mark.asyncio
async def test_dom_parser_metadata(sample_html):
    metadata = DOMParser.extract_metadata(sample_html)
    assert metadata["title"] == "Alex Chen - Software Architect"
    assert metadata["canonical"] == "https://alexchen.dev"
    assert "description" in metadata["meta_tags"]
    assert len(metadata["json_ld"]) == 1
    assert metadata["json_ld"][0]["@type"] == "Person"


@pytest.mark.asyncio
async def test_dom_parser_headings(sample_html):
    headings = DOMParser.extract_heading_hierarchy(sample_html)
    assert len(headings) >= 3
    assert headings[0]["level"] == "h1"
    assert "Full-Stack Developer" in headings[0]["text"]
    assert headings[1]["level"] == "h2"


@pytest.mark.asyncio
async def test_dom_parser_accessibility_tree(sample_html):
    tree = DOMParser.build_accessibility_tree(sample_html)
    assert tree["tag"] in ("body", "main") or "children" in tree
    assert len(tree.get("children", [])) > 0


@pytest.mark.asyncio
async def test_computer_tool_screenshot():
    tool = ComputerTool()
    res = await tool.screenshot()
    assert res.base64_image is not None
    assert len(res.base64_image) > 20


@pytest.mark.asyncio
async def test_browser_bridge_evidence_capture():
    bridge = BrowserBridge()
    ev = await bridge.capture_visual_evidence(
        source_url="https://test.dev",
        dataset_reference="h1.hero",
        observation_notes="Observed friction point in header",
    )
    assert ev.evidence_id.startswith("ev_vnc_")
    assert ev.source_type == "vnc_screenshot"
    assert ev.dataset_reference == "h1.hero"


def test_metric_validator_feasible_growth():
    metric = SuccessMetric(
        kpi="Inbound Lead Contact Form Click-Through Rate",
        baseline="1.2%",
        target="4.5%",
        verification_source="GA4",
    )
    passed, reason, lift = MetricValidator.validate_metric(metric)
    assert passed is True
    assert reason is None
    assert lift == 275.0


def test_metric_validator_excessive_growth_fails():
    metric = SuccessMetric(
        kpi="Inbound Lead Conversion Rate",
        baseline="1.0%",
        target="12.0%",  # 1100% lift
        verification_source="GA4",
    )
    passed, reason, lift = MetricValidator.validate_metric(metric)
    assert passed is False
    assert reason is not None and "Unrealistic growth lift" in reason


def test_metric_validator_unrecognized_platform_fails():
    metric = SuccessMetric(
        kpi="Revenue",
        baseline="$100",
        target="$200",
        verification_source="ImaginaryAnalyticsTool",
    )
    passed, reason, lift = MetricValidator.validate_metric(metric)
    assert passed is False
    assert reason is not None and "Unrecognized verification source" in reason


def test_metric_validator_feasible_inverse_reduction():
    metric = SuccessMetric(
        kpi="Cart Abandonment Rate",
        baseline="68%",
        target="45%",
        verification_source="Shopify Analytics",
    )
    passed, reason, lift = MetricValidator.validate_metric(metric)
    assert passed is True
    assert reason is None


def test_computer_coordinate_scaling_proportional():
    tool = ComputerTool(width=1920, height=1080)
    # Scale from 1920x1080 down to XGA (1024x768)
    scaled_x, scaled_y = tool.scale_coordinates(source="computer", x=1920, y=1080, target="XGA")
    assert scaled_x == 1024
    assert scaled_y == 768

    # Scale from XGA (1024x768) back up to 1920x1080
    up_x, up_y = tool.scale_coordinates(source="api", x=1024, y=768, target="XGA")
    assert up_x == 1920
    assert up_y == 1080


@pytest.mark.asyncio
async def test_vnc_scroll_interaction():
    bridge = BrowserBridge()
    # Execute scroll interaction
    result = await bridge.vnc_interact(
        action_type="scroll",
        scroll_direction="down",
        scroll_amount=3,
        coordinate=(200, 300),
    )
    assert result["status"] == "success"
    assert result["action"] == "scroll"


@pytest.mark.asyncio
async def test_dom_parser_opengraph_extraction():
    og_html = """
    <html>
        <head>
            <title>Test Store</title>
            <meta property="og:title" content="Test eCommerce Store" />
            <meta property="og:description" content="Shop sustainable products" />
            <meta property="og:image" content="https://teststore.com/og.jpg" />
        </head>
        <body><h1>Welcome</h1></body>
    </html>
    """
    metadata = DOMParser.extract_metadata(og_html)
    assert "opengraph" in metadata
    assert metadata["opengraph"].get("og:title") == "Test eCommerce Store"
    assert metadata["opengraph"].get("og:image") == "https://teststore.com/og.jpg"


@pytest.mark.asyncio
async def test_browser_bridge_screenshot_blob_persistence(tmp_path):
    bridge = BrowserBridge()
    ev = await bridge.capture_visual_evidence(
        source_url="https://store.example.com",
        dataset_reference="div.pdp-accordion",
        observation_notes="Accordion collapsed",
        bounding_box=(100, 150, 800, 600),
    )
    assert ev.screenshot_uri is not None
    assert ev.bounding_box == (100, 150, 800, 600)
    assert ev.dataset_reference == "div.pdp-accordion"

