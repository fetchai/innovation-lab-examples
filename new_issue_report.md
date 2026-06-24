## Title
High/Medium Severity Security Vulnerabilities (RCE via `eval`, Insecure Temp Dir)

## Description
A secondary security audit using `bandit` revealed additional vulnerabilities in this repository that should be addressed.

### 1. Remote Code Execution (RCE) via `eval()`
Using `eval()` on untrusted input from an LLM or user allows arbitrary Python code execution.
- `Crewai-agents/trip_planner/tools/calculator_tools.py`: The `calculate` tool calls `eval(operation)` on raw string inputs.
- `anthropic-quickstart/03-function-calling-agent/claude_function_agent.py`: Uses `eval()` for math evaluation. While `__builtins__` is cleared, `eval` is notoriously difficult to sandbox and can still be bypassed.
**Recommendation**: Use `ast.literal_eval`, a secure math parser, or validate the input characters strictly before evaluation.

### 2. Insecure Temporary Directory Usage
Hardcoding `/tmp` is flagged by security scanners as it can lead to symlink attacks or predictable paths on shared systems.
- `openclaw/fetchai-openclaw-orchestrator/connector/policy.py`: Hardcodes `"/tmp"`.
**Recommendation**: Use `tempfile.gettempdir()` instead.

### 3. Vulnerable `urllib.urlopen` Usage
The `urllib.request.urlopen` function is prone to protocol injection vulnerabilities.
- `openclaw/agentverse-caller/scripts/call.py`
- `Claude Agent SDK/real-estate-search-agent/sheets.py`
**Recommendation**: Replace `urllib` requests with the safer `requests` library where feasible, or enforce strict URL validation.

I will be submitting a PR to fix these issues shortly.
