"""
Baseline Implementation: Legacy OOP Class Hierarchy & Visitor Pattern

Demonstrates an over-engineered GoF Visitor pattern with Abstract Base Classes,
manual constructors/dunder methods, double dispatch, and dynamic visitor state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ASTNode(ABC):
    @abstractmethod
    def accept(self, visitor: "ASTVisitor") -> Any:
        pass


class LiteralNode(ASTNode):
    def __init__(self, value: float) -> None:
        self._value = float(value)

    @property
    def value(self) -> float:
        return self._value

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_literal(self)

    def __repr__(self) -> str:
        return f"LiteralNode({self._value})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, LiteralNode) and self._value == other._value


class VariableNode(ASTNode):
    def __init__(self, name: str) -> None:
        self._name = str(name)

    @property
    def name(self) -> str:
        return self._name

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_variable(self)

    def __repr__(self) -> str:
        return f"VariableNode('{self._name}')"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, VariableNode) and self._name == other._name


class BinaryOpNode(ASTNode):
    def __init__(self, op: str, left: ASTNode, right: ASTNode) -> None:
        self._op = op
        self._left = left
        self._right = right

    @property
    def op(self) -> str:
        return self._op

    @property
    def left(self) -> ASTNode:
        return self._left

    @property
    def right(self) -> ASTNode:
        return self._right

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_binary_op(self)

    def __repr__(self) -> str:
        return f"BinaryOpNode('{self._op}', {self._left}, {self._right})"

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, BinaryOpNode)
            and self._op == other._op
            and self._left == other._left
            and self._right == other._right
        )


class UnaryOpNode(ASTNode):
    def __init__(self, op: str, operand: ASTNode) -> None:
        self._op = op
        self._operand = operand

    @property
    def op(self) -> str:
        return self._op

    @property
    def operand(self) -> ASTNode:
        return self._operand

    def accept(self, visitor: "ASTVisitor") -> Any:
        return visitor.visit_unary_op(self)

    def __repr__(self) -> str:
        return f"UnaryOpNode('{self._op}', {self._operand})"

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, UnaryOpNode)
            and self._op == other._op
            and self._operand == other._operand
        )


class ASTVisitor(ABC):
    @abstractmethod
    def visit_literal(self, node: LiteralNode) -> Any:
        pass

    @abstractmethod
    def visit_variable(self, node: VariableNode) -> Any:
        pass

    @abstractmethod
    def visit_binary_op(self, node: BinaryOpNode) -> Any:
        pass

    @abstractmethod
    def visit_unary_op(self, node: UnaryOpNode) -> Any:
        pass


class EvaluatorVisitor(ASTVisitor):
    def __init__(self, env: Dict[str, float]) -> None:
        self.env = env

    def visit_literal(self, node: LiteralNode) -> float:
        return node.value

    def visit_variable(self, node: VariableNode) -> float:
        if node.name not in self.env:
            raise KeyError(f"Undefined variable: {node.name}")
        return self.env[node.name]

    def visit_binary_op(self, node: BinaryOpNode) -> float:
        left_val = node.left.accept(self)
        right_val = node.right.accept(self)
        if node.op == "+":
            return left_val + right_val
        elif node.op == "-":
            return left_val - right_val
        elif node.op == "*":
            return left_val * right_val
        elif node.op == "/":
            if right_val == 0:
                raise ZeroDivisionError("Division by zero in AST evaluation")
            return left_val / right_val
        else:
            raise ValueError(f"Unknown binary operator: {node.op}")

    def visit_unary_op(self, node: UnaryOpNode) -> float:
        val = node.operand.accept(self)
        if node.op == "-":
            return -val
        elif node.op == "+":
            return val
        else:
            raise ValueError(f"Unknown unary operator: {node.op}")


def evaluate_expression(node: ASTNode, env: Dict[str, float]) -> float:
    visitor = EvaluatorVisitor(env)
    return float(node.accept(visitor))
