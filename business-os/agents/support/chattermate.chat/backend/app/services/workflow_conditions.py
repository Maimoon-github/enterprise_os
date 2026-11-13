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

# Evaluates workflow condition nodes.
#
# The structure of a condition is fixed before any variable is looked up, and
# variable values are only ever compared, never parsed. A visitor's answer such
# as `x" OR "a" === "a` is therefore just text and cannot steer routing.

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.logger import get_logger

logger = get_logger(__name__)

# Returned by resolve_variable when no value is stored under the name.
MISSING = object()

OPERATORS = frozenset({"===", "!==", ">", "<", ">=", "<=", "includes", "startsWith", "endsWith"})
_ALIASES = {"==": "===", "!=": "!==", "contains": "includes"}
_NUMERIC = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def resolve_variable(name: str, workflow_state: Optional[Dict[str, Any]]) -> Any:
    """Look up a `{{name}}` value: `node_id.field`, a top-level variable such as
    user_message, or a field from any node (latest wins). MISSING if absent."""
    variables = (workflow_state or {}).get("variables") or {}
    node_variables = {k: v for k, v in variables.items() if isinstance(v, dict)}
    name = name.strip()

    if "." in name:
        node_id, field_name = (part.strip() for part in name.split(".", 1))
        scoped = node_variables.get(node_id, {})
        return scoped[field_name] if field_name in scoped else MISSING

    if name in variables and name not in node_variables:
        return variables[name]
    for node_id in reversed(list(node_variables)):
        if name in node_variables[node_id]:
            return node_variables[node_id][name]
    return MISSING


def _as_text(value: Any) -> Optional[str]:
    if value is MISSING or value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _as_number(text: str) -> Optional[float]:
    return float(text) if _NUMBER.fullmatch(text) else None


def compare(left: Any, operator: str, right: Any) -> bool:
    """Apply one operator to two values. Case-sensitive; surrounding whitespace
    is ignored. A missing value only satisfies `!==`."""
    operator = _ALIASES.get(operator, operator)
    if operator not in OPERATORS:
        logger.warning(f"Unknown condition operator '{operator}', treating as false")
        return False

    left_text, right_text = _as_text(left), _as_text(right)
    if operator == "!==":
        return left_text != right_text
    if left_text is None or right_text is None:
        return False
    if operator == "===":
        return left_text == right_text
    if operator == "includes":
        return right_text in left_text
    if operator == "startsWith":
        return left_text.startswith(right_text)
    if operator == "endsWith":
        return left_text.endswith(right_text)

    left_num, right_num = _as_number(left_text), _as_number(right_text)
    if left_num is None or right_num is None:
        logger.debug(f"Non-numeric '{operator}' comparison is false: {left_text!r} vs {right_text!r}")
        return False
    return _NUMERIC[operator](left_num, right_num)


# --- Builder groups -------------------------------------------------------

def _rule_is_complete(rule: Any) -> bool:
    # Mirrors the dashboard, which leaves half-filled rules out of the expression.
    if not isinstance(rule, dict):
        return False
    value = rule.get("value")
    return bool(rule.get("variable")) and bool(rule.get("operator")) and value is not None and str(value).strip() != ""


def _evaluate_rule(rule: Dict[str, Any], workflow_state: Dict[str, Any]) -> bool:
    name = str(rule["variable"]).strip().removeprefix("{{").removesuffix("}}")
    left = resolve_variable(name, workflow_state)
    if left is MISSING:
        logger.warning(f"Condition variable '{name}' has no value")
    return compare(left, str(rule["operator"]), rule["value"])


def evaluate_groups(groups: List[Any], workflow_state: Dict[str, Any]) -> Optional[bool]:
    """Groups are OR'ed; rules within a group use its logicalOperator (AND by
    default). None when no group holds a complete rule."""
    results = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        rules = [rule for rule in (group.get("rules") or []) if _rule_is_complete(rule)]
        if not rules:
            continue
        outcomes = [_evaluate_rule(rule, workflow_state) for rule in rules]
        any_rule = str(group.get("logicalOperator", "AND")).upper() == "OR"
        results.append(any(outcomes) if any_rule else all(outcomes))
    return any(results) if results else None


# --- Legacy expression strings ---------------------------------------------

class ConditionSyntaxError(ValueError):
    pass


_TOKEN = re.compile(r"""
    \s*(?:
        (?P<var>\{\{[^{}]+\}\})
      | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
      | (?P<method>\.(?:includes|startsWith|endsWith)\()
      | (?P<op>===|!==|==|!=|>=|<=|>|<|&&|\|\|)
      | (?P<paren>[()])
      | (?P<word>[^\s(){}"'=!<>&|.]+(?:\.(?!(?:includes|startsWith|endsWith)\()[^\s(){}"'=!<>&|.]+)*)
    )\s*""", re.VERBOSE)
_METHODS = frozenset({"includes", "startsWith", "endsWith"})
_WORD_KEYWORDS = {"AND": ("and", None), "OR": ("or", None), "contains": ("op", "contains")}

Token = Tuple[str, Optional[str]]


def _tokenize(expression: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    while pos < len(expression):
        match = _TOKEN.match(expression, pos)
        if not match or match.end() == pos:
            if expression[pos:].strip():
                raise ConditionSyntaxError(f"unexpected text at position {pos}")
            break
        pos = match.end()
        kind = match.lastgroup
        text = match.group(kind)
        if kind == "var":
            tokens.append(("var", text[2:-2].strip()))
        elif kind == "str":
            tokens.append(("lit", re.sub(r"\\(.)", r"\1", text[1:-1])))
        elif kind == "method":
            tokens.append(("op", text[1:-1]))
        elif kind == "op" and text in ("&&", "||"):
            tokens.append(("and" if text == "&&" else "or", None))
        elif kind == "paren":
            tokens.append((text, None))
        elif kind == "word":
            tokens.append(_WORD_KEYWORDS.get(text, ("lit", text)))
        else:
            tokens.append((kind, text))
    return tokens


class _Parser:
    """or := and (OR and)* ; and := primary (AND primary)* ;
    primary := '(' or ')' | operand op operand | operand .method( operand )"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        if not self.tokens:
            raise ConditionSyntaxError("empty condition")
        node = self._or()
        if self.pos != len(self.tokens):
            raise ConditionSyntaxError("unexpected trailing tokens")
        return node

    def _peek(self) -> Optional[str]:
        return self.tokens[self.pos][0] if self.pos < len(self.tokens) else None

    def _take(self, kind: str) -> Token:
        if self._peek() != kind:
            raise ConditionSyntaxError(f"expected {kind}")
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _or(self):
        items = [self._and()]
        while self._peek() == "or":
            self.pos += 1
            items.append(self._and())
        return ("or", items) if len(items) > 1 else items[0]

    def _and(self):
        items = [self._primary()]
        while self._peek() == "and":
            self.pos += 1
            items.append(self._primary())
        return ("and", items) if len(items) > 1 else items[0]

    def _primary(self):
        if self._peek() == "(":
            self.pos += 1
            node = self._or()
            self._take(")")
            return node
        left = self._operand()
        _, operator = self._take("op")
        right = self._operand()
        if operator in _METHODS:
            self._take(")")  # closes `.includes(`
        return ("cmp", left, operator, right)

    def _operand(self) -> Token:
        if self._peek() in ("var", "lit"):
            token = self.tokens[self.pos]
            self.pos += 1
            return token
        raise ConditionSyntaxError("expected a value")


def _evaluate_node(node, workflow_state: Dict[str, Any]) -> bool:
    kind = node[0]
    if kind == "or":
        return any(_evaluate_node(item, workflow_state) for item in node[1])
    if kind == "and":
        return all(_evaluate_node(item, workflow_state) for item in node[1])
    _, left, operator, right = node
    return compare(_operand_value(left, workflow_state), operator, _operand_value(right, workflow_state))


def _operand_value(token: Token, workflow_state: Dict[str, Any]) -> Any:
    kind, text = token
    if kind == "lit":
        return text
    value = resolve_variable(text, workflow_state)
    if value is MISSING:
        logger.warning(f"Condition variable '{text}' has no value")
    return value


def evaluate_expression(expression: str, workflow_state: Dict[str, Any]) -> bool:
    """Evaluate a stored `condition_expression`. Unreadable conditions are false."""
    try:
        tree = _Parser(_tokenize(expression)).parse()
    except (ConditionSyntaxError, RecursionError) as e:
        logger.warning(f"Unreadable condition {expression!r} ({e}), treating as false")
        return False
    return _evaluate_node(tree, workflow_state)


def evaluate_condition_config(config: Dict[str, Any], workflow_state: Dict[str, Any]) -> Optional[bool]:
    """Evaluate a condition node's config, preferring the builder's groups over
    the generated expression. None when neither holds a usable condition."""
    groups = config.get("condition_groups")
    if isinstance(groups, list):
        result = evaluate_groups(groups, workflow_state)
        if result is not None:
            return result
    expression = config.get("condition_expression")
    if isinstance(expression, str) and expression.strip():
        return evaluate_expression(expression, workflow_state)
    return None
