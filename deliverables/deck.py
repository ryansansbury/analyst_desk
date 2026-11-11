"""Kiskadee Freight's monthly board deck: five 16:9 slides for the last full month before the demo, October 2026.

Headlines and bullets come from the board deck agent's recorded run through the gate. Charts render from the ledger,
never from the agent: the agent only picks which chart from a fixed list per slide. Weekly values are registered as
derived values, so every bar in a table view traces like any other number. Weeks run from the 1st, so the days after
the 28th make a partial week, and the charts mark it as partial and leave it out of the weekly comparisons.
"""
import html
from datetime import date, timedelta

from agents import replay, validate
from app import charts
from app.render import icon, keep_last_words, keep_terms
from engine import fmt
from engine.metrics import Builder
from generate import common as C

esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
MONTH = C.BOARD_MONTH
MONTH_NAME = fmt.MONTHS[MONTH.month - 1]


def weeks(first):
    """The month in weeks from the 1st: four full weeks, then the days left over as a partial one."""
    last = date(first.year + (first.month == 12), first.month % 12 + 1, 1) - timedelta(days=1)
    starts = [first + timedelta(days=7 * i) for i in range(5)]
    return [(a.isoformat(), min(a + timedelta(days=6), last).isoformat()) for a in starts if a <= last]


WEEKS = weeks(MONTH)


def week_label(first, last):
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    return f"{fmt.MONTHS[a.month - 1][:3]} {a.day} to {b.day}"


class Weekly(Builder):
    """Kiskadee's board month by week: loads, on-time share, empty-mile share, invoiced, collected, receivables."""

    def __init__(self, state):
        super().__init__(state)
        self.k = {}

    def build(self):
        L, ent = self.L, "kiskadee"
        for i, (a, b) in enumerate(WEEKS):
            p = f"{a}..{b}"
            f = lambda m: self.facts(ent, m, a, b)  # noqa: E731
            loads = self.total(ent, p, "loads", f("loads"), "count", "loads that week")
            ontime = self.total(ent, p, "on_time_loads", f("on_time_loads"), "count", "on-time loads that week")
            lm = self.total(ent, p, "loaded_miles", f("loaded_miles"), "miles", "loaded miles that week")
            em = self.total(ent, p, "empty_miles", f("empty_miles"), "miles", "empty miles that week")
            allm = L.derive(ent, p, "all_miles", "sum", [lm, em], L.value(lm) + L.value(em), "miles", "loaded plus empty")
            self.k[f"loads_{i}"] = loads
            self.k[f"on_time_{i}"] = self.ratio(ent, p, "on_time", ontime, loads, "on-time loads over loads")
            self.k[f"empty_{i}"] = self.ratio(ent, p, "empty_pct", em, allm, "empty miles over all miles")
            self.k[f"invoiced_{i}"] = self.total(ent, p, "invoiced", f("invoiced"), "cents", "invoiced that week")
            self.k[f"cash_{i}"] = self.total(ent, p, "cash", f("cash_applied"), "cents", "cash applied that week")
            ar = self.facts(ent, "ar_balance", b, b)
            self.k[f"ar_{i}"] = ar[-1] if ar else None
        return self.k


def render(desk, words, R):
    w, L = words, desk.ledger
    month = desk.board
    meeting = esc(w.fill("deck.meeting", month=f"{MONTH_NAME} {MONTH.year}"))
    weekly = Weekly(desk.clean).build()
    run = desk.runs.get("board_deck")
    chk = replay.check(run, L) if run else None
    usable = chk and chk["status"] in ("valid", "stale")
    slides = {s["n"]: s for s in replay.final(run)["slides"]} if usable else {}
    mapping = chk["mapping"] if usable else {}
    out = []
    for n in range(1, 6):
        s = slides.get(n)
        if s:
            headline = keep_last_words(keep_terms(R.agent_text(validate.to_ledger(s["headline"], mapping))))
            bullets = "".join(f"<li>{keep_last_words(keep_terms(R.agent_text(validate.to_ledger(b, mapping))))}</li>"
                              for b in s["bullets"])
            chart_key = s["chart"]
        else:
            headline = esc(w[f"deck.topic.{n}"])
            bullets = f"<li class=\"muted\">{esc(w['deck.invalid' if run else 'deck.missing'])}</li>"
            chart_key = {1: "kpi_tiles", 2: "margin_bridge", 3: "loads_by_week", 4: "invoiced_vs_collected", 5: "none"}[n]
        chart = chart_html(chart_key, month, weekly, w, R)
        wide = " wide" if chart_key == "none" else ""
        out.append(f"<article class=\"slide{wide}\" id=\"slide-{n}\" aria-label=\"{esc(w['deck.slide'])} {n}\">"
                   f"<header class=\"slide-top\"><span>{esc(w['deck.company'])}</span><span>{meeting}</span>"
                   f"<span data-src=\"slide\">{n} / 5</span></header><h3 class=\"slide-h\">{headline}</h3>"
                   f"<div class=\"slide-body\"><ul class=\"slide-bullets\">{bullets}</ul>"
                   f"{'<div class=\"slide-chart\">' + chart + '</div>' if chart else ''}</div>"
                   f"<footer class=\"slide-foot\">{esc(w['deck.foot'])}</footer></article>")
    if usable:
        when = fmt.day_label(fmt.local_date(run["recorded_at"]), year=True)
        label = f"<p class=\"ai-label\">{icon('spark')}{esc(w.fill('deck.label', date=when))}</p>"
    else:
        label = f"<p class=\"muted\">{esc(w['deck.invalid' if run else 'deck.missing'])}</p>"
    controls = (f"<div class=\"controls\"><span class=\"spacer\"></span><button type=\"button\" class=\"btn ghost\" "
                f"id=\"print-deck\">{esc(w['deck.print'])}</button></div>")
    return (f"{controls}<div class=\"deck-head\"><h2>{esc(w['deck.company'])}</h2><p class=\"muted\">"
            f"{meeting}</p>{label}</div><div class=\"slides\">{''.join(out)}</div>")


def chart_html(key, m, wk, w, R):
    if key == "none":
        return ""
    if key == "kpi_tiles":
        tiles = [("loads", "loads_var"), ("revenue", "revenue_var"), ("gross_margin", "gross_margin_var"),
                 ("gross_margin_pct", None), ("ebitda", "ebitda_var"), ("on_time", None)]
        cells = "".join(f"<div class=\"mini\"><span class=\"mini-l\">{esc(w['deck.kpi.' + k])}</span><span class=\"mini-v\">"
                        f"{R.num(m[k])}</span><span class=\"mini-d\">{R.num(m[v]) if v else ''}</span></div>" for k, v in tiles)
        return f"<div class=\"mini-grid\">{cells}</div>"
    if key == "margin_bridge":
        steps = [(w["deck.bridge.budget"], m["gross_margin_budget"], "total"), (w["deck.bridge.volume"], m["volume_effect"], "step"),
                 (w["deck.bridge.rate"], m["rate_effect"], "step"), (w["deck.bridge.cost"], m["cost_effect"], "step"),
                 (w["deck.bridge.actual"], m["gross_margin"], "total")]
        data = [(label, R.L.value(ref) / 100, R.num(ref), kind) for label, ref, kind in steps]
        table = charts.table(w["deck.chart.margin_bridge"], [w["deck.col.step"], w["deck.col.amount"]],
                             [[esc(label), R.num(ref)] for label, ref, _ in steps])
        return charts.waterfall(data, w["deck.chart.margin_bridge"], esc(w["deck.summary.margin_bridge"]), table)
    weeks = [(week_label(a, b) + (" " + w["deck.partial"] if i == 4 else ""), i) for i, (a, b) in enumerate(WEEKS)]
    if key in ("loads_by_week", "on_time_by_week", "empty_miles_by_week"):
        name = {"loads_by_week": "loads", "on_time_by_week": "on_time", "empty_miles_by_week": "empty"}[key]
        pts = [(label, R.L.value(wk[f"{name}_{i}"])) for label, i in weeks[:4]]
        table = charts.table(w[f"deck.chart.{key}"], [w["deck.col.week"], w["deck.col.value"]],
                             [[esc(label), R.num(wk[f"{name}_{i}"])] for label, i in weeks])
        return charts.columns(pts, w[f"deck.chart.{key}"], esc(w.fill("deck.summary.partial", month=MONTH_NAME)), table_html=table)
    if key in ("invoiced_vs_collected", "receivables_by_week"):
        if key == "invoiced_vs_collected":
            pts = [(label, R.L.value(wk[f"invoiced_{i}"]) / 100, R.L.value(wk[f"cash_{i}"]) / 100) for label, i in weeks[:4]]
            table = charts.table(w[f"deck.chart.{key}"], [w["deck.col.week"], w["deck.col.invoiced"], w["deck.col.collected"]],
                                 [[esc(label), R.num(wk[f"invoiced_{i}"]), R.num(wk[f"cash_{i}"])] for label, i in weeks])
            return charts.pair_columns(pts, (w["deck.col.invoiced"], w["deck.col.collected"]), w[f"deck.chart.{key}"],
                                       esc(w.fill("deck.summary.partial", month=MONTH_NAME)), table_html=table)
        pts = [(label, R.L.value(wk[f"ar_{i}"]) / 100) for label, i in weeks[:4]]
        table = charts.table(w[f"deck.chart.{key}"], [w["deck.col.week"], w["deck.col.value"]],
                             [[esc(label), R.num(wk[f"ar_{i}"])] for label, i in weeks])
        return charts.columns(pts, w[f"deck.chart.{key}"], esc(w.fill("deck.summary.partial", month=MONTH_NAME)), table_html=table)
    return ""
