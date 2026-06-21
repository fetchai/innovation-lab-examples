import importlib.util
from pathlib import Path
import pytest

# Dynamically load the calculator_tools module (handles hyphenated parent folder)
calc_path = Path(__file__).resolve().parents[1] / "tools" / "calculator_tools.py"
spec = importlib.util.spec_from_file_location("calculator_tools", str(calc_path))
calculator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(calculator)
calculate = calculator.calculate


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("2+3", 5),
        ("10*5", 50),
        ("100/4", 25.0),
        ("2**3", 8),
        ("(2+3)*4", 20),
        ("sqrt(16)", 4.0),
        ("sin(0)", 0.0),
        ("cos(0)", 1.0),
        ("tan(0)", 0.0),
        ("log10(100)", 2.0),
        ("abs(-10)", 10),
        ("round(3.14159, 2)", 3.14),
        ("pow(2, 8)", 256),
        ("pi", 3.141592653589793),
        ("e", 2.718281828459045),
    ],
)
def test_valid_expressions(expr, expected):
    result = calculate(expr)
    if isinstance(expected, float):
        assert pytest.approx(expected, rel=1e-9) == result
    else:
        assert expected == result


@pytest.mark.parametrize(
    "expr",
    [
        'import("os")',
        'import("os").system("ls")',
        'eval("2+2")',
        'exec("print(1)")',
        'open("/etc/passwd")',
        'globals()',
        'locals()',
        '().__class__.__bases__[0]',
        'lambda x: x',
        '[1,2,3]',
        '{"a":1}',
        'compile("1+1", "", "eval")',
        'True',
        'False',
    ],
)
def test_malicious_inputs_rejected(expr):
    with pytest.raises(ValueError):
        calculate(expr)
