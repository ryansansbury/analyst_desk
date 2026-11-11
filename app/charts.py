"""Charts in HTML and CSS, with lines as a stretchable SVG.

Text is always HTML, so labels keep their size on a shared screen. Bars size by percentage, colors are CSS
variables, and every mark carries data-tip for the hover layer. Figures shown on a chart come from the caller as
trace links, so a chart never shows a number the ledger can't trace. Each chart can carry a table view.
"""
import html
import math

SERIES = ["var(--s1)", "var(--s2)", "var(--s3)"]


def esc(s):
    return html.escape(str(s), quote=True)


def nice_ticks(lo, hi, count=4):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.001:
        ticks.append(round(t, 10))
        t += step
    if ticks[-1] < hi:
        ticks.append(round(ticks[-1] + step, 10))
    return ticks


def pct(v, hi):
    return f"{max(0.0, min(100.0, v / hi * 100 if hi else 0)):.2f}%"


def sparkline(values, width=120, height=30, label=""):
    """A small line with the latest day as a dot in the accent. No figures, so nothing here needs a trace."""
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    hi = hi if hi > lo else lo + 1
    step = (width - 8) / (len(values) - 1)
    coords = [(4 + i * step, height - 4 - (v - lo) / (hi - lo) * (height - 8)) for i, v in pts]
    path = "M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in coords)
    x, y = coords[-1]
    return (f"<svg class=\"spark\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\" role=\"img\" "
            f"aria-label=\"{esc(label)}\"><path d=\"{path}\" fill=\"none\" stroke=\"var(--spark)\" stroke-width=\"1.5\" "
            f"stroke-linejoin=\"round\" stroke-linecap=\"round\"/><circle cx=\"{x:.1f}\" cy=\"{y:.1f}\" r=\"3\" "
            f"fill=\"var(--accent)\"/></svg>")


def table(caption, headers, rows):
    """rows hold HTML already, so a figure in a table can be a trace link."""
    right = " class=\"r\""
    head = "".join(f"<th scope=\"col\"{right if i else ''}>{esc(h)}</th>" for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f"<td{right if i else ''}>{c}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows)
    return (f"<details class=\"tableview\"><summary>Table view</summary><div class=\"tablewrap\"><table><caption>"
            f"{esc(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>")


def figure(inner, title, summary, table_html="", cls=""):
    head = f"<figcaption class=\"chart-title\">{esc(title)}</figcaption>" if title else ""
    summ = f"<p class=\"chart-summary\">{summary}</p>" if summary else ""
    return f"<figure class=\"chart {cls}\">{head}{inner}{summ}{table_html}</figure>"


def bars(items, title, summary="", table_html=""):
    """Horizontal bars. items: (label, value, shown HTML, tip, css class)."""
    hi = max([abs(v) for _, v, _, _, _ in items] + [1])
    rows = "".join(f"<div class=\"hb {c}\" data-tip=\"{esc(tip)}\" tabindex=\"0\"><span class=\"l\">{esc(lbl)}</span>"
                   f"<span class=\"t\"><span class=\"b\" style=\"width:{pct(abs(v), hi)}\"></span></span>"
                   f"<span class=\"v\">{shown}</span></div>" for lbl, v, shown, tip, c in items)
    return figure(f"<div class=\"hbars\">{rows}</div>", title, summary, table_html, "hb")


def waterfall(steps, title, summary="", table_html=""):
    """A bridge from one total to another. steps: (label, value, shown HTML, kind) with kind total or step."""
    running, spans = 0.0, []
    for lbl, v, shown, kind in steps:
        if kind == "total":
            spans.append((lbl, 0.0, v, shown, kind))
            running = v
        else:
            spans.append((lbl, running, running + v, shown, "up" if v >= 0 else "down"))
            running += v
    lo = min(min(a, b) for _, a, b, _, _ in spans)
    hi = max(max(a, b) for _, a, b, _, _ in spans)
    lo = min(lo, 0.0)
    span = (hi - lo) or 1
    cols = ""
    for lbl, a, b, shown, kind in spans:
        bottom = (min(a, b) - lo) / span * 100
        height = max(abs(b - a) / span * 100, 0.8)
        cols += (f"<div class=\"wf-col {kind}\" data-tip=\"{esc(lbl)}\" tabindex=\"0\"><div class=\"wf-plot\">"
                 f"<span class=\"wf-bar\" style=\"bottom:{bottom:.2f}%;height:{height:.2f}%\"></span></div>"
                 f"<div class=\"wf-v\">{shown}</div><div class=\"wf-l\">{esc(lbl)}</div></div>")
    return figure(f"<div class=\"waterfall\" style=\"--n:{len(spans)}\">{cols}</div>", title, summary, table_html, "wf")


def columns(points, title, summary="", fmt_tip=None, table_html="", highlight_last=False):
    """Vertical columns over time. points: (label, value). Tips name the period, and the value is in the table view."""
    hi = max([v for _, v in points if v is not None] + [1])
    ticks = nice_ticks(0, hi)
    top = ticks[-1]
    cols = "".join(f"<div class=\"cc{' last' if highlight_last and i == len(points) - 1 else ''}\" "
                   f"data-tip=\"{esc(lbl)}{(': ' + esc(fmt_tip(v))) if fmt_tip and v is not None else ''}\" tabindex=\"0\">"
                   f"<span class=\"b\" style=\"height:{pct(v or 0, top)}\"></span></div>" for i, (lbl, v) in enumerate(points))
    labels = "".join(f"<span>{esc(lbl)}</span>" for lbl, _ in points)
    inner = (f"<div class=\"cols-chart\" style=\"--n:{len(points)}\"><div class=\"plot\">{cols}</div>"
             f"<div class=\"xaxis\">{labels}</div></div>")
    return figure(inner, title, summary, table_html, "cols")


def pair_columns(points, names, title, summary="", fmt_tip=None, table_html=""):
    """Two series side by side for each period, like invoiced against collected. points: (label, a, b)."""
    hi = max([max(a or 0, b or 0) for _, a, b in points] + [1])
    top = nice_ticks(0, hi)[-1]
    cols = "".join(f"<div class=\"pc\"><span class=\"b s1\" style=\"height:{pct(a or 0, top)}\" "
                   f"data-tip=\"{esc(lbl)} {esc(names[0])}{(': ' + esc(fmt_tip(a))) if fmt_tip else ''}\" tabindex=\"0\">"
                   f"</span><span class=\"b s2\" style=\"height:{pct(b or 0, top)}\" "
                   f"data-tip=\"{esc(lbl)} {esc(names[1])}{(': ' + esc(fmt_tip(b))) if fmt_tip else ''}\" tabindex=\"0\">"
                   f"</span></div>" for lbl, a, b in points)
    labels = "".join(f"<span>{esc(lbl)}</span>" for lbl, _, _ in points)
    legend = (f"<ul class=\"legend\"><li><span class=\"sw s1\"></span>{esc(names[0])}</li>"
              f"<li><span class=\"sw s2\"></span>{esc(names[1])}</li></ul>")
    inner = (f"<div class=\"pair-chart\" style=\"--n:{len(points)}\"><div class=\"plot\">{cols}</div>"
             f"<div class=\"xaxis\">{labels}</div>{legend}</div>")
    return figure(inner, title, summary, table_html, "pair")


def log_ticks(a, b):
    """Ticks for a log axis from 10**a to 10**b, as (value, minor). Whole decades, plus the 2 and 5 steps as minor
    ticks when fewer than three decades fit. With barely a decade in view every tick is labeled as a major one."""
    found = [(d * 10.0 ** e, d != 1) for e in range(math.floor(a), math.ceil(b) + 1) for d in (1, 2, 5)
             if a <= math.log10(d * 10.0 ** e) <= b]
    majors = [t for t in found if not t[1]]
    if len(majors) >= 3:
        return majors
    return found if len(majors) == 2 else [(v, False) for v, _ in found]


def scatter(points, xticks, yticks, title, axes, summary="", legend="", table_html="", line=None):
    """Points on two axes, each directly labeled. points: (id, left %, bottom %, series class, label HTML, tip,
    ringed), in the order their labels should claim space. Ticks: (position %, label HTML, minor), and a minor
    tick's label gives way on a narrow screen. axes: (y title, x title). line: (bottom %, label) for a reference
    line. The script places each label beside its dot where it fits, and the CSS puts it to the right until then."""
    grid = "".join(f"<span class=\"sc-grid h\" style=\"bottom:{p:.2f}%\"></span>" for p, _, _ in yticks)
    grid += "".join(f"<span class=\"sc-grid v\" style=\"left:{p:.2f}%\"></span>" for p, _, _ in xticks)
    ref = (f"<div class=\"sc-line\" style=\"bottom:{line[0]:.2f}%\"><span>{esc(line[1])}</span></div>" if line else "")
    dots = "".join(f"<span class=\"sc-pt {cls}{' on' if on else ''}\" data-id=\"{esc(pid)}\" style=\"left:{x:.2f}%;"
                   f"bottom:{y:.2f}%\" data-tip=\"{esc(tip)}\" tabindex=\"0\"></span>"
                   for pid, x, y, cls, _, tip, on in points)
    labels = "".join(f"<span class=\"sc-lbl{' on' if on else ''}\" data-for=\"{esc(pid)}\" style=\"left:{x:.2f}%;"
                     f"bottom:{y:.2f}%\">{lbl}</span>" for pid, x, y, _, lbl, _, on in points)
    ys = "".join(f"<span style=\"bottom:{p:.2f}%\">{t}</span>" for p, t, _ in yticks)
    xs = "".join(f"<span class=\"{'minor' if minor else 'major'}\" style=\"left:{p:.2f}%\">{t}</span>"
                 for p, t, minor in xticks)
    inner = (f"<div class=\"scatter\"><p class=\"sc-yt\">{esc(axes[0])}</p><div class=\"sc-body\"><div class=\"sc-y\">"
             f"{ys}</div><div class=\"sc-plot\">{grid}{ref}{dots}{labels}</div></div><div class=\"sc-x\">{xs}</div>"
             f"<p class=\"sc-xt\">{esc(axes[1])}</p></div>{legend}")
    return figure(inner, title, summary, table_html, "sc")


def line(values, labels, title, summary="", table_html=""):
    """One series as a stretchable line with its last point marked."""
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    pad = (hi - lo) * 0.15 or abs(hi) * 0.05 or 1
    lo, hi = lo - pad, hi + pad
    n = len(values)
    X = lambda i: i / (n - 1) * 100  # noqa: E731
    Y = lambda v: (hi - v) / (hi - lo) * 100  # noqa: E731
    path = "M" + " L".join(f"{X(i):.2f},{Y(v):.2f}" for i, v in pts)
    i, v = pts[-1]
    inner = (f"<div class=\"trend\"><svg viewBox=\"0 0 100 100\" preserveAspectRatio=\"none\" aria-hidden=\"true\">"
             f"<path class=\"stroke\" d=\"{path}\" vector-effect=\"non-scaling-stroke\"/></svg>"
             f"<span class=\"tdot\" style=\"left:{X(i):.2f}%;top:{Y(v):.2f}%\"></span></div>"
             f"<div class=\"trend-x\"><span>{esc(labels[0])}</span><span>{esc(labels[-1])}</span></div>")
    return figure(inner, title, summary, table_html, "ln")
