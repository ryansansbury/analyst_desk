#!/bin/bash
# Under a minute. LibreOffice recalculates the deal model from its formulas alone, then the tests compare every
# value it computed with the Python model, to the cent for money.
#
# It converts a copy of the workbook that has formulas and no stored values, using a fresh LibreOffice profile set
# to always recalculate on load, so a pass can't come from values the build wrote. The recalculated file lands in
# scripts/out/recalc/, which is gitignored. LibreOffice is the app in the Mac's main Applications folder, or the
# soffice command if it's on the PATH.
# Run from the build folder:   bash scripts/recalc_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3
"$PY" build.py
SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
if [ ! -x "$SOFFICE" ]; then SOFFICE="$(command -v soffice || true)"; fi
if [ -z "$SOFFICE" ]; then echo "LibreOffice wasn't found. Install it or put soffice on the PATH, then run this again."; exit 1; fi
PROFILE="$PWD/scripts/out/lo-profile"
rm -rf "$PROFILE" scripts/out/recalc
mkdir -p "$PROFILE/user" scripts/out/recalc
cat > "$PROFILE/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="ODFRecalcMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>
XCU
"$SOFFICE" "-env:UserInstallation=file://$PROFILE" --headless --calc --convert-to "xlsx:Calc MS Excel 2007 XML" \
  --outdir scripts/out/recalc .cache/recalc/Brightrow_model_formulas.xlsx
"$PY" -m unittest tests.test_recalc -v 2>&1 | tail -8
echo "Done. The LibreOffice tile on How it works shows this result after the next build."
