"""The hours ledger: each workflow's runs this week, its measured run time, the manual baseline, the review a person
still gives it, and the hours that came back.

Run times are measured: the morning runs from the pipeline's own clock and the agent steps from the CLI's report in
the recordings. Baselines and review times are estimates from config/hours.json, labeled as estimates, and the
page lets anyone change them and recalculates. Hours back is runs times the baseline less review and run time.
"""
import html
import json
from datetime import timedelta
from pathlib import Path

from generate import common as C

HERE = Path(__file__).resolve().parent.parent
CONFIG = HERE.joinpath("config", "hours.json")
DEMO = C.DEMO.isoformat()
WEEK = tuple((C.DEMO - timedelta(days=i)).isoformat() for i in range(C.DEMO.weekday(), -1, -1))   # Monday to the demo
AGENT_TASK = {"daily_report": "daily_commentary", "intake": "intake_demo", "deal_model": "deal_analyst",
              "memo": "memo_writer", "deck": "board_deck"}
esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def rows(desk, model_seconds):
    cfg = json.loads(CONFIG.read_text())["workflows"]
    runs = {r["morning"]: r for r in desk.clean["runs"]}
    pipeline = [runs[m]["seconds"] for m in WEEK if m in runs]
    out = []
    for item in cfg:
        key = item["key"]
        rec = desk.runs.get(AGENT_TASK[key]) or {}
        valid = bool((rec.get("final") or {}).get("valid"))
        agent_s = float(rec.get("seconds") or 0) if valid else 0.0
        if key == "daily_report":
            count = len(pipeline)
            seconds = (sum(pipeline) / count if count else 0) + agent_s
        elif key == "intake":
            count = 1 if (desk.clean["tms_status"].get(DEMO) or {}).get("via") == "agent" else 0
            seconds = agent_s
        elif key == "deal_model":
            count, seconds = 1, agent_s + model_seconds
        else:
            count, seconds = (1 if valid else 0), agent_s
        out.append({"key": key, "runs": count, "seconds": round(seconds, 1), "baseline": item["baseline_hours"],
                    "review": item["review_minutes"]})
    return out


def back(r):
    return r["runs"] * max(0.0, r["baseline"] - r["review"] / 60 - r["seconds"] / 3600)


def today(rows_):
    """Hours back from this morning's run alone: one daily report, and the intake of the changed layout."""
    return sum(max(0.0, r["baseline"] - r["review"] / 60 - r["seconds"] / 3600) for r in rows_
               if r["key"] in ("daily_report", "intake") and r["runs"])


def manual(r):
    return r["runs"] * r["baseline"]


def automated(r):
    return r["runs"] * (r["review"] / 60 + r["seconds"] / 3600)


def totals(rows_):
    return {"week": sum(back(r) for r in rows_), "today": today(rows_), "manual": sum(manual(r) for r in rows_),
            "review": sum(r["runs"] * r["review"] / 60 for r in rows_)}


def out(value, name):
    """A figure the page recalculates when an estimate changes, marked for the lineage test."""
    return f"<span data-src=\"hours\" data-out=\"{name}\">{value:.1f}</span>"


def render(rows_, words):
    w, t = words, totals(rows_)
    tiles = "".join(f"<div class=\"tile{' lead' if k == 'week' else ''}\"><div class=\"tile-label\">{esc(w['hours.k.' + k])}</div>"
                    f"<div class=\"tile-value\">{out(t[k], k)}</div><p class=\"tile-foot\">{esc(w['hours.k.' + k + '.foot'])}</p>"
                    f"</div>" for k in ("week", "today", "manual", "review"))
    body = []
    # Each cell carries its column's name, so on a phone the table can read as one labeled card per workflow (app.css).
    lab = {k: f" data-label=\"{esc(w['hours.col.' + k])}\"" for k in ("runs", "measured", "baseline", "review", "back")}
    for r in rows_:
        body.append(f"<tr data-row=\"{r['key']}\" data-runs=\"{r['runs']}\" data-seconds=\"{r['seconds']}\">"
                    f"<td>{esc(w['hours.wf.' + r['key']])}</td><td class=\"r\"{lab['runs']}><span data-src=\"runlog\">{r['runs']}</span></td>"
                    f"<td class=\"r\"{lab['measured']}>{measured(r, w)}</td>"
                    f"<td class=\"r\"{lab['baseline']}><input type=\"number\" autocomplete=\"off\" min=\"0\" max=\"80\" step=\"0.5\" value=\"{r['baseline']}\" "
                    f"aria-label=\"{esc(w['hours.wf.' + r['key']] + ', ' + w['hours.col.baseline'])}\" data-k=\"baseline\"></td>"
                    f"<td class=\"r\"{lab['review']}><input type=\"number\" autocomplete=\"off\" min=\"0\" max=\"600\" step=\"5\" value=\"{r['review']}\" "
                    f"aria-label=\"{esc(w['hours.wf.' + r['key']] + ', ' + w['hours.col.review'])}\" data-k=\"review\"></td>"
                    f"<td class=\"r\"{lab['back']}><strong>{out(back(r), 'back')}</strong></td></tr>")
    cols = "".join(f"<th{' class=\"r\"' if k != 'workflow' else ''}>{esc(w['hours.col.' + k])}</th>"
                   for k in ("workflow", "runs", "measured", "baseline", "review", "back"))
    top = max([manual(r) for r in rows_] + [automated(r) for r in rows_] + [1e-9])
    bars = []
    for r in rows_:
        pair = "".join(f"<div class=\"hline\"><span class=\"hb {k}\" data-out=\"bar-{k}\" data-tip=\"{esc(tip(w, k, v))}\" "
                       f"style=\"width:{v / top * 100:.1f}%\"></span></div>"
                       for k, v in (("manual", manual(r)), ("auto", automated(r))))
        label = esc(w["hours.row.back"]).replace("{h}", out(back(r), "back-row"))
        bars.append(f"<div class=\"hrow\" data-bar=\"{r['key']}\"><div class=\"hl\">{esc(w['hours.wf.' + r['key']])}</div>"
                    f"<div class=\"hpair\">{pair}</div><div class=\"hback\">{label}</div></div>")
    return (f"<div class=\"page-head\"><h2>{esc(w['hours.title'])}</h2><p>{esc(w['hours.text'])}</p></div>"
            f"<div class=\"tiles hours-tiles\">{tiles}</div>"
            f"<section class=\"panel\"><div class=\"tablewrap\"><table class=\"hours\"><thead><tr>{cols}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody><tfoot><tr><td colspan=\"5\">{esc(w['hours.total'])}</td>"
            f"<td class=\"r\"><strong>{out(t['week'], 'total')}</strong></td></tr></tfoot></table></div>"
            f"<p class=\"muted note-small\">{esc(w['hours.note'])}</p></section><section class=\"panel\"><h3>"
            f"{esc(w['hours.chart'])}</h3><div class=\"hbars\">{''.join(bars)}</div><ul class=\"legend\"><li><span class=\"sw manual\">"
            f"</span>{esc(w['hours.legend.manual'])}</li><li><span class=\"sw auto\"></span>{esc(w['hours.legend.auto'])}</li>"
            f"</ul><p class=\"chart-summary\">{esc(w['hours.chart.summary'])}</p></section>")


def tip(w, kind, hours_):
    """The hover text on a bar, which the page rewrites when an estimate changes."""
    return w["hours.legend." + kind] + " " + w["hours.unit"].replace("{h}", f"{hours_:.1f}")


def measured(r, w):
    """The measured run time, or a plain note when the workflow hasn't been recorded yet."""
    if not r["runs"]:
        return f"<span class=\"muted\">{esc(w['hours.time.none'])}</span>"
    return f"<span data-src=\"runlog\">{esc(run_time(r['seconds'], w))}</span>"


def run_time(seconds, w):
    if seconds < 1:
        return w["hours.time.under"]
    if seconds < 120:
        return w.fill("hours.time.seconds", n=f"{seconds:.0f}")
    return w.fill("hours.time.minutes", n=f"{seconds / 60:.1f}")
