import ast
import operator
import re
from langchain.tools import tool

_ALLOWED_CHARS = re.compile(r"^[0-9+\-*/().\s]+$")
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _eval_math_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_math_node(node.left)
        right = _eval_math_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError("division by zero")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_math_node(node.operand)
    raise ValueError("unsupported expression")


def _safe_eval_math(expression: str) -> float:
    expr = expression.strip()
    if not expr or not _ALLOWED_CHARS.match(expr):
        raise ValueError("invalid characters")
    tree = ast.parse(expr, mode="eval")
    return _eval_math_node(tree.body)


class CalculatorTools:
    @tool("Make a calculation")
    def calculate(operation: str):
        """Useful to perform any mathematical calculations,
        like sum, minus, multiplication, division, etc.
        The input to this tool should be a mathematical
        expression, a couple examples are `200*7` or `5000/2*10`
        """
        try:
            return _safe_eval_math(operation)
        except ZeroDivisionError:
            return "Error: Division by zero"
        except (SyntaxError, ValueError, TypeError, OverflowError):
            return "Error: Invalid syntax in mathematical expression"
