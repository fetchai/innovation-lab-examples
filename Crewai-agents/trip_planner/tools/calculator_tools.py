import ast
import math
from typing import Any

try:
    from langchain.tools import tool
except Exception:
    def tool(name: str):
        def decorator(fn):
            return fn
        return decorator

# Whitelisted math functions and constants
_ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "pow": pow,
}

_ALLOWED_CONSTS = {"pi": math.pi, "e": math.e}

_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}

_ALLOWED_UNARYOPS = {ast.UAdd: lambda a: +a, ast.USub: lambda a: -a}


class _SafeEvaluator(ast.NodeVisitor):
    def visit(self, node: ast.AST) -> Any:
        node_type = type(node)
        if node_type in (ast.Expression, ast.Module):
            # expression wrapped as Module/Expression
            body = getattr(node, "body", None)
            if isinstance(body, list):
                if len(body) != 1:
                    raise ValueError("Only single expressions are allowed")
                return self.visit(body[0])
            return self.visit(node.body)
        return super().visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise ValueError(f"Operator {op_type.__name__} not allowed")
        left = self.visit(node.left)
        right = self.visit(node.right)
        try:
            return _ALLOWED_BINOPS[op_type](left, right)
        except ZeroDivisionError:
            raise ValueError("Division by zero")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARYOPS:
            raise ValueError(f"Unary operator {op_type.__name__} not allowed")
        operand = self.visit(node.operand)
        return _ALLOWED_UNARYOPS[op_type](operand)

    def visit_Call(self, node: ast.Call) -> Any:
        # Only allow simple name calls (no attribute access)
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct function calls are allowed")
        func_name = node.func.id
        if func_name not in _ALLOWED_FUNCS:
            raise ValueError(f"Function '{func_name}' is not allowed")
        # no keywords allowed
        if node.keywords:
            raise ValueError("Keyword arguments are not allowed")
        args = [self.visit(arg) for arg in node.args]
        return _ALLOWED_FUNCS[func_name](*args)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        raise ValueError(f"Use of name '{node.id}' is not allowed")

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed")

    # Reject lists, dicts, attributes, comprehensions, etc.
    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Unsupported expression: {node.__class__.__name__}")


@tool("Make a calculation")
def calculate(operation: str) -> Any:
    """Evaluate a mathematical expression safely.

    Only numeric literals, arithmetic operators, parentheses, and
    a small whitelist of math functions/constants are permitted.
    """
    if not isinstance(operation, str):
        raise ValueError("Operation must be a string")
    expression = operation.strip()
    if not expression:
        raise ValueError("Empty expression")
    try:
        node = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid syntax in mathematical expression") from exc
    evaluator = _SafeEvaluator()
    result = evaluator.visit(node)
    # Keep numeric types only
    if isinstance(result, (int, float)):
        return result
    raise ValueError("Expression did not evaluate to a numeric result")


class CalculatorTools:
    calculate = calculate
