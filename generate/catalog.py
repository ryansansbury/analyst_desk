"""The planted catalog: six errors the checks must catch and three look-alikes they must leave alone.

Frozen with a hash in evals/catalog_frozen.json before any check was written. Each error is a scenario, a copy
of the demo morning with one file changed or missing, so the page can show it as a precomputed state and the
scorer can run the checks on it. The seed picks the target (which site, which rows, which digits), so held-out
seeds put each error somewhere the checks haven't seen. The key says where everything is, and the engine never
reads it.
"""
from generate import common as C
from generate import layouts

ERRORS = {
    "E1": {"company": "sideoats", "title": "Generation reported in the wrong unit (1000 times off)", "rule": "unit_range",
           "also": ["settlement_tie"]},
    "E2": {"company": "kiskadee", "title": "Duplicate load rows in the TMS export", "rule": "key_unique",
           "also": ["control_total"]},
    "E3": {"company": "kiskadee", "title": "The totals row read as a load", "rule": "sum_of_parts",
           "also": ["key_unique", "control_total"]},
    "E4": {"company": "sideoats", "title": "A site's daily file missing", "rule": "continuity", "also": ["settlement_tie"]},
    "E5": {"company": "possumhaw", "title": "ADR times rooms sold doesn't equal room revenue",
           "rule": "internal_consistency", "also": []},
    "E6": {"company": "kiskadee", "title": "A credit's sign flipped", "rule": "control_total", "also": []},
}
LOOKALIKES = {
    "L1": {"company": "possumhaw", "title": "Card deposits land a day after the night audit", "rule": "deposit_tie"},
    "L2": {"company": "sideoats", "title": "A low-generation day with curtailment recorded", "rule": "unit_range"},
    "L3": {"company": "kiskadee", "title": "The Labor Day dip in freight volume", "rule": "volume_band"},
}


def demo_paths(morning=C.DEMO):
    m = morning.isoformat()
    return {"site": lambda sid: f"sideoats/{m}/sideoats_{sid}_{m}.csv",
            "tms": f"kiskadee/{m}/kiskadee_tms_{m}.xlsx",
            "audit": f"possumhaw/{m}/possumhaw_night_audit_{m}.txt"}


def scenario(portfolio, code, seed):
    """{files: {path: bytes, or None for a file that never arrived}, key: where the error is}."""
    rng = C.stream(seed, f"plant:{code}")
    morning = C.DEMO
    ops = C.ops_day(morning)
    p = demo_paths(morning)
    layout = "V00"
    key = {"code": code, "company": ERRORS[code]["company"], "rule": ERRORS[code]["rule"], "morning": morning.isoformat(),
           "ops_date": ops.isoformat()}
    if code == "E1":
        sid = rng.choice(["CR1", "CR2", "CR3", "CR4"])
        direction = "mwh_as_kwh" if seed == C.DEMO_SEED else rng.choice(["mwh_as_kwh", "wh_as_kwh"])
        s = portfolio.sideoats[ops]["sites"][sid]
        if direction == "mwh_as_kwh":
            gen, cur = f"{s['generation_kwh'] / 1000:.3f}", f"{s['curtailment_kwh'] / 1000:.3f}"
        else:
            gen, cur = str(s["generation_kwh"] * 1000), str(s["curtailment_kwh"] * 1000)
        text = C.csv_text(["date", "site_id", "generation_kwh", "availability_pct", "curtailment_kwh",
                           "insolation_kwh_m2", "inverter_faults"],
                          [(ops.isoformat(), sid, gen, f"{s['availability_pct']:.1f}", cur,
                            f"{s['insolation_kwh_m2']:.2f}", s["inverter_faults"])])
        key.update(file=p["site"](sid), site=sid, direction=direction)
        return {"files": {p["site"](sid): text.encode()}, "key": key}
    if code == "E4":
        sid = rng.choice(["CR1", "CR2", "CR3", "CR4"])
        key.update(file=p["site"](sid), site=sid)
        return {"files": {p["site"](sid): None}, "key": key}
    rows = [dict(r) for r in portfolio.tms_rows(ops)]
    if code == "E2":
        loads = [i for i, r in enumerate(rows) if not r.get("credit")]
        n = rng.randint(1, 3)
        start = rng.choice(loads[5:-5])
        picked = [i for i in loads if i >= start][:n]
        dupes = [dict(rows[i]) for i in picked]
        at = picked[-1] + 1
        rows[at:at] = dupes
        key.update(file=p["tms"], load_ids=[d["load_id"] for d in dupes], layout=layout,
                   amount_cents=sum(d["linehaul_rev"] + d["fuel_surcharge"] + d["accessorials"] for d in dupes))
        return {"files": {p["tms"]: layouts.render(layout, rows, ops)}, "key": key}
    if code == "E3":
        key.update(file=p["tms"], layout=layout)
        return {"files": {p["tms"]: layouts.render(layout, rows, ops, totals_label="")}, "key": key}
    if code == "E6":
        credit = next(r for r in rows if r.get("credit"))
        credit["accessorials"] = -credit["accessorials"]
        key.update(file=p["tms"], load_id=credit["load_id"], layout=layout, amount_cents=credit["accessorials"])
        return {"files": {p["tms"]: layouts.render(layout, rows, ops)}, "key": key}
    if code == "E5":
        h = portfolio.possumhaw[ops]
        dollars = str(h["adr"] // 100)
        spots = [i for i in range(len(dollars) - 1) if dollars[i] != dollars[i + 1]]
        i = rng.choice(spots)
        swapped = dollars[:i] + dollars[i + 1] + dollars[i] + dollars[i + 2:]
        adr = int(swapped) * 100 + h["adr"] % 100
        key.update(file=p["audit"], adr_cents=adr, true_adr_cents=h["adr"], rooms_sold=h["sold"])
        return {"files": {p["audit"]: portfolio.night_audit(ops, adr=adr).encode()}, "key": key}
    raise KeyError(code)


def lookalike_key(portfolio):
    """Where the look-alikes are in the clean world."""
    l2 = [{"ops_date": d.isoformat(), "morning": C.morning_of(d).isoformat(), "site": sid,
           "file": f"sideoats/{C.morning_of(d).isoformat()}/sideoats_{sid}_{C.morning_of(d).isoformat()}.csv"}
          for d, sid in sorted(portfolio.l2.items())]
    labor = [d for d, name in C.HOLIDAYS.items() if name == "Labor Day"][0]
    return {"L1": {"company": "possumhaw", "rule": "deposit_tie", "where": "every morning's newest night audit"},
            "L2": {"company": "sideoats", "rule": "unit_range", "days": l2},
            "L3": {"company": "kiskadee", "rule": "volume_band", "ops_date": labor.isoformat(),
                   "morning": C.morning_of(labor).isoformat()}}
