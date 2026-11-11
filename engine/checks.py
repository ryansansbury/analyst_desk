"""The checks: each rule in the spec, written once and run on every morning.

An error-class flag holds that company's report for review, and the fund's report with it. An info flag is a
note, like a budget variance or a volume day outside its band. 'expected' marks a difference the checks know is
normal (a card deposit that settles tomorrow, a day the grid curtailed the site), so a look-alike is explained
rather than flagged. Each result keeps the IDs it used, so its sentence on the page renders from the ledger.

These rules were written after the planted catalog was frozen, against the demo seed and seed 11 only, then
frozen themselves and scored once on held-out seeds (evals/check_runs.json).
"""
RANGE_RATIO = (0.55, 0.95)      # generation plus curtailment over capacity times sunlight
CURTAILED_SHARE = 0.25          # past this share of the day's output, curtailment explains a low day
LINE_LOSS = (0.005, 0.025)      # modeled line losses of 1 to 2 percent, with a margin either side
BATTERY_RTE = (0.80, 0.92)
BATTERY_LOSS = (0.003, 0.015)
VOLUME_BAND = (0.70, 1.30)      # loads against the day's budget, which carries weekends and holidays
CENTS_PER_MILE = (80, 800)
FSC_SHARE = (0.05, 0.45)
ACCESSORIAL_CAP = 150000        # cents a load, since detention and lumper fees are flat and can pass a short haul's linehaul
CARRIER_SHARE = 1.20
ON_TIME_FLOOR = 0.50


def result(rule, status, severity="error", **params):
    return {"rule": rule, "status": status, "severity": severity, "params": params}


# ---------------------------------------------------------------------- Kiskadee's TMS file
def tms_results(rows, totals, mapping, ops, invoice_count, invoiced):
    """Every check one TMS file gets, as plain results. The intake agent's mapping is accepted only if all pass."""
    out = []
    bad_dates = [r["row"] for r in rows if r["date"] != ops]
    out.append(result("dates", "flag" if bad_dates else "pass", rows=bad_dates))
    by_id, blank = {}, []
    for r in rows:
        if r["load_id"]:
            by_id.setdefault(r["load_id"], []).append(r["row"])
        else:
            blank.append(r["row"])
    dupes = {k: v for k, v in sorted(by_id.items()) if len(v) > 1}
    out.append(result("key_unique", "flag" if dupes or blank else "pass", duplicates=dupes, blank_rows=blank,
                      rows=sorted(x for v in dupes.values() for x in v) + blank))
    rev = lambda r: r["linehaul_rev"] + r["fuel_surcharge"] + r["accessorials"]  # noqa: E731
    total_rev = sum(rev(r) for r in rows)
    total_miles = sum(r["miles"] for r in rows)
    read_as_data = [r for r in rows if len(rows) > 2 and r["miles"] > 0 and 2 * rev(r) == total_rev
                    and 2 * r["miles"] == total_miles]
    if read_as_data:
        out.append(result("sum_of_parts", "flag", kind="totals_row_read_as_data", row=read_as_data[0]["row"],
                          rows=[read_as_data[0]["row"]]))
    elif mapping.get("totals_label") and totals is None:
        out.append(result("sum_of_parts", "flag", kind="totals_row_missing", rows=[]))
    elif totals is not None:
        off = [f for f in ("miles", "empty_miles", "linehaul_rev", "fuel_surcharge", "accessorials", "carrier_cost")
               if (totals.get(f) or 0) != sum(r[f] or 0 for r in rows)]
        out.append(result("sum_of_parts", "flag" if off else "pass", kind="totals_disagree" if off else "ties",
                          fields=off, row=totals["row"], rows=[totals["row"]]))
    else:
        out.append(result("sum_of_parts", "pass", kind="no_totals_row", rows=[]))
    loads = [r for r in rows if r["miles"] > 0 and r not in read_as_data]
    bad = []
    for r in loads:
        lh, fsc, acc, carrier = r["linehaul_rev"], r["fuel_surcharge"], r["accessorials"], r["carrier_cost"]
        reasons = []
        if not 1 <= r["miles"] <= 3000 or not 0 <= r["empty_miles"] <= r["miles"]:
            reasons.append("miles")
        if not CENTS_PER_MILE[0] * r["miles"] <= lh <= CENTS_PER_MILE[1] * r["miles"]:
            reasons.append("linehaul per mile")
        if lh and not FSC_SHARE[0] * lh <= fsc <= FSC_SHARE[1] * lh:
            reasons.append("fuel surcharge against linehaul")
        if not 0 <= acc <= ACCESSORIAL_CAP:
            reasons.append("accessorials")
        if carrier is not None and not 0 < carrier <= CARRIER_SHARE * (lh + fsc):
            reasons.append("carrier cost")
        if reasons:
            bad.append((r["row"], reasons))
    on_time = [r["on_time"] for r in loads if r["on_time"] is not None]
    share = sum(on_time) / len(on_time) if on_time else 1.0
    out.append(result("unit_range", "flag" if bad or share < ON_TIME_FLOOR else "pass", rows=[n for n, _ in bad],
                      reasons=sorted({x for _, rs in bad for x in rs}), on_time_share=round(share, 4)))
    diff = total_rev - invoiced
    count_off = len(rows) - invoice_count
    if diff == 0 and count_off == 0:
        out.append(result("control_total", "pass", diff=0, count_off=0))
    else:
        cause, rows_named = "unexplained", []
        flipped = [r for r in rows if r["miles"] == 0 and rev(r) > 0 and diff == 2 * rev(r)]
        dupe_rev = sum(rev(next(x for x in rows if x["row"] == v[-1])) for v in dupes.values())
        if flipped:
            cause, rows_named = "credit_sign", [flipped[0]["row"]]
        elif dupes and diff == dupe_rev:
            cause, rows_named = "duplicates", [v[-1] for v in dupes.values()]
        elif read_as_data and diff == rev(read_as_data[0]):
            cause, rows_named = "totals_row", [read_as_data[0]["row"]]
        out.append(result("control_total", "flag", diff=diff, count_off=count_off, cause=cause, rows=rows_named))
    return out


def tms_accepts(results, problems):
    """Whether a proposed mapping passes validation, and the reasons when it doesn't."""
    reasons = [p[1] for p in problems] + [r["rule"] for r in results if r["status"] != "pass"]
    return not reasons, reasons


# ---------------------------------------------------------------------- writing results with their IDs
class Checker:
    def __init__(self, ledger, intake):
        self.L, self.intake = ledger, intake

    def write(self, company, res, scope, ops, morning, refs=(), source_ids=(), **params):
        p = dict(res["params"], **params)
        return self.L.check(company, res["rule"], res["status"], res["severity"], scope, ops, morning, p, refs,
                            source_ids)

    # ------------------------------------------------------------------ Sideoats
    def sideoats(self, morning, ops, register, sites, battery, settlement, src_ids):
        L = self.L
        for sid, asset in register.items():
            if asset["offtake"] == "arbitrage":
                continue
            parsed = sites.get(sid)
            delivered = settlement["assets"].get(sid, {}).get("delivered_kwh") if settlement else None
            name = asset["name"]
            if parsed is None:
                refs = [delivered] if delivered else []
                L.check("sideoats", "continuity", "flag", "error", f"sideoats/{sid}", ops, morning,
                        {"site": sid, "site_name": name, "delivered": delivered}, refs, [])
                continue
            L.check("sideoats", "continuity", "pass", "error", f"sideoats/{sid}", ops, morning,
                    {"site": sid, "site_name": name}, [], [src_ids.get(sid)])
            gen, cur, ins, cap = parsed["generation_kwh"], parsed["curtailment_kwh"], parsed["insolation"], asset["capacity"]
            g, c, i, k = (L.value(x) for x in (gen, cur, ins, cap))
            expected = L.derive(f"sideoats/{sid}", ops, "expected_kwh", "product", [cap, ins], k * i / 1000, "kwh",
                                "capacity times the day's sunlight per square meter, the most the site could make")
            ratio = L.derive(f"sideoats/{sid}", ops, "output_ratio", "ratio", [gen, cur, expected],
                             (g + c) / (k * i / 1000) if k * i else None, "ratio",
                             "generation plus curtailment over that ceiling")
            r = L.value(ratio)
            share = c / (g + c) if g + c else 0
            if r is None or not RANGE_RATIO[0] <= r <= RANGE_RATIO[1]:
                status = "flag"
            elif share >= CURTAILED_SHARE:
                status = "expected"
            else:
                status = "pass"
            L.check("sideoats", "unit_range", status, "error", f"sideoats/{sid}", ops, morning,
                    {"site": sid, "site_name": name, "gen": gen, "curtailment": cur, "expected": expected,
                     "ratio": ratio, "low": RANGE_RATIO[0], "high": RANGE_RATIO[1]},
                    [gen, cur, expected, ratio], [src_ids.get(sid)])
            if delivered:
                d = L.value(delivered)
                loss = L.derive(f"sideoats/{sid}", ops, "line_loss", "ratio", [gen, delivered],
                                1 - d / g if g else None, "ratio", "one minus delivered over generated")
                lv = L.value(loss)
                ok = lv is not None and LINE_LOSS[0] <= lv <= LINE_LOSS[1]
                L.check("sideoats", "settlement_tie", "pass" if ok else "flag", "error", f"sideoats/{sid}", ops, morning,
                        {"site": sid, "site_name": name, "gen": gen, "delivered": delivered, "loss": loss},
                        [gen, delivered, loss], [src_ids.get(sid), src_ids.get("settlement")])
        if battery:
            sid = battery["asset"]
            if L.value(battery["cycles"]):
                rte = L.derive(f"sideoats/{sid}", ops, "round_trip", "ratio", [battery["discharge_kwh"], battery["charge_kwh"]],
                               L.value(battery["discharge_kwh"]) / L.value(battery["charge_kwh"]), "ratio",
                               "discharged over charged")
                ok = BATTERY_RTE[0] <= L.value(rte) <= BATTERY_RTE[1]
                L.check("sideoats", "unit_range", "pass" if ok else "flag", "error", f"sideoats/{sid}", ops, morning,
                        {"site": sid, "site_name": register[sid]["name"], "rte": rte}, [rte], [src_ids.get("battery")])
            paid = settlement["assets"].get(sid, {}).get("settlement") if settlement else None
            if paid:
                same = L.value(paid) == L.value(battery["arbitrage_revenue"])
                L.check("sideoats", "settlement_tie", "pass" if same else "flag", "error", f"sideoats/{sid}", ops, morning,
                        {"site": sid, "site_name": register[sid]["name"], "reported": battery["arbitrage_revenue"],
                         "settled": paid}, [battery["arbitrage_revenue"], paid],
                        [src_ids.get("battery"), src_ids.get("settlement")])

    # ------------------------------------------------------------------ Kiskadee
    def kiskadee(self, morning, ops, results, tms, invoicing, src_ids, quarantined=False, reasons=()):
        L = self.L
        refs_by_rule = {"control_total": [tms.get("revenue"), invoicing.get("invoiced"), tms.get("loads"),
                                          invoicing.get("invoice_count")] if tms else [invoicing.get("invoiced")],
                        "key_unique": [tms.get("loads")] if tms else [], "sum_of_parts": [tms.get("revenue")] if tms else [],
                        "unit_range": [tms.get("loads")] if tms else [], "dates": [tms.get("loads")] if tms else []}
        for res in results:
            extra = {}
            if res["rule"] == "control_total" and res["status"] == "flag" and tms:
                extra["gap"] = L.derive("kiskadee", ops, "control_gap", "difference", [tms["revenue"], invoicing["invoiced"]],
                                        L.value(tms["revenue"]) - L.value(invoicing["invoiced"]), "cents",
                                        "TMS revenue minus the invoicing batch total")
            self.write("kiskadee", res, "kiskadee/tms", ops, morning,
                       [r for r in refs_by_rule.get(res["rule"], []) if r] + list(extra.values()),
                       [src_ids.get("tms"), src_ids.get("invoicing")], quarantined=quarantined, **extra)
        if tms and not quarantined:
            budget = self.intake.budget_fact("kiskadee", "loads", ops, ops)
            if budget:
                ratio = L.derive("kiskadee", ops, "volume_ratio", "ratio", [tms["loads"], budget],
                                 L.value(tms["loads"]) / L.value(budget) if L.value(budget) else None, "ratio",
                                 "loads over the day's budgeted loads")
                ok = VOLUME_BAND[0] <= L.value(ratio) <= VOLUME_BAND[1]
                L.check("kiskadee", "volume_band", "pass" if ok else "flag", "info", "kiskadee/tms", ops, morning,
                        {"loads": tms["loads"], "budget": budget, "ratio": ratio, "low": VOLUME_BAND[0],
                         "high": VOLUME_BAND[1]}, [tms["loads"], budget, ratio], [src_ids.get("tms")])

    # ------------------------------------------------------------------ Possumhaw
    def possumhaw(self, morning, audit, deposit, card_by_date, src_ids):
        L = self.L
        ops = audit["date"]
        adr, sold, room = (L.value(audit[k]) for k in ("adr_reported", "rooms_sold", "room_revenue"))
        product = L.derive("possumhaw", ops, "adr_times_rooms", "product", [audit["adr_reported"], audit["rooms_sold"]],
                           adr * sold, "cents", "reported ADR times rooms sold")
        gap = L.derive("possumhaw", ops, "adr_gap", "difference", [product, audit["room_revenue"]], adr * sold - room,
                       "cents", "that product minus room revenue")
        ok = abs(adr * sold - room) <= (sold + 1) // 2
        L.check("possumhaw", "internal_consistency", "pass" if ok else "flag", "error", "possumhaw/audit", ops, morning,
                {"adr": audit["adr_reported"], "rooms": audit["rooms_sold"], "room_revenue": audit["room_revenue"],
                 "product": product, "gap": gap}, [audit["adr_reported"], audit["rooms_sold"], audit["room_revenue"],
                                                   product, gap], [src_ids.get("audit")])
        parts = sum(L.value(audit[k]) for k in ("room_revenue", "fb_revenue", "other_revenue"))
        paid = L.value(audit["card_settlements"]) + L.value(audit["direct_bill"])
        total = L.value(audit["total_revenue"])
        ok = parts == total == paid
        L.check("possumhaw", "sum_of_parts", "pass" if ok else "flag", "error", "possumhaw/audit", ops, morning,
                {"total": audit["total_revenue"]}, [audit["total_revenue"], audit["card_settlements"], audit["direct_bill"]],
                [src_ids.get("audit")])
        L.check("possumhaw", "deposit_tie", "expected", "error", "possumhaw/deposits", ops, morning,
                {"card": audit["card_settlements"], "when": "tomorrow"}, [audit["card_settlements"]], [src_ids.get("audit")])
        if deposit and deposit["batch_date"] in card_by_date:
            card = card_by_date[deposit["batch_date"]]
            same = L.value(card) == L.value(deposit["gross"])
            L.check("possumhaw", "deposit_tie", "pass" if same else "flag", "error", "possumhaw/deposits",
                    deposit["batch_date"], morning, {"card": card, "deposit": deposit["gross"],
                                                     "deposit_date": deposit["deposit_date"]},
                    [card, deposit["gross"]], [src_ids.get("deposits"), src_ids.get("audit")])

    # ------------------------------------------------------------------ the data room
    def dataroom(self, fin, cust, src_ids):
        L = self.L
        months = sorted({m for (_, m) in fin if len(m) == 7})
        fys = {"FY2024": months[0:12], "FY2025": months[12:24], "FY2026": months[24:36]}
        for fy, ms in fys.items():
            for metric in ("total_revenue", "gross_profit", "reported_ebitda"):
                monthly = [fin[(metric, m)] for m in ms]
                total = L.derive("brightrow", fy, f"sum:{metric}", "sum", monthly, sum(L.value(x) for x in monthly), "cents",
                                 f"sum of the 12 monthly values for {fy}")
                annual = fin[(f"annual:{metric}", fy)]
                ok = L.value(total) == L.value(annual)
                L.check("brightrow", "annual_tie", "pass" if ok else "flag", "error", "brightrow/financials", None, None,
                        {"fy": fy, "metric": metric, "monthly": total, "annual": annual}, [total, annual],
                        [src_ids.get("financials")])
        broken = []
        for m in months:
            lines = sum(L.value(fin[(f"revenue:{k}", m)]) for k in ("pm", "cr", "mc", "ms") if (f"revenue:{k}", m) in fin)
            if lines != L.value(fin[("total_revenue", m)]):
                broken.append(m)
            gp = L.value(fin[("total_revenue", m)]) - L.value(fin[("total_cost", m)])
            if gp != L.value(fin[("gross_profit", m)]):
                broken.append(m)
            settle = L.value(fin[("settlement", m)]) if ("settlement", m) in fin else 0
            if gp - L.value(fin[("total_sga", m)]) - settle != L.value(fin[("reported_ebitda", m)]):
                broken.append(m)
        L.check("brightrow", "sum_of_parts", "flag" if broken else "pass", "error", "brightrow/financials", None, None,
                {"months": sorted(set(broken))}, [], [src_ids.get("financials")])
        reclass = [m for m in months if ("revenue:mc", m) not in fin]
        memo_ok = all(("memo:revenue", m) in fin for m in reclass) and \
            not any(("memo:revenue", m) in fin for m in months if m not in reclass)
        L.check("brightrow", "reclass", "pass" if memo_ok and reclass else "flag", "error", "brightrow/financials", None, None,
                {"through": reclass[-1] if reclass else None, "months": len(reclass)}, [], [src_ids.get("financials")])
        for fy, ms in fys.items():
            rev = L.derive("brightrow", fy, "sum:total_revenue_customers", "sum", [fin[("total_revenue", m)] for m in ms],
                           sum(L.value(fin[("total_revenue", m)]) for m in ms), "cents", f"P&L revenue for {fy}")
            listed = [ref for (name, f), ref in cust.items() if f == fy and name != "Total"]
            listed_sum = sum(L.value(x) for x in listed)
            ok = listed_sum == L.value(cust[("Total", fy)]) == L.value(rev)
            L.check("brightrow", "customer_tie", "pass" if ok else "flag", "error", "brightrow/customers", None, None,
                    {"fy": fy, "customers_total": cust[("Total", fy)], "revenue": rev},
                    [cust[("Total", fy)], rev], [src_ids.get("customers"), src_ids.get("financials")])


def held(ledger, morning):
    """{company: [error flags]} for one morning. A company with any is held for review."""
    out = {}
    for c in ledger.checks(morning=morning, status="flag", severity="error"):
        out.setdefault(c["company"], []).append(c)
    return out
