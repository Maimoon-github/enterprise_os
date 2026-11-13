"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.workflow import Workflow, WorkflowStatus
from app.models.workflow_node import WorkflowNode, NodeType
from app.services.workflow_conditions import (
    MISSING,
    compare,
    evaluate_condition_config,
    evaluate_expression,
    evaluate_groups,
    resolve_variable,
)
from app.services.workflow_execution import WorkflowExecutionService

NODE = "11111111-1111-1111-1111-111111111111"


def state(**fields):
    return {"variables": {NODE: dict(fields)}}


def rule(variable, operator, value):
    return {"id": "r", "variable": variable, "operator": operator, "value": value}


def group(*rules, op="AND"):
    return {"id": "g", "rules": list(rules), "logicalOperator": op}


# Payloads a visitor might type to try to force a branch.
HOSTILE_ANSWERS = [
    'basic" OR "a" === "a',
    "basic OR 1 === 1",
    'basic") || ("x" === "x',
    "basic === basic",
    "{{plan}}",
    "basic' OR 'a' === 'a",
    "') OR (1 > 0",
    ".includes(",
    "999 > 1 AND 1 < 2",
]


class TestResolveVariable:

    def test_field_scoped_and_top_level(self):
        workflow_state = {"variables": {NODE: {"plan": "pro"}, "user_message": "hi"}}
        assert resolve_variable("plan", workflow_state) == "pro"
        assert resolve_variable(f"{NODE}.plan", workflow_state) == "pro"
        assert resolve_variable(" user_message ", workflow_state) == "hi"

    def test_missing(self):
        assert resolve_variable("plan", {}) is MISSING
        assert resolve_variable("other.plan", state(plan="pro")) is MISSING


class TestCompare:

    @pytest.mark.parametrize("left,op,right,expected", [
        ("pro", "===", "pro", True),
        (" pro ", "===", "pro", True),
        ("Pro", "===", "pro", False),  # case-sensitive, as before
        ("pro", "!==", "basic", True),
        ("pro", "!==", "pro", False),
        ("I need a refund", "includes", "refund", True),
        ("I need a refund", "includes", "Refund", False),
        ("ORD-123", "startsWith", "ORD-", True),
        ("ORD-123", "startsWith", "123", False),
        ("me@example.com", "endsWith", "@example.com", True),
        ("me@example.com", "endsWith", "@other.com", False),
        ("hello", "contains", "ell", True),
        (True, "===", "true", True),
    ])
    def test_string_operators(self, left, op, right, expected):
        assert compare(left, op, right) is expected

    @pytest.mark.parametrize("left,op,right,expected", [
        ("150", ">", "100", True),
        ("100", ">", "150", False),
        ("100", ">=", "100", True),
        ("99.5", "<", "100", True),
        ("-3", "<=", "-3", True),
        (42, ">", "41", True),
        ("1e3", ">", "999", True),
    ])
    def test_numeric_comparisons(self, left, op, right, expected):
        assert compare(left, op, right) is expected

    @pytest.mark.parametrize("left,right", [
        ("zebra", "apple"),   # old code compared ord('z') > ord('a')
        ("apple", "100"),
        ("100", "lots"),
        ("", "1"),
        ("nan", "1"),
        ("inf", "1"),
        ("1,000", "1"),
    ])
    def test_non_numeric_ordering_is_false(self, left, right):
        for op in (">", "<", ">=", "<="):
            assert compare(left, op, right) is False

    def test_missing_value_only_satisfies_not_equals(self):
        assert compare(MISSING, "===", "pro") is False
        assert compare(MISSING, "includes", "p") is False
        assert compare(MISSING, ">", "1") is False
        assert compare(MISSING, "!==", "pro") is True

    def test_unknown_operator_is_false(self):
        assert compare("a", "~=", "a") is False


class TestConditionGroups:

    def test_and_group(self):
        groups = [group(rule("plan", "===", "pro"), rule("seats", ">", "3"))]
        assert evaluate_groups(groups, state(plan="pro", seats="5")) is True
        assert evaluate_groups(groups, state(plan="pro", seats="2")) is False
        assert evaluate_groups(groups, state(plan="basic", seats="5")) is False

    def test_or_group(self):
        groups = [group(rule("plan", "===", "pro"), rule("seats", ">", "3"), op="OR")]
        assert evaluate_groups(groups, state(plan="basic", seats="5")) is True
        assert evaluate_groups(groups, state(plan="pro", seats="1")) is True
        assert evaluate_groups(groups, state(plan="basic", seats="1")) is False

    def test_groups_are_ored(self):
        groups = [
            group(rule("plan", "===", "pro"), rule("seats", ">", "3")),
            group(rule("country", "===", "IN"), rule("email", "endsWith", ".edu"), op="OR"),
        ]
        assert evaluate_groups(groups, state(plan="pro", seats="9", country="US", email="a@b.com")) is True
        assert evaluate_groups(groups, state(plan="pro", seats="1", country="IN", email="a@b.com")) is True
        assert evaluate_groups(groups, state(plan="pro", seats="1", country="US", email="a@b.edu")) is True
        assert evaluate_groups(groups, state(plan="basic", seats="9", country="US", email="a@b.com")) is False

    def test_incomplete_rules_are_ignored_like_the_builder(self):
        groups = [group(rule("plan", "===", "pro"), rule("", "===", "x"), rule("seats", ">", ""))]
        assert evaluate_groups(groups, state(plan="pro")) is True

    def test_no_complete_rule_is_none(self):
        assert evaluate_groups([group(rule("plan", "===", ""))], state(plan="pro")) is None
        assert evaluate_groups([], state()) is None

    @pytest.mark.parametrize("answer", HOSTILE_ANSWERS)
    def test_customer_text_cannot_change_the_result(self, answer):
        groups = [group(rule("plan", "===", "pro"))]
        assert evaluate_groups(groups, state(plan=answer)) is False
        not_pro = [group(rule("plan", "!==", "pro"))]
        assert evaluate_groups(not_pro, state(plan=answer)) is True


class TestLegacyExpression:

    def test_builder_output_with_and_inside_parentheses(self):
        expression = '({{plan}} === "pro" AND {{seats}} > 3)'
        assert evaluate_expression(expression, state(plan="pro", seats="5")) is True
        assert evaluate_expression(expression, state(plan="pro", seats="3")) is False
        assert evaluate_expression(expression, state(plan="basic", seats="5")) is False

    def test_builder_output_with_or_between_groups(self):
        expression = '({{plan}} === "pro" AND {{seats}} > 3) OR ({{country}} === "IN" OR {{email}}.endsWith(".edu"))'
        assert evaluate_expression(expression, state(plan="pro", seats="5", country="US", email="x")) is True
        assert evaluate_expression(expression, state(plan="basic", seats="1", country="IN", email="x")) is True
        assert evaluate_expression(expression, state(plan="basic", seats="1", country="US", email="a@uni.edu")) is True
        assert evaluate_expression(expression, state(plan="basic", seats="9", country="US", email="x")) is False

    def test_and_binds_tighter_than_or(self):
        expression = '{{a}} === "1" OR {{b}} === "1" AND {{c}} === "1"'
        assert evaluate_expression(expression, state(a="1", b="0", c="0")) is True
        assert evaluate_expression(expression, state(a="0", b="1", c="0")) is False

    def test_js_logical_operators(self):
        assert evaluate_expression('{{a}} === "1" && {{b}} === "2"', state(a="1", b="2")) is True
        assert evaluate_expression('{{a}} === "1" || {{b}} === "2"', state(a="0", b="2")) is True

    def test_method_calls(self):
        workflow_state = state(msg="please refund order ORD-9")
        assert evaluate_expression('{{msg}}.includes("refund")', workflow_state) is True
        assert evaluate_expression('{{msg}}.startsWith("please")', workflow_state) is True
        assert evaluate_expression('{{msg}}.endsWith("ORD-9")', workflow_state) is True
        assert evaluate_expression('{{msg}}.includes("cancel")', workflow_state) is False

    def test_bare_words_and_numbers(self):
        assert evaluate_expression("{{plan}} === pro", state(plan="pro")) is True
        assert evaluate_expression("100 > 50", {}) is True
        assert evaluate_expression("10.5 < 20.3", {}) is True
        assert evaluate_expression("hello contains ell", {}) is True
        assert evaluate_expression("{{email}} === a@b.com", state(email="a@b.com")) is True

    def test_quoted_literal_keeps_operators_as_text(self):
        assert evaluate_expression('{{q}} === "a OR b"', state(q="a OR b")) is True
        assert evaluate_expression('{{q}} === "say \\"hi\\""', state(q='say "hi"')) is True

    @pytest.mark.parametrize("answer", HOSTILE_ANSWERS)
    def test_customer_text_cannot_change_the_result(self, answer):
        assert evaluate_expression('{{plan}} === "pro"', state(plan=answer)) is False
        assert evaluate_expression('({{plan}} === "pro" AND {{seats}} > 3)', state(plan=answer, seats="9")) is False
        assert evaluate_expression('{{plan}}.includes("zzz")', state(plan=answer)) is False

    def test_missing_variable_is_not_a_match(self):
        assert evaluate_expression('{{nope}}.includes("o")', state()) is False
        assert evaluate_expression('{{nope}} === "{{nope}}"', state()) is False

    @pytest.mark.parametrize("expression", [
        "this is not a condition",
        "{{plan}}",
        '({{plan}} === "pro"',
        '{{plan}} === "pro")',
        '{{plan}} === "pro" AND',
        '{{plan}}.includes("pro"',
        '{{plan}} === "unterminated',
        "",
    ])
    def test_unreadable_is_false(self, expression):
        assert evaluate_expression(expression, state(plan="pro")) is False


class TestConditionConfig:

    def test_groups_win_over_expression(self):
        config = {
            "condition_groups": [group(rule("plan", "===", "pro"))],
            "condition_expression": '{{plan}} === "basic"',
        }
        assert evaluate_condition_config(config, state(plan="pro")) is True

    def test_expression_only_legacy_config(self):
        assert evaluate_condition_config({"condition_expression": "{{plan}} === pro"}, state(plan="pro")) is True

    def test_empty_groups_fall_back_to_expression(self):
        config = {"condition_groups": [group(rule("", "===", ""))], "condition_expression": "{{n}} > 1"}
        assert evaluate_condition_config(config, state(n="2")) is True

    def test_nothing_usable_is_none(self):
        assert evaluate_condition_config({}, state()) is None
        assert evaluate_condition_config({"condition_groups": [], "condition_expression": "  "}, state()) is None


# --- Condition node routing ----------------------------------------------

@pytest.fixture
def service():
    return WorkflowExecutionService(Mock())


@pytest.fixture
def workflow():
    wf = MagicMock(spec=Workflow)
    wf.id = uuid4()
    wf.status = WorkflowStatus.PUBLISHED
    return wf


def _condition_node(config, *labels):
    node = Mock(spec=WorkflowNode)
    node.id = uuid4()
    node.name = "Is Pro"
    node.node_type = NodeType.CONDITION
    node.config = config
    node.outgoing_connections = [
        Mock(target_node_id=uuid4(), label=label, condition=None) for label in labels
    ]
    node.incoming_connections = []
    return node


def _target(node, label):
    return next(c.target_node_id for c in node.outgoing_connections if c.label == label)


class TestConditionNodeRouting:

    def test_routes_by_groups(self, service, workflow):
        node = _condition_node({"condition_groups": [group(rule("plan", "===", "pro"))]}, "true", "false")
        assert service._execute_condition_node(node, workflow, state(plan="pro")).next_node_id == _target(node, "true")
        assert service._execute_condition_node(node, workflow, state(plan="basic")).next_node_id == _target(node, "false")

    def test_labels_match_case_insensitively(self, service, workflow):
        node = _condition_node({"condition_expression": "1 > 2"}, "True", "False")
        assert service._execute_condition_node(node, workflow, {}).next_node_id == _target(node, "False")

    def test_condition_column_is_also_honoured(self, service, workflow):
        node = _condition_node({"condition_expression": "1 > 2"}, None, None)
        node.outgoing_connections[0].condition = "true"
        node.outgoing_connections[1].condition = "false"
        assert service._execute_condition_node(node, workflow, {}).next_node_id == node.outgoing_connections[1].target_node_id

    def test_missing_false_branch_never_takes_the_true_branch(self, service, workflow):
        node = _condition_node({"condition_expression": '{{plan}} === "pro"'}, "true")
        with patch("app.services.workflow_execution.logger") as log:
            result = service._execute_condition_node(node, workflow, state(plan="basic"))
        assert result.success is True
        assert result.next_node_id is None
        assert result.should_continue is False
        assert any("Is Pro" in str(call) and "'false'" in str(call) for call in log.warning.call_args_list)

    def test_missing_true_branch_stops(self, service, workflow):
        node = _condition_node({"condition_expression": '{{plan}} === "pro"'}, "false")
        assert service._execute_condition_node(node, workflow, state(plan="pro")).next_node_id is None

    def test_unlabelled_connection_is_not_a_branch(self, service, workflow):
        node = _condition_node({"condition_expression": '{{plan}} === "pro"'}, None)
        assert service._execute_condition_node(node, workflow, state(plan="pro")).next_node_id is None

    def test_no_condition_configured_is_an_error(self, service, workflow):
        node = _condition_node({}, "true", "false")
        result = service._execute_condition_node(node, workflow, state())
        assert result.success is False


class TestMissingBranchEndToEnd:
    """Ask -> condition with only a "true" branch. A false answer stops the run
    silently and clears the session's position, so the next message starts the
    workflow again from its first node; the true branch must not run."""

    @pytest.mark.asyncio
    async def test_false_answer_stops_instead_of_running_the_true_branch(self, service, workflow):
        ask = Mock(spec=WorkflowNode)
        ask.id = uuid4()
        ask.name = "Ask Plan"
        ask.node_type = NodeType.USER_INPUT
        ask.config = {"prompt_message": "Which plan?"}
        condition = _condition_node({"condition_expression": '{{ask_plan_input}} === "pro"'}, "true")
        pro = Mock(spec=WorkflowNode)
        pro.id = condition.outgoing_connections[0].target_node_id
        pro.node_type = NodeType.MESSAGE
        pro.config = {"message_text": "Pro customers get priority support."}
        pro.outgoing_connections = []
        pro.incoming_connections = [condition.outgoing_connections[0]]
        ask.incoming_connections = []
        ask.outgoing_connections = [Mock(target_node_id=condition.id)]
        condition.incoming_connections = [ask.outgoing_connections[0]]
        workflow.nodes = [ask, condition, pro]

        with patch.object(service.workflow_repo, "get_workflow_with_nodes_and_connections", return_value=workflow), \
             patch.object(service.session_repo, "add_workflow_history_entry"), \
             patch.object(service, "_update_session_workflow_state") as update_state:
            result = await service.execute_workflow(
                session_id="s", user_message='basic" OR "a" === "a', workflow_id=workflow.id,
            )

        assert result.success is True
        assert result.message == ""
        assert result.next_node_id is None
        assert "Pro customers get priority support." not in (result.intermediate_messages or [])
        update_state.assert_called_once()
        assert update_state.call_args.args[1] is None
