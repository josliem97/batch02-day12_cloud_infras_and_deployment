from __future__ import annotations

import ast
import operator as op
from typing import Any

from tools._shared import err

# Supported operators for safe mathematical expression evaluation
operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg
}

def eval_expr(expr: str) -> Any:
    return eval_ast(ast.parse(expr, mode='eval').body)

def eval_ast(node: ast.AST) -> Any:
    if isinstance(node, ast.Num): # Python < 3.8
        return node.n
    elif isinstance(node, ast.Constant): # Python >= 3.8
        return node.value
    elif isinstance(node, ast.BinOp):
        return operators[type(node.op)](eval_ast(node.left), eval_ast(node.right))
    elif isinstance(node, ast.UnaryOp):
        return operators[type(node.op)](eval_ast(node.operand))
    else:
        raise TypeError(node)

def calculate(expression: str = "") -> dict[str, Any]:
    """
    Safely evaluate a mathematical expression.
    Supports basic arithmetic: +, -, *, /, and ** (power).
    """
    try:
        # Remove whitespace
        expr = expression.replace(" ", "")
        result = eval_expr(expr)
        return {
            "tool": "calculator",
            "expression": expression,
            "result": result
        }
    except Exception as exc:
        return err("calculator", exc)
