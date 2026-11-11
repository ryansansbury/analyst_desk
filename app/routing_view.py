"""Model routing on How it works: how each model did on the same suite, intake quality against cost as a chart, and
the model each agent runs on. Every figure is read from evals/model_comparison.json, the summary of the
comparison run, and the routes come from agents/routing.py, the same rules the recorded morning ran on. Without a
comparison the panel isn't on the page at all.
"""
import math

from agents import routing
from app import charts
from app.how import esc, fill, m
from engine import fmt

AGENT = {"intake_mapper": "intake", "daily_commentary": "commentary", "deal_analyst": "deal", "board_deck": "deck",
         "memo_writer": "memo"}
PROSE = routing.TASKS[1:]
# A vendor's color is fixed here once, so it never depends on which models ran. A fourth vendor folds into Other.
SLOTS = {"Anthropic": "s1", "OpenAI": "s2", "Google": "s3"}


def dollars(x):
    """$0.69 for a morning, and two significant figures for a fraction of a cent, like $0.0065."""
    if x >= 0.1:
        return f"${x:,.2f}"
    if x <= 0:
        return "$0"
    return f"${x:.{max(2, 1 - math.floor(math.log10(x)))}f}"


def tick(x):
    """An axis tick in as few decimals as it needs, like $0.001 or $0.10."""
    return f"${x:.{max(2, -math.floor(math.log10(x) + 1e-9))}f}"


def duration(s):
    return f"{s:.0f} s" if s < 120 else f"{s / 60:.1f} min"


def slot(model):
    return SLOTS.get(model.get("vendor"), "so")


def task(model, name):
    return ((model or {}).get("tasks") or {}).get(name) or {}


def short_list(w, tasks):
    """Agents by their short names for a table cell, like "Commentary, board deck, and memo", so the list stays on
    one line at every desktop width."""
    names = fmt.items(w["route.short." + AGENT[t]] for t in tasks)
    return names[:1].upper() + names[1:]


def routed_cost(plan, by_id):
    """A morning on the routes: each agent's call at its routed model's cost on that same task."""
    costs = [task(by_id.get(r["model"]), t).get("cost") for t, r in plan.items()]
    return None if None in costs else round(sum(costs), 6)


def tiles(w, plan, by_id, default, name):
    out = []

    def tile(label, value, foot):
        out.append(f"<div class=\"tile proof\"><div class=\"tile-label\">{label}</div><div class=\"tile-value\">{value}"
                   f"</div><p class=\"tile-foot\">{foot}</p></div>")

    routed, single = routed_cost(plan, by_id), (by_id.get(default) or {}).get("morning_cost")
    if routed is not None:
        foot = (fill(w, "route.k.routed.save", pct=m(f"{(1 - routed / single) * 100:.0f}%"), model=m(name(default)))
                if single and routed < single else esc(w["route.k.routed.foot"]))
        tile(esc(w["route.k.routed"]), m(dollars(routed)), foot)
    if single is not None:
        tile(fill(w, "route.k.single", model=m(name(default))), m(dollars(single)), esc(w["route.k.single.foot"]))
    r = plan["intake_mapper"]
    s = task(by_id.get(r["model"]), "intake_mapper")
    if s.get("runs"):
        tile(esc(w["route.k.intake"]), fill(w, "how.k.of", a=m(s["exact"]), b=m(s["runs"])),
             fill(w, "route.k.intake.foot", model=m(name(r["model"]))))
    return f"<div class=\"tiles proofs route-tiles\">{''.join(out)}</div>" if out else ""


def y_scale(exacts, top, best):
    """(ticks, low, high) for the exact matches. The axis starts just below the lowest score and keeps half a step of
    room past each end, so no dot sits on an edge, and the quality bar's line always falls inside it."""
    low = max(0, min(min(exacts) - 1, best - 2, top - 2))
    step = next(n for n in (1, 2, 3, 4, 6, 12) if (top - low) / n <= 4)
    bottom = max(0, top - math.ceil((top - low) / step) * step)
    return list(range(bottom, top + 1, step)), bottom - step / 2, top + step / 2


def blend(w, plan, by_id, default, name):
    """How the blended morning adds up: each routed model with the agents it runs and what their calls cost and take,
    the total, and then the same morning on each of those models alone, and on the default."""
    groups = {}
    for t, r in plan.items():
        groups.setdefault(r["model"], []).append(t)
    rows, cost, secs = [], 0.0, 0.0
    for mid, tasks in sorted(groups.items(), key=lambda g: (-len(g[1]), g[0])):
        costs = [task(by_id.get(mid), t).get("cost") for t in tasks]
        times = [task(by_id.get(mid), t).get("seconds") for t in tasks]
        if None in costs or None in times:
            return ""
        cost, secs = cost + sum(costs), secs + sum(times)
        agents = short_list(w, tasks)
        rows.append(f"<tr><td data-label=\"{esc(w['route.col.model'])}\">{m(name(mid))}</td>"
                    f"<td data-label=\"{esc(w['route.blend.runs'])}\">{esc(agents)}</td>"
                    f"<td class=\"r\" data-label=\"{esc(w['route.col.seconds'])}\">{m(duration(sum(times)))}</td>"
                    f"<td class=\"r\" data-label=\"{esc(w['route.col.cost'])}\">{m(dollars(sum(costs)))}</td></tr>")
    rows.append(f"<tr class=\"total\"><td>{esc(w['route.k.routed'])}</td><td></td>"
                f"<td class=\"r\" data-label=\"{esc(w['route.col.seconds'])}\">{m(duration(secs))}</td>"
                f"<td class=\"r\" data-label=\"{esc(w['route.col.cost'])}\">{m(dollars(cost))}</td></tr>")
    for mid in sorted(set(groups) | {default}, key=lambda i: -((by_id.get(i) or {}).get("morning_cost") or 0)):
        x = by_id.get(mid) or {}
        if x.get("morning_cost") is None or x.get("morning_seconds") is None:
            continue
        # A model alone only makes a morning if it gave a valid reply for every agent.
        if any(s.get("valid", 0) < s.get("runs", 0) for s in (x.get("tasks") or {}).values()):
            continue
        rows.append(f"<tr class=\"alone\"><td>{fill(w, 'route.blend.alone', model=m(name(mid)))}</td><td></td>"
                    f"<td class=\"r\" data-label=\"{esc(w['route.col.seconds'])}\">{m(duration(x['morning_seconds']))}</td>"
                    f"<td class=\"r\" data-label=\"{esc(w['route.col.cost'])}\">{m(dollars(x['morning_cost']))}</td></tr>")
    cols = (("", "route.col.model"), ("", "route.blend.runs"), (" class=\"r\"", "route.col.seconds"),
            (" class=\"r\"", "route.col.cost"))
    head = "".join(f"<th scope=\"col\"{cls}>{esc(w[k])}</th>" for cls, k in cols)
    return (f"<h4>{esc(w['route.blend'])}</h4><div class=\"tablewrap\"><table class=\"models blend\"><thead><tr>{head}"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def chart(w, models, plan, name):
    """Intake exact matches against the cost of one mapping on a log axis. A model without a price can't sit on a
    cost axis, so it stays in the tables with a note."""
    priced = [(x, task(x, "intake_mapper")) for x in models if task(x, "intake_mapper").get("runs")]
    off = [x for x, s in priced if not s.get("cost")]
    pts = [(x, s) for x, s in priced if s.get("cost")]
    if len(pts) < 2:
        return ""
    a = math.log10(min(s["cost"] for _, s in pts)) - 0.35
    b = math.log10(max(s["cost"] for _, s in pts)) + 0.35
    best = max(s["exact"] for _, s in priced)
    yt, lo, hi = y_scale([s["exact"] for _, s in pts], max(s["runs"] for _, s in pts), best)
    X = lambda c: (math.log10(c) - a) / (b - a) * 100  # noqa: E731
    Y = lambda v: (v - lo) / (hi - lo) * 100  # noqa: E731
    r = plan["intake_mapper"]
    # The ringed dot's label claims its space first, then the best scores, the dearer model first on a tie.
    order = sorted(pts, key=lambda p: (p[0]["id"] != r["model"], -p[1]["exact"], -p[1]["cost"]))
    points = [(x["id"], X(s["cost"]), Y(s["exact"]), slot(x), m(name(x["id"])),
               w["route.chart.tip"].format(model=name(x["id"]), vendor=x["vendor"], exact=s["exact"], runs=s["runs"],
                                           cost=dollars(s["cost"])), x["id"] == r["model"]) for x, s in order]
    vendors = {x["vendor"] for x, _ in pts}
    legend = [f"<li><span class=\"sw {c}\"></span>{esc(v)}</li>" for v, c in SLOTS.items() if v in vendors]
    if vendors - set(SLOTS):
        legend.append(f"<li><span class=\"sw so\"></span>{esc(w['route.chart.other'])}</li>")
    legend.append(f"<li><span class=\"sw ring\"></span>{esc(w['route.chart.ring'])}</li>")
    cost = task(next((x for x, _ in pts if x["id"] == r["model"]), None), "intake_mapper").get("cost")
    summary = fill(w, "route.chart.summary." + r["why"], cleared=m(r["cleared"]), tested=m(r["tested"]),
                   model=m(name(r["model"])), cost=m(dollars(cost)) if cost else "")
    if off:
        summary += " " + fill(w, "route.chart.unpriced", models=m(fmt.items(name(x["id"]) for x in off)))
    rows = [[m(name(x["id"])), esc(x["vendor"]), fill(w, "how.k.of", a=m(s["exact"]), b=m(s["runs"])),
             m(dollars(s["cost"]))] for x, s in sorted(pts, key=lambda p: p[1]["cost"])]
    table = charts.table(w["route.chart.title"], [w["route.col.model"], w["route.col.vendor"], w["route.col.intake"],
                                                  w["route.chart.col.cost"]], rows)
    # Scores are whole numbers, so the bar's line runs between two levels and never through a dot.
    return charts.scatter(points, [(X(t), m(tick(t)), minor) for t, minor in charts.log_ticks(a, b)],
                          [(Y(v), m(v), False) for v in yt], w["route.chart.title"],
                          (w["route.chart.y"], w["route.chart.x"]), summary,
                          f"<ul class=\"legend\">{''.join(legend)}</ul>", table,
                          line=(Y(best - 1.5), w["route.chart.bar"]) if best >= 2 else None)


def routes_table(w, plan, name):
    head = "".join(f"<th>{esc(w['route.col.' + c])}</th>" for c in ("agent", "on", "why", "fallback"))
    rows = []
    for t in routing.TASKS:
        r = plan[t]
        why = "untested" if r["why"] == "none" and not r["tested"] else r["why"]
        # The first model in the fallback takes over, and the tip lists the whole chain in order.
        back, tip = esc(w["route.fallback.none"]), ""
        if r["fallback"]:
            more = len(r["fallback"]) - 1
            back = (fill(w, "route.fallback.more", model=m(name(r["fallback"][0])), n=m(more)) if more
                    else m(name(r["fallback"][0])))
            if more:
                tip = f" data-tip=\"{esc(fmt.items(name(i) for i in r['fallback']))}\" tabindex=\"0\""
        cells = [f"<td class=\"who\"><strong>{esc(w['how.a.' + AGENT[t]])}</strong></td>",
                 f"<td data-label=\"{esc(w['route.col.on'])}\">{m(name(r['model']))}</td>",
                 f"<td data-label=\"{esc(w['route.col.why'])}\">"
                 f"{fill(w, 'route.why.' + why, n=m(r['cleared']), tested=m(r['tested']))}</td>",
                 f"<td data-label=\"{esc(w['route.col.fallback'])}\"{tip}>{back}</td>"]
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f"<h4>{esc(w['route.routes'])}</h4><div class=\"tablewrap\"><table class=\"agents routes\"><thead><tr>"
            f"{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def models_table(w, models, plan, name):
    routed = {}
    for t, r in plan.items():
        routed.setdefault(r["model"], []).append(t)

    def prose(x):
        return [task(x, t) for t in PROSE if task(x, t).get("runs")]

    def order(x):
        cost = x.get("morning_cost")
        return (-task(x, "intake_mapper").get("exact", -1), -sum(p["first_try"] for p in prose(x)), cost is None,
                cost or 0)

    cols = ("model", "vendor", "intake", "prose", "seconds", "cost", "routed")
    right = {c: " class=\"r\"" if c in ("seconds", "cost") else "" for c in cols}
    head = "".join(f"<th scope=\"col\"{right[c]}>{esc(w['route.col.' + c])}</th>" for c in cols)
    rows = []
    for x in sorted(models, key=order):
        i, p = task(x, "intake_mapper"), prose(x)
        intake = esc(w["route.none"])
        if i.get("runs"):
            intake = fill(w, "how.k.of", a=m(i["exact"]), b=m(i["runs"]))
            if i.get("harmful"):
                intake += f"<span class=\"sub\">{fill(w, 'route.harmful', n=m(i['harmful']))}</span>"
        first = esc(w["route.none"])
        if p:
            first = fill(w, "how.k.of", a=m(sum(s["first_try"] for s in p)), b=m(len(p)))
        secs = x.get("morning_seconds")
        cost = x.get("morning_cost")
        # Under the name, the model the vendor's API said answered, so the table shows it ran for real.
        said = ", ".join(x.get("answered_by") or [])
        cells = [f"<span class=\"sw {slot(x)}\"></span>{m(name(x['id']))}"
                 + (f"<span class=\"mid\">{m(said)}</span>" if said else ""), esc(x.get("vendor", "")), intake, first,
                 m(duration(secs)) if secs is not None else esc(w["route.none"]),
                 m(dollars(cost)) if cost is not None else esc(w["route.unpriced"]),
                 esc(short_list(w, routed[x["id"]])) if x["id"] in routed else esc(w["route.routed.none"])]
        rows.append("<tr>" + "".join(f"<td data-label=\"{esc(w['route.col.' + c])}\"{right[c]}>{v}</td>"
                                     for c, v in zip(cols, cells)) + "</tr>")
    return (f"<h4>{esc(w['route.models'])}</h4><div class=\"tablewrap\"><table class=\"models\"><thead><tr>{head}</tr>"
            f"</thead><tbody>{''.join(rows)}</tbody></table></div>")


def render(comparison, w, cfg=None):
    """The Model routing panel, or nothing before the first comparison."""
    models = [x for x in (comparison or {}).get("models", []) if x.get("tasks")]
    if not models:
        return ""
    cfg = routing.config() if cfg is None else cfg
    labels = {e["id"]: e.get("label") or e.get("model") or e["id"] for e in cfg.get("models", [])}
    labels.update({x["id"]: x["label"] for x in models})
    name = lambda i: labels.get(i, i)  # noqa: E731
    default = comparison.get("default") or cfg.get("default") or "claude-opus"
    plan = routing.routes(comparison, default, cfg.get("holds"))
    by_id = {x["id"]: x for x in models}
    ran = fmt.local_date(comparison.get("ran_at", ""))
    checked = comparison.get("prices_checked") or ""
    notes = [esc(w["route.bars"])]
    if ran:
        notes.append(fill(w, "route.ran", date=m(fmt.day_label(ran))))
    if all(x.get("via") == "claude-cli" for x in models):
        notes.append(esc(w["route.prices.cli"]))
    elif checked and checked == ran:
        notes.append(esc(w["route.prices.same"]))
    else:
        notes.append(fill(w, "route.prices", date=m(fmt.day_label(checked))) if checked
                     else esc(w["route.prices.undated"]))
    # A held agent is named in the intro, so the reason for the stronger model is said where the routes are read.
    held = {}
    for t, r in plan.items():
        if r["why"] == "held":
            held.setdefault(r["model"], []).append("the " + w["how.a." + AGENT[t]].lower())
    intro = esc(w["route.text"]) + "".join(
        " " + fill(w, "route.text.held", agents=esc(fmt.items(agents)[:1].upper() + fmt.items(agents)[1:]),
                   model=m(name(model))) for model, agents in held.items())
    return (f"<section class=\"panel routing\" id=\"how-routing\"><h3>{esc(w['route.title'])}</h3>"
            f"<p>{intro}</p>{tiles(w, plan, by_id, default, name)}{blend(w, plan, by_id, default, name)}"
            f"{chart(w, models, plan, name)}"
            f"{routes_table(w, plan, name)}{models_table(w, models, plan, name)}"
            f"<p class=\"muted note-small\">{' '.join(notes)}</p></section>")
