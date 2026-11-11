# Scripts

These run in a normal terminal from the project folder. None of them calls a model or needs a key. Nothing here needs an account anywhere because the page replays the agents' recorded runs.

| Command | What it does |
|---|---|
| `bash scripts/bootstrap.sh` | Creates `.venv` with Python 3.12 or newer and installs openpyxl. The tests use it to open every workbook the build writes |
| `.venv/bin/python3 build.py` | Builds the whole site into `site/` from the seed in under a minute |
| `.venv/bin/python3 -m tests.run` | Runs every test and writes `data/test_results.json` for How it works to read |
| `bash scripts/recalc_check.sh` | LibreOffice recalculates the deal model from its formulas alone, and the tests compare every value with the Python model to the cent |
| `bash scripts/screenshots.sh` | Builds the site and drives headless Chrome through every tab, state, and presenter step. It reports the line rule, overlaps, console errors, and network requests, and it prints the report, memo, and deck PDFs into `outputs/`. It also takes the README's pictures into `docs/screenshots/` |

`scripts/out/` holds everything these steps write except the README's pictures, and it's gitignored.
