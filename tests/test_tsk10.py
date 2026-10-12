# pyright: reportMissingImports=false, reportGeneralTypeIssues=false
"""Validation tests for TSK-10: Bidirectional Command-and-Control Loop.
Validates typed command models, security containment to /home/gem,
observation feedback ingestion, and cyclic LangGraph loop convergence.
"""

import sys
from pathlib import Path
# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.loop.command_protocol import (
    BrowserActionCommand,
    CodeComputeCommand,
    FileIOCommand,
    ObservationResult,
    ShellExecCommand,
)
from core.loop.sandbox_controller import SandboxController
from core.nodes.closed_loop_node import (
    ClosedLoopState,
    build_closed_loop_graph,
    observation_ingest_node,
    sandbox_dispatch_node,
    strategy_node,
)
from core.state import BrandProfile


def test_typed_command_protocol_and_security_boundary():
    """Verify command schemas and strict path containment within /home/gem."""
    # 1. Valid command instantiations
    browser_cmd = BrowserActionCommand(
        action="navigate",
        url="https://client-store.com",
        screenshot_path="/home/gem/audit.png",
    )
    assert browser_cmd.command_type == "browser"
    assert browser_cmd.screenshot_path == "/home/gem/audit.png"

    shell_cmd = ShellExecCommand(
        command="ls -la",
        exec_dir="/home/gem/workspace",
    )
    assert shell_cmd.command_type == "shell"
    assert shell_cmd.exec_dir == "/home/gem/workspace"

    code_cmd = CodeComputeCommand(
        language="python",
        code="print(2 + 2)",
        cwd="/home/gem",
    )
    assert code_cmd.command_type == "code"

    file_cmd = FileIOCommand(
        operation="write",
        file_path="/home/gem/config.json",
        content='{"key": "value"}',
    )
    assert file_cmd.command_type == "file"

    # 2. Enforce security violations: path traversal
    traversal_caught = False
    try:
        FileIOCommand(
            operation="read",
            file_path="/home/gem/../etc/passwd",
        )
    except ValueError as e:
        if "Path traversal" in str(e):
            traversal_caught = True
    assert traversal_caught, "Expected ValueError for path traversal"

    # 3. Enforce security violations: outside /home/gem
    outside_caught = False
    try:
        ShellExecCommand(
            command="rm -rf /",
            exec_dir="/root",
        )
    except ValueError as e:
        if "restricted to container workspace" in str(e):
            outside_caught = True
    assert outside_caught, "Expected ValueError for path outside /home/gem"

    print("test_typed_command_protocol_and_security_boundary: PASSED")


def test_sandbox_controller_dispatch_and_observation_normalization():
    """Verify SandboxController dispatches typed commands and normalizes ObservationResult."""
    controller = SandboxController()

    # Browser dispatch
    b_cmd = BrowserActionCommand(action="get_markdown", url="https://store.com")
    b_obs = controller.dispatch(b_cmd)
    assert isinstance(b_obs, ObservationResult)
    assert b_obs.command_type == "browser"
    assert b_obs.status == "success"
    assert b_obs.dom_markdown is not None

    # Code dispatch
    c_cmd = CodeComputeCommand(language="python", code="x = 10; y = 20; print(x + y)")
    c_obs = controller.dispatch(c_cmd)
    assert isinstance(c_obs, ObservationResult)
    assert c_obs.command_type == "code"
    assert c_obs.status == "success"

    # Shell dispatch
    s_cmd = ShellExecCommand(command="echo 'SANDBOX_READY'")
    s_obs = controller.dispatch(s_cmd)
    assert isinstance(s_obs, ObservationResult)
    assert s_obs.command_type == "shell"
    assert s_obs.exit_code == 0

    # File dispatch
    f_cmd = FileIOCommand(operation="write", file_path="/home/gem/test.txt", content="Hello Sandbox")
    f_obs = controller.dispatch(f_cmd)
    assert isinstance(f_obs, ObservationResult)
    assert f_obs.command_type == "file"
    assert "/home/gem/test.txt" in f_obs.artifacts_created

    print("test_sandbox_controller_dispatch_and_observation_normalization: PASSED")


def test_cyclic_closed_loop_orchestration_and_convergence():
    """Verify cyclic LangGraph execution between strategy core and sandbox runtime."""
    graph = build_closed_loop_graph()

    initial_state: ClosedLoopState = {
        "brand_profile": BrandProfile(brand_name="AuraGlow Skincare"),
        "goal": "Audit storefront and persist optimization directive",
        "iteration_count": 0,
        "max_iterations": 5,
        "current_command": None,
        "current_observation": None,
        "history": [],
        "is_converged": False,
        "messages": [],
        "metadata": {"target_url": "https://auraglow-store.com"},
    }

    final_state = graph.invoke(initial_state)

    # Validate multi-turn cyclic execution
    assert final_state["is_converged"] is True
    assert final_state["iteration_count"] >= 3
    assert len(final_state["history"]) >= 3

    # Check turns recorded in history
    turns = [h["turn"] for h in final_state["history"]]
    assert turns == list(range(1, len(final_state["history"]) + 1))

    # Verify command types in history
    cmd_types = [h["command"]["command_type"] for h in final_state["history"]]
    assert "browser" in cmd_types
    assert "code" in cmd_types
    assert "shell" in cmd_types

    # Verify convergence message exists
    assert any("[Strategy Converged]" in str(m.content) for m in final_state["messages"])

    print("test_cyclic_closed_loop_orchestration_and_convergence: PASSED")


if __name__ == "__main__":
    test_typed_command_protocol_and_security_boundary()
    test_sandbox_controller_dispatch_and_observation_normalization()
    test_cyclic_closed_loop_orchestration_and_convergence()
    print("ALL TSK-10 TESTS PASSED.")
