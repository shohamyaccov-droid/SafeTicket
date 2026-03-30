#!/usr/bin/env bash
# Render build: Node (nvm if needed) → Vite frontend → Django migrate/collectstatic.
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
npm ci
npm run build

cd "$ROOT/backend"
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "build_render.sh finished OK"
