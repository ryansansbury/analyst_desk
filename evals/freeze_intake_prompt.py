"""Freeze the intake prompt's hash beside the eval's answer keys, before any intake run is recorded.

    python3 -m evals.freeze_intake_prompt          (from the build folder)

The recorder refuses to record an intake task against a different prompt, so the eval's score can't be tuned by
editing the prompt after seeing results. Freezing again takes --again with a reason, kept in the file's history.
"""
import argparse
import json
from datetime import datetime

from agents import prompts
from evals.freeze_catalog import INTAKE_OUT


def frozen_sha():
    return json.loads(INTAKE_OUT.read_text()).get("prompt_sha256")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Freeze the intake prompt's hash.")
    ap.add_argument("--again", help="why the prompt is being frozen again")
    a = ap.parse_args(argv)
    data = json.loads(INTAKE_OUT.read_text())
    if data.get("prompt_sha256") and not a.again:
        raise SystemExit("The intake prompt is already frozen. Freezing again needs --again and a reason.")
    sha = prompts.load("intake_mapper")["sha256"]
    now = datetime.now().isoformat(timespec="minutes")
    data["prompt_sha256"] = sha
    data["history"].append({"at": now, "prompt_sha256": sha,
                            "reason": a.again or "the intake prompt frozen before any intake run was recorded"})
    INTAKE_OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"intake prompt {sha}")


if __name__ == "__main__":
    main()
