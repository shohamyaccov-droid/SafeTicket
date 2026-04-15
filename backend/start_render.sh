#!/usr/bin/env bash
# Render web start: migrate against live Postgres, then seed/idempotency hooks, then Gunicorn.
# Build phase also runs migrate in ../build_render.sh; this guarantees runtime schema matches code.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "[start_render] Applying database migrations..."
python manage.py migrate --noinput

echo "[start_render] Idempotent production seed (skips if DB unavailable)..."
python seed_production.py

echo "[start_render] Admin promotion hook..."
python fix_admin.py

echo "[start_render] Starting Gunicorn on port ${PORT:-8000}..."
exec gunicorn safeticket.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers 1 --worker-class gthread --threads 2 --timeout 90
