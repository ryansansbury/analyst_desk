"""HTML for the page, rendered by the build. Every figure is a button that opens its trace, every status has an icon
and a word, and every word comes from WORDS.md.

A ref made after the shared history (this morning's facts, the report's values) is qualified by its state, like
E1:D7701, since each state has its own copy of the ledger. Refs from the history are shared and stay bare.
"""
import html
import re

from app import charts
from engine import fmt, gate

esc = charts.esc
GLUE = re.compile(r"(<(button|span)\b[^>]*\bclass=\"num\b[^\"]*\"[^>]*>[^<]*</\2>)([.,;:!?)\]]+)")


def glue(markup):
    """A figure and the punctuation right after it stay on one line. A figure is a button, and a browser may break a
    line after a button, which once left a sentence's period at the start of the next line."""
    return GLUE.sub(r'<span class="nw">\1\3</span>', markup)


TERMS = re.compile(r"\b(?:days sales outstanding|on[- ]time delivery|empty miles share|empty miles|revenue per load|"
                   r"gross margin|EBITDA estimate)\b", re.IGNORECASE)


def keep_terms(markup):
    """A metric's name never splits across two lines. A slide's agent-written headline can't be rephrased, so this is
    what keeps its last line from holding only the tail of a name, like "sales outstanding." Only text between tags
    changes."""
    parts = re.split(r"(<[^>]+>)", markup)
    return "".join(p if i % 2 else TERMS.sub(lambda m: f"<span class=\"nw\">{m.group(0)}</span>", p)
                   for i, p in enumerate(parts))


def keep_last_words(markup, n=3):
    """An agent-written paragraph never ends on one or two words alone. Its last n words wrap as one, so the text stays
    exactly as validated and only the places a line may break change. Only spaces between tags change."""
    parts = re.split(r"(<[^>]+>)", markup)
    left, seen = n - 1, False
    for i in range(len(parts) - 1, -1, -1):
        if not left:
            break
        if i % 2:
            continue
        chars = list(parts[i])
        for j in range(len(chars) - 1, -1, -1):
            if chars[j] != " ":
                seen = True
            elif seen:
                chars[j] = "\u00a0"
                left -= 1
                if not left:
                    break
        parts[i] = "".join(chars)
    return "".join(parts)


ICONS = {
    "check": "<path d=\"M3 8.5l3 3 7-7\"/>",
    "alert": "<path d=\"M8 2l6.5 11.5h-13z\"/><path d=\"M8 6.5v3.2M8 11.6v.2\"/>",
    "x": "<path d=\"M4 4l8 8M12 4l-8 8\"/>",
    "info": "<circle cx=\"8\" cy=\"8\" r=\"6\"/><path d=\"M8 7.2v4M8 5v.2\"/>",
    "play": "<path d=\"M5 3.5l7 4.5-7 4.5z\" fill=\"currentColor\" stroke=\"none\"/>",
    "reset": "<path d=\"M3.5 8a4.5 4.5 0 1 0 1.3-3.2\"/><path d=\"M3.5 2.8v2.4h2.4\"/>",
    "down": "<path d=\"M4 6l4 4 4-4\"/>",
    "file": "<path d=\"M4 2h5l3 3v9H4z\"/><path d=\"M9 2v3h3\"/>",
    "spark": "<path d=\"M8 2l1.6 4.4L14 8l-4.4 1.6L8 14l-1.6-4.4L2 8l4.4-1.6z\"/>",
    "skip": "<path d=\"M2.5 3.5l5.5 4.5-5.5 4.5z M8 3.5l5.5 4.5L8 12.5z\" fill=\"currentColor\" stroke=\"none\"/>",
}
STATUS_ICON = {"pass": "check", "flag": "alert", "expected": "info", "info": "info"}
# The brand mark, drawn the same as the tab's icon in build.py, so it scales cleanly to any size.
MARK = ("<svg viewBox=\"0 0 32 32\"><rect width=\"32\" height=\"32\" rx=\"8\" fill=\"currentColor\"/><rect x=\"8.5\" "
        "y=\"8.5\" width=\"15\" height=\"15\" rx=\"3\" fill=\"none\" stroke=\"#fff\" stroke-width=\"2.6\"/></svg>")


def icon(name):
    return f"<svg class=\"icon\" width=\"16\" height=\"16\" viewBox=\"0 0 16 16\" aria-hidden=\"true\">{ICONS[name]}</svg>"


class Renderer:
    def __init__(self, words, ledger, state_name, fork_max):
        self.w, self.L, self.state, self.fork_max = words, ledger, state_name, fork_max
        self.refs = set()

    # ------------------------------------------------------------------ figures and sentences
    def q(self, ref):
        """The ref as the bundle knows it."""
        if not ref or ":" in ref:
            return ref
        kind, n = ref[0], int(ref[1:])
        return ref if n <= self.fork_max.get(kind, 0) else f"{self.state}:{ref}"

    def num(self, ref, short=True, cls="", shown=None):
        if not ref:
            return ""
        qref = self.q(ref)
        self.refs.add(qref)
        shown = shown or gate.display(self.L, ref, short=short)
        return (f"<button type=\"button\" class=\"num {cls}\" data-ref=\"{esc(qref)}\" "
                f"aria-label=\"{esc(shown)}, open where it comes from\">{esc(shown)}</button>")

    def meta(self, text, check_ref):
        """A count or row number that describes a check, like row 216. It opens the check."""
        qref = self.q(check_ref)
        self.refs.add(qref)
        return f"<button type=\"button\" class=\"num meta\" data-ref=\"{esc(qref)}\">{esc(text)}</button>"

    def param(self, v):
        if isinstance(v, tuple):
            if v[0] == "text":
                return esc(v[1])
            if v[0] == "html":
                return v[1]
            if v[0] == "meta":
                return self.meta(v[1], v[2])
        if isinstance(v, str) and v[:1] in "FDCKS" and v[1:].isdigit():
            return self.num(v)
        return esc(v)

    def fill(self, key, params=None):
        """A WORDS.md sentence with each of its names filled, figures as trace buttons."""
        template = html.escape(self.w[key], quote=False)
        return template.format(**{k: self.param(v) for k, v in (params or {}).items()})

    def note(self, sentence):
        key, params, check = sentence
        c = self.L.get(check)
        status = c["status"]
        return (f"<li class=\"note s-{status}\">{icon(STATUS_ICON[status])}<span>{self.fill(key, params)}</span></li>")

    def agent_text(self, text):
        """Agent prose with its ledger placeholders as trace buttons. The rest is escaped as written. A claims check
        keeps the verdict word as the agent wrote it when gate.render folds a repeated verdict into the citation."""
        return gate.render(text, self.L, wrap=lambda ref, shown: self.num(ref, shown=shown if ref[:1] == "C" else None))

    # ------------------------------------------------------------------ the run strip
    def strip(self, vm, pre=False):
        s = vm["strip"]
        w = self.w
        steps = [("received", "done"), ("mapped", "done"), ("checked", "done"), ("tied", "done"),
                 ("held", "held") if s["held"] else ("published", "done")]
        details = {
            "received": self.fill("strip.received.detail", {"files": s["files"]}),
            "mapped": (self.fill("strip.mapped.detail", {"known": s["known"], "agent": s["agent"]}) if s["agent"]
                       else self.fill("strip.mapped.detail_none", {"known": s["known"], "waiting": s["waiting"]})
                       if s["waiting"] else self.fill("strip.mapped.detail_all", {"known": s["known"]})),
            "checked": self.fill("strip.checked.detail", {"checks": s["checks"], "flags": s["flags"]}),
            "tied": self.fill("strip.tied.detail", {"ties": s["ties"]}),
            "published": self.fill("strip.published.detail"),
            "held": self.fill("strip.held.detail", {"flags": s["flags"]}),
        }
        out = []
        for n, (key, state) in enumerate(steps, 1):
            label = w["strip.held"] if key == "held" else w[f"strip.{key}"]
            st = "idle" if pre else state
            out.append(f"<li class=\"step {st}\" data-step=\"{n}\" data-final=\"{state}\"><span class=\"dot\">"
                       f"{icon('alert' if state == 'held' else 'check')}</span><span class=\"st\">{esc(label)}</span>"
                       f"<span class=\"sd\">{details[key]}</span></li>")
        return f"<ol class=\"steps\">{''.join(out)}</ol>"

    # ------------------------------------------------------------------ tiles and cards
    def tiles(self, vm, day):
        out = []
        w = self.w
        for t in vm["tiles"]:
            if t["key"] == "flags":
                n = self.L.value(t["ref"])
                note = w["tile.flags.none"] if not n else w["tile.flags.one"] if n == 1 else w["tile.flags.some"]
                foot = f"<span class=\"tile-note\">{esc(note)}</span>"
            else:
                foot = f"<span class=\"delta\">{self.num(t['var'])}</span>" if t["var"] else ""
            aff = " affected" if t["affected"] else ""
            out.append(f"<div class=\"tile{aff}\"><div class=\"tile-head\"><span class=\"tile-label\">"
                       f"{esc(w['tile.' + t['key']])}</span></div><div class=\"tile-value\">"
                       f"{self.num(t['ref'])}</div><div class=\"tile-foot\">{foot}</div></div>")
        return (f"<p class=\"tiles-caption\">{esc(w.fill('tile.period', day=day))}</p>"
                f"<div class=\"tiles\">{''.join(out)}</div>")

    def card(self, card, names):
        w = self.w
        c = card["company"]
        status = ("held", w["status.held"], "alert") if card["held"] else ("final", w["status.final"], "check")
        rows = []
        for k in card["kpis"]:
            aff = " affected" if k["affected"] else ""
            mark = (f"<span class=\"aff\" title=\"{esc(w['status.affected'])}\">{icon('alert')}</span>"
                    if k["affected"] else "")
            spark = charts.sparkline(k["series"], label=w["kpi." + k["name"]]) if k["series"] else ""
            var = f"<span class=\"kvar\">{self.num(k['var'])}</span>" if k["var"] else "<span class=\"kvar\"></span>"
            rows.append(f"<div class=\"kpi{aff}\"><span class=\"klabel\">{esc(w['kpi.' + k['name']])}{mark}</span>"
                        f"<span class=\"kval\">{self.num(k['ref'])}</span>{var}<span class=\"kspark\">{spark}</span></div>")
        notes = "".join(self.note(n) for n in card["notes"])
        if not any(self.L.get(n[2])["status"] == "flag" for n in card["notes"]):
            notes = f"<li class=\"note s-pass\">{icon('check')}<span>{esc(w['card.checks_passed'])}</span></li>" + notes
        com = card["commentary"]
        if com["state"] in ("valid", "stale"):
            body = "".join(f"<p>{keep_last_words(self.agent_text(s))}</p>" for s in com["sentences"])
            day = fmt.day_label(fmt.local_date(com["recorded_at"])) if com.get("recorded_at") else ""
            label = f"<p class=\"ai-label\">{icon('spark')}{esc(w.fill('commentary.label', date=day))}</p>"
            commentary = f"<div class=\"commentary\">{body}{label}</div>"
        else:
            key = {"held": "commentary.held", "missing": "commentary.missing",
                   "invalid": "commentary.invalid"}.get(com["state"], "commentary.missing")
            commentary = f"<div class=\"commentary muted\"><p>{esc(w[key])}</p></div>"
        return (f"<article class=\"card c-{c}{' held' if card['held'] else ''}\" aria-labelledby=\"h-{c}\">"
                f"<header class=\"card-head\"><div class=\"ch-row\"><h3 id=\"h-{c}\">{esc(names[c])}</h3>"
                f"<span class=\"pill s-{status[0]}\">{icon(status[2])}{esc(status[1])}</span></div><p class=\"sector\">"
                f"{esc(w['company.' + c + '.sector'])}</p></header><div class=\"kpis\">{''.join(rows)}</div>"
                f"<h4>{esc(w['card.checks_title'])}</h4><ul class=\"notes\">{notes}</ul>"
                f"<h4>{esc(w['card.commentary_title'])}</h4>{commentary}</article>")

    def banner(self, vm, names, planted=False):
        w = self.w
        if vm["held"]:
            parts = []
            for c in vm["held"]:
                ref = vm["held_counts"][c]
                n = self.L.value(ref)
                parts.append(self.fill("banner.held.company", {"company": ("text", names[c]), "count": ref,
                                                               "checks": ("text", "check" if n == 1 else "checks")}))
            text = self.fill("banner.held", {"companies": ("html", fmt.items(parts))})
            extra = f"<p class=\"banner-test\">{esc(w['banner.planted'])}</p>" if planted else ""
            return f"<div class=\"banner held\" role=\"status\">{icon('alert')}<div><p>{text}</p>{extra}</div></div>"
        return f"<div class=\"banner ok\" role=\"status\">{icon('check')}<div><p>{esc(w['banner.published'])}</p></div></div>"

    def portfolio(self, vm, names, day, panel="", planted=False):
        cards = "".join(self.card(c, names) for c in vm["cards"])
        return (f"{self.banner(vm, names, planted)}{panel}{self.tiles(vm, day)}<div class=\"cards\">{cards}</div>")

    # ------------------------------------------------------------------ panels
    def lookalike(self, code, notes):
        w = self.w
        items = "".join(self.note(n) for n in notes if n)
        return (f"<section class=\"panel lookalike\" aria-label=\"{esc(w[f'lookalike.{code}.title'])}\"><div class=\"panel-head\">"
                f"<h3>{esc(w[f'lookalike.{code}.title'])}</h3><span class=\"pill s-expected\">{icon('info')}"
                f"{esc(w['lookalike.result'])}</span></div><p>{esc(w[f'lookalike.{code}.text'])}</p>"
                f"<ul class=\"notes\">{items}</ul></section>")

    def intake(self, iv):
        w = self.w
        cols = ""
        for c in iv["columns"]:
            tags = []
            if c["new"]:
                tags.append(f"<span class=\"tag new\">{esc(w['intake.ignored'])}</span>")
            elif c["renamed"] or c["moved"]:
                tags.append(f"<span class=\"tag changed\">{esc(w['intake.changed'])}</span>")
            was = f"<span class=\"was\">{esc(c['was'])}</span>" if c["was"] and c["renamed"] else ""
            field = f"<code>{esc(c['field'])}</code>" if c["field"] else "<code class=\"muted\">null</code>"
            cols += (f"<tr class=\"{'chg' if (c['renamed'] or c['moved'] or c['new']) else ''}\"><td>{esc(c['header'])}"
                     f"{was}</td><td>{field}</td><td>{''.join(tags)}</td></tr>")
        checks = "".join(f"<li class=\"note s-{st}\">{icon(STATUS_ICON[st])}<span>{esc(w['vcheck.' + rule])}</span></li>"
                         for rule, st, _ in iv["checks"])
        tie = ""
        if len(iv["tie"]) == 2:
            tie = f"<p class=\"tie\">{self.num(iv['tie'][0], short=False)} = {self.num(iv['tie'][1], short=False)}</p>"
        if iv["status"] == "accepted":
            result = f"<p class=\"result ok\">{icon('check')}{esc(w.fill('intake.accepted', layout=iv['layout']))}</p>"
        elif iv["status"] == "pending":
            result = f"<p class=\"result held\">{icon('alert')}{esc(w['intake.pending'])}</p>"
        else:
            result = (f"<p class=\"result held\">{icon('alert')}"
                      f"{esc(w.fill('intake.held', reasons=fmt.items(iv['reasons'])))}</p>")
        e = iv["eval"]
        if e["recorded"]:
            ev = f"<p class=\"eval\">{self.fill('intake.eval', {'exact': ('html', self.evalnum(e['exact']))})}"
            if e["wrong"] and not e["harmful"]:
                ev += " " + self.fill("intake.eval_equivalent", {"wrong": ("html", self.evalnum(e["wrong"]))})
            elif e["harmful"]:
                ev += " " + self.fill("intake.eval_caught", {"caught": ("html", self.evalnum(e["caught"])),
                                                            "wrong": ("html", self.evalnum(e["harmful"]))})
            ev += "</p>"
        else:
            ev = f"<p class=\"eval muted\">{esc(w['intake.eval_pending'])}</p>"
        return (f"<section class=\"panel intake\" aria-label=\"{esc(w['intake.title'])}\"><div class=\"panel-head\">"
                f"<h3>{esc(w['intake.title'])}</h3></div><p>{esc(w['intake.text'])}</p><div class=\"intake-grid\">"
                f"<div><h4>{esc(w['intake.mapping'])}</h4><table class=\"map\"><thead><tr><th>{esc(w['intake.new'])}</th>"
                f"<th>Schema field</th><th></th></tr></thead><tbody>{cols}</tbody></table></div><div><h4>"
                f"{esc(w['intake.checks'])}</h4><ul class=\"notes\">{checks}</ul>{tie}{result}{ev}</div></div></section>")

    def evalnum(self, n):
        return f"<span class=\"num meta\" data-src=\"eval\">{esc(str(n))}</span>"

    def prerun(self, file_names):
        w = self.w
        items = "".join(f"<li>{icon('file')}<code>{esc(n)}</code></li>" for n in file_names)
        # The way into the tour names the arrow key. On a touch screen, which has no arrow key, app.js touchTour finds
        # that clause in this paragraph and swaps it for a button that starts the tour. The page itself keeps the plain
        # sentence, so a desktop draws it exactly as before.
        assert w["prerun.text"].count(w["prerun.tour.keys"]) == 1, "prerun.text must hold prerun.tour.keys once"
        return (f"<section class=\"panel prerun\"><h3>{esc(w['prerun.title'])}</h3><p>{esc(w['prerun.text'])}</p>"
                f"<ul class=\"files\">{items}</ul></section>")


# ---------------------------------------------------------------------- the page around the tabs
def page(words, header_html, sections, nav, links=""):
    """The page's frame around its tabs. links is the footer's second line, with the only links that leave the page."""
    w = words
    more = f"<p class=\"links\">{links}</p>" if links else ""
    tabs = "".join(f"<li><button type=\"button\" role=\"tab\" data-tab=\"{k}\" aria-controls=\"t-{k}\">{esc(w['tab.' + k])}"
                   f"</button></li>" for k in nav)
    return (f"<a class=\"skip\" href=\"#main\">Skip to the content</a>"
            f"<header class=\"top\" id=\"top\"><div class=\"bar\"><div class=\"brand\"><a class=\"mark\" href=\"index.html\" "
            f"data-home aria-label=\"{esc(w['header.home'])}\">{MARK.replace('<svg ', '<svg aria-hidden=\"true\" ', 1)}</a><div><h1>{esc(w['page.title'])}</h1><p class=\"line\">{esc(w['page.line'])}</p></div></div>"
            f"<div class=\"bar-right\">{header_html}</div></div>"
            f"<nav class=\"tabs\" aria-label=\"Tabs\"><ul role=\"tablist\">{tabs}</ul></nav></header>"
            f"<main id=\"main\" tabindex=\"-1\">{''.join(sections)}</main>"
            f"<aside id=\"drawer\" class=\"drawer\" aria-labelledby=\"drawer-title\" hidden><header><div>"
            f"<p class=\"kicker\">{esc(w['drawer.kicker'])}</p><h2 id=\"drawer-title\"></h2><p id=\"drawer-value\" "
            f"class=\"drawer-value\"></p></div><button type=\"button\" id=\"drawer-close\" class=\"btn icon\" "
            f"aria-label=\"{esc(w['drawer.close'])}\">{icon('x')}</button></header><div id=\"drawer-body\" "
            f"class=\"drawer-body\"></div></aside><div id=\"tip\" class=\"tip\" role=\"tooltip\" hidden></div>"
            f"<footer><div class=\"wrap\"><p>{esc(w['page.footer'])}</p>{more}</div></footer>")
