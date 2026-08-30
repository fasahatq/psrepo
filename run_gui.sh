#!/usr/bin/env bash
# Launch the Perfect Store pipeline GUI (local browser dashboard, not hosted).
set -e
cd "$(dirname "$0")"
PY=venv/bin/python
[ -x "$PY" ] || PY=python3
exec "$PY" -m streamlit run gui/app.py "$@"
