"""Freeze the planted catalog and the intake eval's answer keys with hashes, before any check or prompt exists.

    python3 -m evals.freeze_catalog          (from the build folder)

catalog_frozen.json pins generate/catalog.py, which defines and plants E1 to E6 and L1 to L3, and records the key
it produces on the demo and dev seeds. intake_variants_frozen.json pins the answer keys of V00 and V01 to V12 and
the bytes of each eval file. The tests fail if either changes after the freeze. Freezing again takes --again with
a reason, and every freeze stays in the file's history.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CATALOG_OUT = HERE.joinpath("evals", "catalog_frozen.json")
INTAKE_OUT = HERE.joinpath("evals", "intake_variants_frozen.json")
CATALOG_FILES = ("generate/catalog.py",)


def catalog_sha256():
    h = hashlib.sha256()
    for name in CATALOG_FILES:
        h.update(name.encode())
        h.update(HERE.joinpath(*name.split("/")).read_bytes())
    return h.hexdigest()


def answer_keys_sha256():
    from generate import layouts
    keys = {vid: layouts.answer_key(vid) for vid in ("V00",) + layouts.EVAL_IDS}
    return hashlib.sha256(json.dumps(keys, sort_keys=True).encode()).hexdigest()


def key_sha256(world):
    planted = {"errors": world["key"]["errors"], "lookalikes": world["key"]["lookalikes"]}
    return hashlib.sha256(json.dumps(planted, sort_keys=True).encode()).hexdigest()


def history(path):
    return json.loads(path.read_text()).get("history", []) if path.exists() else []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Freeze the planted catalog and the intake answer keys.")
    ap.add_argument("--again", help="why the freeze is being redone, kept in the history")
    a = ap.parse_args(argv)
    if (CATALOG_OUT.exists() or INTAKE_OUT.exists()) and not a.again:
        raise SystemExit("Already frozen. Freezing again needs --again and a reason.")
    from generate import layouts, run
    now = datetime.now().isoformat(timespec="minutes")
    reason = a.again or "first freeze, before any check or prompt was written"
    demo, dev = run.build(2026), run.build(11)
    catalog = {"frozen_at": now, "catalog_sha256": catalog_sha256(), "files": list(CATALOG_FILES),
               "key_sha256": {"2026": key_sha256(demo), "11": key_sha256(dev)},
               "errors": sorted(demo["key"]["errors"]), "lookalikes": sorted(demo["key"]["lookalikes"]),
               "history": history(CATALOG_OUT) + [{"at": now, "catalog_sha256": catalog_sha256(), "reason": reason}]}
    files = {}
    for path, data in sorted(demo["files"].items()):
        if path.startswith("kiskadee/eval/"):
            files[path.split("/")[-1].split("_")[0]] = hashlib.sha256(data).hexdigest()
    intake = {"frozen_at": now, "answer_keys_sha256": answer_keys_sha256(), "variants": list(layouts.EVAL_IDS),
              "demo_layout": "V00", "files": files, "prompt_sha256": None,
              "history": history(INTAKE_OUT) + [{"at": now, "answer_keys_sha256": answer_keys_sha256(), "reason": reason}]}
    CATALOG_OUT.write_text(json.dumps(catalog, indent=1) + "\n")
    INTAKE_OUT.write_text(json.dumps(intake, indent=1) + "\n")
    print(f"catalog {catalog['catalog_sha256']}")
    print(f"intake answer keys {intake['answer_keys_sha256']}")


if __name__ == "__main__":
    main()
