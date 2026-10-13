import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.test_e2e_agent import (
    test_benchmark_xml_dataset_suite_evaluation,
    test_continuous_learning_flywheel_distillation,
    test_edge_case_resilience_guards,
    test_weekly_operating_cadence_orchestrator,
)

if __name__ == "__main__":
    test_continuous_learning_flywheel_distillation()
    test_edge_case_resilience_guards()
    test_weekly_operating_cadence_orchestrator()
    test_benchmark_xml_dataset_suite_evaluation()
    print("ALL TSK-09 TESTS PASSED.")
