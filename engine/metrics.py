"""Derived values for the morning report: each company's month to date against budget, the fund's rollups, and
the daily series behind each sparkline.

Every KPI is a derived value whose inputs are facts or other derived values, so a click on any number walks back
to the rows it came from. Only facts from accepted files count, so a quarantined file never reaches a total. A
variance carries the comparison it's against, and the renderer writes its direction ("above budget"), so no
sentence can say above when the number is below. The EBITDA estimate is the usual flash: revenue less variable
costs from the data, less fixed costs from the budget, pro-rated by day.
"""
from datetime import date, timedelta

PERIOD_SEP = ".."


def day_before(iso):
    return (date.fromisoformat(iso) - timedelta(days=1)).isoformat()


class Builder:
    """Shared helpers for derived values over the ledger."""

    def __init__(self, state):
        self.L, self.intake = state["ledger"], state["intake"]

    def facts(self, entity, metric, first, last):
        """Refs of accepted facts for one entity and metric over a day range, one per day, oldest first."""
        rows = self.L.conn.execute(
            "SELECT f.fact_id, f.period FROM facts f JOIN sources s ON s.source_id = f.source_id WHERE f.entity = ? "
            "AND f.metric = ? AND f.period BETWEEN ? AND ? AND s.status = 'accepted' ORDER BY f.period, f.fact_id",
            (entity, metric, first, last)).fetchall()
        by_day = {}
        for fid, period in rows:
            by_day[period] = f"F{fid}"
        return [by_day[d] for d in sorted(by_day)]

    def total(self, entity, period, metric, refs, unit, transform):
        return self.L.derive(entity, period, metric, "sum", refs, sum(self.L.value(r) or 0 for r in refs), unit, transform)

    def ratio(self, entity, period, metric, num, den, transform, unit="ratio"):
        d = self.L.value(den)
        return self.L.derive(entity, period, metric, "ratio", [num, den], self.L.value(num) / d if d else None, unit,
                             transform)

    def diff(self, entity, period, metric, a, b, unit, transform):
        return self.L.derive(entity, period, metric, "difference", [a, b], self.L.value(a) - self.L.value(b), unit,
                             transform)

    def variance(self, entity, period, metric, actual, budget, unit, vs="budget"):
        return self.L.derive(entity, period, metric, "variance", [actual, budget],
                             self.L.value(actual) - self.L.value(budget), unit, f"actual minus {vs}", extra={"vs": vs})

    def product(self, entity, period, metric, a, b, unit, transform, scale=1):
        return self.L.derive(entity, period, metric, "product", [a, b], self.L.value(a) * self.L.value(b) * scale, unit,
                             transform)

    def combine(self, entity, period, metric, plus, minus, unit, transform):
        value = sum(self.L.value(r) for r in plus) - sum(self.L.value(r) for r in minus)
        return self.L.derive(entity, period, metric, "combine", list(plus) + list(minus), value, unit, transform,
                             extra={"plus": list(plus), "minus": list(minus)})


class Report(Builder):
    """The report for one morning: the operating day before it, and the month to date."""

    def __init__(self, state, morning):
        super().__init__(state)
        self.state = state
        self.morning = morning
        self.ops = day_before(morning)
        self.first = self.ops[:8] + "01"
        self.period = f"{self.first}{PERIOD_SEP}{self.ops}"
        self.days = (date.fromisoformat(self.ops) - date.fromisoformat(self.first)).days + 1
        self.register = state["register"]
        self.k = {}

    def budget(self, company, column, asset=None):
        return self.intake.budget_fact(company, column, self.first, self.ops, asset=asset)

    # ------------------------------------------------------------------ Sideoats
    def sideoats(self):
        p, k = self.period, {}
        sites = [s for s, a in self.register.items() if a["offtake"] != "arbitrage"]
        battery = [s for s, a in self.register.items() if a["offtake"] == "arbitrage"]
        gen, cur, rev, bud_gen, bud_rev, opex, weighted, cap_days, ceiling = [], [], [], [], [], [], [], [], []
        for s in sites:
            ent = f"sideoats/{s}"
            g = self.facts(ent, "generation_kwh", self.first, self.ops)
            c = self.facts(ent, "curtailment_kwh", self.first, self.ops)
            gen.append(self.total(ent, p, "generation", g, "kwh", f"sum of {len(g)} daily meter readings"))
            cur.append(self.total(ent, p, "curtailment", c, "kwh", f"sum of {len(c)} daily readings"))
            bud_gen.append(self.budget("sideoats", "generation_kwh", s))
            cap = self.register[s]["capacity"]
            avail = self.facts(ent, "availability", self.first, self.ops)
            ins = self.facts(ent, "insolation", self.first, self.ops)
            capv = self.L.value(cap)
            weighted.append(sum(self.L.value(a) for a in avail) * capv)
            cap_days.append(capv * len(avail))
            ceiling.append(sum(self.L.value(i) for i in ins) * capv / 1000)
            k[f"avail_inputs_{s}"] = avail
        for s in sites + battery:
            ent = f"sideoats/{s}"
            r = self.facts(ent, "settlement", self.first, self.ops)
            rev.append(self.total(ent, p, "revenue", r, "cents", f"sum of {len(r)} daily settlement lines"))
            bud_rev.append(self.budget("sideoats", "revenue_cents", s))
            opex.append(self.budget("sideoats", "opex_cents", s))
        k["generation"] = self.total("sideoats", p, "generation", gen, "kwh", "sum of the four sites")
        k["generation_budget"] = self.total("sideoats", p, "generation_budget", bud_gen, "kwh", "sum of the four sites' budgets")
        k["generation_var"] = self.variance("sideoats", p, "generation_var", k["generation"], k["generation_budget"], "kwh")
        k["curtailment"] = self.total("sideoats", p, "curtailment", cur, "kwh", "sum of the four sites")
        k["revenue"] = self.total("sideoats", p, "revenue", rev, "cents", "sum of the four sites and the battery")
        k["revenue_budget"] = self.total("sideoats", p, "revenue_budget", bud_rev, "cents", "sum of the five budgets")
        k["revenue_var"] = self.variance("sideoats", p, "revenue_var", k["revenue"], k["revenue_budget"], "cents")
        avail_refs = [r for s in sites for r in k.pop(f"avail_inputs_{s}")]
        k["availability"] = self.L.derive("sideoats", p, "availability", "weighted_average",
                                          avail_refs + [self.register[s]["capacity"] for s in sites],
                                          sum(weighted) / sum(cap_days) / 10000 if sum(cap_days) else None, "ratio",
                                          "daily availability averaged by each site's capacity")
        k["performance_ratio"] = self.L.derive("sideoats", p, "performance_ratio", "ratio", gen + cur,
                                               (self.L.value(k["generation"]) + self.L.value(k["curtailment"]))
                                               / sum(ceiling) if sum(ceiling) else None, "ratio",
                                               "generation plus curtailment over capacity times sunlight")
        k["opex_budget"] = self.total("sideoats", p, "opex_budget", opex, "cents", "fixed operating costs at budget")
        k["ebitda"] = self.diff("sideoats", p, "ebitda", k["revenue"], k["opex_budget"], "cents",
                                "revenue less fixed operating costs at budget")
        k["ebitda_budget"] = self.diff("sideoats", p, "ebitda_budget", k["revenue_budget"], k["opex_budget"], "cents",
                                       "budget revenue less budget operating costs")
        k["ebitda_var"] = self.variance("sideoats", p, "ebitda_var", k["ebitda"], k["ebitda_budget"], "cents")
        remit = self.facts("sideoats", "remittance", self.first, self.ops)
        k["cash"] = self.total("sideoats", p, "cash", remit, "cents", f"sum of {len(remit)} utility remittances received this month")
        self.k["sideoats"] = k
        return k

    # ------------------------------------------------------------------ Kiskadee
    def kiskadee(self):
        p, k, ent = self.period, {}, "kiskadee"
        f = lambda m: self.facts(ent, m, self.first, self.ops)  # noqa: E731
        loads, rev, carrier, asset, loaded, empty, ontime = (f(m) for m in (
            "loads", "revenue", "carrier_cost", "asset_miles", "loaded_miles", "empty_miles", "on_time_loads"))
        held = self.days - len(loads)
        note = f" ({held} day held for review)" if held == 1 else f" ({held} days held for review)" if held else ""
        k["loads"] = self.total(ent, p, "loads", loads, "count", f"sum of {len(loads)} daily TMS counts{note}")
        k["loads_budget"] = self.budget("kiskadee", "loads")
        k["loads_var"] = self.variance(ent, p, "loads_var", k["loads"], k["loads_budget"], "count")
        k["revenue"] = self.total(ent, p, "revenue", rev, "cents", f"sum of {len(rev)} daily TMS totals{note}")
        k["revenue_budget"] = self.budget("kiskadee", "revenue_cents")
        k["revenue_var"] = self.variance(ent, p, "revenue_var", k["revenue"], k["revenue_budget"], "cents")
        k["revenue_per_load"] = self.ratio(ent, p, "revenue_per_load", k["revenue"], k["loads"], "revenue over loads",
                                           unit="cents")
        k["carrier_cost"] = self.total(ent, p, "carrier_cost", carrier, "cents", "brokered loads' carrier cost")
        k["asset_miles"] = self.total(ent, p, "asset_miles", asset, "miles", "miles on the company's own trucks")
        rate = self.intake.budget_fact("kiskadee", "std_cost_per_mile_cents", self.first, self.first)
        k["asset_cost"] = self.product(ent, p, "asset_cost", k["asset_miles"], rate, "cents",
                                       "own-truck miles times the budget's standard cost per mile")
        k["gross_margin"] = self.combine(ent, p, "gross_margin", [k["revenue"]], [k["carrier_cost"], k["asset_cost"]],
                                         "cents", "revenue less carrier cost and own-truck cost")
        k["gross_margin_pct"] = self.ratio(ent, p, "gross_margin_pct", k["gross_margin"], k["revenue"],
                                           "gross margin over revenue")
        bud_carrier = self.budget("kiskadee", "carrier_cost_cents")
        bud_miles = self.budget("kiskadee", "asset_miles")
        bud_asset = self.product(ent, p, "asset_cost_budget", bud_miles, rate, "cents", "budget miles times the standard cost")
        k["gross_margin_budget"] = self.combine(ent, p, "gross_margin_budget", [k["revenue_budget"]],
                                                [bud_carrier, bud_asset], "cents", "budget revenue less budget costs")
        k["on_time"] = self.ratio(ent, p, "on_time", self.total(ent, p, "on_time_loads", ontime, "count",
                                                                  "loads marked on time"), k["loads"],
                                  "on-time loads over loads")
        lm = self.total(ent, p, "loaded_miles", loaded, "miles", "loaded miles")
        em = self.total(ent, p, "empty_miles", empty, "miles", "empty miles")
        all_miles = self.L.derive(ent, p, "all_miles", "sum", [lm, em], self.L.value(lm) + self.L.value(em), "miles",
                                  "loaded plus empty miles")
        k["empty_pct"] = self.ratio(ent, p, "empty_pct", em, all_miles, "empty miles over all miles")
        fixed = self.budget("kiskadee", "fixed_cost_cents")
        k["ebitda"] = self.diff(ent, p, "ebitda", k["gross_margin"], fixed, "cents", "gross margin less fixed costs at budget")
        k["ebitda_budget"] = self.diff(ent, p, "ebitda_budget", k["gross_margin_budget"], fixed, "cents",
                                       "budget gross margin less budget fixed costs")
        k["ebitda_var"] = self.variance(ent, p, "ebitda_var", k["ebitda"], k["ebitda_budget"], "cents")
        cash = self.facts(ent, "cash_applied", self.first, self.ops)
        k["cash"] = self.total(ent, p, "cash", cash, "cents", f"cash applied over {len(cash)} daily batches")
        self.k["kiskadee"] = k
        return k

    # ------------------------------------------------------------------ Possumhaw
    def possumhaw(self):
        p, k, ent = self.period, {}, "possumhaw"
        f = lambda m: self.facts(ent, m, self.first, self.ops)  # noqa: E731
        sold = self.total(ent, p, "rooms_sold", f("rooms_sold"), "count", "sum of nightly rooms sold")
        avail = self.total(ent, p, "rooms_available", f("rooms_available"), "count", "sum of nightly rooms available")
        room = self.total(ent, p, "room_revenue", f("room_revenue"), "cents", "sum of nightly room revenue")
        fb = self.total(ent, p, "fb_revenue", f("fb_revenue"), "cents", "sum of nightly food and beverage")
        other = self.total(ent, p, "other_revenue", f("other_revenue"), "cents", "sum of nightly spa, golf, and other revenue")
        k["occupancy"] = self.ratio(ent, p, "occupancy", sold, avail, "rooms sold over rooms available")
        k["adr"] = self.ratio(ent, p, "adr", room, sold, "room revenue over rooms sold", unit="cents")
        k["revpar"] = self.ratio(ent, p, "revpar", room, avail, "room revenue over rooms available", unit="cents")
        k["revenue"] = self.L.derive(ent, p, "revenue", "sum", [room, fb, other],
                                     sum(self.L.value(x) for x in (room, fb, other)), "cents", "rooms, F&B, and other")
        b = {c: self.budget("possumhaw", c) for c in ("room_revenue_cents", "fb_revenue_cents", "other_revenue_cents",
                                                       "rooms_sold", "fixed_cost_cents")}
        k["revenue_budget"] = self.L.derive(ent, p, "revenue_budget", "sum", [b["room_revenue_cents"], b["fb_revenue_cents"],
                                                                             b["other_revenue_cents"]],
                                            sum(self.L.value(b[c]) for c in ("room_revenue_cents", "fb_revenue_cents",
                                                                           "other_revenue_cents")), "cents",
                                            "budget rooms, F&B, and other")
        k["revenue_var"] = self.variance(ent, p, "revenue_var", k["revenue"], k["revenue_budget"], "cents")
        k["fb_share"] = self.ratio(ent, p, "fb_share", fb, k["revenue"], "F&B over total revenue")
        rates = {c: self.intake.budget_fact("possumhaw", c, self.first, self.first)
                 for c in ("room_cost_per_occupied_cents", "fb_cost_bp", "other_cost_bp")}

        def costs(sold_ref, fb_ref, other_ref, tag):
            room_cost = self.product(ent, p, f"room_cost{tag}", sold_ref, rates["room_cost_per_occupied_cents"], "cents",
                                     "rooms sold times the cost per occupied room")
            fb_cost = self.product(ent, p, f"fb_cost{tag}", fb_ref, rates["fb_cost_bp"], "cents", "F&B times its cost rate",
                                   scale=1 / 10000)
            other_cost = self.product(ent, p, f"other_cost{tag}", other_ref, rates["other_cost_bp"], "cents",
                                      "other revenue times its cost rate", scale=1 / 10000)
            return [room_cost, fb_cost, other_cost]

        k["ebitda"] = self.combine(ent, p, "ebitda", [k["revenue"]], costs(sold, fb, other, "") + [b["fixed_cost_cents"]],
                                   "cents", "revenue less variable costs at budget rates and fixed costs at budget")
        k["ebitda_budget"] = self.combine(ent, p, "ebitda_budget", [k["revenue_budget"]],
                                          costs(b["rooms_sold"], b["fb_revenue_cents"], b["other_revenue_cents"], "_budget")
                                          + [b["fixed_cost_cents"]], "cents", "the same on budget volumes")
        k["ebitda_var"] = self.variance(ent, p, "ebitda_var", k["ebitda"], k["ebitda_budget"], "cents")
        dep = self.facts(ent, "deposit_net", day_before(self.first), day_before(self.ops))
        k["cash"] = self.total(ent, p, "cash", dep, "cents", f"sum of {len(dep)} card deposits net of fees this month")
        self.k["possumhaw"] = k
        return k

    # ------------------------------------------------------------------ the fund
    def fund(self):
        c = [self.k[x] for x in ("sideoats", "kiskadee", "possumhaw")]
        p, k = self.period, {}
        k["revenue"] = self.total("fund", p, "revenue", [x["revenue"] for x in c], "cents",
                                  "sum of the three companies' revenue")
        k["revenue_budget"] = self.total("fund", p, "revenue_budget", [x["revenue_budget"] for x in c], "cents",
                                         "sum of the three companies' revenue budgets")
        k["revenue_var"] = self.variance("fund", p, "revenue_var", k["revenue"], k["revenue_budget"], "cents")
        k["ebitda"] = self.total("fund", p, "ebitda", [x["ebitda"] for x in c], "cents",
                                 "sum of the three companies' EBITDA estimates")
        k["ebitda_budget"] = self.total("fund", p, "ebitda_budget", [x["ebitda_budget"] for x in c], "cents",
                                        "sum of the three companies' EBITDA budgets")
        k["ebitda_var"] = self.variance("fund", p, "ebitda_var", k["ebitda"], k["ebitda_budget"], "cents")
        k["cash"] = self.total("fund", p, "cash", [x["cash"] for x in c], "cents",
                               "sum of the cash the three companies collected")
        flags = [cc["ref"] for cc in self.L.checks(morning=self.morning, status="flag")]
        k["open_flags"] = self.L.derive("fund", self.morning, "open_flags", "count", flags, len(flags), "count",
                                        "checks flagged this morning")
        self.k["fund"] = k
        return k

    def build(self):
        self.sideoats()
        self.kiskadee()
        self.possumhaw()
        self.fund()
        return self.k

    # ------------------------------------------------------------------ sparklines (below), board month (after)
    def series(self, entity, metric, days):
        """Daily values for a chart, None where a day has no accepted fact. Charts carry no figures of their own."""
        vals = {}
        for fid, period, value in self.L.conn.execute(
                "SELECT f.fact_id, f.period, f.value FROM facts f JOIN sources s ON s.source_id = f.source_id "
                "WHERE f.entity = ? AND f.metric = ? AND s.status = 'accepted'", (entity, metric)):
            vals[period] = value
        return [vals.get(d) for d in days]


class BoardMonth(Report):
    """Kiskadee's month for its board: the month against budget, the margin bridge, and cash and receivables."""

    def __init__(self, state, month):
        y, m = int(month[:4]), int(month[5:])
        nxt = f"{y + (m == 12):04d}-{m % 12 + 1:02d}-01"
        super().__init__(state, nxt)
        self.month = month

    def build(self):
        k = self.kiskadee()
        p, ent = self.period, "kiskadee"
        gm_per_load_budget = self.ratio(ent, p, "gm_per_load_budget", k["gross_margin_budget"], k["loads_budget"],
                                        "budget gross margin over budget loads", unit="cents")
        rpl_budget = self.ratio(ent, p, "revenue_per_load_budget", k["revenue_budget"], k["loads_budget"],
                                "budget revenue over budget loads", unit="cents")
        k["volume_effect"] = self.product(ent, p, "volume_effect", k["loads_var"], gm_per_load_budget, "cents",
                                          "loads above or below budget times the budget margin per load")
        rate_gap = self.diff(ent, p, "revenue_per_load_gap", k["revenue_per_load"], rpl_budget, "cents",
                             "revenue per load less the budget's")
        k["rate_effect"] = self.product(ent, p, "rate_effect", rate_gap, k["loads"], "cents",
                                        "that difference times actual loads")
        k["cost_effect"] = self.combine(ent, p, "cost_effect", [k["gross_margin"]],
                                        [k["gross_margin_budget"], k["volume_effect"], k["rate_effect"]], "cents",
                                        "what's left of the margin gap after volume and rate, and that's cost")
        k["gross_margin_var"] = self.variance(ent, p, "gross_margin_var", k["gross_margin"], k["gross_margin_budget"],
                                              "cents")
        inv = self.facts(ent, "invoiced", self.first, self.ops)
        k["invoiced"] = self.total(ent, p, "invoiced", inv, "cents", f"sum of {len(inv)} daily invoicing batches")
        ar = self.facts(ent, "ar_balance", self.ops, self.ops)
        k["ar_end"] = ar[-1] if ar else None
        daily = self.L.derive(ent, p, "revenue_per_day", "ratio", [k["revenue"]], self.L.value(k["revenue"]) / self.days,
                              "cents", f"revenue over the month's {self.days} days")
        k["dso"] = self.ratio(ent, p, "dso", k["ar_end"], daily, "receivables over a day's revenue", unit="days")
        self.k["kiskadee"] = k
        return k
