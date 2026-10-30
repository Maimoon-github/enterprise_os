from app.observability.evals.trajectory_evals import evaluate_trajectory_order


def test_trajectory_evaluator():
    executed = ["BrandRAG", "Playwright", "DraftCopy", "ApprovalGate", "Publish"]
    expected = ["BrandRAG", "DraftCopy", "ApprovalGate", "Publish"]
    assert evaluate_trajectory_order(executed, expected) is True
