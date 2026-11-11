"""The data bundle: every state the page can show, rendered in advance, and the trace of every figure in them.

States: before the run, the clean morning, each planted error E1 to E6, each look-alike L1 to L3, and the new
file. A state is the Portfolio tab's HTML and the run strip's. Traces start from the figures a state shows and
follow their inputs down to the files, so any click in the drawer has its answer already. Refs from the shared
history are stored once, and refs made in a state are stored under that state's name.
"""
import json
from datetime import date

from app import portfolio
from app.notes import page_note
from app.render import Renderer, STATUS_ICON, icon
from engine import fmt, gate
from engine.ledger import PREFIX
from engine.lineage import Lineage

MAX_TRACES_PER_STATE = 4000
NAMES = {"sideoats": "Sideoats Renewables", "kiskadee": "Kiskadee Freight", "possumhaw": "Possumhaw Lodge"}


def fork_max(ledger):
    out = {}
    for kind, (table, key) in PREFIX.items():
        out[kind] = ledger.conn.execute(f"SELECT COALESCE(MAX({key}), 0) FROM {table}").fetchone()[0]
    return out


def period_label(p):
    if ".." in p:
        a, b = p.split("..")
        da, db = date.fromisoformat(a), date.fromisoformat(b)
        if (da.year, da.month) == (db.year, db.month):
            return f"{fmt.MONTHS[da.month - 1]} {da.day} to {db.day}"
        return f"{fmt.day_label(a)} to {fmt.day_label(b)}"
    if len(p) == 10 and p[4] == "-":
        return fmt.day_label(p, year=True)
    if len(p) == 7 and p[4] == "-":
        return f"{fmt.MONTHS[int(p[5:]) - 1]} {p[:4]}"
    return {"register": "the asset register", "per month": "a month", "per year": "a year"}.get(p, p)


class Labeler:
    def __init__(self, words, register):
        self.entity = words.table("labels.entity")
        self.metric = words.table("labels.metric")
        self.rule = words.table("labels.rule")
        self.status = words.table("labels.status")
        self.sites = {f"sideoats/{s}": a["name"] for s, a in register.items()}

    def ent(self, e):
        if e in self.sites:
            return self.sites[e]
        if e.startswith("brightrow/customer/"):
            return e.split("/", 2)[2]
        return self.entity.get(e, e)

    def met(self, m):
        return self.metric.get(m, m.replace("_", " ").replace(":", " "))

    def title(self, row):
        return f"{self.met(row['metric'])}, {self.ent(row['entity'])}"


class Traces:
    """Collects traces across states into one dictionary."""

    def __init__(self, words, files, register):
        self.w, self.files, self.lab = words, files, Labeler(words, register)
        self.out = {}
        self.excerpts, self._excerpt_ids = {}, {}

    def excerpt_id(self, path, x):
        """Excerpts are stored once and shared by every fact read from the same rows of a file."""
        col = x.get("column")
        body = dict(x)
        body.pop("column", None)
        key = path + "|" + json.dumps(body, sort_keys=True)
        if key not in self._excerpt_ids:
            self._excerpt_ids[key] = f"x{len(self._excerpt_ids)}"
            self.excerpts[self._excerpt_ids[key]] = body
        return self._excerpt_ids[key], col

    def add_state(self, state, renderer, extra_files=None):
        files = dict(self.files)
        files.update({k: v for k, v in (extra_files or {}).items() if v is not None})
        lin = Lineage(state["ledger"], files)
        # Sorted, since a set's order changes from run to run and the walk's order names the shared excerpts. Two builds
        # of the same seed then write the same bytes.
        todo, seen, n = sorted(renderer.refs), set(), 0
        while todo and n < MAX_TRACES_PER_STATE:
            q = todo.pop()
            if q in seen or q in self.out:
                continue
            seen.add(q)
            ref = q.split(":", 1)[1] if ":" in q else q
            t = self.one(lin, state, renderer, ref)
            if t is None:
                continue
            self.out[q] = t
            n += 1
            todo += t.get("_next", [])
            t.pop("_next", None)

    def one(self, lin, state, R, ref):
        t = lin.trace(ref, max_inputs=40)
        if t is None:
            return None
        L, lab = state["ledger"], self.lab
        if t["kind"] in ("fact", "derived"):
            row = L.get(ref)
            out = {"k": t["kind"], "title": lab.title(row), "period": period_label(row["period"]),
                   "shown": gate.display(L, ref, short=False), "steps": [page_note(t["transform"])]}
            checks = [R.q(c) for c in t["checks"]]
            out["checks"] = checks
            nxt = list(checks)
            if t["kind"] == "fact":
                s = t["source"]
                out["source"] = {"name": s["path"].split("/")[-1], "path": s["path"], "sha": (s["sha256"] or "")[:16],
                                 "morning": fmt.day_label(s["morning"], weekday=True) if s["morning"] else "",
                                 "layout": s["layout"], "status": s["status"], "note": s["note"]}
                out["locator"] = t["locator"]
                out["x"], out["col"] = self.excerpt_id(s["path"], t["excerpt"])
            else:
                ins = [R.q(r) for r in t["inputs"]]
                nxt += ins
                out["inputs"] = ins
                out["more"] = t["more_inputs"]
                out["count"] = t["input_count"]
            out["_next"] = nxt
            return out
        if t["kind"] == "check":
            row = L.get(ref)
            s = portfolio.sentence(row, L, state)
            before = set(R.refs)
            html = R.fill(s[0], s[1]) if s else ""
            return {"k": "check", "title": lab.rule.get(row["rule"], row["rule"]),
                    "status": row["status"], "status_label": lab.status.get(row["status"], row["status"]),
                    "icon": STATUS_ICON[row["status"]], "html": html,
                    "who": lab.ent(row["scope"]) if row["scope"] in lab.sites else lab.ent(row["company"]),
                    "_next": sorted(R.refs - before)}
        if t["kind"] == "source":
            out = {"k": "source", "title": t["path"].split("/")[-1], "path": t["path"], "sha": (t["sha256"] or "")[:16],
                   "morning": fmt.day_label(t["morning"], weekday=True) if t["morning"] else "",
                   "layout": t["layout"], "status": t["status"], "note": t["note"], "_next": []}
            if "/dataroom/" in t["path"]:          # the data room's files open whole in the drawer
                out["x"], out["col"] = self.excerpt_id(t["path"], lin.preview(t["path"]))
            return out
        if t["kind"] == "claim":
            return {"k": "claim", "title": t["text"], "status": t["status"], "refs": [R.q(r) for r in t["refs"]],
                    "_next": [R.q(r) for r in t["refs"]]}
        return None


def make(desk, words, tabs=None):
    """{states, traces, meta, tabs}: everything the page needs, from the desk. tabs maps a tab's name to a function
    that renders it with a renderer on the clean ledger, so its figures are traced like the Portfolio's."""
    fm = fork_max(desk.history["ledger"])
    traces = Traces(words, desk.files, desk.clean["register"])
    states = {}
    day = fmt.day_label(portfolio.OPS)
    clean_view = portfolio.View(desk, desk.clean, "clean", words, report=desk.report).build()

    def render_state(name, st, vm, panel_fn=None, planted=False, extra=None, ledger_name=None):
        R = Renderer(words, st["ledger"], ledger_name or name, fm)
        panel = panel_fn(R) if panel_fn else ""
        states[name] = {"portfolio": R.portfolio(vm, NAMES, day, panel, planted), "strip": R.strip(vm),
                        "held": bool(vm["held"])}
        traces.add_state(st, R, extra)
        return R

    render_state("clean", desk.clean, clean_view)
    pre = Renderer(words, desk.ledger, "clean", fm)
    files = [f["path"].split("/")[-1] for f in desk.clean["last"]["files"]]
    states["pre"] = {"portfolio": pre.prerun(files), "strip": pre.strip(clean_view, pre=True), "held": False}
    for code in ("L1", "L2", "L3"):
        notes = portfolio.lookalike(desk, code)
        render_state(code, desk.clean, clean_view, lambda R, c=code, n=notes: R.lookalike(c, n), ledger_name="clean")
    iv = portfolio.intake_view(desk)
    render_state("intake", desk.clean, clean_view, lambda R: R.intake(iv), ledger_name="clean")
    for code in ("E1", "E2", "E3", "E4", "E5", "E6"):
        st = desk.state(code)
        vm = portfolio.View(desk, st, code, words).build()
        render_state(code, st, vm, planted=True, extra=desk.world["scenarios"][code]["files"])
    rendered = {}
    for name, fn in (tabs or {}).items():
        R = Renderer(words, desk.ledger, "clean", fm)
        rendered[name] = fn(R)
        traces.add_state(desk.clean, R)
    meta = {"demo": portfolio.DEMO, "ops": portfolio.OPS, "fork_max": fm,
            "states": sorted(states), "traces": len(traces.out)}
    return {"states": states, "traces": traces.out, "excerpts": traces.excerpts, "meta": meta, "tabs": rendered}


def js_assign(name, obj):
    return f"window.{name} = " + json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + ";\n"


__all__ = ["make", "js_assign", "icon"]
