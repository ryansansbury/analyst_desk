"""The deal model for Brightrow Field Services in Python: five years of projections, the debt schedule, returns and
the sensitivity grid.

Each step runs in the same order as the workbook's formula for it, so the two agree to the cent. Year 0 is FY2026,
the last twelve months, from the data room through the ledger. Interest runs on each year's opening balance, so
nothing is circular. Cash builds after the sweep and offsets debt in net debt. There are no interim distributions,
so IRR is exactly MOIC to the one-fifth less one, and the workbook checks that too.
"""
YEARS = 5
LINES = ("pm", "cr", "mc", "ms")
FY = ("FY2026A", "FY2027E", "FY2028E", "FY2029E", "FY2030E", "FY2031E")
GRID = (7.0, 7.5, 8.0, 8.5, 9.0)


def compute(base, a, t):
    """base: FY2026 in dollars (rev_pm..rev_ms, gross_profit, sga_ex, standalone, adjusted_ebitda).
    a: the operating assumptions as fractions. t: the deal terms as multiples and fractions."""
    r = {"rev": {line: [base[f"rev_{line}"]] for line in LINES}}
    for y in range(1, YEARS + 1):
        for line in LINES:
            r["rev"][line].append(r["rev"][line][y - 1] * (1 + a[f"growth_{line}"]))
    rev = r["rev"]
    r["revenue"] = [rev["pm"][y] + rev["cr"][y] + rev["mc"][y] + rev["ms"][y] for y in range(YEARS + 1)]
    R = r["revenue"]
    r["gross_profit"] = [base["gross_profit"]] + [R[y] * a["gross_margin"] for y in range(1, YEARS + 1)]
    r["sga"] = [base["sga_ex"]] + [R[y] * a["sga_pct"] for y in range(1, YEARS + 1)]
    standalone = [base["standalone"]]
    for _ in range(YEARS):
        standalone.append(standalone[-1] * (1 + t["escalation"]))
    r["standalone"] = standalone
    r["ebitda"] = [base["adjusted_ebitda"]] + [r["gross_profit"][y] - r["sga"][y] - standalone[y]
                                                for y in range(1, YEARS + 1)]
    E = r["ebitda"]
    r["margin"] = [E[y] / R[y] for y in range(YEARS + 1)]
    r["da"] = [None] + [R[y] * a["da_pct"] for y in range(1, YEARS + 1)]
    r["ebit"] = [None] + [E[y] - r["da"][y] for y in range(1, YEARS + 1)]
    r["capex"] = [None] + [R[y] * a["capex_pct"] for y in range(1, YEARS + 1)]
    r["nwc"] = [R[y] * a["nwc_pct"] for y in range(YEARS + 1)]
    r["dnwc"] = [None] + [r["nwc"][y] - r["nwc"][y - 1] for y in range(1, YEARS + 1)]

    debt0 = E[0] * t["leverage"]
    keys = ("opening", "interest", "taxes", "cfads", "mandatory", "avail", "sweep", "closing", "cash", "net_debt",
            "net_leverage", "coverage", "lev_headroom", "cov_headroom")
    for k in keys:
        r[k] = [None]
    r["closing"][0], r["cash"][0] = debt0, 0.0
    r["net_debt"][0] = debt0
    r["net_leverage"][0] = debt0 / E[0]
    for y in range(1, YEARS + 1):
        op = r["closing"][y - 1]
        it = op * t["rate"]
        tx = max(0.0, (r["ebit"][y] - it) * t["tax"])
        cf = E[y] - tx - r["capex"][y] - r["dnwc"][y]
        md = min(op, t["amortization"] * debt0)
        av = cf - it - md
        sw = max(0.0, min(op - md, t["sweep"] * av))
        cl = op - md - sw
        ca = r["cash"][y - 1] + av - sw
        nd = cl - ca
        for k, v in (("opening", op), ("interest", it), ("taxes", tx), ("cfads", cf), ("mandatory", md), ("avail", av),
                     ("sweep", sw), ("closing", cl), ("cash", ca), ("net_debt", nd)):
            r[k].append(v)
        r["net_leverage"].append(nd / E[y])
        r["coverage"].append(E[y] / it if it > 0 else None)
        r["lev_headroom"].append(t["covenant_leverage"][y - 1] - nd / E[y])
        r["cov_headroom"].append(E[y] / it - t["covenant_coverage"] if it > 0 else None)

    ev = E[0] * t["entry"]
    fees = ev * t["fees"]
    uses = ev + fees
    equity0 = uses - debt0
    ev_exit = E[YEARS] * t["exit"]
    nd_exit = r["net_debt"][YEARS]
    equity_exit = ev_exit - nd_exit
    moic = equity_exit / equity0
    r.update(debt0=debt0, ev=ev, fees=fees, uses=uses, equity0=equity0, ev_exit=ev_exit, nd_exit=nd_exit,
             equity_exit=equity_exit, moic=moic, irr=moic ** (1 / 5) - 1,
             flows=[-equity0, 0.0, 0.0, 0.0, 0.0, equity_exit])
    r["grid_moic"] = [[(E[YEARS] * x - nd_exit) / (e * E[0] * (1 + t["fees"]) - debt0) for x in GRID] for e in GRID]
    r["grid_irr"] = [[m ** (1 / 5) - 1 for m in row] for row in r["grid_moic"]]
    return r


def multiple_text(x):
    """A multiple with its article for a lineage note, like a 7.5x or an 8.0x."""
    article = "an" if f"{x:.1f}".startswith(("8", "11.", "18.")) else "a"
    return f"{article} {x:.1f}x"


def register(L, r, inputs):
    """Write the model's headline outputs into the ledger, so the memo and the page can cite them. inputs maps
    'ebitda0', 'terms' and 'assumptions' to the ledger refs they came from. Money goes in as cents."""
    out = {}
    c = lambda v: v * 100  # noqa: E731

    def d(name, value, unit, transform, ins, extra=None):
        out[name] = L.derive("brightrow", "model", name, "model", [x for x in ins if x], value, unit, transform, extra)
        return out[name]

    t, a = inputs["terms"], inputs["assumptions"]
    e0 = inputs["ebitda0"]
    d("ev", c(r["ev"]), "cents", "FY2026 adjusted EBITDA times the entry multiple in Returns!C6", [e0, t["entry"]])
    d("fees", c(r["fees"]), "cents", "the enterprise value times the fee rate in Returns!C7", [out["ev"], t["fees"]])
    d("debt0", c(r["debt0"]), "cents", "FY2026 adjusted EBITDA times the leverage at close in Returns!C9", [e0, t["leverage"]])
    d("equity0", c(r["equity0"]), "cents", "total uses less the debt at close in Returns!C10",
      [out["ev"], out["fees"], out["debt0"]])
    for y in range(1, YEARS + 1):
        d(f"revenue_y{y}", c(r["revenue"][y]), "cents", f"{FY[y]} revenue from the service lines grown at their "
                                                         f"assumed rates on the Projections tab", [a.get(f"growth_{x}") for x in LINES])
        d(f"ebitda_y{y}", c(r["ebitda"][y]), "cents", f"{FY[y]} EBITDA as gross profit less SG&A and the "
                                                       f"standalone cost on the Projections tab", [out[f"revenue_y{y}"], a.get("gross_margin"),
                                                                             a.get("sga_pct")])
        d(f"net_leverage_y{y}", r["net_leverage"][y], "multiple", f"{FY[y]} net debt over EBITDA on the Debt tab",
          [out[f"ebitda_y{y}"], t["leverage"], t["rate"], t["sweep"]])
        d(f"lev_headroom_y{y}", r["lev_headroom"][y], "multiple", f"{FY[y]} headroom to the illustrative leverage "
                                                                  f"covenant on the Debt tab", [out[f"net_leverage_y{y}"],
                                                                                         t["covenant_leverage"]])
    d("margin_y5", r["margin"][YEARS], "ratio", "FY2031 EBITDA over revenue on the Projections tab",
      [out[f"ebitda_y{YEARS}"], out[f"revenue_y{YEARS}"]])
    d("revenue_cagr", (r["revenue"][YEARS] / r["revenue"][0]) ** (1 / YEARS) - 1, "ratio",
      "compound annual growth from FY2026 to FY2031", [out[f"revenue_y{YEARS}"]])
    d("net_leverage_0", r["net_leverage"][0], "multiple", "net leverage at close on the Debt tab", [out["debt0"], e0])
    d("coverage_y1", r["coverage"][1], "multiple", "FY2027 EBITDA over interest on the Debt tab", [out["ebitda_y1"], t["rate"]])
    d("min_headroom", min(r["lev_headroom"][1:]), "multiple", "the smallest headroom to the leverage covenant",
      [out[f"lev_headroom_y{y}"] for y in range(1, YEARS + 1)])
    d("ev_exit", c(r["ev_exit"]), "cents", "FY2031 EBITDA times the exit multiple in Returns!C13",
      [out[f"ebitda_y{YEARS}"], t["exit"]])
    d("nd_exit", c(r["nd_exit"]), "cents", "debt less cash at the end of FY2031 in Returns!C14", [out["debt0"]])
    d("equity_exit", c(r["equity_exit"]), "cents", "exit enterprise value less net debt in Returns!C15",
      [out["ev_exit"], out["nd_exit"]])
    d("moic", r["moic"], "multiple", "exit equity over equity at close in Returns!C16", [out["equity_exit"], out["equity0"]])
    d("irr", r["irr"], "ratio", "the IRR of the equity cash flows in Returns!C20", [out["moic"]])
    d("debt_paid", c(r["debt0"] - r["closing"][YEARS]), "cents", "debt at close less debt at the end of FY2031",
      [out["debt0"]])
    for i, e in enumerate(GRID):
        for j, x in enumerate(GRID):
            d(f"grid_moic_{i}{j}", r["grid_moic"][i][j], "multiple",
              f"MOIC at {multiple_text(e)} entry and {multiple_text(x)} exit on the Sensitivity tab", [out["moic"], out["ebitda_y5"], out["nd_exit"]])
            d(f"grid_irr_{i}{j}", r["grid_irr"][i][j], "ratio",
              f"IRR at {multiple_text(e)} entry and {multiple_text(x)} exit on the Sensitivity tab", [out[f"grid_moic_{i}{j}"]])
    return out
