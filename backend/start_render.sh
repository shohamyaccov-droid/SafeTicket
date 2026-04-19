#!/usr/bin/env bash
# Render web start: migrate against live Postgres, then seed/idempotency hooks, then Gunicorn.
# Build phase also runs migrate in ../build_render.sh; this guarantees runtime schema matches code.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Fail fast with a clear message if the DB env var is missing (common after DB plan changes / new instances).
if [ "${RENDER:-}" = "true" ]; then
  if [ -z "${DATABASE_URL:-}" ]; then
    echo "[start_render] FATAL: DATABASE_URL is empty. Link Postgres to this service or set Internal Database URL."
    exit 1
  fi
  # Log connection target only (never print credentials).
  python -c "
import os
from urllib.parse import urlparse, unquote
raw = os.environ.get('DATABASE_URL', '')
if not raw:
    print('[start_render] DATABASE_URL: (empty)')
else:
    u = urlparse(raw)
    host = u.hostname or '(no host)'
    port = u.port or 'default'
    db = (u.path or '').lstrip('/') or '(no db name)'
    print(f'[start_render] DATABASE_URL -> {u.scheme}://{host}:{port}/{db} (user={unquote(u.username) if u.username else \"?\"})')
" || true
fi

echo "[start_render] Applying database migrations..."
python manage.py migrate --noinput

echo "[start_render] Idempotent production seed (skips if DB unavailable)..."
python seed_production.py

echo "[start_render] Admin promotion hook..."
python fix_admin.py

echo "[start_render] Starting Gunicorn on port ${PORT:-8000}..."
exec gunicorn safeticket.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers 1 --worker-class gthread --threads 2 --timeout 90
