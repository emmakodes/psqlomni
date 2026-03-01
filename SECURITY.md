# Security Policy

## Security Tooling

This repository uses the following security controls:

- Dependabot version updates (`.github/dependabot.yml`)
- Dependency vulnerability scanning via `pip-audit`
- Optional CodeQL static analysis
- GitHub secret scanning and Dependabot alerts (enable in repository settings)

## Enable Optional CodeQL Auto-Runs

CodeQL is set to be optional by default to avoid unexpected CI cost/noise.

To enable automatic CodeQL scans on `push`, `pull_request`, and the weekly schedule:

1. Go to repository `Settings` -> `Secrets and variables` -> `Actions`.
2. Open the `Variables` tab.
3. Create repository variable `ENABLE_CODEQL` with value `true`.

Without that variable, CodeQL can still be run manually from the Actions tab using `workflow_dispatch`.

## Triage Expectations

- Critical: remediate within 24 hours
- High: remediate within 7 days
- Medium: remediate within 30 days

## Reporting a Vulnerability

Please report vulnerabilities privately through GitHub Security Advisories or by contacting the repository maintainers directly.
