import ast
import os
from dataclasses import dataclass
from operator import add, floordiv, mod, mul, pow, sub, truediv
from typing import Any


@dataclass(frozen=True)
class CodeExecutionResult:
    success: bool
    output: str = ""
    error: str | None = None


def execute_code(source: str) -> CodeExecutionResult:
    if os.environ.get("INSIGHT_GRAPH_ENABLE_CODE_EXECUTION", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        return CodeExecutionResult(success=False, error="code execution disabled")
    try:
        tree = ast.parse(source, mode="eval")
        value = _evaluate_expression(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError):
        return CodeExecutionResult(success=False, error="unsupported expression")
    return CodeExecutionResult(success=True, output=str(value))


def _evaluate_expression(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_expression(node.operand)
    if isinstance(node, ast.BinOp):
        operator = _operator_for(node.op)
        return operator(_evaluate_expression(node.left), _evaluate_expression(node.right))
    raise ValueError("unsupported expression")


def _operator_for(node: ast.operator):
    operators = {
        ast.Add: add,
        ast.Sub: sub,
        ast.Mult: mul,
        ast.Div: truediv,
        ast.FloorDiv: floordiv,
        ast.Mod: mod,
        ast.Pow: pow,
    }
    for operator_type, operator_fn in operators.items():
        if isinstance(node, operator_type):
            return operator_fn
    raise ValueError("unsupported expression")
