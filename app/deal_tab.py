"""The Deal tab: Brightrow's data room, the deal analyst's assumptions, the model with its in-page view, the claims
check on the seller's teaser, and the memo.

The tab opens on the data room. "Build the model", "Check the teaser's claims" and "Draft the memo" reveal their
sections in turn, which is the order presenter mode uses. Every figure is a trace link, and every cell in the
Model view shows its formula.
"""
from app import model_view
from app.render import icon
from engine import fmt

esc = model_view.esc
FILES = (("financials.xlsx", "deal.file.financials"), ("customers.xlsx", "deal.file.customers"),
         ("kpis.csv", "deal.file.kpis"), ("teaser.md", "deal.file.teaser"))
TILES = (("ev", "deal.kpi.ev"), ("equity0", "deal.kpi.equity0"), ("moic", "deal.kpi.moic"), ("irr", "deal.kpi.irr"),
         ("net_leverage_0", "deal.kpi.lev"), ("min_headroom", "deal.kpi.headroom"))


def render(desk, deal, book, words, R, memo_html=""):
    w, L = words, desk.ledger
    labels = words.table("labels.model")
    files = []
    for name, key in FILES:
        src = next(s for s in L.sources(company="brightrow") if s["path"].endswith(name))
        q = R.q(src["ref"])
        R.refs.add(q)
        files.append(f"<li><button type=\"button\" class=\"dfile\" data-ref=\"{esc(q)}\" aria-label=\""
                     f"{esc(w.fill('deal.file.open', name=name))}\">{icon('file')}<span class=\"dfile-n\"><code>{esc(name)}"
                     f"</code><span class=\"muted\">{esc(w[key])}</span></span><code class=\"sha\">{esc(src['sha256'][:12])}"
                     f"</code></button></li>")
    controls = (f"<div class=\"controls\" role=\"toolbar\"><button type=\"button\" class=\"btn primary\" data-reveal=\"model\">"
                f"{icon('play')}<span>{esc(w['deal.controls.model'])}</span></button><button type=\"button\" class=\"btn\" "
                f"data-reveal=\"claims\">{esc(w['deal.controls.claims'])}</button><button type=\"button\" class=\"btn\" "
                f"data-reveal=\"memo\">{esc(w['deal.controls.memo'])}</button><span class=\"spacer\"></span>"
                f"<a class=\"btn ghost\" href=\"Brightrow_model.xlsx\" download>{esc(w['deal.controls.download'])}</a>"
                f"</div>")
    head = (f"<div class=\"deal-head\"><h2>{esc(w['deal.title'])}</h2><p class=\"muted\">{esc(w['deal.line'])}</p></div>"
            f"<section class=\"panel dataroom\"><h3>{esc(w['deal.dataroom'])}</h3><ul class=\"files\">{''.join(files)}</ul>"
            f"</section>")
    return (f"{controls}{head}{assumptions(desk, deal, w, labels, R)}{summary(deal, w, R)}{model_panel(book, w, R)}"
            f"{claims(desk, w, R)}{memo_html}")


def assumptions(desk, deal, w, labels, R):
    run = desk.runs.get("deal_analyst")
    rows = []
    for key, item in deal.assumptions.items():
        proposed = R.num(item["ref"]) if item["source"] == "agent" else ""
        src = {"agent": "deal.source.agent", "override": "deal.source.override", "history": "deal.source.history"}
        why = R.agent_text(item["rationale"]) if item.get("rationale") else ""
        rows.append(f"<tr><td>{esc(labels['assume.' + key])}</td><td class=\"r\">{R.num(item['history'])}</td>"
                    f"<td class=\"r\">{proposed}</td><td class=\"r\"><strong>{R.num(item['ref'])}</strong></td>"
                    f"<td><span class=\"pill s-{item['source']}\">{esc(w[src[item['source']]])}</span></td>"
                    f"<td class=\"why\">{why}</td></tr>")
    if run and any(i["source"] == "agent" for i in deal.assumptions.values()):
        when = fmt.day_label(fmt.local_date(run["recorded_at"]), year=True)
        label = f"<p class=\"ai-label\">{icon('spark')}{esc(w.fill('deal.assume.label', date=when))}</p>"
    else:
        label = f"<p class=\"muted\">{esc(w['deal.assume.invalid' if run else 'deal.assume.missing'])}</p>"
    cols = "".join(f"<th{' class=r' if k in ('history', 'proposed', 'used') else ''}>{esc(w['deal.assume.col.' + k])}</th>"
                   for k in ("input", "history", "proposed", "used", "source", "why"))
    return (f"<section class=\"panel assumptions\" data-step=\"model\" hidden><h3>{esc(w['deal.assume.title'])}</h3>"
            f"<p>{esc(w['deal.assume.text'])}</p><div class=\"tablewrap\"><table class=\"assume\"><thead><tr>{cols}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>{label}</section>")


def summary(deal, w, R):
    tiles = "".join(f"<div class=\"tile\"><div class=\"tile-head\"><span class=\"tile-label\">{esc(w[key])}</span></div>"
                    f"<div class=\"tile-value\">{R.num(deal.refs[name])}</div></div>" for name, key in TILES)
    return (f"<section class=\"model-summary\" data-step=\"model\" hidden><div class=\"tiles six\">{tiles}</div>"
            f"</section>")


def model_panel(book, w, R):
    tabs, panes = model_view.grid(book, R)
    bar = (f"<div class=\"fbar\"><span class=\"fx-cell\" id=\"fx-cell\"></span><span class=\"fx\">fx</span>"
           f"<span class=\"fx-text\" id=\"fx-text\">{esc(w['deal.formula.hint'])}</span><span id=\"fx-trace\"></span></div>")
    return (f"<section class=\"panel modelview\" data-step=\"model\" hidden><h3>{esc(w['deal.model.title'])}</h3>"
            f"<p>{esc(w['deal.model.text'])}</p>{bar}<div class=\"sheets\">{''.join(panes)}</div>"
            f"<div class=\"sheet-tabs\">{''.join(tabs)}</div></section>")


def claims(desk, w, R):
    L, items = desk.ledger, []
    for ref in desk.claims:
        c = L.get(ref)
        if not c["metric"]:
            continue
        p = c["params"]
        params = {"threshold": ("html", R.meta(f"{c['stated'] * 100:.0f}%", ref)), "ledger": p["ledger"]}
        if p.get("context"):
            params["context"] = p["context"]
        status = c["status"]
        kind = {"supported": "pass", "contradicted": "flag"}.get(status, "info")
        items.append(f"<li class=\"note s-{kind}\">{icon('check' if kind == 'pass' else 'alert')}<div><p class=\"claim\" "
                     f"data-src=\"quote\">&ldquo;{esc(c['text'])}&rdquo;</p><p><strong>{esc(w['deal.claim.' + status])}.</strong> "
                     f"{R.fill('deal.claim.' + c['metric'], params)}</p></div></li>")
    return (f"<section class=\"panel claims\" data-step=\"claims\" hidden><h3>{esc(w['deal.claims.title'])}</h3>"
            f"<p>{esc(w['deal.claims.text'])}</p><ul class=\"notes big\">{''.join(items)}</ul></section>")
