"""Score the checks on one seed against the frozen catalog.

Caught means an error-class flag for the planted company under the planted rule on the demo morning. Diagnosed
also needs the right cause where the check names one (duplicates for E2, a flipped credit for E6). A false alarm
is any error-class flag in the clean world across every morning in the window. A look-alike counts as left alone only if no
check of any severity flags it: L1 on every morning, L2 on its days, L3 on Labor Day.
"""
from engine import pipeline
from generate import common as C
from generate import run

CAUSE = {"E6": "credit_sign"}       # E2 is diagnosed when the key check names exactly the planted load IDs


def score(seed):
    w = run.build(seed)
    key = w["key"]
    answer = key["intake"]["V00"]
    p = pipeline.Pipeline(w["files"], mapping_for=lambda path, sheet: dict(answer))
    hist = p.history([m.isoformat() for m in C.MORNINGS[:-1]])
    clean = p.fork(hist)
    p.run(clean, C.DEMO.isoformat())
    L = clean["ledger"]
    false_alarms = [{"company": c["company"], "rule": c["rule"], "morning": c["morning"], "scope": c["scope"]}
                    for c in L.checks(status="flag", severity="error")]
    notes = len(L.checks(status="flag", severity="info"))
    look = {}
    l1 = [c for c in L.checks(rule="deposit_tie") if c["status"] == "flag"]
    look["L1"] = {"left_alone": not l1, "checks": len(L.checks(rule="deposit_tie"))}
    l2_ok = []
    for d in key["lookalikes"]["L2"]["days"]:
        cs = [c for c in L.checks(rule="unit_range", scope=f"sideoats/{d['site']}") if c["ops_date"] == d["ops_date"]]
        l2_ok.append(bool(cs) and all(c["status"] in ("pass", "expected") for c in cs))
    look["L2"] = {"left_alone": all(l2_ok), "days": len(l2_ok)}
    l3 = [c for c in L.checks(rule="volume_band") if c["ops_date"] == key["lookalikes"]["L3"]["ops_date"]]
    look["L3"] = {"left_alone": bool(l3) and all(c["status"] == "pass" for c in l3)}
    errors = {}
    for code, s in w["scenarios"].items():
        st = p.fork(hist)
        r = p.run(st, C.DEMO.isoformat(), override=s["files"])
        flags = st["ledger"].checks(morning=C.DEMO.isoformat(), status="flag", severity="error")
        want = s["key"]
        hits = [c for c in flags if c["company"] == want["company"] and c["rule"] == want["rule"]]
        if code == "E2":
            diagnosed = any(set(c["params"].get("duplicates", {})) == set(want["load_ids"]) for c in hits)
        else:
            diagnosed = bool(hits) and (code not in CAUSE or any(c["params"].get("cause") == CAUSE[code] for c in hits))
        errors[code] = {"caught": bool(hits), "diagnosed": diagnosed,
                        "flags": sorted({f"{c['company']}:{c['rule']}" for c in flags}),
                        "quarantined": bool(r["tms"] and r["tms"].get("quarantined"))}
    return {"seed": seed, "planted": len(errors), "caught": sum(e["caught"] for e in errors.values()),
            "diagnosed": sum(e["diagnosed"] for e in errors.values()), "false_alarms": len(false_alarms),
            "false_alarm_list": false_alarms[:10], "info_notes": notes, "lookalikes": look,
            "lookalikes_left_alone": sum(v["left_alone"] for v in look.values()), "errors": errors}
