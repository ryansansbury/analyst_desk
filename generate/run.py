"""Build one synthetic world from a seed, in memory or on disk.

    python3 -m generate.run --seed 2026          (from the build folder; writes data/sources, data/scenarios and data/key)

The world is the 96 mornings of portfolio files, the three budgets, the Brightrow data room, the intake eval set,
the six planted-error scenarios of the demo morning, and the key. Only scoring code and tests open the key. A
manifest records every file's SHA-256, so the same seed always proves to be the same bytes.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from generate import catalog, layouts
from generate import common as C
from generate.dataroom import DataRoom
from generate.portfolio import Portfolio

HERE = Path(__file__).resolve().parent.parent
DATA = HERE.joinpath("data")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def build(seed=C.DEMO_SEED, scenarios=True):
    """{files, scenarios, key, portfolio, dataroom} for one seed. files maps a path under data/sources to bytes."""
    p = Portfolio(seed)
    d = DataRoom(seed)
    files = {}
    for morning in C.MORNINGS:
        files.update(p.daily_files(morning))
    files.update(p.budget_files())
    files.update(d.files())
    files.update(p.eval_files())
    planted = {code: catalog.scenario(p, code, seed) for code in catalog.ERRORS} if scenarios else {}
    key = {"seed": seed, "errors": {code: s["key"] for code, s in planted.items()},
           "lookalikes": catalog.lookalike_key(p),
           "intake": {vid: layouts.answer_key(vid) for vid in ("V00",) + layouts.EVAL_IDS},
           "dataroom": {"fy2026_revenue_cents": d.fy_sum(d.total_revenue, 2),
                        "fy2026_adjusted_ebitda_cents": d.adjusted_ebitda(2),
                        "largest_customer_fy2026_cents": max(v[2] for v in d.customers.values()),
                        "claims": {"ebitda_margin": "contradicted", "customer_concentration": "contradicted",
                                   "renewal_rate": "supported"}}}
    return {"files": files, "scenarios": planted, "key": key, "portfolio": p, "dataroom": d}


def manifest(world):
    return {"seed": world["key"]["seed"],
            "files": {k: sha256(v) for k, v in sorted(world["files"].items())},
            "scenarios": {code: {k: (sha256(v) if v is not None else None) for k, v in sorted(s["files"].items())}
                          for code, s in sorted(world["scenarios"].items())}}


def key_text(world):
    return json.dumps(world["key"], indent=1, sort_keys=True) + "\n"


def write(seed=C.DEMO_SEED, root=DATA):
    """Write the world under root: sources/, scenarios/<code>/ and key/. Earlier output is replaced."""
    return write_world(build(seed), root)


def write_world(world, root=DATA):
    root = Path(root)
    for sub in ("sources", "scenarios", "key"):
        shutil.rmtree(root.joinpath(sub), ignore_errors=True)
    for rel, data in world["files"].items():
        path = root.joinpath("sources", *rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for code, s in world["scenarios"].items():
        for rel, data in s["files"].items():
            path = root.joinpath("scenarios", code, *rel.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            if data is None:
                path.with_name(path.name + ".missing").write_text("This file never arrived in this scenario.\n")
            else:
                path.write_bytes(data)
    root.joinpath("key").mkdir(parents=True, exist_ok=True)
    root.joinpath("key", "key.json").write_text(key_text(world))
    m = manifest(world)
    root.joinpath("sources", "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
    return world, m


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Write one synthetic world under data/.")
    ap.add_argument("--seed", type=int, default=C.DEMO_SEED)
    a = ap.parse_args()
    _, m = write(a.seed)
    print(f"seed {a.seed}: {len(m['files'])} source files and {len(m['scenarios'])} scenarios written under data/")
