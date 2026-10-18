# Dashboard end-to-end tests

The dashboard is designed to run against the API at `http://127.0.0.1:8765`.
Install Playwright in a dedicated CI job, start the server, and exercise login,
overview, analysis, retraining, and audit navigation. The production CI job validates the
build; browser execution requires a running browser service and is kept separate
from unit tests.
