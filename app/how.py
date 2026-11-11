"""How it works: the architecture, what each agent may and may not do, the results read from files the tests, evals
and recordings wrote, and how the desk would roll out at a fund. No result on this tab is typed. Each one comes
from the test run, the frozen check runs, the recordings, the ledger's own counts, or the workbook's comparisons
with the Python model and with LibreOffice.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

from agents import replay, routing
from app import code_view, portfolio
from app.render import icon, keep_last_words
from deliverables.model_xlsx import parity_gaps
from engine import fmt, xlsx

HERE = Path(__file__).resolve().parent.parent
RECALC = HERE.joinpath("scripts", "out", "recalc", "Brightrow_model_formulas.xlsx")
esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
AGENTS = ("intake", "commentary", "deal", "memo", "deck")


def scored_hashes(record):
    """The detector hashes the last held-out score holds for: the one it was taken on, and the one after each rename
    of the invented names, which swapped words and left detection alone."""
    last = record["runs"][-1]
    return {last["detectors_sha256"]} | {r["detectors_sha256"] for r in record.get("renames", [])
                                          if r.get("run_version") == last.get("version")}


def fill(w, key, **params):
    """A WORDS.md sentence, escaped, with figures from the result files filled in."""
    return html.escape(w[key], quote=False).format(**params)


def m(text):
    """A figure from a test or eval file, marked as such for the lineage test."""
    return f"<span data-src=\"results\">{esc(text)}</span>"


def model_name(model_id):
    """claude-opus-5-5 reads as Claude Opus 5.5. Another vendor's model reads as its label in config/models.json,
    matched on the longest model name it starts with, since an API can answer with a dated snapshot of the name."""
    mid = re.sub(r"\[.*?\]$", "", model_id or "")
    parts = mid.split("-")
    if len(parts) >= 3 and parts[0] == "claude":
        names = [p.capitalize() for p in parts if not p.isdigit()]
        version = [p for p in parts if p.isdigit() and len(p) < 3]
        return " ".join(names) + (" " + ".".join(version) if version else "")
    labels = {e["model"]: e["label"] for e in routing.config().get("models", []) if e.get("model") and e.get("label")}
    best = max((k for k in labels if mid.startswith(k)), key=len, default=None)
    return labels[best] if best else model_id


def diagram(desk, w):
    """Sources, intake and checks, the ledger, the gate and the deliverables, left to right. It's HTML so it reflows
    into one column on a narrow screen."""
    def box(key, cls="", extra=""):
        mark = icon("spark") if "agentic" in cls else ""
        code = code_view.BOXES.get(key)
        link = f" data-code=\"{esc(code)}\" role=\"button\" tabindex=\"0\"" if code else ""
        return (f"<div class=\"abox {cls}\"{link}><div class=\"abox-t\">{mark}<span>{esc(w['how.d.' + key])}</span></div>"
                f"<p class=\"abox-s\">{esc(w['how.d.' + key + '.sub'])}</p>{extra}</div>")
    L = desk.ledger
    stats = fill(w, "how.d.ledger.stats", sources=m(f"{L.count('sources'):,}"), facts=m(f"{L.count('facts'):,}"),
                 derived=m(f"{L.count('derived'):,}"))
    arrow = ("<div class=\"aflow\" aria-hidden=\"true\"><svg viewBox=\"0 0 24 24\"><path d=\"M3 12h16M13 6l6 6-6 6\"/>"
             "</svg></div>")
    cols = [("src", box("files") + box("dataroom")),
            ("in", box("intake", "agentic") + box("checks")),
            ("core", box("ledger", "core", f"<p class=\"abox-n\">{stats}</p>")),
            ("gatecol", box("gate", "gatebox")),
            ("out", box("report", "agentic") + box("model", "agentic") + box("memo", "agentic") + box("deck", "agentic"))]
    acols = [f"<div class=\"acol {k}\">{inner}</div>" for k, inner in cols]
    # The two input columns share one grid so all four boxes take the tallest one's size and line up in two rows.
    flow = arrow.join([f"<div class=\"apair\">{acols[0]}{arrow}{acols[1]}</div>"] + acols[2:])
    return (f"<div class=\"arch\">{flow}</div>"
            f"<p class=\"arch-legend\">{icon('spark')}<span>{esc(w['how.d.legend'])}</span></p>")


def agents_table(w):
    head = "".join(f"<th>{esc(w['how.col.' + c])}</th>" for c in ("agent", "sees", "returns", "limits"))
    rows = []
    for a in AGENTS:
        cells = [f"<td class=\"who\"><strong>{icon('spark')}<span>{esc(w['how.a.' + a])}</span></strong></td>"]
        cells += [f"<td data-label=\"{esc(w['how.col.' + c])}\">{esc(w['how.a.' + a + '.' + c])}</td>"
                  for c in ("sees", "returns", "limits")]
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f"<div class=\"tablewrap\"><table class=\"agents roles\"><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>")


MORNING = ("intake_demo", "daily_commentary", "deal_analyst", "board_deck", "memo_writer")


def modes(desk, w):
    """How the AI steps came to be on this page: recorded once on real models, then replayed here at no cost. The cost
    is what the recorded calls reported, so it's read and never typed."""
    costs = [(a.get("meta") or {}).get("cost_usd") for t in MORNING for a in (desk.runs.get(t) or {}).get("attempts", [])]
    have = all(t in desk.runs for t in MORNING) and costs and all(c is not None for c in costs)
    cost = f"<p class=\"mode-cost\">{fill(w, 'how.mode.recorded.cost', cost=m(f'${sum(costs):.2f}'))}</p>" if have else ""
    return (f"<div class=\"modes\"><div class=\"mode live\"><h4>{icon('spark')}<span>"
            f"{esc(w['how.mode.recorded.title'])}</span></h4><p>{esc(w['how.mode.recorded.text'])}</p>{cost}</div>"
            f"<div class=\"mode\"><h4>{icon('reset')}<span>{esc(w['how.mode.replay.title'])}</span></h4>"
            f"<p>{esc(w['how.mode.replay.text'])}</p></div></div>")


def libreoffice(book):
    """How many formulas LibreOffice recalculated and matched, once the recalc check has run on this build."""
    if not RECALC.exists():
        return None
    checked, bad = book.against(xlsx.read(RECALC.read_bytes()))
    return None if bad else checked


def results(desk, book, w):
    tiles, notes = [], []

    def tile(key, value, foot):
        tiles.append(f"<div class=\"tile proof\"><div class=\"tile-label\">{esc(w[key])}</div>"
                     f"<div class=\"tile-value\">{value}</div><p class=\"tile-foot\">{foot}</p></div>")

    def of(a, b):
        return fill(w, "how.k.of", a=m(a), b=m(b))

    runs = HERE.joinpath("evals", "check_runs.json")
    if runs.exists():
        last = json.loads(runs.read_text())["runs"][-1]
        tot = last["total"]
        tile("how.k.caught", of(tot["caught"], tot["planted"]),
             fill(w, "how.k.caught.foot", seeds=m(fmt.items(str(s) for s in last["held_out_seeds"]))))
        tile("how.k.alarms", m(tot["false_alarms"]), esc(w["how.k.alarms.foot"]))
        tile("how.k.lookalikes", of(tot["lookalikes_left_alone"], tot["lookalikes"]), esc(w["how.k.lookalikes.foot"]))
        from evals.freeze_checks import detectors_sha256
        if detectors_sha256() not in scored_hashes(json.loads(runs.read_text())):
            notes.append(esc(w["how.r.checks_stale"]))
    ev = portfolio.intake_view(desk)["eval"]
    if ev["recorded"]:
        foot = (fill(w, "how.k.intake.equivalent", wrong=m(ev["wrong"])) if ev["wrong"] and not ev["harmful"]
                else esc(w["how.k.intake.foot"]))
        tile("how.k.intake", of(ev["exact"], ev["recorded"]), foot)
    tr = HERE.joinpath("data", "test_results.json")
    if tr.exists():
        t = json.loads(tr.read_text())
        when = m(fmt.day_label(t["finished"][:10]))
        foot = (fill(w, "how.k.tests.skipped", when=when, skipped=m(t["skipped"])) if t.get("skipped")
                else fill(w, "how.k.tests.foot", when=when))
        tile("how.k.tests", of(f"{t['passed']:,}", f"{t['ran']:,}"), foot)
    n, off = parity_gaps(book)
    if not off:
        tile("how.k.model", fill(w, "how.k.model.value", n=m(n)), esc(w["how.k.model.foot"]))
    lo = libreoffice(book)
    if lo:
        tile("how.k.lo", fill(w, "how.k.lo.value", n=m(f"{lo:,}")), esc(w["how.k.lo.foot"]))
    valid = [r for r in desk.runs.values() if (r.get("final") or {}).get("valid")]
    days = sorted({fmt.local_date(r.get("recorded_at", "")) for r in valid} - {""})
    if days:
        models = sorted({model_name(x) for r in valid for x in (r.get("model") or "").split(", ") if x})
        tile("how.k.recorded", m(len(valid)), recorded_foot(w, fmt.items(models), days[0], days[-1]))
    return tiles, notes


def recorded_foot(w, models, first, last):
    """Which models the recorded runs used and the days they ran. One day reads as October 29, and a span reads as
    October 27 to 29 with its last three words kept on one line."""
    if first == last:
        return fill(w, "how.k.recorded.foot", model=m(models), when=m(fmt.day_label(last)))
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    end = str(b.day) if (a.year, a.month) == (b.year, b.month) else fmt.day_label(last)
    return keep_last_words(fill(w, "how.k.recorded.span", model=m(models), first=m(fmt.day_label(first)), last=m(end)))


def plain_results(desk, book, w):
    """The same results as a Markdown table for the README, so the README and the page can't disagree."""
    tiles, notes = results(desk, book, w)
    plain = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\u00a0", " ").strip()  # noqa: E731
    rows = []
    for t in tiles:
        label, value, foot = (plain(x) for x in re.findall(r"class=\"tile-(?:label|value|foot)\">(.*?)</(?:div|p)>", t))
        rows.append(f"| {label} | {value} | {foot} |")
    return ("| Result | Value | Detail |\n|---|---|---|\n" + "\n".join(rows) + "\n"
            + "".join(f"\n{plain(n)}\n" for n in notes))


def plan(w):
    steps = "".join(f"<li><span class=\"plan-dot\" aria-hidden=\"true\"></span><h4>{esc(w['how.p.' + k + '.title'])}</h4>"
                    f"<p>{esc(w['how.p.' + k])}</p></li>" for k in ("30", "60", "90"))
    return f"<ol class=\"plan-line\">{steps}</ol>"


def render(desk, book, w, code="", routes=""):
    tiles, notes = results(desk, book, w)
    notes_html = "".join(f"<p class=\"muted note-small\">{n}</p>" for n in notes)
    return (f"<div class=\"page-head\"><h2>{esc(w['how.title'])}</h2><p>{esc(w['how.text'])}</p></div>"
            f"<section class=\"panel\"><h3>{esc(w['how.arch'])}</h3>{diagram(desk, w)}</section>"
            f"<section class=\"panel\"><h3>{esc(w['how.agents'])}</h3><p>{esc(w['how.agents.text'])}</p>"
            f"{agents_table(w)}{modes(desk, w)}</section>{routes}{code}"
            f"<section class=\"panel\" id=\"how-results\"><h3>{esc(w['how.results'])}</h3><p class=\"muted\">{esc(w['how.results.text'])}</p>"
            f"<div class=\"tiles proofs\">{''.join(tiles)}</div>{notes_html}</section>"
            f"<section class=\"panel plan\" id=\"how-plan\"><h3>{esc(w['how.plan'])}</h3>{plan(w)}</section>")
