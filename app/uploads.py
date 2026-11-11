"""The Upload panel. Anyone can pick one of the twelve freight layouts the intake agent had never seen and see what it
did with each, from the recorded eval runs. No file leaves the page and no model is called.

check_file gives each file the same checks a morning's freight file gets. The file's own dates say which day it
covers, and its revenue has to tie to that day's invoicing batch in the ledger.
"""
import html
from collections import Counter

from agents import replay, validate
from app import portfolio
from app.render import STATUS_ICON, icon
from engine import checks, fmt, intake

DEFAULT = "V03"
esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def check_file(sheet, mapping, ledger):
    """Apply a mapping to one freight export and run the morning's checks on it."""
    rows, totals, problems = intake.apply_mapping(sheet, mapping, None)
    days = Counter(r["date"] for r in rows if r.get("date"))
    ops = days.most_common(1)[0][0] if days else None
    count_ref = ledger.find("F", "kiskadee", "invoice_count", ops) if ops else None
    total_ref = ledger.find("F", "kiskadee", "invoiced", ops) if ops else None
    if problems or not count_ref or not total_ref:
        reasons = [p[1] for p in problems] or ["no invoicing batch in the ledger for that day to tie the file to"]
        return {"ops": ops, "results": [], "accepted": False, "reasons": reasons, "revenue": None, "invoiced": None}
    invoiced = ledger.value(total_ref)
    results = checks.tms_results(rows, totals, mapping, ops, ledger.value(count_ref), invoiced)
    ok, reasons = checks.tms_accepts(results, problems)
    revenue = sum(r["linehaul_rev"] + r["fuel_surcharge"] + r["accessorials"] for r in rows)
    return {"ops": ops, "results": [[r["rule"], r["status"]] for r in results], "accepted": ok, "reasons": reasons,
            "revenue": revenue, "invoiced": invoiced, "loads": len(rows)}


def header_of(sheet, header_rows=1):
    cells = intake.header_texts(sheet, header_rows)
    while cells and not cells[-1]:
        cells.pop()
    return cells


def eval_views(desk):
    """What the intake agent did with each of the twelve held-out layouts, from the recorded eval runs."""
    out = []
    for task in replay.INTAKE_EVAL:
        run = desk.runs.get(task)
        if not run:
            continue
        path = desk.intake_path(task)
        sheet = intake.tms_sheet(desk.files[path])
        parsed = replay.final(run)
        view = {"id": task.split("_", 1)[1], "file": path.split("/")[-1], "recorded_at": run.get("recorded_at"),
                "model": run.get("model"), "seconds": run.get("seconds")}
        if parsed is None:
            view.update(header=header_of(sheet), mapping=[], check=None, accepted=False,
                        reasons=(run.get("final") or {}).get("problems", []))
        else:
            mapping = validate.mapping_of(parsed)
            chk = check_file(sheet, mapping, desk.ledger)
            exact = bool((run.get("intake") or {}).get("exact_match"))
            view.update(header=header_of(sheet, mapping["header_rows"]), mapping=mapping["columns"], check=chk,
                        accepted=chk["accepted"], reasons=chk["reasons"], exact=exact,
                        same_rows=exact or portfolio.same_rows(desk, run))
        out.append(view)
    return out


def money(cents):
    return f"<span class=\"num meta\" data-src=\"upload\">{esc(fmt.value('cents', cents))}</span>"


def tag(view, w):
    if not view.get("accepted"):
        return f"<span class=\"tag held\">{esc(w['upload.tag.held'])}</span>"
    key = "upload.tag.exact" if view.get("exact") else "upload.tag.same" if view.get("same_rows") else "upload.tag.differs"
    return f"<span class=\"tag changed\">{esc(w[key])}</span>"


def chip(view, w):
    first = " · ".join(view["header"][:3])
    return (f"<button type=\"button\" class=\"uchip\" data-upload=\"{esc(view['id'])}\" aria-pressed=\"false\">"
            f"<code>{esc(view['id'])}</code><span class=\"uchip-h\" data-src=\"quote\">{esc(first)}</span>{tag(view, w)}"
            f"</button>")


def detail(view, w):
    chk = view.get("check") or {}
    rows = "".join(f"<tr><td data-src=\"quote\">{esc(h)}</td><td>"
                   f"{'<code>' + esc(f) + '</code>' if f else '<code class=muted>null</code>'}</td></tr>"
                   for h, f in view.get("mapping") or [])
    mapping = (f"<div><h4>{esc(w['upload.mapping'])}</h4>"
               f"<p class=\"ufile\"><code>{esc(view['file'])}</code></p><table class=\"map\"><thead><tr><th>"
               f"{esc(w['upload.col.file'])}</th><th>{esc(w['upload.col.field'])}</th></tr></thead><tbody>{rows}</tbody>"
               f"</table></div>") if rows else f"<div><p class=\"ufile\"><code>{esc(view['file'])}</code></p></div>"
    items = "".join(f"<li class=\"note s-{st}\">{icon(STATUS_ICON[st])}<span>{esc(w['vcheck.' + rule])}</span></li>"
                    for rule, st in chk.get("results") or [])
    tie = (f"<p class=\"tie\">{money(chk['revenue'])} = {money(chk['invoiced'])}</p>"
           if chk.get("revenue") is not None and chk.get("accepted") else "")
    if view.get("accepted"):
        result = f"<p class=\"result ok\">{icon('check')}{esc(w['upload.accepted'])}</p>"
    else:
        reasons = [w.get("upload.reason." + r, r) for r in view.get("reasons") or []] or [w["upload.reason.control_total"]]
        result = f"<p class=\"result held\">{icon('alert')}{esc(w.fill('upload.held', reasons=fmt.items(reasons)))}</p>"
    key = ""
    if view.get("mapping"):
        key = ("upload.exact" if view.get("exact") else "upload.same" if view.get("same_rows") else "upload.differs")
        key = f"<p class=\"eval\">{esc(w[key])}</p>"
    when = fmt.day_label(fmt.local_date(view["recorded_at"])) if view.get("recorded_at") else ""
    secs = f"<span data-src=\"upload\">{esc(round(view['seconds']))}</span>" if view.get("seconds") else ""
    model = f"<span data-src=\"upload\">{esc(model_label(view.get('model')))}</span>"
    how = html.escape(w["upload.how.recorded"], quote=False).format(model=model, when=esc(when), seconds=secs)
    return (f"<div class=\"udetail\" data-upload-detail=\"{esc(view['id'])}\" hidden><div class=\"intake-grid\">{mapping}"
            f"<div><h4>{esc(w['intake.checks'])}</h4><ul class=\"notes\">{items}</ul>{tie}{result}{key}"
            f"<p class=\"ai-label\">{icon('spark')}<span>{how}</span></p></div></div></div>")


def model_label(model_id):
    from app.how import model_name
    return model_name(model_id or "") or ""


def render(desk, w):
    evals = eval_views(desk)
    picker = (f"<h4>{esc(w['upload.layouts'])}</h4><p class=\"muted\">{esc(w['upload.demo'])}</p>"
              f"<div class=\"upick\">{''.join(chip(v, w) for v in evals)}</div>") if evals else \
        f"<p class=\"muted\">{esc(w['upload.none'])}</p>"
    default = DEFAULT if any(v["id"] == DEFAULT for v in evals) else (evals[0]["id"] if evals else "")
    details = "".join(detail(v, w) for v in evals)
    return (f"<section class=\"panel upload\" id=\"upload-panel\" data-default=\"{esc(default)}\" hidden "
            f"aria-label=\"{esc(w['upload.title'])}\"><div class=\"panel-head\"><h3>{esc(w['upload.title'])}</h3>"
            f"<button type=\"button\" class=\"btn ghost\" id=\"upload-close\">{esc(w['upload.close'])}</button></div>"
            f"<p>{esc(w['upload.text'])}</p>{picker}{details}</section>")
