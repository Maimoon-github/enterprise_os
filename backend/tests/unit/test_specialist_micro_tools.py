"""Unit tests for the 7 specialist sandbox micro-tools (Layer 6)."""

from __future__ import annotations

import json
import pytest

from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.micro_tools import (
    dispatch_micro_tool,
    execute_s_attr,
    execute_s_code,
    execute_s_comp,
    execute_s_copy,
    execute_s_parse,
    execute_s_scrape,
    execute_s_val,
)
from app.integrations.sandbox.s_alloc_core import execute_s_alloc
from app.schemas.sandbox import SandboxCapability


def test_s_code_ast_parser_valid_code() -> None:
    code = (
        "class HeaderComponent:\n"
        "    def render(self, title: str) -> str:\n"
        "        return f'<h1>{title}</h1>'\n"
    )
    result = execute_s_code({"code": code, "task_id": "task-code-1"})

    assert result["status"] == "success"
    assert result["ast_valid"] == "True"
    assert int(result["function_count"]) >= 1
    assert int(result["class_count"]) >= 1
    assert "+++ b/components/" in result["diff"]


def test_s_code_ast_parser_syntax_error() -> None:
    code = "def broken_code(:\n    return False"
    result = execute_s_code({"code": code, "task_id": "task-code-err"})

    assert result["status"] == "lint_failed"
    assert result["ast_valid"] == "False"
    assert "SyntaxError" in result["syntax_error"]


def test_s_alloc_media_budget_optimizer() -> None:
    payload = {
        "task_id": "task-alloc-1",
        "budget": "20000.0",
        "channels": "meta,google,tiktok",
        "prior_roas_meta": "3.5",
        "prior_roas_google": "4.0",
        "prior_roas_tiktok": "2.5",
    }
    result = execute_s_alloc(payload)

    assert result["status"] == "success"
    allocations = json.loads(result["allocations"])
    assert "meta" in allocations
    assert "google" in allocations
    assert "tiktok" in allocations
    assert sum(allocations.values()) == pytest.approx(20000.0, abs=1.0)
    assert result["primary_channel"] == "google"  # Highest ROAS gets highest share


def test_s_copy_deterministic_utilities_screening_and_deduplication() -> None:
    # 1. Proves zero-generation when only high-level prompt is passed (no hallucinated copy)
    empty_payload = {
        "task_id": "task-copy-empty",
        "brand_voice": "punchy and premium",
        "objective": "Q4 launch",
        "prohibited_terms": "secret, formula",
    }
    empty_result = execute_s_copy(empty_payload)
    assert empty_result["status"] == "success"
    assert empty_result["deterministic"] == "true"
    assert empty_result["generative_execution"] == "denied"
    assert empty_result["variants_count"] == "0"

    # 2. Proves deterministic screening and deduplication on candidate variants
    payload = {
        "task_id": "task-copy-1",
        "brand_voice": "punchy and premium",
        "objective": "Q4 launch",
        "prohibited_terms": "secret, formula",
        "variants": json.dumps([
            {"hook": "Upgrade your enterprise workflows today.", "score": 0.92},
            {"hook": "Discover the secret to 10x ROI.", "score": 0.85},
            {"hook": "Here is the proven formula for growth.", "score": 0.88},
            {"hook": "Upgrade your enterprise workflows today.", "score": 0.92},  # duplicate
        ]),
    }
    result = execute_s_copy(payload)

    assert result["status"] == "success"
    assert result["brand_voice"] == "punchy and premium"
    assert result["deterministic"] == "true"
    assert int(result["variants_count"]) == 1

    # Filtered variants must not contain prohibited terms and duplicate removed
    variants = json.loads(result["variants"])
    assert len(variants) == 1
    assert "secret" not in variants[0]["hook"].lower()
    assert "formula" not in variants[0]["hook"].lower()


def test_s_val_claim_validator_clean_claim() -> None:
    payload = {
        "task_id": "task-val-1",
        "claim": "Demonstrated 30% increase in workflow velocity. *Results may vary based on deployment.",
        "required_disclaimer": "*Results may vary based on deployment.",
    }
    result = execute_s_val(payload)

    assert result["status"] == "success"
    assert result["is_compliant"] == "True"
    assert float(result["compliance_score"]) == 1.0


def test_s_val_claim_validator_flags_unsupported_absolute() -> None:
    payload = {
        "task_id": "task-val-2",
        "claim": "This revolutionary system cures all latency issues and is 100% guaranteed.",
    }
    result = execute_s_val(payload)

    assert result["status"] == "compliance_warning"
    assert result["is_compliant"] == "False"
    assert float(result["compliance_score"]) < 1.0
    violations = json.loads(result["violations"])
    assert any("cures" in v for v in violations)


def test_s_comp_price_and_ad_scraper() -> None:
    payload = {
        "task_id": "task-comp-1",
        "competitor": "AcmeRival",
        "benchmark_price": "79.95",
        "active_ads": "28",
    }
    result = execute_s_comp(payload)

    assert result["status"] == "success"
    assert result["competitor"] == "AcmeRival"
    assert result["benchmark_price"] == "79.95"
    assert result["active_ads"] == "28"
    assert "top_ad_hook" in result

    # Verify backward-compatibility alias produces identical result
    compat_result = execute_s_scrape(payload)
    assert compat_result == result


def test_s_parse_sentiment_and_objection_parser() -> None:
    payload = {
        "task_id": "task-parse-1",
        "feedback_text": "Product is excellent and fast, but the price is expensive and customer service was delayed.",
    }
    result = execute_s_parse(payload)

    assert result["status"] == "success"
    objections = json.loads(result["objections"])
    assert "price_sensitivity" in objections or "fulfillment_delay" in objections


def test_s_attr_attribution_and_decay_modeler() -> None:
    payload = {
        "task_id": "task-attr-1",
        "roas": "3.8",
        "days_active": "21.0",
    }
    result = execute_s_attr(payload)

    assert result["status"] == "success"
    decay = float(result["decay_multiplier"])
    assert 0.0 < decay < 1.0
    assert float(result["projected_roas"]) < 3.8
    assert "learning_delta" in result


def test_dispatch_micro_tool_dispatches_correct_capability() -> None:
    for cap in SandboxCapability:
        if cap == SandboxCapability.ALLOC:
            with pytest.raises(
                SandboxInvocationError,
                match="S_ALLOC is not available via host micro-tool dispatch",
            ):
                dispatch_micro_tool(cap, {"task_id": f"test-{cap.value}"})
            continue
        res = dispatch_micro_tool(cap, {"task_id": f"test-{cap.value}"})
        assert "status" in res
        assert res["task_id"] == f"test-{cap.value}"


def test_dispatch_micro_tool_unknown_capability_raises() -> None:
    with pytest.raises(ValueError, match="No specialist micro-tool found"):
        dispatch_micro_tool("S_NONEXISTENT", {"task_id": "test-invalid"})  # type: ignore[arg-type]


def test_s_alloc_handles_malformed_and_negative_inputs() -> None:
    # Negative budget should be normalized to 0.0
    res1 = execute_s_alloc({"budget": "-5000", "channels": "meta,google"})
    assert res1["status"] == "success"
    assert float(res1["budget_total"]) == 0.0

    # Non-numeric budget should fall back to default
    res2 = execute_s_alloc({"budget": "not-a-number", "channels": ""})
    assert res2["status"] == "success"
    assert float(res2["budget_total"]) == 10000.0
    allocations = json.loads(res2["allocations"])
    assert len(allocations) > 0


def test_s_comp_handles_malformed_inputs() -> None:
    payload = {
        "task_id": "task-comp-malformed",
        "benchmark_price": "invalid-price",
        "active_ads": "invalid-ads",
    }
    result = execute_s_comp(payload)
    assert result["status"] == "success"
    assert result["benchmark_price"] == "49.99"
    assert result["active_ads"] == "14"


def test_s_parse_handles_empty_and_neutral_text() -> None:
    result = execute_s_parse({"task_id": "task-parse-neutral", "feedback_text": "The box is blue."})
    assert result["status"] == "success"
    assert result["primary_sentiment"] == "neutral"
    assert "none_detected" in json.loads(result["objections"])


def test_s_attr_handles_extreme_and_negative_days() -> None:
    # Negative days should be clamped to 0.0 (no decay)
    res1 = execute_s_attr({"roas": "4.0", "days_active": "-10.0"})
    assert res1["status"] == "success"
    assert float(res1["decay_multiplier"]) == pytest.approx(1.0, abs=0.01)
    assert float(res1["projected_roas"]) == pytest.approx(4.0, abs=0.01)
    assert res1["fatigue_detected"] == "False"
    assert res1["recommended_action"] == "scale_spend"

    # Extreme days active should trigger fatigue
    res2 = execute_s_attr({"roas": "4.0", "days_active": "60.0"})
    assert res2["status"] == "success"
    assert float(res2["decay_multiplier"]) < 0.2
    assert res2["fatigue_detected"] == "True"
    assert res2["recommended_action"] == "refresh_creative_hooks"

