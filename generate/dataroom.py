"""Brightrow Field Services' data room: 36 months of P&L by service line, revenue by customer, monthly KPIs, and the
seller's teaser.

Fiscal years end in September, and the 36 months run Oct 2023 to Sep 2026, so FY2026 is the last twelve months.
Module cleaning sat inside corrective repairs through March 2025 (month 18), with memo rows that let the model
restate it. Month 23 carries a one-time legal settlement. The parent charges a fixed overhead allocation, and the
Notes sheet gives management's estimate of what a standalone business would spend instead.

Tuned so the ledger's FY2026 adjusted EBITDA margin is exactly 18.4% and the largest customer is exactly 12.7% of
FY2026 revenue. The teaser's margin claim adds back the allocation without the standalone cost, which comes out
above 20%. Its concentration claim says no customer is above 10%. Its renewal claim is true.
"""
from datetime import date

from engine import xlsx
from generate import common as C

MONTHS = [date(2023 + (9 + i) // 12, (9 + i) % 12 + 1, 1) for i in range(36)]   # Oct 2023 .. Sep 2026
LINES = [("pm", "Preventive maintenance contracts"), ("cr", "Corrective repairs"), ("mc", "Module cleaning"),
         ("ms", "Monitoring subscriptions")]
FY_REVENUE = {"pm": (13300000, 14600000, 16000000), "cr": (8200000, 8900000, 9600000),
              "mc": (3100000, 3600000, 4100000), "ms": (2100000, 2700000, 3300000)}   # dollars by fiscal year
COST_RATES = {"pm": (0.38, 0.06, 0.08), "cr": (0.35, 0.18, 0.10), "mc": (0.45, 0.05, 0.12), "ms": (0.15, 0.02, 0.03)}
SEASON = {"pm": [1.0] * 12,
          "cr": [0.92, 0.88, 0.85, 0.86, 0.9, 1.0, 1.05, 1.12, 1.15, 1.12, 1.08, 1.02],     # Oct .. Sep
          "mc": [0.8, 0.65, 0.55, 0.55, 0.7, 0.95, 1.2, 1.35, 1.35, 1.3, 1.2, 1.0],
          "ms": [1.0] * 12}
RECLASS_THROUGH = 18          # module cleaning sits inside corrective repairs through this month
SETTLEMENT_MONTH = 23
SETTLEMENT_CENTS = 41250000
ALLOCATION_CENTS = (11500000, 12000000, 12375000)   # parent overhead per month, by fiscal year
STANDALONE_CENTS = 8525000                            # management's standalone estimate per month
TARGET_MARGIN_PERMILLE = 184
TOP_SHARE_PERMILLE = 127
RENEWALS_FY26 = (130, 122)                            # contracts expiring, renewed
CLAIMS = {"margin_floor_pct": 20, "customer_cap_pct": 10, "renewal_floor_pct": 90}
BALANCE_LINES = [("Accounts receivable", "receivables"), ("Unbilled services", "unbilled"), ("Accounts payable", "payables"),
                 ("Accrued liabilities", "accrued"), ("Capital expenditures", "capex"),
                 ("Depreciation and amortization", "da")]
SG_A = [("salaries", "Salaries and benefits"), ("facilities", "Facilities"), ("it", "IT and software"),
        ("insurance", "Insurance"), ("allocation", "Corporate overhead allocation (parent)")]


def fy(i):
    """Fiscal year index 0, 1 or 2 for month index 0 to 35."""
    return i // 12


class DataRoom:
    def __init__(self, seed):
        self.seed = seed
        # Both random streams keep the labels they were first built with, so the data room's numbers never change.
        rng = C.stream(seed, "sunline")
        self.rev, self.cost = {}, {}
        for key, _ in LINES:
            months = []
            for i in range(36):
                annual = FY_REVENUE[key][fy(i)] * 100
                ramp = 0.94 + 0.12 * (i % 12) / 11
                months.append(annual / 12 * ramp * SEASON[key][i % 12] * rng.uniform(0.97, 1.03))
            for y in range(3):     # each fiscal year lands on its plan, so growth reads cleanly
                scale = FY_REVENUE[key][y] * 100 / sum(months[y * 12:(y + 1) * 12])
                for i in range(y * 12, (y + 1) * 12):
                    months[i] *= scale
            self.rev[key] = [round(v) for v in months]
            self.cost[key] = [[round(self.rev[key][i] * (r + rng.uniform(-0.012, 0.012))) for i in range(36)]
                              for r in COST_RATES[key]]
        total = [sum(self.rev[k][i] for k, _ in LINES) for i in range(36)]
        self.sga = {"salaries": [round(total[i] * rng.uniform(0.187, 0.190)) for i in range(36)],
                    "facilities": [round(6800000 * (1.03 ** fy(i)) * rng.uniform(0.97, 1.03)) for i in range(36)],
                    "it": [round(total[i] * 0.017 * rng.uniform(0.95, 1.05)) for i in range(36)],
                    "insurance": [4100000 + 150000 * fy(i) for i in range(36)],
                    "allocation": [ALLOCATION_CENTS[fy(i)] for i in range(36)]}
        self.settlement = [SETTLEMENT_CENTS if i + 1 == SETTLEMENT_MONTH else 0 for i in range(36)]
        self._tune_margin()
        self.customers = self._customers(rng)
        self.kpis = self._kpis(rng)
        self.balances = self._balances(C.stream(seed, "sunline:balances"))

    def _balances(self, rng):
        """Year-end working capital and the year's capex and D&A, as shares of revenue near a field-service norm."""
        out = {k: [] for _, k in BALANCE_LINES}
        for y in range(3):
            rev = self.fy_sum(self.total_revenue, y)
            cost = rev - self.fy_sum(self.gross_profit, y)
            out["receivables"].append(round(rev * rng.uniform(0.135, 0.145)))
            out["unbilled"].append(round(rev * rng.uniform(0.018, 0.024)))
            out["payables"].append(round(cost * rng.uniform(0.075, 0.085)))
            out["accrued"].append(round(rev * rng.uniform(0.028, 0.034)))
            out["capex"].append(round(rev * rng.uniform(0.022, 0.026)))
            out["da"].append(round(rev * rng.uniform(0.018, 0.021)))
        return out

    # ------------------------------------------------------------------ totals
    def total_revenue(self, i):
        return sum(self.rev[k][i] for k, _ in LINES)

    def gross_profit(self, i):
        return self.total_revenue(i) - sum(sum(c[i] for c in self.cost[k]) for k, _ in LINES)

    def sga_total(self, i, with_allocation=True):
        return sum(v[i] for k, v in self.sga.items() if with_allocation or k != "allocation")

    def reported_ebitda(self, i):
        return self.gross_profit(i) - self.sga_total(i) - self.settlement[i]

    def fy_sum(self, f, y):
        return sum(f(i) for i in range(y * 12, (y + 1) * 12))

    def adjusted_ebitda(self, y):
        """Reported EBITDA plus the settlement and the allocation, minus the standalone cost that replaces it."""
        return (self.fy_sum(self.reported_ebitda, y) + sum(self.settlement[y * 12:(y + 1) * 12])
                + sum(self.sga["allocation"][y * 12:(y + 1) * 12]) - 12 * STANDALONE_CENTS)

    def _tune_margin(self):
        """Spread the residual over FY2026's salaries so adjusted EBITDA is exactly 18.4% of revenue. The salary
        base sits just low enough that the residual is always a small addition, one to three percent a month."""
        revenue = self.fy_sum(self.total_revenue, 2)
        residual = self.adjusted_ebitda(2) - C.half_up(revenue * TARGET_MARGIN_PERMILLE, 1000)
        assert residual >= 0, residual
        share, rem = divmod(residual, 12)
        for i in range(24, 36):
            self.sga["salaries"][i] += share + (rem if i == 35 else 0)

    # ------------------------------------------------------------------ customers
    def _customers(self, rng):
        prefixes = ["Arroyo", "Bluebell", "Coralbean", "Desert Bloom", "Eastfield", "Falcon Ridge", "Granite Peak",
                    "High Plains", "Ironwood", "Juniper Flats", "Kestrel", "Longleaf", "Mesa Verde", "North Star",
                    "Ocotillo", "Pinyon", "Quail Run", "Redbud", "Sage Hollow", "Tumbleweed", "Upland", "Vista Ridge",
                    "Willow Creek", "Yellow Rose", "Agarita", "Bandera", "Cottonwood", "Dogwood", "Elm Fork", "Flint Hill"]
        suffixes = ["Solar Fund", "Community Solar", "Energy Partners", "Solar Holdings", "Retail Properties",
                    "School District", "Distribution Centers", "Solar LLC", "Clean Power", "Industrial Park"]
        names = set()
        while len(names) < 45:
            names.add(f"{rng.choice(prefixes)} {rng.choice(suffixes)}")
        names = sorted(names)
        rng.shuffle(names)
        tops = {0: (108, [81, 74, 66, 58, 51, 45, 39, 34, 30]), 1: (119, [84, 73, 63, 55, 50, 43, 37, 33, 29]),
                2: (TOP_SHARE_PERMILLE, [86, 73, 62, 54, 49, 41, 36, 32, 28])}
        tail_weights = [rng.uniform(0.4, 1.0) for _ in range(35)]
        out = {n: [0, 0, 0] for n in names}
        for y in range(3):
            revenue = self.fy_sum(self.total_revenue, y)
            top, rest = tops[y]
            amounts = [C.half_up(revenue * top, 1000)] + [C.half_up(revenue * p, 1000) for p in rest]
            left = revenue - sum(amounts)
            w = [t * rng.uniform(0.9, 1.1) for t in tail_weights]
            tail = [round(left * x / sum(w)) for x in w]
            tail[-1] += left - sum(tail)
            for n, a in zip(names, amounts + tail):
                out[n][y] = a
        return out

    # ------------------------------------------------------------------ KPIs
    def _kpis(self, rng):
        expiring = [rng.randint(8, 14) for _ in range(36)]
        renewed = [e - (1 if rng.random() < 0.6 else 0) for e in expiring]
        exp26, ren26 = RENEWALS_FY26
        expiring[24:] = _spread(exp26, 12, rng, low=6)
        lost = [0] * 12
        for _ in range(exp26 - ren26):
            j = rng.choice([j for j in range(12) if expiring[24 + j] - lost[j] > 0])
            lost[j] += 1
        renewed[24:] = [e - lo for e, lo in zip(expiring[24:], lost)]
        assert sum(renewed[24:]) == ren26
        rows = []
        for i, m in enumerate(MONTHS):
            rows.append({"month": m.strftime("%Y-%m"), "mw_under_contract": round(1040 + 375 * i / 35 + rng.uniform(-4, 4)),
                         "technicians": round(112 + 39 * i / 35), "tickets_closed": round(
                             (850 + 15 * i) * SEASON["cr"][i % 12] * rng.uniform(0.95, 1.05)),
                         "avg_response_hours": round(7.8 - 1.4 * i / 35 + rng.uniform(-0.3, 0.3), 1),
                         "contracts_expiring": expiring[i], "contracts_renewed": renewed[i]})
        return rows

    # ------------------------------------------------------------------ files
    def financials_xlsx(self):
        wb = xlsx.Workbook()
        bold, money = xlsx.Style(bold=True), xlsx.Style(num_fmt="#,##0.00")
        s = wb.sheet("P&L")
        s.set("A1", "Brightrow Field Services", style=bold)
        s.set("A2", "Monthly income statement in US dollars. The fiscal year ends September 30.")
        s.set("A4", "Line item", style=bold)
        for i, m in enumerate(MONTHS):
            s.set((4, i + 2), m.strftime("%b %Y"), style=bold)
        r = 5

        def row(label, values, style=money, label_style=None):
            nonlocal r
            s.set((r, 1), label, style=label_style)
            for i, v in enumerate(values):
                if v is not None:
                    s.set((r, i + 2), v / 100, style=style)
            r += 1

        def gap():
            nonlocal r
            r += 1

        reported = {k: list(v) for k, v in self.rev.items()}
        reported_cost = {k: [list(c) for c in v] for k, v in self.cost.items()}
        for i in range(RECLASS_THROUGH):     # through month 18, cleaning was booked inside corrective repairs
            reported["cr"][i] += reported["mc"][i]
            reported["mc"][i] = None
            for j in range(3):
                reported_cost["cr"][j][i] += reported_cost["mc"][j][i]
                reported_cost["mc"][j][i] = None
        s.set((r, 1), "Revenue", style=bold)
        r += 1
        for k, label in LINES:
            row(label, reported[k])
        row("Total revenue", [self.total_revenue(i) for i in range(36)], label_style=bold)
        gap()
        for j, head in enumerate(("Direct labor", "Materials", "Subcontractors")):
            s.set((r, 1), head, style=bold)
            r += 1
            for k, label in LINES:
                row(f"  {label}", reported_cost[k][j])
        row("Total cost of services", [self.total_revenue(i) - self.gross_profit(i) for i in range(36)], label_style=bold)
        row("Gross profit", [self.gross_profit(i) for i in range(36)], label_style=bold)
        gap()
        s.set((r, 1), "Selling, general and administrative", style=bold)
        r += 1
        for k, label in SG_A:
            row(label, self.sga[k])
        row("Total SG&A", [self.sga_total(i) for i in range(36)], label_style=bold)
        row("Legal settlement (one-time)", self.settlement)
        row("Reported EBITDA", [self.reported_ebitda(i) for i in range(36)], label_style=bold)
        gap()
        s.set((r, 1), "Memo: module cleaning included in corrective repairs through March 2025", style=bold)
        r += 1
        memo = lambda vals: [vals[i] if i < RECLASS_THROUGH else None for i in range(36)]  # noqa: E731
        row("  Revenue", memo(self.rev["mc"]))
        for j, head in enumerate(("Direct labor", "Materials", "Subcontractors")):
            row(f"  {head}", memo(self.cost["mc"][j]))
        s.width(1, 58)
        s.freeze = "B5"

        a = wb.sheet("Annual summary")
        a.set("A1", "Fiscal years end September 30, in US dollars", style=bold)
        for y, label in enumerate(("FY2024", "FY2025", "FY2026")):
            a.set((2, y + 2), label, style=bold)
        for n, (label, f) in enumerate([("Total revenue", self.total_revenue), ("Gross profit", self.gross_profit),
                                        ("Reported EBITDA", self.reported_ebitda)], 3):
            a.set((n, 1), label)
            for y in range(3):
                a.set((n, y + 2), self.fy_sum(f, y) / 100, style=money)
        a.width(1, 30)

        wc = wb.sheet("Working capital and capex")
        wc.set("A1", "Fiscal year-end balances and annual capital spending, in US dollars", style=bold)
        for y, label in enumerate(("FY2024", "FY2025", "FY2026")):
            wc.set((2, y + 2), label, style=bold)
        for n, (label, key) in enumerate(BALANCE_LINES, 3):
            wc.set((n, 1), label)
            for y in range(3):
                wc.set((n, y + 2), self.balances[key][y] / 100, style=money)
        wc.width(1, 44)

        notes = wb.sheet("Notes")
        lines = [
            "Notes to the monthly income statement",
            "1. Module cleaning was reported inside corrective repairs through March 2025. From April 2025 it has its "
            "own line. The memo rows at the bottom of the P&L show the amounts that were included.",
            f"2. The legal settlement in {MONTHS[SETTLEMENT_MONTH - 1].strftime('%B %Y')} resolved a workmanship claim "
            f"from 2022 and is not expected to recur.",
            "3. The parent allocates corporate overhead for finance, HR, IT and insurance administration at a fixed "
            "monthly amount, shown on its own line.",
            f"4. Management estimates that a standalone Brightrow would spend ${STANDALONE_CENTS // 100:,} a month on "
            f"the same functions after the carve-out.",
        ]
        for n, text in enumerate(lines, 1):
            notes.set((n, 1), text, style=bold if n == 1 else None)
        notes.width(1, 120)
        return wb.to_bytes()

    def customers_xlsx(self):
        wb = xlsx.Workbook()
        bold, money = xlsx.Style(bold=True), xlsx.Style(num_fmt="#,##0.00")
        s = wb.sheet("Revenue by customer")
        for c, label in enumerate(("Customer", "FY2024", "FY2025", "FY2026"), 1):
            s.set((1, c), label, style=bold)
        order = sorted(self.customers, key=lambda n: -self.customers[n][2])
        for r, name in enumerate(order, 2):
            s.set((r, 1), name)
            for y in range(3):
                s.set((r, y + 2), self.customers[name][y] / 100, style=money)
        total_row = len(order) + 2
        s.set((total_row, 1), "Total", style=bold)
        for y in range(3):
            s.set((total_row, y + 2), sum(v[y] for v in self.customers.values()) / 100, style=bold.but(num_fmt="#,##0.00"))
        s.width(1, 40)
        return wb.to_bytes()

    def kpis_csv(self):
        cols = ["month", "mw_under_contract", "technicians", "tickets_closed", "avg_response_hours",
                "contracts_expiring", "contracts_renewed"]
        return C.csv_text(cols, [[r[c] if c != "avg_response_hours" else f"{r[c]:.1f}" for c in cols] for r in self.kpis])

    def teaser_md(self):
        c = CLAIMS
        return f"""# Project Brightrow

## A carve-out in commercial solar operations and maintenance

Confidential teaser prepared by Halvorsen Pike Advisors for the seller. Not an offer to sell securities.

### The opportunity

Our client, a diversified electrical contractor, is exploring the sale of Brightrow Field Services ("Brightrow" or the "Company"), its commercial solar operations and maintenance business. Brightrow will be offered as a standalone carve-out with its own management team, field technicians and customer contracts, and the seller will provide transition services for twelve months after closing.

### Investment highlights

- **Recurring, contracted revenue.** Preventive maintenance contracts and monitoring subscriptions provide a predictable base, and contract renewal rates have stayed above {c['renewal_floor_pct']}% through the last twelve months.
- **Attractive margins.** Brightrow has delivered EBITDA margins above {c['margin_floor_pct']}% over the last twelve months, supported by route density and disciplined pricing.
- **Diversified customer base.** No customer accounts for more than {c['customer_cap_pct']}% of revenue, and the Company serves commercial owners, community solar funds and school districts across Texas and Oklahoma.
- **Growth runway.** The installed base of commercial solar in the region keeps growing, and the Company adds technicians ahead of demand.

### Business overview

Founded in 2012, Brightrow maintains rooftop and ground-mount commercial solar systems under multi-year service agreements. Services span preventive maintenance, corrective repairs, module cleaning and remote monitoring, delivered from three regional depots by a field team trained on every major inverter platform.

The Company has grown alongside its customers' portfolios, and its monitoring platform lets technicians resolve many faults before a site visit is needed.

### Process

The seller expects to share a confidential information memorandum with qualified parties who sign a non-disclosure agreement. First-round indications of interest will be requested in early 2027. All inquiries should go through Halvorsen Pike Advisors, and the Company's management and employees should not be contacted directly.
"""

    def files(self):
        return {"brightrow/dataroom/financials.xlsx": self.financials_xlsx(),
                "brightrow/dataroom/customers.xlsx": self.customers_xlsx(),
                "brightrow/dataroom/kpis.csv": self.kpis_csv().encode(),
                "brightrow/dataroom/teaser.md": self.teaser_md().encode()}


def _spread(total, n, rng, low=1):
    """n whole numbers that add up to total, each at least low."""
    cuts = sorted(rng.randint(0, total - low * n) for _ in range(n - 1))
    parts = [b - a for a, b in zip([0] + cuts, cuts + [total - low * n])]
    return [p + low for p in parts]
