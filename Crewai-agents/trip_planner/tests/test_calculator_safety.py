"""Regression tests for the trip_planner calculator tool.

The tool used to call eval() on an expression written by the LLM, so anything
the model could be talked into emitting ran as Python on the host. These tests
pin both halves of the fix: ordinary arithmetic still works, and the payloads
that made the old version dangerous are refused.

Test coverage originally proposed by @Chitranshu0 in PR #160.
"""

import pytest

from tools.calculator_tools import CalculatorTools

# The @tool decorator wraps the function; reach through to the callable.
calculate = getattr(CalculatorTools.calculate, "func", CalculatorTools.calculate)


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("200*7", 1400),
        ("5000/2*10", 25000.0),
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("-3 + 4", 1),
        ("2**10", 1024),
        ("10 % 3", 1),
        ("7 // 2", 3),
        ("1.5 * 2", 3.0),
    ],
)
def test_arithmetic_still_works(expression, expected):
    assert calculate(expression) == expected


@pytest.mark.parametrize(
    "payload",
    [
        "__import__('os').system('echo pwned')",
        "open('/etc/passwd').read()",
        "().__class__.__bases__[0].__subclasses__()",
        "exec('x=1')",
        "eval('1+1')",
        "globals()",
        "[x for x in range(10)]",
        "lambda: 1",
        "os.getcwd()",
    ],
)
def test_code_execution_is_refused(payload):
    result = calculate(payload)
    assert isinstance(result, str) and result.startswith("Error:")


def test_division_by_zero_is_reported_not_raised():
    assert calculate("1/0") == "Error: Division by zero"


def test_syntax_error_is_reported_not_raised():
    assert calculate("2 +") == "Error: Invalid syntax in mathematical expression"


def test_huge_exponent_is_refused_rather_than_hanging():
    # 9**9**9 would otherwise allocate for a very long time before returning.
    result = calculate("9**9**9")
    assert isinstance(result, str) and result.startswith("Error:")
