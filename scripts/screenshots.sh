#!/bin/bash
# About four minutes. Builds the page, opens it from the file system in headless Chrome with a fresh profile, takes
# every tab and every presenter step at 1440 and 1280 pixels and every tab at tablet and phone widths, checks the line
# rule, overlaps, console errors and network requests, and prints the report, memo and deck PDFs into outputs/.
# Results land in scripts/out/.
# Run from the build folder:   bash scripts/screenshots.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3
"$PY" build.py
"$PY" scripts/browser_check.py "$@"
