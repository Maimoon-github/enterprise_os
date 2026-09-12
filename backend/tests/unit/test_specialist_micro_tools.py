"""Unit tests for the 7 specialist sandbox micro-tools (Layer 6)."""

from __future__ import annotations

import json
import pytest

from app.integrations.sandbox.micro_tools import (
    dispatch_micro_tool,
    execute_s_alloc,
    execute_s_attr,
    execute_s_code,
    execute_s_copy,
    execute_s_parse,
    execute_s_scrape,
    execute_s_val,
)
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


def test_s_copy_variant_generator_with_prohibited_terms() -> None:
    payload = {
        "task_id": "task-copy-1",
        "brand_voice": "punchy and premium",
        "objective": "Q4 launch",
        "prohibited_terms": "secret, formula",
    }
    result = execute_s_copy(payload)

    assert result["status"] == "success"
    assert result["brand_voice"] == "punchy and premium"
    assert "headline" in result
    assert float(result["hook_score"]) > 0.8
    # Best hook shouldn't contain prohibited terms
    variants = json.loads(result["variants"])
    for var in variants:
        assert "secret" not in var["hook"].lower()
        assert "formula" not in var["hook"].lower()


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


def test_s_scrape_price_and_ad_scraper() -> None:
    payload = {
        "task_id": "task-scrape-1",
        "competitor": "AcmeRival",
        "benchmark_price": "79.95",
        "active_ads": "28",
    }
    result = execute_s_scrape(payload)

    assert result["status"] == "success"
    assert result["competitor"] == "AcmeRival"
    assert result["benchmark_price"] == "79.95"
    assert result["active_ads"] == "28"
    assert "top_ad_hook" in result


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
        res = dispatch_micro_tool(cap, {"task_id": f"test-{cap.value}"})
        assert "status" in res
        assert res["task_id"] == f"test-{cap.value}"
