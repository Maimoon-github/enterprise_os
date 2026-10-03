"""OWASP Top 10 for Agentic Applications (2026) Adversarial Certification Runner.
Executes the comprehensive 17-vector red-team test matrix and compiles
an authoritative executive security certification report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OWASP_AGENTIC_2026_MAPPING = {
    "ASI-01": {
        "title": "Agent Goal Hijacking & Prompt Injection",
        "tests": [
            "test_adversarial_rag_indirect_prompt_injection",
            "test_adversarial_agent_goal_hijack_detection",
            "test_adversarial_multi_agent_collusion_confused_deputy",
        ],
    },
    "ASI-02": {
        "title": "Tool Misuse & Malicious MCP Injection",
        "tests": [
            "test_adversarial_malicious_mcp_response_injection",
            "test_adversarial_tool_misuse_parameter_tampering",
        ],
    },
    "ASI-03": {
        "title": "Identity, Privilege Abuse & Delegation Flaws",
        "tests": [
            "test_adversarial_forged_and_replayed_taskgrant",
            "test_adversarial_privilege_escalation",
            "test_adversarial_compromised_worker_direct_db_block",
        ],
    },
    "ASI-04": {
        "title": "Memory & Context Poisoning",
        "tests": [
            "test_adversarial_memory_poisoning_prevention",
            "test_adversarial_poisoned_brand_persona",
            "test_adversarial_poisoned_telemetry_promotion",
        ],
    },
    "ASI-05": {
        "title": "Agentic Supply-Chain & Evidence Envelope Compromise",
        "tests": [
            "test_adversarial_specialist_envelope_tampering",
        ],
    },
    "ASI-06": {
        "title": "Sandbox & Execution Boundary Escape",
        "tests": [
            "test_adversarial_egress_grant_abuse",
            "test_adversarial_sandbox_escape_path_traversal",
        ],
    },
    "ASI-07": {
        "title": "HITL Subversion & Provenance Falsification",
        "tests": [
            "test_adversarial_forged_hitl_approval_signature",
            "test_adversarial_provenance_tampering_detection",
        ],
    },
    "ASI-08": {
        "title": "Cross-Tenant Data Retrieval & Scope Leakage",
        "tests": [
            "test_adversarial_cross_tenant_data_retrieval",
        ],
    },
    "ASI-09": {
        "title": "Cascading Agentic Failure & Resource Exhaustion",
        "tests": [
            "test_adversarial_tool_misuse_parameter_tampering",
            "test_adversarial_egress_grant_abuse",
        ],
    },
    "ASI-10": {
        "title": "Trust, Telemetry & Audit Invalidation",
        "tests": [
            "test_adversarial_provenance_tampering_detection",
            "test_adversarial_poisoned_telemetry_promotion",
        ],
    },
}


def run_adversarial_matrix() -> dict[str, Any]:
    test_file = Path(__file__).parent / "test_owasp_agentic_top10.py"
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
    ]

    t0 = datetime.now(UTC)
    res = subprocess.run(cmd, capture_output=True, text=True)
    t1 = datetime.now(UTC)

    passed = res.returncode == 0
    raw_output = res.stdout + res.stderr

    matrix_results: dict[str, Any] = {}
    for code, info in OWASP_AGENTIC_2026_MAPPING.items():
        tests_status = []
        for t in info["tests"]:
            t_passed = f"{t} PASSED" in raw_output
            tests_status.append({"test_name": t, "status": "CONTAINED" if t_passed else "FAILED"})
        
        all_contained = all(ts["status"] == "CONTAINED" for ts in tests_status)
        matrix_results[code] = {
            "title": info["title"],
            "status": "SECURED" if all_contained else "VULNERABLE",
            "tests_evaluated": tests_status,
        }

    report = {
        "title": "OWASP Top 10 for Agentic Applications (2026) Certification Matrix",
        "verdict": "CERTIFIED_AGENTIC_RESILIENT" if passed else "FAILED",
        "total_threat_vectors_tested": 17,
        "threat_vectors_contained": 17 if passed else 0,
        "containment_rate_pct": 100.0 if passed else 0.0,
        "execution_duration_s": (t1 - t0).total_seconds(),
        "owasp_agentic_matrix": matrix_results,
    }

    return report


if __name__ == "__main__":
    rep = run_adversarial_matrix()
    print(json.dumps(rep, indent=2))
    if rep["verdict"] != "CERTIFIED_AGENTIC_RESILIENT":
        sys.exit(1)
