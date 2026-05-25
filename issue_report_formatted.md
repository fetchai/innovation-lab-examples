### Summary
A security scan (using Bandit and npm audit) has identified multiple security vulnerabilities across the repository, including a Flask app running in debug mode, vulnerable NPM packages, missing request timeouts, and silent error suppression.

### Steps to reproduce
1. Run `bandit -r .` in the root of the repository to identify Python issues.
2. Run `npm install --package-lock-only && npm audit` inside `frontend-integration/frontend-integration` to see JavaScript dependency vulnerabilities.

### Expected behavior
The repository code should adhere to basic security guidelines:
- Flask should not be run in debug mode in production-like environments.
- HTTP requests via the `requests` library should specify a timeout to avoid hangs.
- Node dependencies should be regularly audited and updated.
- Exceptions should be properly caught and logged rather than silently ignored.

### Actual behavior
1. **Flask `debug=True` enabled (High Severity):** `frontend-integration/frontend_app.py:131` runs Flask with `debug=True`, which exposes an interactive debugger potentially allowing Remote Code Execution (RCE).
2. **Vulnerable NPM Dependencies (High Severity):** `frontend-integration/frontend-integration/package.json` uses outdated versions of `axios`, `next`, and other packages containing known SSRF, DoS, and Prototype Pollution vulnerabilities.
3. **Missing Request Timeouts (Medium Severity):** `web3/internet-computer/fetch/agent.py` and other agents call `requests.post()` and `requests.get()` without `timeout` parameters, risking denial of service if the endpoint hangs.
4. **Silent Error Suppression (Low Severity):** `video-to-map-agent/pdf_generator_agent.py` and `video-to-map-agent/weather_monitor_agent.py` globally suppress errors via `except Exception: pass`.

### Affected file or folder path
`frontend-integration/frontend_app.py`
`frontend-integration/frontend-integration/package.json`
`web3/internet-computer/fetch/agent.py`
`video-to-map-agent/pdf_generator_agent.py`

### Logs / traceback
```shell
# Bandit Finding (B201)
B201 (flask_debug_true) - frontend-integration/frontend_app.py:131
Severity: HIGH

# NPM Audit
9 vulnerabilities (4 moderate, 5 high) in frontend-integration/frontend-integration
```

### Environment
macOS, Python 3.11, Automated Scanner
