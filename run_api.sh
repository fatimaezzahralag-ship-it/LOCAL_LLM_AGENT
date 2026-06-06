#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_python="$project_root/.venv/bin/python"

if [[ ! -x "$venv_python" ]]; then
  echo "Virtualenv Python not found at $venv_python"
  echo "Create it with: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

exec "$venv_python" -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000