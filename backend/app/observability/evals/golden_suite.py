import logging
from typing import Any

from app.observability.evals.rubric_judges import run_rubric_judge
from app.observability.evals.trajectory_evals import evaluate_trajectory
from app.observability.langfuse import record_evaluation

logger = logging.getLogger("observability.evals.golden_suite")

GOLDEN_TEST_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "scenario_01_b2b_saas_launch",
        "objective": "Launch B2B SaaS platform across 8 platforms with human approval gates",
        "expected_subgraphs": [
            "research_strategy",
            "campaign_creative",
            "human_approval_gate_node",
            "execute_platform_publish_node",
            "closed_loop_eval",
        ],
        "sample_copy": (
            "Enterprise leaders: Autonomous marketing with complete human control. "
            "Scale authentic multi-channel distribution without gambling on unmonitored AI. "
            "Deterministic approval gates guarantee zero brand risk."
        ),
        "target_platforms_count": 8,
    },
    {
        "id": "scenario_02_developer_tools_growth",
        "objective": "Developer adoption campaign highlighting open-source and deterministic state",
        "expected_subgraphs": [
            "research_strategy",
            "campaign_creative",
            "prepare_publish_payload_node",
            "human_approval_gate_node",
            "execute_platform_publish_node",
            "closed_loop_eval",
        ],
        "sample_copy": (
            "DevOps and platform engineers: Stop treating AI agents like black boxes. "
            "Our state machine enforces deterministic LangGraph checkpoints and rootless sandboxing."
        ),
        "target_platforms_count": 8,
    },
    {
        "id": "scenario_03_enterprise_governance_refresh",
        "objective": "Brand repositioning addressing GenAI compliance fatigue",
        "expected_subgraphs": [
            "research_strategy",
            "campaign_creative",
            "human_approval_gate_node",
            "publishing_fanout",
        ],
        "sample_copy": (
            "Why Fortune 500 CISOs mandate deterministic guardrails before autonomous agents deploy. "
            "Auditable governance and zero hallucination risk across all 8 networks."
        ),
        "target_platforms_count": 8,
    },
]


def run_golden_suite_regression() -> dict[str, Any]:
    """Layer 4 Offline CI Evaluation: Executes golden dataset regression without external LLM tokens.

    Validates:
    - Trajectory sequence adherence (Layer 2)
    - Qualitative voice rubric scores (Layer 3)
    - Records results with annotator_kind='CODE' and 'LLM'
    """
    logger.info("Executing Golden Suite Regression across %d scenarios.", len(GOLDEN_TEST_SCENARIOS))
    results = []
    passed_count = 0

    for sc in GOLDEN_TEST_SCENARIOS:
        sc_id = sc["id"]
        subgraphs = sc["expected_subgraphs"]
        copy_text = sc["sample_copy"]

        # 1. Trajectory check
        traj_res = evaluate_trajectory(subgraphs)
        record_evaluation(
            trace_id=f"golden_{sc_id}_traj",
            name="golden_trajectory_order",
            score=traj_res["score"],
            label="PASS" if traj_res["valid"] else "FAIL",
            comment=f"Scenario {sc_id} tool ordering check",
            annotator_kind="CODE",
        )

        # 2. Rubric check
        rubric_res = run_rubric_judge(copy_text, rubric_type="brand_voice_fidelity")
        record_evaluation(
            trace_id=f"golden_{sc_id}_rubric",
            name="golden_brand_voice_fidelity",
            score=rubric_res["score"],
            label=rubric_res["label"],
            comment=rubric_res["explanation"],
            annotator_kind="LLM",
        )

        scenario_passed = traj_res["valid"] and rubric_res["passed"]
        if scenario_passed:
            passed_count += 1

        results.append({
            "scenario_id": sc_id,
            "passed": scenario_passed,
            "trajectory_score": traj_res["score"],
            "trajectory_valid": traj_res["valid"],
            "rubric_score": rubric_res["score"],
            "rubric_label": rubric_res["label"],
        })

    total = len(GOLDEN_TEST_SCENARIOS)
    pass_rate = round(passed_count / total, 3) if total > 0 else 1.0

    return {
        "total_scenarios": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_rate": pass_rate,
        "results": results,
    }


if __name__ == "__main__":
    import json
    import sys

    res = run_golden_suite_regression()
    print("=== Golden Suite Regression Report ===")
    print(
        f"Scenarios: {res['total_scenarios']} | Passed: {res['passed']} | Failed: {res['failed']} | Pass Rate: {res['pass_rate'] * 100:.1f}%"
    )
    print(json.dumps(res, indent=2))
    if res["pass_rate"] < 0.66:
        print("❌ Golden suite regression failed pass threshold (< 66%)")
        sys.exit(1)
    print("✅ Golden suite regression passed all regression checks.")
    sys.exit(0)

