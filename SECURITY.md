# Security Policy

## Supported Scope

This repository contains example projects and reference implementations.
Security reports are welcome for:

- Credential/token exposure in code or docs
- Unsafe defaults in example configurations
- Dependency vulnerabilities in maintained example projects
- Sensitive data leakage in logs or sample files

## Reporting a Vulnerability

**Do not open public issues for security vulnerabilities.**

Use GitHub private vulnerability reporting:

→ [Report a vulnerability](https://github.com/fetchai/innovation-lab-examples/security/advisories/new)

Include:

1. A clear summary of the issue
2. Steps to reproduce
3. Affected file paths and example folders
4. Potential impact
5. Suggested mitigation (if available)

## What we run on this repo

| Feature | Status |
|---|---|
| Dependabot alerts | Enabled |
| Dependabot security updates | Enabled |
| Dependabot version updates | Enabled (`.github/dependabot.yml`) |
| Secret scanning | Enabled |
| Push protection (secrets) | Enabled |
| Code scanning (CodeQL) | Enabled (`.github/workflows/codeql.yml`) |
| Private vulnerability reporting | Enabled |

## Disclosure Process

- We review and validate reports
- We prepare a fix and documentation update
- We publish coordinated disclosure details after remediation

## Security Best Practices for Contributors

- Never commit real secrets, API keys, or private keys
- Use `.env.example` for placeholder values
- Keep dependencies updated (Dependabot PRs auto-merge when CI is green)
- Avoid copying sensitive logs into public issues/PRs
