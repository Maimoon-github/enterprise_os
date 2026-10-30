import pytest
from app.observability.evals.golden_suite import run_golden_suite_regression
from app.observability.evals.rubric_judges import run_rubric_judge
from app.observability.evals.trajectory_evals import (
    evaluate_blueprint_schema,
    evaluate_platform_constraints,
    evaluate_trajectory,
    evaluate_trajectory_order,
)
from mcp_servers.brand_rag_server.resources import get_brand_voice_guidelines
from mcp_servers.brand_rag_server.tools import search_brand_knowledge
from scripts.seed_db import seed


def test_trajectory_evaluator_legacy():
    executed = ["BrandRAG", "Playwright", "DraftCopy", "ApprovalGate", "Publish"]
    expected = ["BrandRAG", "DraftCopy", "ApprovalGate", "Publish"]
    assert evaluate_trajectory_order(executed, expected) is True


def test_layer1_deterministic_schema_and_constraints():
    # Valid blueprint
    valid_blueprint = {
        "campaign_id": "test_camp_01",
        "objective": "Test launch",
        "target_audience_segments": ["Engineers"],
        "positioning_statement": "Deterministic agents",
        "platform_assets": [
            {
                "platform": "linkedin",
                "copy_text": "Deterministic marketing workflows.",
                "scheduled_utc": "2026-11-01T10:00:00Z",
                "aspect_ratio": "1:1",
                "idempotency_key": "idemp_01",
            }
        ],
    }
    schema_res = evaluate_blueprint_schema(valid_blueprint)
    assert schema_res["valid"] is True
    assert schema_res["score"] == 1.0

    # Invalid blueprint (missing required fields)
    invalid_schema = evaluate_blueprint_schema({"invalid_key": "data"})
    assert invalid_schema["valid"] is False
    assert invalid_schema["score"] == 0.0

    # Platform constraints: valid
    constraint_res = evaluate_platform_constraints(valid_blueprint["platform_assets"])
    assert constraint_res["valid"] is True
    assert constraint_res["score"] == 1.0

    # Platform constraints: x exceeding 280 chars
    long_assets = [
        {
            "platform": "x",
            "copy_text": "X" * 350,
            "aspect_ratio": "16:9",
        }
    ]
    long_res = evaluate_platform_constraints(long_assets)
    assert long_res["valid"] is False
    assert len(long_res["violations"]) > 0


def test_layer2_trajectory_evaluator():
    # Valid lifecycle order with payload stager
    valid_steps = [
        "research_strategy_node",
        "campaign_creative_node",
        "prepare_publish_payload_node",
        "human_approval_gate_node",
        "execute_platform_publish_node",
    ]
    eval_res = evaluate_trajectory(valid_steps)
    assert eval_res["valid"] is True
    assert eval_res["score"] == 1.0
    assert eval_res["recall"] == 1.0
    assert len(eval_res["violations"]) == 0

    # Inverted order: publish before approval
    inverted_steps = [
        "research_strategy_node",
        "execute_platform_publish_node",
        "human_approval_gate_node",
    ]
    inverted_res = evaluate_trajectory(inverted_steps)
    assert inverted_res["valid"] is False
    assert len(inverted_res["violations"]) > 0

    # Incomplete lifecycle: missing gate and publish
    incomplete_steps = ["research_strategy_node", "campaign_creative_node"]
    incomplete_res = evaluate_trajectory(incomplete_steps)
    assert incomplete_res["valid"] is False
    assert incomplete_res["recall"] == 0.5


def test_layer3_rubric_judges():
    # Authoritative brand copy
    good_copy = (
        "Enterprise marketing teams mandate deterministic approval gates and auditable governance. "
        "Eliminate hallucination risk with complete human control."
    )
    good_res = run_rubric_judge(good_copy, rubric_type="brand_voice_fidelity")
    assert good_res["passed"] is True
    assert good_res["score"] >= 0.85

    # Buzzword-laden copy
    buzzword_copy = "Our disruptive paradigm shift is a game-changer with deep dive synergy!"
    buzzword_res = run_rubric_judge(buzzword_copy, rubric_type="brand_voice_fidelity")
    assert buzzword_res["score"] < 0.70
    assert "prohibited buzzwords" in buzzword_res["explanation"].lower()

    # Groundedness
    grounded_res = run_rubric_judge(
        text="The campaign delivers SOC-2 compliant automated workflows.",
        rubric_type="groundedness",
        context="The platform ensures SOC-2 compliant workflows.",
    )
    assert grounded_res["score"] >= 0.75

    # Platform native quality
    quality_res = run_rubric_judge(good_copy, rubric_type="platform_native_quality")
    assert quality_res["passed"] is True


def test_layer4_golden_suite_regression():
    reg_res = run_golden_suite_regression()
    assert reg_res["total_scenarios"] == 3
    assert reg_res["passed"] == 3
    assert reg_res["pass_rate"] == 1.0
    assert len(reg_res["results"]) == 3


def test_brand_rag_preindexed_guidelines():
    """Verify seeded guidelines and personas are retrievable through Brand RAG tools and resources."""
    guidelines = get_brand_voice_guidelines("apex-horizon")
    assert "apex-horizon" in guidelines
    assert "Zero Hallucinations" in guidelines
    assert "Prohibited Phrases" in guidelines

    search_res = search_brand_knowledge("deterministic governance", limit=2)
    assert len(search_res) >= 1
    assert any("governance" in (doc["title"] + " " + doc["snippet"]).lower() for doc in search_res)


@pytest.mark.asyncio
async def test_seed_db_idempotency():
    """Verify seed_db runs idempotently multiple times without duplicate key violations."""
    res1 = await seed()
    assert res1["admin_user"] == "admin@marketing-os.local"
    assert res1["brand_slug"] == "apex-horizon"
    assert res1["guidelines_indexed"] == 3

    # Re-run: must succeed with 0 errors and preserve state
    res2 = await seed()
    assert res2["admin_user"] == "admin@marketing-os.local"
    assert res2["brand_slug"] == "apex-horizon"
    assert res2["guidelines_indexed"] == 3
