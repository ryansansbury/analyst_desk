"""The investment committee memo: the memo agent's eleven sections from the recorded run, every figure rendered
from a placeholder with a citation that opens its trace, and tables drawn by code from the same ledger.

The gate checks the agent's text before it shows. "Inject an unsupported number" is a labeled test that types one
figure into the projections section, the way a careless edit would, and the gate fails the memo with the location.
Removing it passes again. Nothing in the memo is typed by hand.
"""
import html

from agents import replay, validate
from agents.validate import MEMO_SECTIONS
from engine import fmt, gate, model
from app.render import icon

esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
INJECTED = " Revenue reaches $61.2 million by FY2031."


def render(desk, deal, words, R):
    w, L = words, desk.ledger
    lab = words.table("labels.memo")
    run = desk.runs.get("memo_writer")
    chk = replay.check(run, L) if run else None
    usable = chk and chk["status"] in ("valid", "stale")
    out = replay.final(run) if usable else None
    mapping = chk["mapping"] if usable else {}
    head = (f"<div class=\"memo-head\"><p class=\"kicker\">{esc(w['memo.kicker'])}</p><h3>{esc(w['memo.title'])}</h3>")
    if out:
        run_id = run.get("input_sha256", "")[:8]
        head += f"<p class=\"draft-line\">{icon('spark')}<span>{R.fill('memo.draft', {'run': ('html', f'<code>{run_id}</code>')})}</span></p>"
    else:
        head += f"<p class=\"muted\">{esc(w['memo.invalid' if run else 'memo.missing'])}</p>"
    head += "</div>"
    texts = {}
    if out:
        for s in out["sections"]:
            texts[s["id"]] = [validate.to_ledger(p, mapping) for p in s["paragraphs"]]
    conditions = [validate.to_ledger(c, mapping) for c in out["conditions"]] if out else []
    pieces = [(f"section {i} paragraph {j}", p) for i, sid in enumerate(MEMO_SECTIONS, 1)
              for j, p in enumerate(texts.get(sid, []), 1)]
    allowed = {r for r in mapping.values() if r}
    figures = sum(len(gate.PLACEHOLDER.findall(p)) for _, p in pieces)
    gate_ok = gate.check(pieces, L, allowed)["passed"] if out else None
    clean = body(desk, deal, w, lab, R, texts, conditions)
    injected_html, fail_html = "", ""
    if out and texts.get("projections"):
        bad = dict(texts)
        bad["projections"] = list(texts["projections"])
        bad["projections"][0] = bad["projections"][0] + INJECTED
        loc = f"section {MEMO_SECTIONS.index('projections') + 1} paragraph 1"
        result = gate.check([(loc, bad["projections"][0])], L, allowed)
        token = result["failures"][0]["token"] if result["failures"] else ""
        injected_html = body(desk, deal, w, lab, R, bad, conditions, mark=token)
        section = MEMO_SECTIONS.index("projections") + 1
        params = {"token": ("html", f"<mark data-src=\"injected\">{esc(token)}</mark>"),
                  "n": ("html", f"<span data-src=\"gate\">{section}</span>")}
        fail_html = f"<div class=\"gate fail\" role=\"status\">{icon('x')}<p>{R.fill('memo.gate.fail', params)}</p></div>"
    gate_html = ""
    if out:
        state = "pass" if gate_ok else "fail"
        gate_html = (f"<div class=\"gate {state}\" role=\"status\" id=\"gate-pass\">{icon('check' if gate_ok else 'x')}<p>"
                     f"{R.fill('memo.gate.pass', {'n': ('html', f'<span data-src=\"gate\">{figures}</span>')})}</p></div>")
    controls = ""
    if injected_html:
        controls = (f"<div class=\"memo-controls\"><button type=\"button\" class=\"btn\" id=\"inject\">"
                    f"{esc(w['memo.inject'])}</button><button type=\"button\" class=\"btn\" id=\"uninject\" hidden>"
                    f"{esc(w['memo.remove'])}</button><span class=\"muted test-note\">{esc(w['memo.inject.note'])}</span>"
                    f"<span class=\"spacer\"></span><button type=\"button\" class=\"btn ghost\" id=\"print-memo\">"
                    f"{esc(w['memo.print'])}</button></div>")
    return (f"<section class=\"panel memo\" data-step=\"memo\" hidden>{head}{controls}{gate_html}"
            f"<div id=\"gate-fail\" hidden>{fail_html}</div><article class=\"memo-body\" id=\"memo-clean\">{clean}</article>"
            f"<article class=\"memo-body\" id=\"memo-injected\" hidden>{injected_html}</article></section>")


def body(desk, deal, w, lab, R, texts, conditions, mark=None):
    out = []
    for i, sid in enumerate(MEMO_SECTIONS, 1):
        paras = "".join(f"<p>{para(R, p, mark)}</p>" for p in texts.get(sid, []))
        extra = ""
        if sid == "recommendation" and conditions:
            extra = f"<h5>{esc(w['memo.conditions'])}</h5><ul>" + "".join(f"<li>{R.agent_text(c)}</li>" for c in conditions) + "</ul>"
        extra += table_for(sid, desk, deal, lab, R)
        out.append(f"<section class=\"memo-section\" id=\"memo-{sid}\"><h4><span data-src=\"section\">{i}</span>. "
                   f"{esc(w['memo.s.' + sid])}</h4>{paras}{extra}</section>")
    return "".join(out)


def para(R, text, mark):
    """A paragraph with its figures as trace links, and the injected figure marked when there is one."""
    rendered = R.agent_text(text)
    if mark:
        rendered = rendered.replace(esc(mark), f"<mark data-src=\"injected\">{esc(mark)}</mark>", 1)
    return rendered


def tbl(head, rows, cls=""):
    th = "".join(f"<th{' class=\"r\"' if i else ''}>{esc(h)}</th>" for i, h in enumerate(head))
    tb = "".join("<tr>" + "".join(f"<td{' class=\"r\"' if i else ''}>{c}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<div class=\"tablewrap\"><table class=\"memo-table {cls}\"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>"


def table_for(sid, desk, deal, lab, R):
    dm, r = desk.deal, deal.refs
    fys = ("FY2024", "FY2025", "FY2026")
    if sid == "historicals":
        rows = [[lab[f"hist.{x}"]] + [R.num(dm[f"rev_{x}_{fy}"]) for fy in fys] for x in model.LINES]
        rows += [[lab["hist.revenue"]] + [R.num(dm[f"revenue_{fy}"]) for fy in fys],
                 [lab["hist.gm"]] + [R.num(dm[f"gross_margin_{fy}"]) for fy in fys],
                 [lab["hist.reported"]] + [R.num(dm[f"reported_ebitda_{fy}"]) for fy in fys],
                 [lab["hist.adjusted"]] + [R.num(dm[f"adjusted_ebitda_{fy}"]) for fy in fys],
                 [lab["hist.adjusted_margin"]] + [R.num(dm[f"adjusted_margin_{fy}"]) for fy in fys]]
        return tbl([lab["col.line"]] + list(fys), rows)
    if sid == "adjustments":
        rows = [[lab["adj.reported"]] + [R.num(dm[f"reported_ebitda_{fy}"]) for fy in fys],
                [lab["adj.settlement"]] + [R.num(dm[f"settlement_{fy}"]) for fy in fys],
                [lab["adj.allocation"]] + [R.num(dm[f"allocation_{fy}"]) for fy in fys],
                [lab["adj.standalone"]] + [R.num(dm["standalone_year"]) for _ in fys],
                [lab["adj.adjusted"]] + [R.num(dm[f"adjusted_ebitda_{fy}"]) for fy in fys]]
        return tbl([lab["col.bridge"]] + list(fys), rows)
    if sid == "customers":
        rows = [[lab["cust.largest"], R.num(dm["largest_customer_FY2026"]), R.num(dm["largest_share_FY2026"])],
                [lab["cust.top10"], "", R.num(dm["top10_share_FY2026"])]]
        return tbl([lab["col.customers"], lab["col.revenue"], lab["col.share"]], rows)
    if sid == "projections":
        head = [lab["col.year"]] + list(model.FY)
        rows = [[lab["proj.revenue"], R.num(dm["revenue_FY2026"])] + [R.num(r[f"revenue_y{y}"]) for y in range(1, 6)],
                [lab["proj.ebitda"], R.num(dm["adjusted_ebitda_FY2026"])] + [R.num(r[f"ebitda_y{y}"]) for y in range(1, 6)]]
        return tbl(head, rows)
    if sid == "returns":
        rows = [[lab["ret.ev"], R.num(r["ev"])], [lab["ret.equity0"], R.num(r["equity0"])],
                [lab["ret.equity_exit"], R.num(r["equity_exit"])], [lab["ret.moic"], R.num(r["moic"])],
                [lab["ret.irr"], R.num(r["irr"])]]
        grid = [[f"<span data-src=\"grid\">{e:.1f}x</span>"] + [R.num(r[f"grid_moic_{i}{j}"]) for j in range(5)]
                for i, e in enumerate(model.GRID)]
        head = [lab["col.entry_exit"]] + [f"{x:.1f}x" for x in model.GRID]
        return tbl([lab["col.returns"], lab["col.value"]], rows) + \
            f"<p class=\"table-caption\">{esc(lab['ret.grid'])}</p>" + tbl(head, grid, "grid").replace(
                "<th class=\"r\">", "<th class=\"r\" data-src=\"grid\">")
    if sid == "debt":
        head = [lab["col.year"]] + list(model.FY[1:])
        rows = [[lab["debt.net_leverage"]] + [R.num(r[f"net_leverage_y{y}"]) for y in range(1, 6)],
                [lab["debt.headroom"]] + [R.num(r[f"lev_headroom_y{y}"]) for y in range(1, 6)]]
        return tbl(head, rows)
    if sid == "risks":
        rows = []
        for ref in desk.claims:
            c = desk.ledger.get(ref)
            if c["metric"]:
                rows.append([f"<span data-src=\"quote\">{esc(c['text'])}</span>", R.num(ref), R.num(c["params"]["ledger"])])
        return tbl([lab["col.claim"], lab["col.result"], lab["col.ledger"]], rows, "claims-table")
    return ""
