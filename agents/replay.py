"""Load the recorded agent runs and check each one still holds against today's ledger.

A run is replayed only if its final output passes the same validation again: the schema, the limits, the gate and
the writing rules. Its local IDs resolve by meaning, so the run is stale when a value it saw has changed since it
was recorded, and the page says so. Nothing here calls a model.
"""
import json
from pathlib import Path

from agents import validate

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE.joinpath("data", "ai_runs")
INTAKE_EVAL = tuple(f"intake_V{i:02d}" for i in range(1, 13))


def load(folder=None):
    folder = Path(folder) if folder else RUNS
    out = {}
    if folder.exists():
        for p in sorted(folder.glob("*.json")):
            try:
                run = json.loads(p.read_text())
            except ValueError:
                continue
            if isinstance(run, dict) and run.get("task_id"):
                out[run["task_id"]] = run
    return out


def final(run):
    f = (run or {}).get("final") or {}
    return f.get("parsed") if f.get("valid") else None


def intake_mapping(runs, task_id="intake_demo"):
    """The engine mapping from a recorded intake run whose output passed its schema, or None. The pipeline still
    validates it against the data before accepting it."""
    out = final(runs.get(task_id))
    if out is None or validate.intake_mapper(out, runs[task_id]["input"]):
        return None
    return validate.mapping_of(out)


def check(run, ledger):
    """{status: valid, stale or invalid, problems, mapping} for a prose task's recording against today's ledger."""
    out = final(run)
    if out is None:
        return {"status": "invalid", "problems": ["the recording has no valid final output"], "mapping": {}}
    mapping = validate.resolve(ledger, run.get("ids", {}))
    stale = [local for local, item in run.get("ids", {}).items()
             if mapping.get(local) is None or (item["key"][0] != "C" and _shown(ledger, mapping[local]) != item["shown"])]
    problems = validate.validate(run["task"], out, run["input"], ledger, mapping)
    status = "invalid" if problems else "stale" if stale else "valid"
    return {"status": status, "problems": problems, "stale": stale, "mapping": mapping}


def _shown(ledger, ref):
    from engine import gate
    return gate.display(ledger, ref)


def summary(run):
    """What the page shows about a recording: when, which model, how long, and how many tries."""
    if not run:
        return None
    attempts = run.get("attempts", [])
    return {"task_id": run["task_id"], "recorded_at": run.get("recorded_at"), "model": run.get("model"),
            "seconds": run.get("seconds"), "attempts": len(attempts),
            "repaired": len(attempts) > 1 and bool((run.get("final") or {}).get("valid"))}
