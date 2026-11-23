"""The small expression language of the `consistency` rules in a CME spec file.

A rule compares two arithmetic expressions over the columns of one row:

    Q_supplied ≈ m_flow_supply_i / 3600 * 4180 * (T_supply_i - T_return_i)
    T_supply_i > T_return_i

* names are column keys; numbers, `+ - * / **` and brackets are allowed;
* `≈` (or `~=`) means "equal within `tolerance_relative`" of the right-hand side;
* or one comparison: `<`, `<=`, `>`, `>=`, `==`, `!=`.

Nothing else is accepted (no function calls, no attributes), so a spec file can
never run code. Example:

    >>> rule = parse_rule("a > b + 1")
    >>> sorted(rule.names), check_rule(rule, {"a": 3.0, "b": 1.0}).ok
    (['a', 'b'], True)
"""

import ast
import math
import operator
from collections.abc import Callable, Mapping
from dataclasses import dataclass

_APPROX = ("≈", "~=")

_BINARY: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_COMPARE: dict[type[ast.cmpop], tuple[str, Callable[[float, float], bool]]] = {
    ast.Lt: ("<", operator.lt),
    ast.LtE: ("<=", operator.le),
    ast.Gt: (">", operator.gt),
    ast.GtE: (">=", operator.ge),
    ast.Eq: ("==", operator.eq),
    ast.NotEq: ("!=", operator.ne),
}


@dataclass(frozen=True)
class Rule:
    """A parsed consistency rule."""

    text: str
    left: ast.expr
    right: ast.expr
    op: str  # "≈" or one of the comparison operators
    names: frozenset[str]


@dataclass(frozen=True)
class Outcome:
    """Result of a rule on one row."""

    ok: bool
    left: float
    right: float


def _check_node(node: ast.AST, names: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _check_node(node.body, names)
    elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        _check_node(node.left, names)
        _check_node(node.right, names)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        _check_node(node.operand, names)
    elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
        pass
    elif isinstance(node, ast.Name):
        names.add(node.id)
    else:
        raise ValueError(f"not allowed in a rule: '{ast.unparse(node)}'")


def _parse_side(text: str, names: set[str]) -> ast.expr:
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"cannot read '{text.strip()}': {exc.msg}") from exc
    _check_node(tree, names)
    return tree.body


def parse_rule(text: str) -> Rule:
    """Parse a rule; raises `ValueError` with a readable message if it is not allowed."""
    names: set[str] = set()
    for sign in _APPROX:
        if sign in text:
            left_text, _, right_text = text.partition(sign)
            if any(s in right_text for s in _APPROX):
                raise ValueError(f"use '{sign}' only once")
            left = _parse_side(left_text, names)
            right = _parse_side(right_text, names)
            return Rule(text, left, right, "≈", frozenset(names))
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"cannot read the rule: {exc.msg}") from exc
    node = tree.body
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1):
        raise ValueError("a rule needs '≈' or exactly one comparison (<, <=, >, >=, ==, !=)")
    if type(node.ops[0]) not in _COMPARE:
        raise ValueError(f"comparison not allowed: '{ast.unparse(node)}'")
    _check_node(node.left, names)
    _check_node(node.comparators[0], names)
    op = _COMPARE[type(node.ops[0])][0]
    return Rule(text, node.left, node.comparators[0], op, frozenset(names))


def evaluate(node: ast.expr, values: Mapping[str, float]) -> float:
    """Value of an (already checked) expression for one row."""
    if isinstance(node, ast.BinOp):
        return _BINARY[type(node.op)](evaluate(node.left, values), evaluate(node.right, values))
    if isinstance(node, ast.UnaryOp):
        return _UNARY[type(node.op)](evaluate(node.operand, values))
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.Name):
        return values[node.id]
    raise ValueError(f"not allowed in a rule: '{ast.unparse(node)}'")  # pragma: no cover


def check_rule(rule: Rule, values: Mapping[str, float], tolerance: float = 0.0) -> Outcome:
    """Apply a rule to one row. A division by zero or overflow counts as a failure."""
    try:
        left, right = evaluate(rule.left, values), evaluate(rule.right, values)
    except (ZeroDivisionError, OverflowError):
        return Outcome(False, math.nan, math.nan)
    if rule.op == "≈":
        ok = abs(left - right) <= tolerance * abs(right)
    else:
        compare = next(f for sign, f in _COMPARE.values() if sign == rule.op)
        ok = compare(left, right)
    return Outcome(ok, left, right)
