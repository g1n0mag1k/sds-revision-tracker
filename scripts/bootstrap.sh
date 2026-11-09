#!/usr/bin/env bash
# Repeatable dependency installation for SDS Revision Tracker.
# Creates ./.venv (if missing) and installs pinned requirements.
# It does NOT initialize/reset the database, download SDS documents,
# or start a server.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

if [ ! -x .venv/bin/python ]; then
  echo "Creating virtual environment in .venv"
  "$PYTHON" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt

echo
echo "Dependencies installed. Next steps (run explicitly):"
echo "  .venv/bin/python -m sdstracker init-db"
echo "  .venv/bin/python -m sdstracker demo-data"
echo "  .venv/bin/streamlit run app.py"
