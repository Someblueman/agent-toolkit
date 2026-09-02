"""
Simplified Implementation: Modern `@dataclass(slots=True)` & Pattern Matching (`match/case`)

Replaces the entire Visitor pattern and ABC hierarchy with concise, immutable,
slot-backed dataclasses and a single pure recursive function using Python 3.10+ `match/case`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Union


@dataclass(slots=True, frozen=True)
class Literal:
    value: float


@dataclass(slots=True, frozen=True)
class Variable:
    name: str


@dataclass(slots=True, frozen=True)
class BinaryOp:
    op: str
    left: Expr
    right: Expr


@dataclass(slots=True, frozen=True)
class UnaryOp:
    op: str
    operand: Expr


Expr = Union[Literal, Variable, BinaryOp, UnaryOp]


def _eval_binary(op: str, left_val: float, right_val: float) -> float:
    match op:
        case "+":
            return left_val + right_val
        case "-":
            return left_val - right_val
        case "*":
            return left_val * right_val
        case "/":
            if right_val == 0:
                raise ZeroDivisionError("Division by zero in AST evaluation")
            return left_val / right_val
        case _:
            raise ValueError(f"Unknown binary operator: {op}")


def evaluate_expression(expr: Expr, env: Dict[str, float]) -> float:
    """
    Evaluates an AST expression tree using structural pattern matching.
    """
    match expr:
        case Literal(val):
            return float(val)

        case Variable(name):
            if name not in env:
                raise KeyError(f"Undefined variable: {name}")
            return float(env[name])

        case BinaryOp(op, left, right):
            l_val = evaluate_expression(left, env)
            r_val = evaluate_expression(right, env)
            return _eval_binary(op, l_val, r_val)

        case UnaryOp(op, operand):
            val = evaluate_expression(operand, env)
            if op == "+":
                return val
            elif op == "-":
                return -val
            else:
                raise ValueError(f"Unknown unary operator: {op}")

        case _:
            raise TypeError(f"Invalid AST node type: {type(expr).__name__}")
