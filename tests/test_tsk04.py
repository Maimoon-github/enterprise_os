# pyright: reportMissingImports=false
"""Validation tests for TSK-04: Digital Storefront, CRO Heuristics, and Analytics Audit Node."""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from audit.baymard_rules import (
    BaymardEvaluationResult,
    BaymardHeuristicsEngine,
    evaluate_baymard_rules,
)
from audit.storefront_auditor import StorefrontAuditResult, StorefrontAuditor
from core.nodes.perception_node import perception_and_audit_node
from core.state import AgentState, AuditMetrics, BrandProfile


SAMPLE_FRICTION_CHECKOUT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LuxeBeauty Checkout</title>
    <!-- Analytics Telemetry Scripts -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC1234XYZ"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-ABC1234XYZ');
    </script>
    <script>
      !function(f,b,e,v,n,t,s)
      {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
      n.callMethod.apply(n,arguments):n.queue.push(arguments)};
      if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
      n.queue=[];t=b.createElement(e);t.async=!0;
      t.src=v;s=b.getElementsByTagName(e)[0];
      s.parentNode.insertBefore(t,s)}(window, document,'script',
      'https://connect.facebook.net/en_US/fbevents.js');
      fbq('init', '987654321012345');
      fbq('track', 'PageView');
    </script>
</head>
<body>
    <header><h1>Complete Your Order</h1></header>
    <main>
        <!-- Baymard Friction: Forced Account Creation -->
        <section class="auth-gate">
            <h3>Account Required</h3>
            <p>Create an account to continue with your purchase. Guest checkout is disabled.</p>
            <input type="email" placeholder="Your Email" />
            <input type="password" placeholder="Create Password" />
        </section>

        <!-- Baymard Friction: Hidden Shipping Costs -->
        <section class="order-summary">
            <p>Subtotal: $85.00</p>
            <p>Shipping calculated at next step.</p>
            <p>Additional fees apply upon review.</p>
        </section>

        <!-- Baymard Friction: Excessive Form Fields -->
        <form class="address-form">
            <input type="text" name="f1" placeholder="First Name" />
            <input type="text" name="f2" placeholder="Middle Name" />
            <input type="text" name="f3" placeholder="Last Name" />
            <input type="text" name="f4" placeholder="Suffix" />
            <input type="text" name="f5" placeholder="Address Line 1" />
            <input type="text" name="f6" placeholder="Address Line 2" />
            <input type="text" name="f7" placeholder="Building" />
            <input type="text" name="f8" placeholder="Floor" />
            <input type="text" name="f9" placeholder="City" />
            <input type="text" name="f10" placeholder="County" />
            <input type="text" name="f11" placeholder="State" />
            <input type="text" name="f12" placeholder="Zip Code" />
            <input type="text" name="f13" placeholder="Evening Phone" />
            <input type="text" name="f14" placeholder="Day Phone" />
        </form>

        <!-- Baymard Friction: Prominent Uncollapsed Coupon Box -->
        <section class="coupon">
            <input type="text" placeholder="Enter Promo Code" />
            <button>Apply Discount Code</button>
        </section>

        <button class="submit">Place Order</button>
    </main>
</body>
</html>
"""


def test_baymard_heuristics_engine():
    """Verify Baymard heuristic engine flags all checkout friction patterns."""
    engine = BaymardHeuristicsEngine()
    result = engine.evaluate(
        dom_markdown="# Checkout\nCreate an account to continue\nShipping calculated at next step",
        html_content=SAMPLE_FRICTION_CHECKOUT_HTML,
    )

    assert isinstance(result, BaymardEvaluationResult)
    assert len(result.violations) >= 4

    rule_ids = [v.rule_id for v in result.violations]
    assert "BAYMARD-01" in rule_ids  # Forced Registration
    assert "BAYMARD-02" in rule_ids  # Hidden Shipping Costs
    assert "BAYMARD-03" in rule_ids  # Missing Trust Signals
    assert "BAYMARD-04" in rule_ids  # Excessive Form Fields (> 12)

    assert result.friction_score >= 60.0
    assert len(result.baymard_issues) >= 4
    print("test_baymard_heuristics_engine: PASSED")


def test_storefront_auditor_sandbox_execution():
    """Verify StorefrontAuditor executes inside AIO Sandbox container runtime."""
    auditor = StorefrontAuditor()
    result = auditor.audit_storefront(
        target_url="file:///home/gem/staged_storefront.html",
        custom_html=SAMPLE_FRICTION_CHECKOUT_HTML,
    )

    assert isinstance(result, StorefrontAuditResult)
    assert result.status_code == 200
    assert result.screenshot_path == "/home/gem/audit_shot.png"
    assert result.har_path == "/home/gem/audit_network.har"

    # Telemetry verification: GA4 and Meta Pixel
    assert result.ga4_detected is True
    assert result.meta_pixel_detected is True

    # Baymard heuristics verification
    assert len(result.baymard_issues) >= 3
    assert any("BAYMARD-01" in issue for issue in result.baymard_issues)
    assert any("BAYMARD-02" in issue for issue in result.baymard_issues)

    # Validated AuditMetrics
    metrics = result.audit_metrics
    assert isinstance(metrics, AuditMetrics)
    assert metrics.reach > 0
    assert metrics.traffic > 0
    assert metrics.health_ratio >= 3.0
    assert len(metrics.baymard_issues) == len(result.baymard_issues)
    print("test_storefront_auditor_sandbox_execution: PASSED")


def test_perception_and_audit_node_langgraph_workflow():
    """Verify LangGraph perception_and_audit_node returns validated AuditMetrics."""
    brand = BrandProfile(
        brand_name="LuxeBeauty eCommerce",
        tone_of_voice=["Scientific", "Elevated"],
        target_audience="D2C Premium Skincare Shoppers",
        guidelines={"storefront_url": "file:///home/gem/staged_storefront.html"},
    )

    initial_state: AgentState = {
        "messages": [HumanMessage(content="Trigger store audit node")],
        "phase": "perception",
        "brand_profile": brand,
        "metadata": {
            "custom_html": SAMPLE_FRICTION_CHECKOUT_HTML,
        },
        "errors": [],
        "artifacts": [],
    }

    # Execute perception node
    output = perception_and_audit_node(initial_state)

    assert "audit_metrics" in output
    assert isinstance(output["audit_metrics"], AuditMetrics)
    assert output["phase"] == "reasoning"
    assert len(output["artifacts"]) >= 2
    assert "/home/gem/audit_shot.png" in output["artifacts"]
    assert "/home/gem/audit_network.har" in output["artifacts"]
    assert len(output["messages"]) >= 1

    metrics: AuditMetrics = output["audit_metrics"]
    assert len(metrics.baymard_issues) >= 3
    assert metrics.traffic > 0
    assert metrics.health_ratio >= 3.0

    # Test within LangGraph StateGraph assembly
    workflow = StateGraph(AgentState)
    workflow.add_node("perception_node", perception_and_audit_node)
    workflow.add_edge(START, "perception_node")
    workflow.add_edge("perception_node", END)

    app = workflow.compile()
    final_state = app.invoke(initial_state)

    assert final_state["phase"] == "reasoning"
    assert isinstance(final_state["audit_metrics"], AuditMetrics)
    assert len(final_state["artifacts"]) >= 2
    assert len(final_state["messages"]) == 2  # 1 human + 1 AI
    print("test_perception_and_audit_node_langgraph_workflow: PASSED")


if __name__ == "__main__":
    test_baymard_heuristics_engine()
    test_storefront_auditor_sandbox_execution()
    test_perception_and_audit_node_langgraph_workflow()
    print("=== ALL TSK-04 TESTS PASSED ===")
