#!/bin/sh
set -eu

if [ -n "${DRIFTWATCH_DATABASE_URL:-}" ]; then
  python tools/migrate.py
fi
exec "$@"
