import ast
import operator

from langchain.tools import tool

# Arithmetic only. Anything outside this table is rejected rather than executed.
_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Bounds an expression like 9**9**9, which would otherwise hang the agent
# allocating an enormous integer before any result is returned.
_MAX_EXPONENT = 100


def _evaluate(node):
    """Evaluate one node of a parsed arithmetic expression."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("only numeric literals are allowed")
        return node.value

    if isinstance(node, ast.BinOp):
        op = _BINARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("unsupported operator")
        left, right = _evaluate(node.left), _evaluate(node.right)
        if op is operator.pow and abs(right) > _MAX_EXPONENT:
            raise ValueError("exponent too large")
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("unsupported operator")
        return op(_evaluate(node.operand))

    raise ValueError("unsupported expression")


class CalculatorTools:
    @tool("Make a calculation")
    def calculate(operation):
        """Useful to perform any mathematical calculations,
        like sum, minus, multiplication, division, etc.
        The input to this tool should be a mathematical
        expression, a couple examples are `200*7` or `5000/2*10`
        """
        # This runs on text produced by the model, so it must never reach eval():
        # an expression such as __import__('os').system(...) would otherwise run
        # arbitrary code. Parse it and walk only the arithmetic node types.
        try:
            tree = ast.parse(str(operation).strip(), mode="eval")
        except SyntaxError:
            return "Error: Invalid syntax in mathematical expression"

        try:
            return _evaluate(tree.body)
        except ZeroDivisionError:
            return "Error: Division by zero"
        except ValueError as exc:
            return f"Error: {exc}"
        except OverflowError:
            return "Error: Result too large"
