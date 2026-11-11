"""Run every test quietly and write data/test_results.json, which the How it works tab reads.

    .venv/bin/python3 -m tests.run          (from the build folder)

It runs the same discovery as `python3 -m unittest discover -s tests -t . -q`, prints only failures and one
summary line, and exits 1 when anything fails.
"""
import json
import platform
import sys
import time
import traceback
import unittest
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT = HERE.joinpath("data", "test_results.json")


class Quiet(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.outcomes = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()] = "passed"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "failed"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "failed"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "skipped"


def module_of(test_id):
    parts = test_id.split(".")
    return parts[1] if len(parts) > 2 and parts[0] == "tests" else parts[0]


def main(argv=None):
    t0 = time.time()
    suite = unittest.defaultTestLoader.discover(str(HERE.joinpath("tests")), top_level_dir=str(HERE))
    result = Quiet()
    suite.run(result)
    seconds = round(time.time() - t0, 1)
    by_module = {}
    for test_id, outcome in sorted(result.outcomes.items()):
        m = by_module.setdefault(module_of(test_id), {"ran": 0, "passed": 0, "failed": 0, "skipped": 0})
        m["ran"] += 1
        m[outcome] += 1
    counts = {k: sum(m[k] for m in by_module.values()) for k in ("ran", "passed", "failed", "skipped")}
    summary = dict(counts, seconds=seconds, finished=datetime.now().isoformat(timespec="minutes"),
                   python=platform.python_version(), by_module=by_module)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=1) + "\n")
    for test, err in result.failures + result.errors:
        lines = err.strip().splitlines()
        print(f"FAIL {test.id()}\n    " + "\n    ".join(lines[-6:]))
    print(f"{counts['ran']} tests, {counts['passed']} passed, {counts['failed']} failed, "
          f"{counts['skipped']} skipped in {seconds} s")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
