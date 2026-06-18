from langchain.tools import tool


class CalculatorTools:
    @tool("Make a calculation")
    def calculate(operation):
        """Useful to perform any mathematical calculations,
        like sum, minus, multiplication, division, etc.
        The input to this tool should be a mathematical
        expression, a couple examples are `200*7` or `5000/2*10`
        """
        import re

        if not re.match(r"^[0-9+\-*/().\s]+$", str(operation)):
            return "Error: Invalid characters in mathematical expression"
        try:
            return eval(operation)  # nosec B307
        except SyntaxError:
            return "Error: Invalid syntax in mathematical expression"
