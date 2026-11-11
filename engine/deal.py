"""The deal target's measures from its data room: fiscal-year rollups, the EBITDA adjustments, concentration and
renewals. The claims check reads these, and the model and the deal analyst's inputs build on them.

The adjustments follow the data room's own disclosures: the month-23 legal settlement is added back as one-time,
the parent's overhead allocation is added back, and management's standalone cost estimate replaces it. The seller's
basis is the same bridge without the replacement cost, which is how a teaser gets a higher margin.
"""
from engine.metrics import Builder

FYS = {"FY2024": ("2023-10", "2024-09"), "FY2025": ("2024-10", "2025-09"), "FY2026": ("2025-10", "2026-09")}
LINES = ("pm", "cr", "mc", "ms")


def months(fy):
    first, last = FYS[fy]
    y, m = int(first[:4]), int(first[5:])
    out = []
    while True:
        out.append(f"{y:04d}-{m:02d}")
        if out[-1] == last:
            return out
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


class DataRoomMeasures(Builder):
    def __init__(self, state):
        super().__init__(state)
        self.fin, self.cust, self.kpis = state["fin"], state["cust"], state["kpis"]
        self.k = {}

    def fy_sum(self, metric, fy, transform=None):
        refs = [self.fin[(metric, m)] for m in months(fy) if (metric, m) in self.fin]
        return self.total("brightrow", fy, metric, refs, "cents", transform or f"sum of {len(refs)} months in {fy}")

    def restated(self, line, fy):
        """Revenue for a service line in a fiscal year with module cleaning restated out of corrective repairs."""
        if line == "mc":
            refs = [self.fin.get(("revenue:mc", m)) or self.fin[("memo:revenue", m)] for m in months(fy)]
            return self.total("brightrow", fy, "restated:mc", refs, "cents",
                              "module cleaning from the memo rows before April 2025 and from its own line after")
        if line == "cr":
            plus = [self.fin[("revenue:cr", m)] for m in months(fy)]
            minus = [self.fin[("memo:revenue", m)] for m in months(fy) if ("memo:revenue", m) in self.fin]
            return self.combine("brightrow", fy, "restated:cr", plus, minus, "cents",
                                "corrective repairs less the module cleaning booked inside it before April 2025")
        return self.fy_sum(f"revenue:{line}", fy)

    def build(self):
        k = self.k
        for fy in FYS:
            k[f"revenue_{fy}"] = self.fy_sum("total_revenue", fy)
            k[f"reported_ebitda_{fy}"] = self.fy_sum("reported_ebitda", fy)
            k[f"settlement_{fy}"] = self.fy_sum("settlement", fy, "the one-time legal settlement")
            k[f"allocation_{fy}"] = self.fy_sum("sga:allocation", fy, "the parent's overhead allocation")
            k[f"gross_profit_{fy}"] = self.fy_sum("gross_profit", fy)
            for line in LINES:
                k[f"rev_{line}_{fy}"] = self.restated(line, fy)
        standalone = self.fin[("standalone_cost_month", "notes")]
        twelve = self.L.derive("brightrow", "per year", "months", "constant", [], 12, "count", "twelve months")
        k["standalone_year"] = self.product("brightrow", "per year", "standalone_year", standalone, twelve, "cents",
                                            "management's monthly standalone estimate times twelve")
        for fy in FYS:
            k[f"adjusted_ebitda_{fy}"] = self.combine(
                "brightrow", fy, "adjusted_ebitda",
                [k[f"reported_ebitda_{fy}"], k[f"settlement_{fy}"], k[f"allocation_{fy}"]], [k["standalone_year"]], "cents",
                "reported EBITDA plus the settlement and the parent's allocation minus the standalone cost")
            k[f"adjusted_margin_{fy}"] = self.ratio("brightrow", fy, "adjusted_margin", k[f"adjusted_ebitda_{fy}"],
                                                    k[f"revenue_{fy}"], "adjusted EBITDA over revenue")
            k[f"reported_margin_{fy}"] = self.ratio("brightrow", fy, "reported_margin", k[f"reported_ebitda_{fy}"],
                                                    k[f"revenue_{fy}"], "reported EBITDA over revenue")
        k["seller_ebitda_FY2026"] = self.combine(
            "brightrow", "FY2026", "seller_basis_ebitda",
            [k["reported_ebitda_FY2026"], k["settlement_FY2026"], k["allocation_FY2026"]], [], "cents",
            "reported EBITDA plus the parent's allocation with no standalone cost to replace it")
        k["seller_margin_FY2026"] = self.ratio("brightrow", "FY2026", "seller_basis_margin", k["seller_ebitda_FY2026"],
                                               k["revenue_FY2026"], "that basis over revenue")
        for fy in FYS:
            rows = [(name, ref) for (name, f), ref in self.cust.items() if f == fy and name != "Total"]
            rows.sort(key=lambda x: -self.L.value(x[1]))
            top = rows[0]
            k[f"largest_customer_{fy}"] = self.L.derive(
                "brightrow", fy, "largest_customer", "max", [r for _, r in rows], self.L.value(top[1]), "cents",
                f"{top[0]} as the largest of {len(rows)} customers", extra={"name": top[0]})
            k[f"largest_share_{fy}"] = self.ratio("brightrow", fy, "largest_share", k[f"largest_customer_{fy}"],
                                                  self.cust[("Total", fy)], "the largest customer over all customers")
            top10 = self.total("brightrow", fy, "top10_revenue", [r for _, r in rows[:10]], "cents", "the ten largest customers")
            k[f"top10_share_{fy}"] = self.ratio("brightrow", fy, "top10_share", top10, self.cust[("Total", fy)],
                                                "the ten largest over all customers")
            k[f"largest_name_{fy}"] = top[0]
        fy26 = months("FY2026")
        renewed = self.total("brightrow", "FY2026", "contracts_renewed",
                             [self.kpis[("contracts_renewed", m)] for m in fy26], "count", "sum of the contracts renewed each month")
        expiring = self.total("brightrow", "FY2026", "contracts_expiring",
                              [self.kpis[("contracts_expiring", m)] for m in fy26], "count", "sum of the contracts expiring each month")
        k["renewal_rate_FY2026"] = self.ratio("brightrow", "FY2026", "renewal_rate", renewed, expiring,
                                              "contracts renewed over contracts expiring")
        self.history(k)
        return k

    def history(self, k):
        """What the deal analyst cites: growth by line, margins and the cash-flow shares, each by fiscal year."""
        fys = list(FYS)
        for line in LINES:
            for a, b in zip(fys, fys[1:]):
                base = k[f"rev_{line}_{a}"]
                grown = self.diff("brightrow", b, f"growth_amount:{line}", k[f"rev_{line}_{b}"], base, "cents",
                                  f"{b} revenue less {a}")
                k[f"growth_{line}_{b}"] = self.ratio("brightrow", b, f"growth:{line}", grown, base,
                                                     f"growth over {a}")
        for fy in fys:
            rev = k[f"revenue_{fy}"]
            k[f"gross_margin_{fy}"] = self.ratio("brightrow", fy, "gross_margin", k[f"gross_profit_{fy}"], rev,
                                                 "gross profit over revenue")
            sga = [self.fy_sum(f"sga:{x}", fy) for x in ("salaries", "facilities", "it", "insurance")]
            sga_ex = self.total("brightrow", fy, "sga_ex_allocation", sga, "cents",
                                "SG&A without the parent's allocation")
            k[f"sga_ex_{fy}"] = sga_ex
            k[f"sga_pct_{fy}"] = self.ratio("brightrow", fy, "sga_pct", sga_ex, rev,
                                            "SG&A over revenue with the allocation left out")
            bal = {x: self.fin[(f"balance:{x}", fy)] for x in ("receivables", "unbilled", "payables", "accrued", "capex", "da")}
            nwc = self.combine("brightrow", fy, "nwc", [bal["receivables"], bal["unbilled"]], [bal["payables"], bal["accrued"]],
                               "cents", "receivables and unbilled less payables and accruals")
            k[f"nwc_{fy}"] = nwc
            k[f"nwc_pct_{fy}"] = self.ratio("brightrow", fy, "nwc_pct", nwc, rev, "net working capital over revenue")
            k[f"capex_pct_{fy}"] = self.ratio("brightrow", fy, "capex_pct", bal["capex"], rev, "capital spending over revenue")
            k[f"da_pct_{fy}"] = self.ratio("brightrow", fy, "da_pct", bal["da"], rev, "D&A over revenue")
            k[f"capex_{fy}"] = bal["capex"]
            k[f"da_{fy}"] = bal["da"]
