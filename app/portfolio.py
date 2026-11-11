"""The Portfolio tab's view model for one state: the run strip, the fund tiles, a card per company, the checks in
plain sentences, the recorded commentary, and the look-alike and new-file panels.

Every figure is a ledger ref, so the renderer can make it a trace link. Counts that describe the run itself
(files received, checks run, control totals tied) are derived values over the sources and checks they count,
so they trace too. A KPI is marked affected when a flagged check touches anything it's built from, when its
company's file is quarantined, or when a site's file is missing.
"""
from datetime import date

from agents import replay, validate
from engine import checks as checks_mod
from engine import fmt
from engine.intake import TMS_V1
from engine.metrics import Report
from generate import common as C
from generate import portfolio as world

DEMO = C.DEMO.isoformat()
OPS = C.ops_day(C.DEMO).isoformat()
OPS_DAYS = [d.isoformat() for d in C.OPS_DAYS]
COMPANIES = ("sideoats", "kiskadee", "possumhaw")
KPIS = {
    "sideoats": [("generation", "generation_var", "gen"), ("availability", None, "avail"), ("curtailment", None, "curt"),
                ("performance_ratio", None, "pr"), ("revenue", "revenue_var", "rev"), ("ebitda", "ebitda_var", None)],
    "kiskadee": [("loads", "loads_var", "loads"), ("revenue", "revenue_var", "rev"), ("revenue_per_load", None, "rpl"),
                   ("gross_margin_pct", None, "gm"), ("on_time", None, "ot"), ("empty_pct", None, "empty"),
                   ("ebitda", "ebitda_var", None)],
    "possumhaw": [("occupancy", None, "occ"), ("adr", None, "adr"), ("revpar", None, "revpar"),
                   ("revenue", "revenue_var", "rev"), ("fb_share", None, "fb"), ("ebitda", "ebitda_var", None)],
}
SITE_FAMILY = ("generation", "generation_var", "availability", "curtailment", "performance_ratio")
CONTROL_RULES = ("control_total", "settlement_tie", "deposit_tie")


class View:
    def __init__(self, desk, state, name, words, report=None):
        self.desk, self.state, self.name, self.w = desk, state, name, words
        self.L = state["ledger"]
        self.report = report or (desk.report if name == "clean" else Report(state, DEMO).build())
        self.run = state["last"]
        self.held = checks_mod.held(self.L, DEMO)
        self._inputs = {}

    # ------------------------------------------------------------------ helpers
    def inputs_of(self, ref, depth=0):
        """Every ref a derived value is built from, all the way down."""
        if ref in self._inputs:
            return self._inputs[ref]
        out = set()
        row = self.L.get(ref)
        if row and ref.startswith("D"):
            for r in row["inputs"]:
                out.add(r)
                if r.startswith("D") and depth < 12:
                    out |= self.inputs_of(r, depth + 1)
        self._inputs[ref] = out
        return out

    def count(self, metric, refs, transform):
        return self.L.derive("run", DEMO, metric, "count", refs, len(refs), "count", transform)

    def daily(self, entity_prefix, metric):
        rows = self.L.conn.execute(
            "SELECT f.period, SUM(f.value) FROM facts f JOIN sources s ON s.source_id = f.source_id "
            "WHERE (f.entity = ? OR f.entity LIKE ?) AND f.metric = ? AND s.status = 'accepted' GROUP BY f.period",
            (entity_prefix, entity_prefix + "/%", metric)).fetchall()
        return dict(rows)

    # ------------------------------------------------------------------ the run strip
    def strip(self):
        files = [f["source"] for f in self.run["files"]]
        tms = self.run["tms"] or {}
        tms_src = next((f["source"] for f in self.run["files"] if f["path"] == tms.get("path")), None)
        agent = [tms_src] if tms_src and tms.get("via") == "agent" and tms.get("accepted") else []
        waiting = [tms_src] if tms_src and (tms.get("via") is None or tms.get("quarantined")) else []
        known = [f for f in files if f not in agent and f not in waiting]
        morning_checks = self.L.checks(morning=DEMO)
        flags = [c["ref"] for c in morning_checks if c["status"] == "flag" and c["severity"] == "error"]
        ties = [c["ref"] for c in morning_checks if c["rule"] in CONTROL_RULES and c["status"] == "pass"]
        return {"files": self.count("files_received", files, "files received this morning"),
                "known": self.count("files_known", known, "files whose layout a parser knows"),
                "agent": self.count("files_agent", agent, "files mapped by the intake agent and accepted") if agent else None,
                "waiting": self.count("files_waiting", waiting, "files waiting on a mapping") if waiting else None,
                "checks": self.count("checks_run", [c["ref"] for c in morning_checks], "checks run this morning"),
                "flags": self.count("checks_flagged", flags, "error checks flagged this morning"),
                "ties": self.count("ties", ties, "control totals that tied this morning"),
                "held": bool(self.held), "flag_refs": flags}

    # ------------------------------------------------------------------ cards
    def affected(self, company, kpi_ref, kpi_name):
        if company not in self.held and company != "fund":
            return False
        flagged = {r for c in self.held.get(company, []) for r in c["refs"]}
        quarantined = any(f["status"] == "quarantined" and f["company"] == company for f in self.run["files"])
        if quarantined:
            return True
        if any(c["rule"] == "continuity" for c in self.held.get(company, [])) and kpi_name in SITE_FAMILY:
            return True
        return bool(flagged & (self.inputs_of(kpi_ref) | {kpi_ref}))

    def series(self, company, key):
        if key is None:
            return None
        cap = {s: self.L.value(a["capacity"]) for s, a in self.state["register"].items() if a["offtake"] != "arbitrage"}
        if company == "sideoats":
            if key == "gen":
                d = self.daily("sideoats", "generation_kwh")
            elif key == "curt":
                d = self.daily("sideoats", "curtailment_kwh")
            elif key == "rev":
                d = self.daily("sideoats", "settlement")
            elif key == "avail":
                w = {}
                for s, c in cap.items():
                    for p, v in self.daily(f"sideoats/{s}", "availability").items():
                        w.setdefault(p, [0, 0])
                        w[p][0] += v * c
                        w[p][1] += c
                d = {p: a / b for p, (a, b) in w.items()}
            else:
                gen, cur = self.daily("sideoats", "generation_kwh"), self.daily("sideoats", "curtailment_kwh")
                ceil = {}
                for s, c in cap.items():
                    for p, v in self.daily(f"sideoats/{s}", "insolation").items():
                        ceil[p] = ceil.get(p, 0) + v * c / 1000
                d = {p: (gen[p] + cur.get(p, 0)) / ceil[p] for p in gen if ceil.get(p)}
        elif company == "kiskadee":
            loads, rev = self.daily("kiskadee", "loads"), self.daily("kiskadee", "revenue")
            if key == "loads":
                d = loads
            elif key == "rev":
                d = rev
            elif key == "rpl":
                d = {p: rev[p] / loads[p] for p in loads if loads[p]}
            elif key == "gm":
                car, am = self.daily("kiskadee", "carrier_cost"), self.daily("kiskadee", "asset_miles")
                d = {p: (rev[p] - car.get(p, 0) - am.get(p, 0) * 185) / rev[p] for p in rev if rev[p]}
            elif key == "ot":
                ot = self.daily("kiskadee", "on_time_loads")
                d = {p: ot.get(p, 0) / loads[p] for p in loads if loads[p]}
            else:
                lm, em = self.daily("kiskadee", "loaded_miles"), self.daily("kiskadee", "empty_miles")
                d = {p: em.get(p, 0) / (lm[p] + em.get(p, 0)) for p in lm if lm[p]}
        else:
            sold, avail = self.daily("possumhaw", "rooms_sold"), self.daily("possumhaw", "rooms_available")
            room = self.daily("possumhaw", "room_revenue")
            if key == "occ":
                d = {p: sold[p] / avail[p] for p in sold if avail.get(p)}
            elif key == "adr":
                d = {p: room[p] / sold[p] for p in sold if sold[p]}
            elif key == "revpar":
                d = {p: room[p] / avail[p] for p in avail if avail[p]}
            else:
                total = self.daily("possumhaw", "total_revenue")
                if key == "rev":
                    d = total
                else:
                    fb = self.daily("possumhaw", "fb_revenue")
                    d = {p: fb[p] / total[p] for p in total if total[p]}
        return [d.get(p) for p in OPS_DAYS]

    def card(self, company):
        k = self.report[company]
        kpis = []
        for name, var, key in KPIS[company]:
            kpis.append({"name": name, "ref": k[name], "var": k[var] if var else None,
                         "series": self.series(company, key), "affected": self.affected(company, k[name], name)})
        held = company in self.held
        notes = self.check_notes(company)
        return {"company": company, "held": held, "kpis": kpis, "notes": notes,
                "commentary": self.commentary(company, held)}

    def check_notes(self, company):
        """(template key, params, check ref) for each flag, and for each expected difference, this morning."""
        out = []
        for c in self.L.checks(morning=DEMO, company=company):
            if c["status"] == "pass" or c["severity"] == "info":
                continue
            note = sentence(c, self.L, self.state)
            if note:
                out.append(note)
        return out

    def commentary(self, company, held):
        run = self.desk.runs.get("daily_commentary")
        if held:
            return {"state": "held"}
        if not run:
            return {"state": "missing"}
        chk = replay.check(run, self.L)
        if chk["status"] == "invalid":
            return {"state": "invalid", "problems": chk["problems"][:3]}
        body = next((c["sentences"] for c in replay.final(run)["companies"] if c["company"] == company), [])
        return {"state": chk["status"], "sentences": [validate.to_ledger(s, chk["mapping"]) for s in body],
                "recorded_at": run.get("recorded_at"), "model": run.get("model")}

    # ------------------------------------------------------------------ the whole tab
    def build(self):
        f = self.report["fund"]
        tiles = [{"key": "revenue", "ref": f["revenue"], "var": f["revenue_var"]},
                 {"key": "ebitda", "ref": f["ebitda"], "var": f["ebitda_var"]},
                 {"key": "cash", "ref": f["cash"], "var": None},
                 {"key": "flags", "ref": f["open_flags"], "var": None}]
        for t in tiles:
            t["affected"] = t["key"] != "flags" and any(
                self.affected(c, self.report[c][t["key"]], t["key"]) for c in COMPANIES if c in self.held)
        counts = {c: self.count(f"flags_{c}", [x["ref"] for x in v], "error checks flagged on this company's files")
                  for c, v in sorted(self.held.items())}
        return {"name": self.name, "strip": self.strip(), "tiles": tiles,
                "cards": [self.card(c) for c in COMPANIES], "held": sorted(self.held), "held_counts": counts}


def day_plan(iso):
    """The kind of day the freight budget planned, which is a holiday by name, Saturday, or Sunday. A weekday is
    None, since the budget gives it the full load."""
    d = date.fromisoformat(iso)
    names = {(k if isinstance(k, date) else date.fromisoformat(k)): n for k, n in world.HOLIDAYS.items()}
    return names.get(d) or {5: "Saturday", 6: "Sunday"}.get(d.weekday())


def sentence(c, L, state):
    """A check as (WORDS key, params). Params are ledger refs, ('text', s) or ('meta', s, check ref)."""
    rule, status, p = c["rule"], c["status"], c["params"]
    names = {s: a["name"] for s, a in state["register"].items()}
    meta = lambda v: ("meta", str(v), c["ref"])  # noqa: E731
    text = lambda v: ("text", str(v))  # noqa: E731
    # A count of rows takes the entry's .one wording for a single row, so it reads "1 row ... has no load ID."
    counted = lambda key, n: (key + ".one" if n == 1 else key, {"count": meta(n)}, c["ref"])  # noqa: E731
    day = text(fmt.day_label(c["ops_date"])) if c.get("ops_date") else text("")
    if c["company"] == "sideoats":
        site = text(names.get(p.get("site"), p.get("site", "")))
        battery = p.get("site", "").startswith("CB")
        if rule == "unit_range" and status == "flag":
            if battery:
                return ("check.unit_range.flag.battery", {"rte": p["rte"]}, c["ref"])
            return ("check.unit_range.flag.solar", {"site": site, "gen": p["gen"], "curt": p["curtailment"],
                                                    "ceiling": p["expected"], "ratio": p["ratio"]}, c["ref"])
        if rule == "unit_range" and status == "expected":
            return ("check.unit_range.expected.solar", {"site": site, "curt": p["curtailment"], "day": day,
                                                        "ratio": p["ratio"]}, c["ref"])
        if rule == "settlement_tie" and status == "flag":
            if battery:
                return ("check.settlement_tie.flag.battery", {"reported": p["reported"], "settled": p["settled"]}, c["ref"])
            return ("check.settlement_tie.flag.solar", {"site": site, "gen": p["gen"], "delivered": p["delivered"],
                                                        "loss": p["loss"]}, c["ref"])
        if rule == "continuity" and status == "flag":
            return ("check.continuity.flag", {"site": site, "day": day, "delivered": p["delivered"]}, c["ref"])
    if c["company"] == "kiskadee" and status == "flag":
        if rule == "key_unique":
            if p.get("duplicates"):
                ids = fmt.items(f"<code>{x}</code>" for x in sorted(p["duplicates"]))
                return ("check.key_unique.flag", {"ids": ("html", ids)}, c["ref"])
            return counted("check.key_unique.flag.blank", len(p.get("blank_rows", [])))
        if rule == "sum_of_parts":
            kind = {"totals_row_read_as_data": "read", "totals_disagree": "disagree", "totals_row_missing": "missing"}
            return (f"check.sum_of_parts.flag.{kind.get(p.get('kind'), 'disagree')}", {"row": meta(p.get("row", ""))},
                    c["ref"])
        if rule == "control_total":
            cause = p.get("cause", "unexplained")
            params = {"gap": p["gap"]} if p.get("gap") else {"gap": text("")}
            if cause == "credit_sign":
                params["row"] = meta(p["rows"][0])
            return (f"check.control_total.flag.{cause}", params, c["ref"])
        if rule == "dates":
            return counted("check.dates.flag", len(p.get("rows", [])))
        if rule == "unit_range":
            return counted("check.unit_range.flag.freight", len(p.get("rows", [])))
        if rule == "types":
            return ("check.types.flag", {}, c["ref"])
        if rule == "layout":
            return ("check.layout.flag", {}, c["ref"])
    if c["company"] == "possumhaw":
        if rule == "internal_consistency" and status == "flag":
            return ("check.internal_consistency.flag", {"adr": p["adr"], "rooms": p["rooms"], "product": p["product"],
                                                        "room": p["room_revenue"], "gap": p["gap"]}, c["ref"])
        if rule == "sum_of_parts" and status == "flag":
            return ("check.sum_of_parts.flag.hotel", {}, c["ref"])
        if rule == "deposit_tie" and status == "expected":
            return ("check.deposit_tie.expected", {"card": p["card"]}, c["ref"])
        if rule == "deposit_tie" and status == "pass":
            return ("check.deposit_tie.pass", {"card": p["card"], "day": day, "deposit": p["deposit"]}, c["ref"])
    if rule == "volume_band":
        plan = day_plan(c["ops_date"]) if status == "pass" and c.get("ops_date") else None
        key = "check.volume_band." + ("pass.plan" if plan else "pass" if status == "pass" else "flag")
        return (key, {"loads": p["loads"], "day": day, "budget": p["budget"], "ratio": p["ratio"],
                      "plan": text(plan or "")}, c["ref"])
    return None


def lookalike(desk, code):
    """The evidence for one look-alike, found by the checks' own statuses in the clean ledger."""
    L = desk.ledger
    if code == "L1":
        cs = [c for c in L.checks(morning=DEMO, rule="deposit_tie")]
        return [sentence(c, L, desk.clean) for c in sorted(cs, key=lambda c: c["status"] != "expected")]
    if code == "L2":
        cs = [c for c in L.checks(rule="unit_range", status="expected")]
        return [sentence(cs[-1], L, desk.clean)] if cs else []
    if code == "L3":
        labor = [d for d, n in C.HOLIDAYS.items() if n == "Labor Day"][0].isoformat()
        cs = [c for c in L.checks(rule="volume_band") if c["ops_date"] == labor]
        return [sentence(c, L, desk.clean) for c in cs]
    raise KeyError(code)


def intake_view(desk):
    """The new-file panel: the known layout, the new file's columns, the agent's mapping, and what it had to pass."""
    st = desk.clean["tms_status"].get(DEMO) or {}
    known = [h for h, _ in TMS_V1["columns"]]
    from engine import intake
    sheet = intake.tms_sheet(desk.files[f"kiskadee/{DEMO}/kiskadee_tms_{DEMO}.xlsx"])
    header = [h for h in intake.header_texts(sheet, 1) if h]
    mapping = dict(st.get("mapping") or {}).get("columns") or []
    by_header = {h: f for h, f in mapping}
    known_field = {f: h for h, f in TMS_V1["columns"]}
    cols = []
    for i, h in enumerate(header):
        field = by_header.get(h) if mapping else None
        was = known_field.get(field) if field else None
        moved = was is not None and known.index(was) != i
        cols.append({"header": h, "field": field, "was": was, "renamed": was is not None and was != h, "moved": moved,
                     "new": bool(mapping) and field is None})
    L = desk.ledger
    vchecks = [c for c in L.checks(morning=DEMO, company="kiskadee") if c["rule"] in
               ("dates", "key_unique", "sum_of_parts", "unit_range", "control_total")]
    parsed = desk.clean["last"]["parsed"]
    tie = [r for r in ((parsed.get("tms") or {}).get("revenue"), (parsed.get("invoicing") or {}).get("invoiced")) if r]
    runs = desk.runs
    evals = [runs.get(t) for t in replay.INTAKE_EVAL]
    recorded = [r for r in evals if r]
    exact = sum(1 for r in recorded if (r.get("intake") or {}).get("exact_match"))
    wrong = [r for r in recorded if not (r.get("intake") or {}).get("exact_match")]
    harmful = [r for r in wrong if not same_rows(desk, r)]
    caught = sum(1 for r in harmful if not (r.get("intake") or {}).get("accepted"))
    run = runs.get("intake_demo")
    return {"status": "accepted" if st.get("accepted") and st.get("via") == "agent" else
            "pending" if st.get("via") is None else "held",
            "layout": st.get("layout"), "reasons": st.get("reasons", []), "known": known, "columns": cols,
            "checks": [(c["rule"], c["status"], c["ref"]) for c in vchecks], "tie": tie,
            "eval": {"recorded": len(recorded), "exact": exact, "wrong": len(wrong), "harmful": len(harmful),
                     "caught": caught},
            "run": replay.summary(run)}


def same_rows(desk, run):
    """Whether an inexact mapping still parses the file's rows exactly as the answer key does."""
    from engine import intake
    from agents import validate
    out = replay.final(run)
    if out is None:
        return False
    task = run["task_id"]
    vid = task.split("_", 1)[1]
    path = desk.intake_path(task)
    from datetime import date, timedelta
    ops = (date.fromisoformat(path.split("_")[-1][:10]) - timedelta(days=1)).isoformat()
    sheet = intake.tms_sheet(desk.files[path])
    key = desk.world["key"]["intake"][vid]
    mine = intake.apply_mapping(sheet, validate.mapping_of(out), ops)
    theirs = intake.apply_mapping(sheet, {k: key[k] for k in key if k != "layout"}, ops)
    return mine[2] == [] and mine[0] == theirs[0] and mine[1] == theirs[1]
