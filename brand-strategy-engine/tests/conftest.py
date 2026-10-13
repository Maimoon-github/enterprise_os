"""Pytest configuration and shared fixtures for brand strategy engine tests."""

import pytest
from src.schemas.evidence import EvidenceReference
from src.schemas.initiative import (
    ApprovalStatus,
    PriorityLevel,
    PriorityMatrix,
    StrategicInitiative,
    SuccessMetric,
)
from src.schemas.state import (
    BrandProfile,
    MasterEngineState,
    OperationalMode,
    ResearchRepository,
    StrategicArtifacts,
)


@pytest.fixture
def sample_brand_profile_personal():
    return BrandProfile(
        website_url="https://alexchen.dev",
        brand_name="Alex Chen",
        industry="Distributed Systems",
        target_market=["Enterprise Decision Makers", "High-Growth Scaleups"],
        business_goals=["Increase inbound high-value contracting inquiries to 4% CTR"],
    )


@pytest.fixture
def sample_brand_profile_ecommerce():
    return BrandProfile(
        website_url="https://nordicapparel.com",
        brand_name="Nordic Apparel",
        industry="Technical Apparel & DTC",
        target_market=["High-intent outdoor shoppers"],
        business_goals=["Lift mobile Add-to-Cart CVR from 1.8% to 3.1%"],
    )


@pytest.fixture
def sample_evidence():
    return EvidenceReference(
        evidence_id="ev_vnc_screen_004",
        source_url="https://alexchen.dev",
        source_type="dom_selector",
        dataset_reference="h1.hero-title",
        observation_notes="Headline contains ungrounded claims with zero proof of domain specialization",
    )


@pytest.fixture
def sample_strategic_initiative(sample_evidence):
    return StrategicInitiative(
        recommendation_id="REC-A-001",
        initiating_agent="Agent_5_Growth",
        finding="Hero headline lacks empirical proof of competence.",
        evidence=sample_evidence,
        business_implication="High bounce rate (>65%) from enterprise clients.",
        actionable_prescription="Rewrite hero copy to define a clear Category of One with terminal demo.",
        priority=PriorityMatrix(
            impact=PriorityLevel.HIGH,
            effort=PriorityLevel.LOW,
            cost=PriorityLevel.LOW,
            confidence="92%",
            ice_score=8.28,
        ),
        success_metric=SuccessMetric(
            kpi="Inbound Lead Contact Form Click-Through Rate",
            baseline="1.2%",
            target="4.5%",
            verification_source="GA4",
        ),
        approval_status=ApprovalStatus.PROPOSED,
        rejection_reasons=None,
        iteration_cycle=0,
    )


@pytest.fixture
def sample_master_state(sample_brand_profile_personal, sample_evidence, sample_strategic_initiative):
    return MasterEngineState(
        session_id="test-session-123",
        mode=OperationalMode.MODE_A_PERSONAL,
        brand_profile=sample_brand_profile_personal,
        research_repository=ResearchRepository(
            visual_evidence_vnc=[sample_evidence],
            dom_snapshots={
                "https://alexchen.dev": {
                    "metadata": {"title": "Alex Chen | Portfolio"},
                    "accessibility_tree": {"tag": "body", "children": []},
                }
            },
        ),
        strategic_artifacts=StrategicArtifacts(
            growth_initiatives=[sample_strategic_initiative],
        ),
    )


@pytest.fixture
def sample_html():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <title>Alex Chen - Software Architect</title>
    <meta name="description" content="Distributed systems consultant and software architect.">
    <link rel="canonical" href="https://alexchen.dev">
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Person", "name": "Alex Chen"}
    </script>
</head>
<body>
    <header role="banner">
        <nav role="navigation"><a href="/">Home</a><a href="/work">Work</a></nav>
    </header>
    <main role="main">
        <section class="hero">
            <h1 class="hero-title">Full-Stack Developer & Passionate Problem Solver</h1>
            <p>Building scalable systems and modern web applications.</p>
            <button id="contact-btn">Contact Me</button>
        </section>
        <section class="case-studies">
            <h2>Selected Works</h2>
            <h3>High Throughput Architecture</h3>
        </section>
    </main>
</body>
</html>"""
