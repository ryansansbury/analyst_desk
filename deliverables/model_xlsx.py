"""The deal model as a workbook: ten tabs of real formulas, defined once here and read by both the .xlsx writer and
the page's Model view, so the two can't differ.

Blue cells are inputs, black cells are formulas, and green cells link to another tab. Sources holds the data room's
values with their file and cells, and those are the only hard-coded history. The formula evaluator fills each
formula's cached value, the tests hold those equal to the Python model, and LibreOffice recalculates them again
in scripts/recalc_check.sh. Checks turns red if any tie-out breaks.
"""
from engine import fmt, model, xlsx
from engine.formula import Evaluator

SHEETS = ("README", "Sources", "Historicals", "Adjustments", "Assumptions", "Projections", "Debt", "Returns",
          "Sensitivity", "Checks")
MONEY = "#,##0;(#,##0)"
PCT = "0.0%"
MULT = "0.0\"x\""
MULT2 = "0.00\"x\""
YEARS_ROW = ("FY2026A", "FY2027E", "FY2028E", "FY2029E", "FY2030E", "FY2031E")
FY = ("FY2024", "FY2025", "FY2026")
SRC_ROWS = [("revenue:pm", "src.revenue_pm"), ("revenue:cr", "src.revenue_cr"), ("revenue:mc", "src.revenue_mc"),
            ("revenue:ms", "src.revenue_ms"), ("total_revenue", "src.total_revenue"), ("gross_profit", "src.gross_profit"),
            ("sga:salaries", "src.sga_salaries"), ("sga:facilities", "src.sga_facilities"), ("sga:it", "src.sga_it"),
            ("sga:insurance", "src.sga_insurance"), ("sga:allocation", "src.sga_allocation"),
            ("settlement", "src.settlement"), ("reported_ebitda", "src.reported_ebitda"), ("memo:revenue", "src.memo_revenue")]
SRC_ROW = {m: 5 + i for i, (m, _) in enumerate(SRC_ROWS)}
BAL_ROWS = [("receivables", 32), ("unbilled", 33), ("payables", 34), ("accrued", 35), ("capex", 36), ("da", 37)]
ASSUME_ROW = {k: 6 + i for i, k in enumerate(("growth_pm", "growth_cr", "growth_mc", "growth_ms", "gross_margin",
                                               "sga_pct", "da_pct", "capex_pct", "nwc_pct"))}
TERM_ROW = {"tax": 17, "escalation": 18, "entry": 19, "fees": 20, "exit": 21, "leverage": 22, "rate": 23,
            "amortization": 24, "sweep": 25}
STYLES = {
    "title": xlsx.Style(bold=True, size=14), "header": xlsx.Style(bold=True, fill="EEF0F3", align="right"),
    "header_l": xlsx.Style(bold=True, fill="EEF0F3"), "label": xlsx.Style(), "label_b": xlsx.Style(bold=True),
    "section": xlsx.Style(bold=True, color="0F766E"), "text": xlsx.Style(wrap=True), "note": xlsx.Style(italic=True, color="5B6B7F"),
}


def style_for(kind, fmt):
    if kind in STYLES:
        return STYLES[kind]
    color = {"input": "0000FF", "link": "008000", "formula": None, "formula_b": None, "value": None, "status": None}[kind]
    return xlsx.Style(color=color, num_fmt=fmt, bold=kind in ("formula_b", "status"), align="right" if kind == "status" else None)


class Cell:
    __slots__ = ("value", "formula", "kind", "fmt", "ref")

    def __init__(self, value=None, formula=None, kind="label", fmt=None, ref=None):
        self.value, self.formula, self.kind, self.fmt, self.ref = value, formula, kind, fmt, ref


class Sheet:
    def __init__(self, name):
        self.name, self.cells, self.widths, self.freeze, self.ok_cells = name, {}, {}, None, []

    def put(self, where, value=None, f=None, kind=None, fmt=None, ref=None):
        rc = xlsx.parse_ref(where) if isinstance(where, str) else where
        if kind is None:
            kind = "formula" if f else "label"
        self.cells[rc] = Cell(value, f, kind, fmt, ref)


def col(n):
    return xlsx.col_letter(n)


def month_cols(fy_index):
    first = 3 + fy_index * 12
    return col(first), col(first + 11)


class Book:
    def __init__(self, deal, words, ledger_values):
        self.deal, self.L = deal, deal.L
        self.w = words.table("labels.model")
        self.sheets = {name: Sheet(name) for name in SHEETS}
        self.ledger_values = ledger_values
        self.build()
        self.values = Evaluator({n: s.cells for n, s in self.sheets.items()}).all()

    def t(self, key):
        if key not in self.w:
            raise KeyError(f"WORDS.md labels.model has no {key}")
        return self.w[key]

    # ------------------------------------------------------------------ tabs
    def build(self):
        self.readme()
        self.sources()
        self.historicals()
        self.adjustments()
        self.assumptions()
        self.projections()
        self.debt()
        self.returns()
        self.sensitivity()
        self.checks()

    def readme(self):
        s = self.sheets["README"]
        s.put("A1", self.t("readme.title"), kind="title")
        for i, key in enumerate(("readme.1", "readme.2", "readme.3", "readme.4", "readme.5", "readme.6"), 3):
            s.put((i, 1), self.t(key), kind="text")
        s.put("A10", self.t("readme.key"), kind="section")
        s.put("A11", self.t("readme.key_input"), kind="input")
        s.put("A12", self.t("readme.key_formula"), kind="formula")
        s.put("A13", self.t("readme.key_link"), kind="link")
        s.put("A15", self.t("readme.version"), kind="note")
        s.widths = {1: 110}

    def sources(self):
        s, fin, cust = self.sheets["Sources"], self.deal.desk.clean["fin"], self.deal.desk.clean["cust"]
        s.put("A1", self.t("sources.title"), kind="title")
        s.put("A2", self.t("sources.note"), kind="note")
        s.put("A4", self.t("sources.line"), kind="header_l")
        s.put("B4", self.t("sources.from"), kind="header_l")
        months = sorted({m for (_, m) in fin if len(m) == 7})
        labels = {m: i for i, m in enumerate(months)}
        for m, i in labels.items():
            from engine.fmt import MONTHS
            s.put((4, 3 + i), f"{MONTHS[int(m[5:]) - 1][:3]} {m[:4]}", kind="header")
        for metric, key in SRC_ROWS:
            r = SRC_ROW[metric]
            s.put((r, 1), self.t(key))
            first = next((fin[(metric, m)] for m in months if (metric, m) in fin), None)
            if first:
                loc = self.L.get(first)["locator"].split("!")[1]
                row_no = "".join(ch for ch in loc if ch.isdigit())
                s.put((r, 2), f"financials.xlsx P&L row {row_no}", kind="note")
            for m, i in labels.items():
                ref = fin.get((metric, m))
                if ref:
                    s.put((r, 3 + i), self.L.value(ref) / 100, kind="value", fmt=MONEY, ref=ref)
        s.put("A20", self.t("src.annual"), kind="section")
        for i, fy in enumerate(FY):
            s.put((20, 3 + i), fy, kind="header")
        for r, metric, key in ((21, "annual:total_revenue", "src.annual_revenue"), (22, "annual:gross_profit", "src.annual_gp"),
                               (23, "annual:reported_ebitda", "src.annual_ebitda")):
            s.put((r, 1), self.t(key))
            s.put((r, 2), "financials.xlsx Annual summary", kind="note")
            for i, fy in enumerate(FY):
                ref = fin[(metric, fy)]
                s.put((r, 3 + i), self.L.value(ref) / 100, kind="value", fmt=MONEY, ref=ref)
        ref = fin[("standalone_cost_month", "notes")]
        s.put("A25", self.t("src.standalone"))
        s.put("B25", "financials.xlsx Notes item 4", kind="note")
        s.put("C25", self.L.value(ref) / 100, kind="value", fmt=MONEY, ref=ref)
        s.put("A27", self.t("src.customers"), kind="section")
        for i, fy in enumerate(FY):
            s.put((27, 3 + i), fy, kind="header")
        largest = self.deal.desk.deal["largest_name_FY2026"]
        for r, name, key in ((28, "Total", "src.customers_total"), (29, largest, "src.largest")):
            s.put((r, 1), self.t(key))
            s.put((r, 2), "customers.xlsx", kind="note")
            for i, fy in enumerate(FY):
                ref = cust[(name, fy)]
                s.put((r, 3 + i), self.L.value(ref) / 100, kind="value", fmt=MONEY, ref=ref)
        s.put("A31", self.t("src.balances"), kind="section")
        for i, fy in enumerate(FY):
            s.put((31, 3 + i), fy, kind="header")
        for key, r in BAL_ROWS:
            s.put((r, 1), self.t(f"src.{key}"))
            s.put((r, 2), "financials.xlsx Working capital and capex", kind="note")
            for i, fy in enumerate(FY):
                ref = fin[(f"balance:{key}", fy)]
                s.put((r, 3 + i), self.L.value(ref) / 100, kind="value", fmt=MONEY, ref=ref)
        s.widths = {1: 46, 2: 30}
        s.widths.update({3 + i: 12 for i in range(36)})
        s.freeze = "C5"

    def historicals(self):
        s = self.sheets["Historicals"]
        s.put("A1", self.t("hist.title"), kind="title")
        for i, fy in enumerate(FY):
            s.put((4, 3 + i), fy, kind="header")
        rows = [(5, "hist.pm", lambda c, a, b: f"SUM(Sources!{a}5:{b}5)", MONEY, "link"),
                (6, "hist.cr", lambda c, a, b: f"SUM(Sources!{a}6:{b}6)", MONEY, "link"),
                (7, "hist.mc", lambda c, a, b: f"SUM(Sources!{a}7:{b}7)", MONEY, "link"),
                (8, "hist.ms", lambda c, a, b: f"SUM(Sources!{a}8:{b}8)", MONEY, "link"),
                (9, "hist.revenue", lambda c, a, b: f"SUM({c}5:{c}8)", MONEY, "formula_b"),
                (10, "hist.memo", lambda c, a, b: f"SUM(Sources!{a}18:{b}18)", MONEY, "link"),
                (11, "hist.cr_restated", lambda c, a, b: f"{c}6-{c}10", MONEY, "formula"),
                (12, "hist.mc_restated", lambda c, a, b: f"{c}7+{c}10", MONEY, "formula"),
                (13, "hist.revenue_restated", lambda c, a, b: f"{c}5+{c}11+{c}12+{c}8", MONEY, "formula_b"),
                (14, "hist.gp", lambda c, a, b: f"SUM(Sources!{a}10:{b}10)", MONEY, "link"),
                (15, "hist.gm", lambda c, a, b: f"{c}14/{c}9", PCT, "formula"),
                (16, "hist.sga", lambda c, a, b: f"SUM(Sources!{a}11:{b}11)+SUM(Sources!{a}12:{b}12)+"
                                                 f"SUM(Sources!{a}13:{b}13)+SUM(Sources!{a}14:{b}14)", MONEY, "link"),
                (17, "hist.alloc", lambda c, a, b: f"SUM(Sources!{a}15:{b}15)", MONEY, "link"),
                (18, "hist.settlement", lambda c, a, b: f"SUM(Sources!{a}16:{b}16)", MONEY, "link"),
                (19, "hist.ebitda", lambda c, a, b: f"SUM(Sources!{a}17:{b}17)", MONEY, "link"),
                (20, "hist.ebitda_rebuilt", lambda c, a, b: f"{c}14-{c}16-{c}17-{c}18", MONEY, "formula"),
                (21, "hist.ebitda_margin", lambda c, a, b: f"{c}19/{c}9", PCT, "formula"),
                (22, "hist.sga_pct", lambda c, a, b: f"{c}16/{c}9", PCT, "formula"),
                (28, "hist.nwc", lambda c, a, b: f"Sources!{c}32+Sources!{c}33-Sources!{c}34-Sources!{c}35", MONEY, "link"),
                (29, "hist.nwc_pct", lambda c, a, b: f"{c}28/{c}9", PCT, "formula"),
                (30, "hist.capex_pct", lambda c, a, b: f"Sources!{c}36/{c}9", PCT, "formula"),
                (31, "hist.da_pct", lambda c, a, b: f"Sources!{c}37/{c}9", PCT, "formula")]
        for r, key, f, fmt, kind in rows:
            s.put((r, 1), self.t(key), kind="label_b" if kind == "formula_b" else "label")
            for i in range(3):
                a, b = month_cols(i)
                s.put((r, 3 + i), f=f(col(3 + i), a, b), kind=kind, fmt=fmt)
        for r, key, num in ((24, "hist.growth_pm", 5), (25, "hist.growth_cr", 11), (26, "hist.growth_mc", 12),
                            (27, "hist.growth_ms", 8)):
            s.put((r, 1), self.t(key))
            for i in (1, 2):
                c, p = col(3 + i), col(2 + i)
                s.put((r, 3 + i), f=f"{c}{num}/{p}{num}-1", fmt=PCT)
        s.widths = {1: 44, 2: 2, 3: 14, 4: 14, 5: 14}

    def adjustments(self):
        s = self.sheets["Adjustments"]
        s.put("A1", self.t("adj.title"), kind="title")
        for i, fy in enumerate(FY):
            s.put((4, 3 + i), fy, kind="header")
        s.put("F4", self.t("adj.why"), kind="header_l")
        for r, key, f, kind, why in ((5, "adj.reported", "Historicals!{c}19", "link", None),
                                     (6, "adj.settlement", "Historicals!{c}18", "link", "adj.why_settlement"),
                                     (7, "adj.allocation", "Historicals!{c}17", "link", "adj.why_allocation"),
                                     (8, "adj.standalone", "-Sources!$C$25*12", "link", "adj.why_standalone"),
                                     (9, "adj.adjusted", "SUM({c}5:{c}8)", "formula_b", None)):
            s.put((r, 1), self.t(key), kind="label_b" if kind == "formula_b" else "label")
            for i in range(3):
                c = col(3 + i)
                s.put((r, 3 + i), f=f.format(c=c), kind=kind, fmt=MONEY)
            if why:
                s.put((r, 6), self.t(why), kind="note")
        s.put("A10", self.t("adj.margin"))
        for i in range(3):
            c = col(3 + i)
            s.put((10, 3 + i), f=f"{c}9/Historicals!{c}9", kind="formula", fmt=PCT)
        s.widths = {1: 44, 2: 2, 3: 14, 4: 14, 5: 14, 6: 70}

    def assumptions(self):
        s, a, terms = self.sheets["Assumptions"], self.deal.assumptions, self.deal.terms
        s.put("A1", self.t("assume.title"), kind="title")
        for c, key in ((1, "assume.input"), (3, "assume.history"), (4, "assume.value"), (5, "assume.source"),
                       (6, "assume.rationale")):
            s.put((4, c), self.t(key), kind="header_l" if c in (1, 5, 6) else "header")
        s.put("A5", self.t("assume.operating"), kind="section")
        hist_cell = {"growth_pm": "Historicals!E24", "growth_cr": "Historicals!E25", "growth_mc": "Historicals!E26",
                     "growth_ms": "Historicals!E27", "gross_margin": "Historicals!E15", "sga_pct": "Historicals!E22",
                     "da_pct": "Historicals!E31", "capex_pct": "Historicals!E30", "nwc_pct": "Historicals!E29"}
        recorded = fmt.local_date(self.deal.desk.runs.get("deal_analyst", {}).get("recorded_at", ""))
        for key, r in ASSUME_ROW.items():
            item = a[key]
            s.put((r, 1), self.t(f"assume.{key}"))
            s.put((r, 3), f=hist_cell[key], kind="link", fmt=PCT)
            s.put((r, 4), item["value"], kind="input", fmt=PCT, ref=item["ref"])
            src = {"agent": self.t("assume.src_agent").format(date=recorded), "override": self.t("assume.src_override"),
                   "history": self.t("assume.src_history")}[item["source"]]
            s.put((r, 5), src, kind="note")
            if item.get("rationale"):
                from engine import gate
                s.put((r, 6), gate.render(item["rationale"], self.L), kind="text")
        s.put("A16", self.t("assume.terms"), kind="section")
        term_key = {"tax": "tax_bp", "escalation": "standalone_escalation_bp", "entry": "entry_multiple_x10",
                    "fees": "fees_bp", "exit": "exit_multiple_x10", "leverage": "leverage_x10", "rate": "rate_bp",
                    "amortization": "amortization_bp", "sweep": "sweep_bp"}
        for key, r in TERM_ROW.items():
            term = terms[term_key[key]]
            s.put((r, 1), self.t(f"assume.{key}"))
            s.put((r, 4), term["value"], kind="input", fmt=MULT if key in ("entry", "exit", "leverage") else PCT,
                  ref=term["ref"])
            s.put((r, 5), self.t("assume.src_terms"), kind="note")
        s.widths = {1: 50, 2: 2, 3: 14, 4: 12, 5: 30, 6: 90}

    def projections(self):
        s = self.sheets["Projections"]
        A = lambda k: f"Assumptions!$D${ASSUME_ROW[k]}"  # noqa: E731
        T = lambda k: f"Assumptions!$D${TERM_ROW[k]}"  # noqa: E731
        s.put("A1", self.t("proj.title"), kind="title")
        for i, label in enumerate(YEARS_ROW):
            s.put((4, 3 + i), label, kind="header")
        s.put("A5", self.t("proj.revenue_head"), kind="section")
        labels = [(6, "proj.pm"), (7, "proj.cr"), (8, "proj.mc"), (9, "proj.ms"), (10, "proj.revenue"),
                  (11, "proj.growth"), (12, "proj.gp"), (13, "proj.sga"), (14, "proj.standalone"), (15, "proj.ebitda"),
                  (16, "proj.margin"), (17, "proj.da"), (18, "proj.ebit"), (19, "proj.interest"), (20, "proj.taxes"),
                  (21, "proj.capex"), (22, "proj.nwc"), (23, "proj.dnwc"), (24, "proj.cfads")]
        for r, key in labels:
            s.put((r, 1), self.t(key), kind="label_b" if r in (10, 15, 24) else "label")
        for r, f in ((6, "Historicals!E5"), (7, "Historicals!E11"), (8, "Historicals!E12"), (9, "Historicals!E8"),
                     (12, "Historicals!E14"), (13, "Historicals!E16"), (14, "-Adjustments!E8"), (15, "Adjustments!E9")):
            s.put((r, 3), f=f, kind="link", fmt=MONEY)
        s.put("C10", f="SUM(C6:C9)", kind="formula_b", fmt=MONEY)
        s.put("C16", f="C15/C10", fmt=PCT)
        s.put("C22", f=f"C10*{A('nwc_pct')}", fmt=MONEY)
        for i in range(1, 6):
            c, p = col(3 + i), col(2 + i)
            for r, k in ((6, "growth_pm"), (7, "growth_cr"), (8, "growth_mc"), (9, "growth_ms")):
                s.put((r, 3 + i), f=f"{p}{r}*(1+{A(k)})", fmt=MONEY)
            s.put((10, 3 + i), f=f"SUM({c}6:{c}9)", kind="formula_b", fmt=MONEY)
            s.put((11, 3 + i), f=f"{c}10/{p}10-1", fmt=PCT)
            s.put((12, 3 + i), f=f"{c}10*{A('gross_margin')}", fmt=MONEY)
            s.put((13, 3 + i), f=f"{c}10*{A('sga_pct')}", fmt=MONEY)
            s.put((14, 3 + i), f=f"{p}14*(1+{T('escalation')})", fmt=MONEY)
            s.put((15, 3 + i), f=f"{c}12-{c}13-{c}14", kind="formula_b", fmt=MONEY)
            s.put((16, 3 + i), f=f"{c}15/{c}10", fmt=PCT)
            s.put((17, 3 + i), f=f"{c}10*{A('da_pct')}", fmt=MONEY)
            s.put((18, 3 + i), f=f"{c}15-{c}17", fmt=MONEY)
            s.put((19, 3 + i), f=f"Debt!{c}6", kind="link", fmt=MONEY)
            s.put((20, 3 + i), f=f"MAX(0,({c}18-{c}19)*{T('tax')})", fmt=MONEY)
            s.put((21, 3 + i), f=f"{c}10*{A('capex_pct')}", fmt=MONEY)
            s.put((22, 3 + i), f=f"{c}10*{A('nwc_pct')}", fmt=MONEY)
            s.put((23, 3 + i), f=f"{c}22-{p}22", fmt=MONEY)
            s.put((24, 3 + i), f=f"{c}15-{c}20-{c}21-{c}23", kind="formula_b", fmt=MONEY)
        s.widths = {1: 40, 2: 2}
        s.widths.update({3 + i: 14 for i in range(6)})
        s.freeze = "C5"

    def debt(self):
        s = self.sheets["Debt"]
        T = lambda k: f"Assumptions!$D${TERM_ROW[k]}"  # noqa: E731
        s.put("A1", self.t("debt.title"), kind="title")
        s.put("C4", self.t("debt.at_close"), kind="header")
        for i in range(1, 6):
            s.put((4, 3 + i), YEARS_ROW[i], kind="header")
        labels = [(5, "debt.opening"), (6, "debt.interest"), (7, "debt.mandatory"), (8, "debt.avail"), (9, "debt.sweep"),
                  (10, "debt.closing"), (11, "debt.cash"), (12, "debt.net_debt"), (13, "debt.ebitda"),
                  (14, "debt.net_leverage"), (15, "debt.coverage"), (16, "debt.cov_leverage"), (17, "debt.lev_headroom"),
                  (18, "debt.cov_coverage"), (19, "debt.cov_headroom")]
        for r, key in labels:
            s.put((r, 1), self.t(key), kind="label_b" if r in (10, 12) else "label")
        s.put("C10", f="Returns!C9", kind="link", fmt=MONEY)
        s.put("C11", 0, kind="input", fmt=MONEY)
        s.put("C12", f="C10-C11", kind="formula_b", fmt=MONEY)
        s.put("C13", f="Projections!C15", kind="link", fmt=MONEY)
        s.put("C14", f="C12/C13", fmt=MULT2)
        cov = self.deal.terms["covenant_leverage_x100"]
        cov_min = self.deal.terms["covenant_coverage_x100"]
        for i in range(1, 6):
            c, p = col(3 + i), col(2 + i)
            s.put((5, 3 + i), f=f"{p}10", fmt=MONEY)
            s.put((6, 3 + i), f=f"{c}5*{T('rate')}", fmt=MONEY)
            s.put((7, 3 + i), f=f"MIN({c}5,{T('amortization')}*$C$10)", fmt=MONEY)
            s.put((8, 3 + i), f=f"Projections!{c}24-{c}6-{c}7", fmt=MONEY)
            s.put((9, 3 + i), f=f"MAX(0,MIN({c}5-{c}7,{T('sweep')}*{c}8))", fmt=MONEY)
            s.put((10, 3 + i), f=f"{c}5-{c}7-{c}9", kind="formula_b", fmt=MONEY)
            s.put((11, 3 + i), f=f"{p}11+{c}8-{c}9", fmt=MONEY)
            s.put((12, 3 + i), f=f"{c}10-{c}11", kind="formula_b", fmt=MONEY)
            s.put((13, 3 + i), f=f"Projections!{c}15", kind="link", fmt=MONEY)
            s.put((14, 3 + i), f=f"{c}12/{c}13", fmt=MULT2)
            s.put((15, 3 + i), f=f"IF({c}6>0,{c}13/{c}6,\"\")", fmt=MULT2)
            s.put((16, 3 + i), cov["value"][i - 1], kind="input", fmt=MULT2, ref=cov["refs"][i - 1])
            s.put((17, 3 + i), f=f"{c}16-{c}14", fmt=MULT2)
            s.put((18, 3 + i), cov_min["value"], kind="input", fmt=MULT2, ref=cov_min["ref"])
            s.put((19, 3 + i), f=f"IF({c}6>0,{c}15-{c}18,\"\")", fmt=MULT2)
        s.put("A21", self.t("debt.note"), kind="note")
        s.widths = {1: 42, 2: 2}
        s.widths.update({3 + i: 14 for i in range(6)})

    def returns(self):
        s = self.sheets["Returns"]
        T = lambda k: f"Assumptions!$D${TERM_ROW[k]}"  # noqa: E731
        s.put("A1", self.t("ret.title"), kind="title")
        rows = [(4, "ret.ebitda0", "Adjustments!E9", "link", MONEY), (5, "ret.entry", T("entry"), "link", MULT),
                (6, "ret.ev", "C4*C5", "formula", MONEY), (7, "ret.fees", f"C6*{T('fees')}", "formula", MONEY),
                (8, "ret.uses", "C6+C7", "formula_b", MONEY), (9, "ret.debt0", f"C4*{T('leverage')}", "formula", MONEY),
                (10, "ret.equity0", "C8-C9", "formula_b", MONEY), (11, "ret.ebitda5", "Projections!H15", "link", MONEY),
                (12, "ret.exit", T("exit"), "link", MULT), (13, "ret.ev_exit", "C11*C12", "formula", MONEY),
                (14, "ret.nd_exit", "Debt!H12", "link", MONEY), (15, "ret.equity_exit", "C13-C14", "formula_b", MONEY),
                (16, "ret.moic", "C15/C10", "formula_b", MULT2)]
        for r, key, f, kind, fmt in rows:
            s.put((r, 1), self.t(key), kind="label_b" if kind == "formula_b" else "label")
            s.put((r, 3), f=f, kind=kind, fmt=fmt)
        s.put("A18", self.t("ret.flows_head"), kind="section")
        for i, label in enumerate(YEARS_ROW):
            s.put((18, 3 + i), self.t("debt.at_close") if i == 0 else label, kind="header")
        s.put("A19", self.t("ret.flows"))
        s.put("C19", f="-C10", fmt=MONEY)
        for i in range(1, 5):
            s.put((19, 3 + i), 0, kind="value", fmt=MONEY)
        s.put("H19", f="C15", fmt=MONEY)
        s.put("A20", self.t("ret.irr"), kind="label_b")
        s.put("C20", f="IRR(C19:H19)", kind="formula_b", fmt=PCT)
        s.put("A21", self.t("ret.irr_check"))
        s.put("C21", f="C16^(1/5)-1", fmt=PCT)
        s.widths = {1: 40, 2: 2}
        s.widths.update({3 + i: 14 for i in range(6)})

    def sensitivity(self):
        s = self.sheets["Sensitivity"]
        s.put("A1", self.t("sens.title"), kind="title")
        s.put("A3", self.t("sens.rows"), kind="note")
        for block, top, fmt in ((0, 5, MULT2), (1, 13, PCT)):
            s.put((top - 1, 1), self.t("sens.title" if block == 0 else "sens.irr_title"), kind="section")
            for j, x in enumerate(model.GRID):
                s.put((top, 3 + j), x, kind="input", fmt=MULT)
            for i, e in enumerate(model.GRID):
                r = top + 1 + i
                s.put((r, 2), e, kind="input", fmt=MULT)
                for j in range(5):
                    c = col(3 + j)
                    if block == 0:
                        f = (f"(Returns!$C$11*{c}${top}-Returns!$C$14)/($B{r}*Returns!$C$4*(1+Assumptions!$D$"
                             f"{TERM_ROW['fees']})-Returns!$C$9)")
                    else:
                        f = f"{c}{r - 8}^(1/5)-1"
                    s.put((r, 3 + j), f=f, fmt=fmt)
        s.widths = {1: 28, 2: 10}
        s.widths.update({3 + j: 12 for j in range(5)})

    def checks(self):
        s, r = self.sheets["Checks"], self.deal.results
        s.put("A1", self.t("checks.title"), kind="title")
        s.put("A3", self.t("checks.all"), kind="label_b")
        for c, key in ((1, "checks.what"), (3, "checks.a"), (4, "checks.b"), (5, "checks.diff"), (6, "checks.status")):
            s.put((4, c), self.t(key), kind="header_l" if c == 1 else "header")
        dm = self.deal.desk.deal
        rows = [("checks.c1", "Historicals!E9", "Sources!E21", None, MONEY),
                ("checks.c2", "Historicals!E13", "Historicals!E9", None, MONEY),
                ("checks.c3", "Historicals!E20", "Sources!E23", None, MONEY),
                ("checks.c4", "Adjustments!E9", None, self.L.value(dm["adjusted_ebitda_FY2026"]) / 100, MONEY),
                ("checks.c5", "Sources!E28", "Historicals!E9", None, MONEY),
                ("checks.c6", "Returns!C8", "Returns!C9+Returns!C10", None, MONEY),
                ("checks.c7", "+".join(f"ABS(Debt!{c}5-Debt!{c}7-Debt!{c}9-Debt!{c}10)" for c in "DEFGH"), None, 0, MONEY),
                ("checks.c8", "MIN(Debt!D10:H10)", None, 0, MONEY),
                ("checks.c9", "Returns!C16", None, r["moic"], MULT2),
                ("checks.c10", "Returns!C20", None, r["irr"], PCT),
                ("checks.c11", "Returns!C20", "Returns!C21", None, PCT)]
        status = []
        for i, (key, fa, fb, vb, fmt) in enumerate(rows):
            n = 5 + i
            s.put((n, 1), self.t(key))
            s.put((n, 3), f=fa, kind="link", fmt=fmt)
            if fb:
                s.put((n, 4), f=fb, kind="link", fmt=fmt)
            else:
                s.put((n, 4), vb, kind="value", fmt=fmt)
            s.put((n, 5), f=f"C{n}-D{n}", fmt=fmt if fmt == MONEY else "0.000000")
            tol = "0.005" if fmt == MONEY else "0.000001"
            rule = f"C{n}>=0" if key == "checks.c8" else f"ABS(E{n})<{tol}"
            s.put((n, 6), f=f"IF({rule},\"OK\",\"CHECK\")", kind="status")
            status.append(f"F{n}=\"OK\"")
        s.put("F3", f=f"IF(AND({','.join(status)}),\"OK\",\"CHECK\")", kind="status")
        s.ok_cells = ["F3:F3", f"F5:F{4 + len(rows)}"]
        s.widths = {1: 60, 2: 2, 3: 16, 4: 16, 5: 14, 6: 10}

    # ------------------------------------------------------------------ outputs
    def workbook(self, cached=True):
        wb = xlsx.Workbook(recalc_on_load=True)
        for name in SHEETS:
            sh = self.sheets[name]
            ws = wb.sheet(name)
            for (r, c), cell in sorted(sh.cells.items()):
                value = self.values.get((name, (r, c))) if cell.formula else cell.value
                ws.set((r, c), value, formula=cell.formula, style=style_for(cell.kind, cell.fmt))
            for c, w in sh.widths.items():
                ws.width(c, w)
            ws.freeze = sh.freeze
            for sq in sh.ok_cells:
                ws.highlight_equal(sq, "OK", "C6EFCE", "006100")
                ws.highlight_equal(sq, "CHECK", "FFC7CE", "9C0006")
        return wb.to_bytes(cached=cached)

    def value(self, sheet, where):
        return self.values.get((sheet, xlsx.parse_ref(where)))

    def against(self, other):
        """Every formula's value here against another engine's values for the same workbook, to the cent for money
        and a millionth for ratios. other is {sheet: reader} from xlsx.read. Returns (checked, mismatches)."""
        bad, checked = [], 0
        for name, sheet in self.sheets.items():
            theirs_sheet = other.get(name)
            for rc, cell in sheet.cells.items():
                if cell.formula is None:
                    continue
                mine, theirs = self.values[(name, rc)], theirs_sheet.value(rc) if theirs_sheet else None
                checked += 1
                if isinstance(mine, str) or isinstance(theirs, str):
                    if str(mine) != str(theirs):
                        bad.append((name, xlsx.ref(*rc), mine, theirs))
                    continue
                tol = 0.005 if cell.fmt == MONEY else 1e-6
                if theirs is None or abs(float(mine) - float(theirs)) > tol:
                    bad.append((name, xlsx.ref(*rc), mine, theirs))
        return checked, bad


def parity(r):
    """The cells where the workbook's formulas must equal the Python model, as (sheet, cell, value, tolerance): money
    to the cent, and MOIC, IRR and the MOIC grid to a billionth."""
    out = [("Returns", "C6", r["ev"]), ("Returns", "C7", r["fees"]), ("Returns", "C9", r["debt0"]),
           ("Returns", "C10", r["equity0"]), ("Returns", "C13", r["ev_exit"]), ("Returns", "C14", r["nd_exit"]),
           ("Returns", "C15", r["equity_exit"])]
    for y in range(1, 6):
        c = xlsx.col_letter(3 + y)
        out += [("Projections", f"{c}10", r["revenue"][y]), ("Projections", f"{c}15", r["ebitda"][y]),
                ("Projections", f"{c}20", r["taxes"][y]), ("Projections", f"{c}24", r["cfads"][y]),
                ("Debt", f"{c}6", r["interest"][y]), ("Debt", f"{c}9", r["sweep"][y]),
                ("Debt", f"{c}10", r["closing"][y]), ("Debt", f"{c}11", r["cash"][y])]
    out = [(s, c, v, 0.005) for s, c, v in out]
    out += [("Returns", "C16", r["moic"], 5e-10), ("Returns", "C20", r["irr"], 5e-10)]
    out += [("Sensitivity", f"{xlsx.col_letter(3 + j)}{6 + i}", r["grid_moic"][i][j], 5e-10)
            for i in range(5) for j in range(5)]
    return out


def parity_gaps(book):
    """(cells compared, cells outside their tolerance) for the workbook against the Python model it was built from."""
    pairs = parity(book.deal.results)
    off = [(s, c) for s, c, v, tol in pairs if abs((book.value(s, c) or 0) - v) >= tol]
    return len(pairs), off
