#!/bin/bash
# About a minute. Creates .venv with Python 3.12 or newer and installs openpyxl, which the tests use as an
# independent check that every workbook the build writes opens in a real spreadsheet library. The build itself
# needs only the standard library.
# Run from the build folder:   bash scripts/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=""
for cand in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    PY="$(command -v "$cand")"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "No Python 3.12 or newer was found. Run 'brew install python@3.12', then run this again."
  exit 1
fi
echo "Using $PY ($("$PY" --version))"
"$PY" -m venv .venv
.venv/bin/python3 -m pip install --quiet --upgrade pip
.venv/bin/python3 -m pip install --quiet "openpyxl==3.1.5"
.venv/bin/python3 -c 'import sys, openpyxl; print("Ready: Python", sys.version.split()[0], "with openpyxl", openpyxl.__version__)'
