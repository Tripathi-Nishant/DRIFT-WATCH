# Public launch checklist

## Required configuration

- Use PostgreSQL and run the API and `driftwatch-worker` as separate services.
- Put Caddy, Cloudflare, or an equivalent WAF in front of the API.
- Set `DRIFTWATCH_ALLOWED_ORIGINS`, `DRIFTWATCH_APP_URL`, and strong secret values.
- Configure SMTP variables to deliver approved beta invitations.
- Set an edge rate limit/CAPTCHA on `POST /api/v1/access-requests`.
- Keep PostgreSQL private and enable encrypted automated backups.

## Operations

- Probe `/healthz`, `/readyz`, and `/metrics`.
- Ship container logs to a retained log platform.
- Alert on 5xx responses, failed schedule runs, database saturation, and backup failures.
- Run `tools/backup_postgres.py` daily and perform a monthly restore drill.
- Configure an error tracker or OpenTelemetry collector at the reverse proxy/host.

## Commercial readiness

Usage quotas and billing should be enforced at the organization boundary before
charging customers. The current API-key and organization model is the correct
integration point; add a metering worker and provider webhook reconciliation
before enabling paid plans.

## Release

Create a version tag such as `v0.1.1`. The release workflow builds the wheel,
publishes it to PyPI using `PYPI_API_TOKEN`, and attaches the artifacts to a
GitHub release.
