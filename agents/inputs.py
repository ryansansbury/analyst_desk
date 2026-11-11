"""What each agent sees: a fixed JSON input built from the ledger. No model is called here.

Every figure an agent may cite comes with a local ID (D7, F3), a label and the value as the page shows it. Local
IDs keep prompts short, and each one carries its meaning (company, measure, period), so the build resolves it to
whatever the ledger calls that value today. A recording survives code changes that renumber the ledger, and it
goes stale only when the value it saw has changed.
"""
from engine import gate
from engine.intake import TMS_V1

SCHEMA = [
    {"field": "load_id", "kind": "text", "meaning": "the load's unique ID"},
    {"field": "date", "kind": "date", "meaning": "the day the load shipped or was picked up"},
    {"field": "customer", "kind": "text", "meaning": "the customer billed for the load"},
    {"field": "lane", "kind": "text", "meaning": "origin and destination"},
    {"field": "miles", "kind": "whole number", "meaning": "loaded miles"},
    {"field": "empty_miles", "kind": "whole number", "meaning": "empty or deadhead miles driven to reach the load"},
    {"field": "linehaul_rev", "kind": "money", "meaning": "linehaul revenue for the load"},
    {"field": "fuel_surcharge", "kind": "money", "meaning": "fuel surcharge revenue for the load"},
    {"field": "accessorials", "kind": "money",
     "meaning": "accessorial charges like detention or lumper fees, negative on a credit row"},
    {"field": "carrier_cost", "kind": "money",
     "meaning": "what was paid to an outside carrier on a brokered load, blank on the company's own trucks"},
    {"field": "on_time", "kind": "yes or no", "meaning": "whether the load was delivered on time"},
]


class Ids:
    """Local IDs for one task's input, each tied to a ledger value by its meaning."""

    def __init__(self, ledger):
        self.L = ledger
        self.items, self.by_ref, self.n = {}, {}, {"F": 0, "D": 0, "C": 0}

    def add(self, ref, label):
        if ref in self.by_ref:
            return self.by_ref[ref]
        row = self.L.get(ref)
        kind = ref[0]
        self.n[kind] += 1
        local = f"{kind}{self.n[kind]}"
        if kind == "C":
            key = ["C", row["deliverable"], row["metric"] or "", row["location"]]
            unit, shown = "claim", row["status"]
        else:
            key = [kind, row["entity"], row["metric"], row["period"]]
            unit, shown = row["unit"], gate.display(self.L, ref)
        self.items[local] = {"id": local, "label": label, "shown": shown, "unit": unit, "key": key}
        self.by_ref[ref] = local
        return local

    def listing(self, locals_):
        return [{k: self.items[x][k] for k in ("id", "label", "shown")} for x in locals_]

    def keys(self):
        return {x: {"key": v["key"], "shown": v["shown"], "unit": v["unit"]} for x, v in self.items.items()}


# ---------------------------------------------------------------------- the intake mapper
def intake(file_name, sample):
    example = {"header_rows": TMS_V1["header_rows"], "columns": TMS_V1["columns"], "date_format": TMS_V1["date_format"],
               "money_format": TMS_V1["money_format"], "on_time": TMS_V1["on_time"],
               "totals_label": TMS_V1["totals_label"]}
    return {"task": "intake_mapper", "file": file_name, "top_rows": sample["top_rows"],
            "sample_rows": sample["sample_rows"], "last_rows": sample["last_rows"], "row_count": sample["row_count"],
            "schema": SCHEMA,
            "known_layout_example": example,
            "formats": {"date_format": "a Python strptime format string, like %m/%d/%Y",
                        "money_format": {"text": "currency text like $1,234.56 and -$250.00",
                                         "plain": "plain numbers like 1234.56 and -250",
                                         "paren": "text like 1,234.56 with negatives in parentheses (250.00)"}}}


# ---------------------------------------------------------------------- daily commentary
COMPANY_KPIS = {
    "sideoats": [("generation", "Generation, month to date"), ("generation_budget", "Generation budget, month to date"),
                ("generation_var", "Generation against budget"), ("curtailment", "Curtailment, month to date"),
                ("availability", "Availability, month to date"), ("performance_ratio", "Performance ratio"),
                ("revenue", "Revenue, month to date"), ("revenue_var", "Revenue against budget"),
                ("ebitda", "EBITDA estimate, month to date"), ("ebitda_var", "EBITDA estimate against budget")],
    "kiskadee": [("loads", "Loads, month to date"), ("loads_var", "Loads against budget"),
                   ("revenue", "Revenue, month to date"), ("revenue_var", "Revenue against budget"),
                   ("revenue_per_load", "Revenue per load"), ("gross_margin_pct", "Gross margin"),
                   ("on_time", "On-time delivery"), ("empty_pct", "Empty miles share"),
                   ("ebitda", "EBITDA estimate, month to date"), ("ebitda_var", "EBITDA estimate against budget")],
    "possumhaw": [("occupancy", "Occupancy, month to date"), ("adr", "ADR, month to date"),
                   ("revpar", "RevPAR, month to date"), ("revenue", "Revenue, month to date"),
                   ("revenue_var", "Revenue against budget"), ("fb_share", "Food and beverage share of revenue"),
                   ("ebitda", "EBITDA estimate, month to date"), ("ebitda_var", "EBITDA estimate against budget")],
}
NAMES = {"sideoats": "Sideoats Renewables", "kiskadee": "Kiskadee Freight", "possumhaw": "Possumhaw Lodge",
         "fund": "the fund"}


def commentary(ledger, report, morning, ops_label, check_notes):
    """check_notes: {company: [plain sentences about today's checks]}, written by the build from WORDS.md."""
    ids = Ids(ledger)
    companies = []
    for c, kpis in COMPANY_KPIS.items():
        locals_ = [ids.add(report[c][name], label) for name, label in kpis]
        companies.append({"company": c, "name": NAMES[c], "figures": ids.listing(locals_), "checks": check_notes.get(c, [])})
    return {"task": "daily_commentary", "morning": morning, "covers": ops_label, "companies": companies}, ids


# ---------------------------------------------------------------------- the board deck
SLIDES = [
    (1, "the month at a glance", [("loads", "Loads"), ("loads_var", "Loads against budget"), ("revenue", "Revenue"),
                                  ("revenue_var", "Revenue against budget"), ("gross_margin", "Gross margin"),
                                  ("gross_margin_pct", "Gross margin share of revenue"),
                                  ("ebitda", "EBITDA estimate"), ("ebitda_var", "EBITDA estimate against budget")],
     ["kpi_tiles"]),
    (2, "the revenue and margin bridge from budget to actual",
     [("gross_margin_budget", "Budget gross margin"), ("volume_effect", "Effect of loads above or below budget"),
      ("rate_effect", "Effect of revenue per load"), ("cost_effect", "Effect of costs"),
      ("gross_margin", "Actual gross margin"), ("gross_margin_var", "Gross margin against budget")],
     ["margin_bridge", "kpi_tiles"]),
    (3, "operations", [("on_time", "On-time delivery"), ("empty_pct", "Empty miles share"), ("loads", "Loads"),
                       ("revenue_per_load", "Revenue per load")],
     ["loads_by_week", "on_time_by_week", "empty_miles_by_week"]),
    (4, "cash and receivables", [("invoiced", "Invoiced"), ("cash", "Cash collected"), ("ar_end", "Receivables at month end"),
                                 ("dso", "Days sales outstanding")],
     ["invoiced_vs_collected", "receivables_by_week"]),
    (5, "risks and asks", [("on_time", "On-time delivery"), ("empty_pct", "Empty miles share"),
                           ("dso", "Days sales outstanding"), ("gross_margin_var", "Gross margin against budget")],
     ["none"]),
]


def deck(ledger, month_k, month_label):
    ids = Ids(ledger)
    slides = []
    for n, topic, figs, charts in SLIDES:
        locals_ = [ids.add(month_k[name], label) for name, label in figs]
        slides.append({"n": n, "topic": topic, "figures": ids.listing(locals_), "charts": charts})
    return {"task": "board_deck", "company": "Kiskadee Freight", "month": month_label, "slides": slides}, ids


# ---------------------------------------------------------------------- the memo writer
def memo(ledger, dm, deal, claim_refs, kpi_refs):
    """Everything the memo may cite, grouped the way the memo uses it."""
    ids = Ids(ledger)
    r = deal.refs

    def group(items):
        return ids.listing([ids.add(ref, label) for ref, label in items if ref])

    model_out = group([(r["ev"], "entry enterprise value at the deal team's entry multiple"),
                       (r["fees"], "transaction fees"), (r["debt0"], "senior debt at close"),
                       (r["equity0"], "equity at close"), (r["net_leverage_0"], "net leverage at close"),
                       (r["revenue_y5"], "FY2031 revenue in the base case"), (r["ebitda_y5"], "FY2031 EBITDA in the base case"),
                       (r["revenue_cagr"], "revenue growth a year from FY2026 to FY2031"),
                       (r["margin_y5"], "FY2031 EBITDA margin"), (r["ev_exit"], "exit enterprise value"),
                       (r["nd_exit"], "net debt at exit"), (r["equity_exit"], "equity at exit"), (r["moic"], "MOIC"),
                       (r["irr"], "IRR"), (r["debt_paid"], "debt repaid over five years"),
                       (r["coverage_y1"], "FY2027 interest coverage"),
                       (r["net_leverage_y1"], "FY2027 net leverage"), (r["net_leverage_y5"], "FY2031 net leverage"),
                       (r["min_headroom"], "smallest headroom to the illustrative leverage covenant"),
                       (r["grid_moic_00"], "MOIC at the lowest entry and exit multiples in the grid"),
                       (r["grid_moic_04"], "MOIC at the lowest entry and highest exit multiple"),
                       (r["grid_moic_40"], "MOIC at the highest entry and lowest exit multiple"),
                       (r["grid_irr_40"], "IRR at the highest entry and lowest exit multiple"),
                       (r["grid_irr_04"], "IRR at the lowest entry and highest exit multiple")])
    terms = group([(deal.terms["entry_multiple_x10"]["ref"], "entry multiple"),
                   (deal.terms["exit_multiple_x10"]["ref"], "exit multiple"),
                   (deal.terms["leverage_x10"]["ref"], "senior debt at close as a multiple of EBITDA"),
                   (deal.terms["rate_bp"]["ref"], "interest rate on the term loan")])
    assumptions = group([(a["ref"], f"{m} used in the model ({a['source']})")
                         for (key, m), a in zip(ASSUMPTIONS, deal.assumptions.values())])
    adjustments = group([(dm["reported_ebitda_FY2026"], "FY2026 reported EBITDA"),
                         (dm["allocation_FY2026"], "FY2026 overhead allocation from the parent, added back"),
                         (dm["standalone_year"], "standalone corporate cost a year, which replaces it"),
                         (dm["settlement_FY2025"], "FY2025 one-time legal settlement, added back"),
                         (dm["adjusted_ebitda_FY2026"], "FY2026 adjusted EBITDA"),
                         (dm["reported_margin_FY2026"], "FY2026 reported EBITDA margin"),
                         (dm["adjusted_margin_FY2026"], "FY2026 adjusted EBITDA margin"),
                         (dm["seller_margin_FY2026"], "the seller's margin basis with the allocation added back and no "
                                                      "standalone cost")])
    history = group([(dm["revenue_FY2024"], "FY2024 revenue"), (dm["revenue_FY2025"], "FY2025 revenue"),
                     (dm["revenue_FY2026"], "FY2026 revenue"), (dm["gross_margin_FY2026"], "FY2026 gross margin")]
                    + [(dm[f"rev_{line}_FY2026"], f"FY2026 revenue, {name}, restated") for line, name in LINE_NAMES.items()]
                    + [(dm[f"growth_{line}_FY2026"], f"FY2026 growth, {name}") for line, name in LINE_NAMES.items()])
    customers = group([(dm["largest_customer_FY2026"], "the largest customer's FY2026 revenue"),
                       (dm["largest_share_FY2026"], "the largest customer's share of FY2026 revenue"),
                       (dm["top10_share_FY2026"], "the ten largest customers' share of FY2026 revenue")])
    kpis = group([(ref, label) for ref, label in kpi_refs] + [(dm["renewal_rate_FY2026"], "FY2026 contract renewal rate")])
    claims_out = []
    for ref in claim_refs:
        row = ledger.get(ref)
        if row["metric"]:
            local = ids.add(ref, row["text"])
            claims_out.append({"id": local, "claim": row["text"], "result": row["status"]})
    return {"task": "memo_writer", "company": "Brightrow Field Services",
            "situation": "a carve-out of a commercial solar operations and maintenance business from a larger electrical "
                         "contractor, with fiscal years ending September 30 and a first round of bids in early 2027",
            "model_outputs": model_out, "deal_terms": terms, "assumptions": assumptions, "adjustments": adjustments,
            "history": history, "customers": customers, "kpis": kpis, "claims_check": claims_out}, ids


# ---------------------------------------------------------------------- the deal analyst
LINE_NAMES = {"pm": "preventive maintenance contracts", "cr": "corrective repairs", "mc": "module cleaning",
              "ms": "monitoring subscriptions"}
ASSUMPTIONS = [("growth_pm", "annual revenue growth, preventive maintenance contracts"),
               ("growth_cr", "annual revenue growth, corrective repairs"),
               ("growth_mc", "annual revenue growth, module cleaning"),
               ("growth_ms", "annual revenue growth, monitoring subscriptions"),
               ("gross_margin", "gross margin, all service lines together"),
               ("sga_pct", "SG&A as a share of revenue, before the standalone corporate cost"),
               ("da_pct", "depreciation and amortization as a share of revenue"),
               ("capex_pct", "capital spending as a share of revenue"),
               ("nwc_pct", "net working capital as a share of revenue")]


def bands(ledger, dm):
    """The range each proposed value must fall in, from the three years of history, wide enough for judgment."""
    v = ledger.value
    out = {}
    for line in LINE_NAMES:
        hist = [v(dm[f"growth_{line}_{fy}"]) for fy in ("FY2025", "FY2026")]
        out[f"growth_{line}"] = (round(min(hist) - 0.08, 3), round(max(hist) + 0.05, 3))
    for key, name in (("gross_margin", "gross_margin"), ("sga_pct", "sga_pct"), ("da_pct", "da_pct"),
                      ("capex_pct", "capex_pct"), ("nwc_pct", "nwc_pct")):
        hist = [v(dm[f"{name}_{fy}"]) for fy in ("FY2024", "FY2025", "FY2026")]
        pad = 0.03 if key in ("gross_margin", "sga_pct") else 0.015
        out[key] = (round(max(0.0, min(hist) - pad), 3), round(max(hist) + pad, 3))
    return out


def deal(ledger, dm):
    ids = Ids(ledger)
    history = []
    for fy in ("FY2024", "FY2025", "FY2026"):
        items = [(f"revenue_{fy}", f"total revenue, {fy}")]
        items += [(f"rev_{line}_{fy}", f"revenue, {name}, {fy}, restated") for line, name in LINE_NAMES.items()]
        if fy != "FY2024":
            items += [(f"growth_{line}_{fy}", f"growth, {name}, {fy}") for line, name in LINE_NAMES.items()]
        items += [(f"gross_margin_{fy}", f"gross margin, {fy}"), (f"sga_pct_{fy}", f"SG&A share of revenue without the "
                                                                              f"parent's allocation, {fy}"),
                  (f"adjusted_ebitda_{fy}", f"adjusted EBITDA, {fy}"), (f"adjusted_margin_{fy}", f"adjusted EBITDA margin, {fy}"),
                  (f"nwc_pct_{fy}", f"net working capital share of revenue, {fy}"),
                  (f"capex_pct_{fy}", f"capital spending share of revenue, {fy}"),
                  (f"da_pct_{fy}", f"D&A share of revenue, {fy}")]
        history.append({"fiscal_year": fy, "figures": ids.listing([ids.add(dm[k], label) for k, label in items])})
    extra = ids.listing([ids.add(dm["renewal_rate_FY2026"], "contract renewal rate, FY2026"),
                         ids.add(dm["largest_share_FY2026"], "largest customer's share of revenue, FY2026"),
                         ids.add(dm["standalone_year"], "standalone corporate cost a year, from management's note")])
    b = bands(ledger, dm)
    return {"task": "deal_analyst", "company": "Brightrow Field Services",
            "situation": "a carve-out of a commercial solar operations and maintenance business from a larger "
                         "electrical contractor, with fiscal years ending September 30",
            "history": history, "other": extra,
            "propose": [{"key": k, "meaning": m, "allowed_range": list(b[k])} for k, m in ASSUMPTIONS]}, ids
