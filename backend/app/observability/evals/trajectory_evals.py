def evaluate_trajectory_order(executed_tools: list[str], expected_order: list[str]) -> bool:
    positions = [executed_tools.index(req) for req in expected_order if req in executed_tools]
    return len(positions) == len(expected_order) and positions == sorted(positions)
