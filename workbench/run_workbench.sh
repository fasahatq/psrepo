#!/usr/bin/env bash
# Perfect Store AI Workbench — starts the FastAPI backend (:8020) and the Vite
# dev server (:5173) together. Ctrl-C stops both. Nothing is deployed.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"

PY="$ROOT/venv/bin/python"
[ -x "$PY" ] || PY="python3"

if ! "$PY" -c "import fastapi" 2>/dev/null; then
  echo "→ installing backend deps (fastapi, uvicorn, python-multipart)"
  "$PY" -m pip install -r server/requirements.txt
fi

if [ ! -d node_modules ]; then
  echo "→ installing frontend deps (npm install)"
  npm install
fi

pids=()
cleanup() { for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

echo "→ API   http://localhost:8020  (docs at /docs)"
( cd "$ROOT" && "$PY" -m uvicorn workbench.server.app:app --port 8020 --reload ) &
pids+=($!)

echo "→ UI    http://localhost:5173"
npm run dev -- --host &
pids+=($!)

wait
