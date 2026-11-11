"""Freeze the checks and score them once on seeds no earlier run used.

    python3 -m evals.freeze_checks --seeds 4101 5202 6303          (from the build folder)

The checks were written against the demo seed (2026) and seed 11 only. A frozen run records a hash of every file
that decides detection and scores the checks on three held-out seeds. Runs append to evals/check_runs.json and are
never redone. A later version has to use fresh seeds, so a miss can't be tuned away on the data that showed it.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE.joinpath("evals", "check_runs.json")
DEV_SEEDS = (2026, 11)
DETECTOR_FILES = ("engine/checks.py", "engine/intake.py", "engine/pipeline.py")


def detectors_sha256():
    h = hashlib.sha256()
    for name in DETECTOR_FILES:
        h.update(name.encode())
        h.update(HERE.joinpath(*name.split("/")).read_bytes())
    return h.hexdigest()


def history():
    return json.loads(RUNS.read_text())["runs"] if RUNS.exists() else []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Freeze the checks and score them on held-out seeds.")
    ap.add_argument("--seeds", type=int, nargs=3, required=True)
    ap.add_argument("--notes", default="")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(HERE))
    from evals import freeze_catalog, score_checks
    runs = history()
    used = set(DEV_SEEDS) | {s for r in runs for s in r["held_out_seeds"]}
    if used & set(a.seeds):
        raise SystemExit(f"Seeds {sorted(used & set(a.seeds))} were used before. Score on fresh seeds.")
    sha = detectors_sha256()
    if runs and runs[-1]["detectors_sha256"] == sha:
        raise SystemExit("The checks haven't changed since the last frozen run.")
    frozen = json.loads(freeze_catalog.CATALOG_OUT.read_text())
    if freeze_catalog.catalog_sha256() != frozen["catalog_sha256"]:
        raise SystemExit("The planted catalog changed after it was frozen, so a score would mean nothing.")
    seeds = [score_checks.score(s) for s in a.seeds]
    total = {k: sum(s[k] for s in seeds) for k in ("planted", "caught", "diagnosed", "false_alarms",
                                                   "lookalikes_left_alone")}
    total["lookalikes"] = 3 * len(seeds)
    runs.append({"version": len(runs) + 1, "frozen": datetime.now().isoformat(timespec="minutes"),
                 "detectors_sha256": sha, "detector_files": list(DETECTOR_FILES), "catalog_sha256": frozen["catalog_sha256"],
                 "held_out_seeds": list(a.seeds), "developed_on": list(DEV_SEEDS), "total": total, "seeds": seeds,
                 "notes": a.notes})
    RUNS.write_text(json.dumps({"runs": runs}, indent=1) + "\n")
    print(json.dumps(total))


if __name__ == "__main__":
    main()
