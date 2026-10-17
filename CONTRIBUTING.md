# Contributing to DriftWatch

Thanks for helping improve DriftWatch. Please keep changes focused, tested, and documented.

## Development setup

DriftWatch requires Python 3.12 and Node.js 22 for dashboard work.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,server]"
pytest
ruff check src tests tools
```

For the dashboard:

```powershell
npm ci --prefix dashboard
npm run build --prefix dashboard
```

## Pull requests

- Explain the user-visible or operational impact.
- Add or update tests for behavior changes.
- Update documentation and configuration examples when applicable.
- Do not commit credentials, local databases, generated assets, or customer data.
- Keep public APIs backward compatible unless the change is explicitly documented.

All pull requests must pass the CI workflow and receive review before merging.
