#!/usr/bin/env bash
# Render build: Node (nvm if needed) → Vite frontend → Django migrate/collectstatic.
# Migrations + idempotent catalog seeds (incl. seed_odiya_osher_hope_event, seed_eyal_golan_menora)
# run at container start (backend/start_render.sh) — no Render Shell required.
# Run from repo root: bash build_render.sh
# With Render rootDir=backend: bash ../build_render.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export VITE_API_URL="${VITE_API_URL:-https://safeticket-api.onrender.com}"
# Render sets RENDER_GIT_COMMIT during deploy builds — baked into the bundle to verify live assets.
export VITE_BUILD_ID="${VITE_BUILD_ID:-${RENDER_GIT_COMMIT:-unknown}}"
# Django collectstatic + WhiteNoise expose files at /static/... (not /assets/ at domain root).
export VITE_STATIC_BASE="${VITE_STATIC_BASE:-/static/}"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  fi
  # shellcheck disable=SC1090
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  nvm install 20
  nvm use 20
fi

echo "Using node=$(node -v) npm=$(npm -v) VITE_API_URL=$VITE_API_URL VITE_BUILD_ID=$VITE_BUILD_ID VITE_STATIC_BASE=$VITE_STATIC_BASE"

cd "$ROOT/frontend"
# Prefer reproducible npm ci; if package-lock.json drifts (common with optional platform
# packages like esbuild/@emnapi), fall back to npm install so deploys are not blocked.
if ! npm ci --no-audit --no-fund; then
  echo "build_render.sh: npm ci failed (lockfile out of sync) — falling back to npm install..."
  npm install --no-audit --no-fund
fi
npm run build

cd "$ROOT/backend"
pip install -r requirements.txt
if [ "${RENDER:-}" = "true" ] && [ -z "${DATABASE_URL:-}" ]; then
  echo "build_render.sh FATAL: DATABASE_URL is empty on Render — link Postgres to the web service."
  exit 1
fi

# FAILSAFE: hard-copy critical marketplace rows BEFORE migrate (and any ORM mutations).
# Do not invoke wipe/reset manage.py helpers in this script.
echo "build_render.sh: CRITICAL BACKUP (before migrate)..."
python manage.py backup_critical_data

python manage.py migrate --noinput

# CRITICAL RESCUE: Fault-tolerant restore from backup
# Standard loaddata is atomic: if ANY record fails (e.g., IntegrityError), the ENTIRE
# transaction rolls back and NO records are restored (deleted tickets stay deleted).
# Solution: Use force_restore command which attempts each object individually.
# If one fails (e.g., PK conflict), it logs a warning but CONTINUES.
# Result: All restorable records are recovered; broken ones are skipped.
# This ensures deleted tickets reappear even if some events already exist.
BACKUP_FILE="$ROOT/backend/critical_backups/latest_critical_backup.json"
if [ -f "$BACKUP_FILE" ]; then
  echo "build_render.sh: FAULT-TOLERANT RESTORE from latest_critical_backup.json..."
  python manage.py force_restore
  if [ $? -eq 0 ]; then
    echo "build_render.sh: Backup restore completed ✓"
  else
    echo "build_render.sh: WARNING - Backup restore had issues, see output above..."
  fi
else
  echo "build_render.sh: FATAL - Critical backup file not found at $BACKUP_FILE"
  echo "  This file MUST be committed to git for production deployment."
  echo "  File: backend/critical_backups/latest_critical_backup.json"
  echo "  Size: ~350 KB (JSON export of critical marketplace data)"
  exit 1
fi

# SEED: Populate NEXT 2026 festival events (Ramat Gan + Jerusalem)
# Runs AFTER restore so we add to the recovered data
python manage.py seed_next_2026
python manage.py collectstatic --noinput

echo "build_render.sh finished OK"
