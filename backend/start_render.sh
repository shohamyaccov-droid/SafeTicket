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

echo "[start_render] Concert catalog (Mor Ravia, Pe'er Tasi, Itay Levi, Eden Ben Zaken, Ben Tzur)..."
python manage.py seed_august_2026_concerts || true

echo "[start_render] High-demand Menora events (Odiya & Osher Cohen, Eyal Golan Sept 2026)..."
python manage.py seed_odiya_osher_hope_event || true
python manage.py seed_eyal_golan_menora || true

echo "[start_render] Itay Levi Caesarea Amphitheater (29.08 & 01.09.2026)..."
python manage.py seed_itay_levi_caesarea || true

echo "[start_render] Deactivate demo coupon AFFILIATE5 (no longer offered)..."
python manage.py deactivate_affiliate5_coupon || true

echo "[start_render] Platform coupon TRADETIX5 (global fee split, affiliate 0%)..."
python manage.py seed_platform_coupon || true

echo "[start_render] Ramat Gan Stadium venue sections (Sell page dropdown)..."
python manage.py seed_ramat_gan_sections || true

echo "[start_render] Caesarea Amphitheater venue sections (Sell page dropdown)..."
python manage.py seed_caesarea_sections || true

# Dummy/test marketplace inventory — OFF by default in production. Enable with RUN_DUMMY_SEED=true.
if [ "${RUN_DUMMY_SEED:-}" = "true" ]; then
  echo "[start_render] RUN_DUMMY_SEED=true — seeding dummy tickets..."
  python manage.py seed_dummy_tickets || true
  echo "[start_render] Mark seed/test marketplace tickets as taken (נתפס)..."
  python manage.py mark_tickets_taken || true
else
  echo "[start_render] Skipping seed_dummy_tickets (set RUN_DUMMY_SEED=true only for non-prod)."
fi

# FOMO / map QA: taken-only listings for empty active events (never touches stocked events).
echo "[start_render] Seed taken FOMO tickets for empty active events..."
python manage.py seed_taken_tickets || true

echo "[start_render] Admin promotion hook..."
python fix_admin.py

echo "[start_render] Starting Gunicorn on port ${PORT:-8000}..."
exec gunicorn safeticket.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers 1 --worker-class gthread --threads 2 --timeout 90
