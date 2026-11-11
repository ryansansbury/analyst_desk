"""Paths and small helpers the tests share. Scratch files go in .cache/tmp, which is gitignored."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DEMO_DAY = "2026-11-04"     # the demo morning. test_generate checks it against generate/common.py
TMP = HERE.joinpath(".cache", "tmp")
TMP.mkdir(parents=True, exist_ok=True)


def load_module(name, path):
    """Import a script that isn't a package module, like the copy checker or a script in scripts/."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_worlds = {}


def world(seed=2026):
    """The generator's world for a seed, built once per test run."""
    if seed not in _worlds:
        from generate import run
        _worlds[seed] = run.build(seed)
    return _worlds[seed]


_desks = {}


def desk(seed=2026):
    """(world, pipeline, history state) for a seed, with the V00 answer key standing in for an accepted mapping."""
    if seed not in _desks:
        from engine import pipeline
        from generate import common as C
        w = world(seed)
        answer = w["key"]["intake"]["V00"]
        p = pipeline.Pipeline(w["files"], mapping_for=lambda path, sheet: dict(answer))
        _desks[seed] = (w, p, p.history([m.isoformat() for m in C.MORNINGS[:-1]]))
    return _desks[seed]


def demo_state(seed=2026, scenario=None):
    """A fresh fork of the history with the demo morning run, clean or with one planted error."""
    from generate import common as C
    w, p, hist = desk(seed)
    st = p.fork(hist)
    p.run(st, C.DEMO.isoformat(), override=w["scenarios"][scenario]["files"] if scenario else None)
    return st


_site = []


def stand_in_runs(seed=2026):
    """A stand-in for the recorded intake run, made from the answer key, so the test page publishes the way the
    demo does once the real run exists. Tests only. The real page replays only real recordings."""
    from agents import inputs
    from engine import intake
    from generate import common as C
    w = world(seed)
    demo = C.DEMO.isoformat()
    path = f"kiskadee/{demo}/kiskadee_tms_{demo}.xlsx"
    inp = inputs.intake(path.split("/")[-1], intake.sample_for_agent(intake.tms_sheet(w["files"][path])))
    k = w["key"]["intake"]["V00"]
    parsed = {f: k[f] for f in ("header_rows", "columns", "date_format", "money_format", "on_time", "totals_label")}
    runs = {"intake_demo": {"task_id": "intake_demo", "task": "intake_mapper", "input": inp,
                            "final": {"parsed": parsed, "valid": True, "problems": []},
                            "recorded_at": "2026-10-28T13:05:00+00:00", "model": "stand-in", "attempts": []}}
    from agents import replay
    for task in replay.INTAKE_EVAL:
        key = w["key"]["intake"][task.split("_", 1)[1]]
        runs[task] = {"task_id": task, "task": "intake_mapper", "input": {},
                      "final": {"parsed": {f: key[f] for f in ("header_rows", "columns", "date_format", "money_format",
                                                              "on_time", "totals_label")}, "valid": True, "problems": []},
                      "intake": {"accepted": True, "reasons": [], "exact_match": True},
                      "recorded_at": "2026-10-27T19:01:00+00:00", "model": "stand-in", "seconds": 7.0, "attempts": []}
    from app.desk import Desk
    from tests.test_agents import StandIn
    desk = Desk(runs=runs)
    inp, ids = desk.input_for("memo_writer")
    runs["memo_writer"] = {"task_id": "memo_writer", "task": "memo_writer", "input": inp, "ids": ids.keys(),
                           "final": {"parsed": StandIn("x").memo_writer(inp, False), "valid": True, "problems": []},
                           "recorded_at": "2026-10-28T13:20:00+00:00", "model": "stand-in", "input_sha256": "5tand1n0",
                           "attempts": []}
    return runs


def stand_in_comparison():
    """A model comparison shaped like evals/model_comparison.json, for the routing panel's tests. Tests only.
    The real page shows only the recorded comparison. Its models cover every case: four vendors, so one folds into
    Other, a model without a price, a harmful intake miss, a repaired reply, and a prose agent that failed."""
    from agents import routing
    prose = ("daily_commentary", "deal_analyst", "board_deck", "memo_writer")

    def model(mid, label, vendor, exact, harmful, cost, replies="ffff", secs=10.0, via="openai"):
        tasks = {"intake_mapper": {"runs": 12, "valid": 12, "first_try": 12, "errors": 0, "seconds": secs / 2,
                                   "cost": cost, "exact": exact, "same": 0, "harmful": harmful,
                                   "caught": 12 - exact - harmful, "accepted": exact + harmful}}
        for i, (t, r) in enumerate(zip(prose, replies)):
            tasks[t] = {"runs": 1, "valid": int(r != "x"), "first_try": int(r == "f"), "errors": 0,
                        "seconds": secs * (1 + i), "cost": None if cost is None else round(cost * (3 + i), 6)}
        m = {"id": mid, "label": label, "vendor": vendor, "via": via, "model": mid, "answered_by": [mid],
             "ran_at": "2026-10-28T15:10:00+00:00", "tasks": tasks}
        m["morning_cost"] = routing.morning_cost(m)
        m["morning_seconds"] = round(sum(tasks[t]["seconds"] for t in routing.TASKS), 1)
        return m

    return {"ran_at": "2026-10-28T15:10:00+00:00", "prices_checked": "2026-10-28", "default": "alpha-large",
            "left_out": [], "notes": [],
            "models": [model("alpha-large", "Alpha Large", "Anthropic", 12, 0, 0.031, secs=20.0, via="claude-cli"),
                       model("alpha-small", "Alpha Small", "Anthropic", 11, 0, 0.0062, "fffr", 8.0, "claude-cli"),
                       model("beta-mini", "Beta Mini", "OpenAI", 11, 0, 0.0021, "ffrf", 10.0),
                       model("gamma-flash", "Gamma Flash", "Google", 9, 0, 0.0009, "fxff", 6.0),
                       model("delta-one", "Delta One", "xAI", 10, 1, 0.004, secs=9.0),
                       model("epsilon", "Epsilon", "Mistral", 12, 0, None, secs=12.0)]}


def site():
    """The page built once per test run into .cache/tmp/site_test with the stand-in intake run and the stand-in
    model comparison, so tests never touch site/."""
    if not _site:
        import build
        out = TMP.joinpath("site_test")
        r = build.build(out=out, quiet=True, runs=stand_in_runs(), write_data=False, comparison=stand_in_comparison())
        _site.append((out, r))
    return _site[0][0]


def built():
    site()
    return _site[0][1]


_real = []
_real_desk = []


def real_desk():
    """The desk built on the real recordings in data/ai_runs, once per test run."""
    if not _real_desk:
        from app.desk import Desk
        _real_desk.append(Desk())
    return _real_desk[0]


def real_book():
    """The deal model's workbook built from the real recordings in data/ai_runs, the way the build makes it."""
    if not _real:
        from app import words
        from deliverables.model_xlsx import Book
        _real.append(Book(real_desk().deal_model(), words.load(), None))
    return _real[0]


_lint = []


def lint():
    """The writing-rules checker, tools/lint_copy.py, imported rather than run."""
    if not _lint:
        _lint.append(load_module("lint_copy", HERE.joinpath("tools", "lint_copy.py")))
    return _lint[0]


def copy_problems(path):
    """Every flagged sentence in a .md, .txt or .html file, as (sentence, issues), with the comma-before-so rule."""
    from agents.validate import rule_issues
    mod = lint()
    out = []
    for line in mod.prose(Path(path)):
        for sent in mod.sentences(line):
            issues = rule_issues(mod, sent)
            if issues:
                out.append((sent, issues))
    return out


def text_problems(text):
    """The same check over plain text, like an agent's sentence."""
    from agents.validate import rule_issues
    mod = lint()
    out = []
    for sent in mod.sentences(" ".join(text.split())):
        issues = rule_issues(mod, sent)
        if issues:
            out.append((sent, issues))
    return out
