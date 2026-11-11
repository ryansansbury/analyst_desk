"""Build everything from the seed: generate the world, ingest it, run the checks, build the deliverables and render
the page into site/.

    .venv/bin/python3 build.py          (from the build folder)

site/index.html opens from the file system with no network requests. data.js holds every precomputed state and
the trace of every figure. Nothing in the build or on the page calls a model. AI steps replay the recorded runs in
data/ai_runs/, and each one is validated again before it's shown.
"""
import base64
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agents import routing  # noqa: E402
from app import bundle, code_view, deal_tab, how, render, routing_view, uploads  # noqa: E402
from app import words as words_mod  # noqa: E402

from app.desk import Desk  # noqa: E402
from deliverables import deck, hours, memo  # noqa: E402
from deliverables.model_xlsx import Book  # noqa: E402
from generate import run as gen  # noqa: E402

SITE = HERE.joinpath("site")
UI = HERE.joinpath("app", "ui")
FONTS = UI.joinpath("fonts")
FONT_FACES = (("InterVariable.woff2", "normal"), ("InterVariable-Italic.woff2", "italic"))
PREVIEW = UI.joinpath("preview.png")         # the link-card image, which scripts/screenshots.sh refreshes
SITE_CFG = HERE.joinpath("config", "site.json")
OUTPUTS = HERE.joinpath("outputs")
RECALC = HERE.joinpath(".cache", "recalc")
TABS = ("portfolio", "deal", "board", "hours", "how")
# The brand mark as the tab's icon, inline so it costs no file and no request.
_MARK = ("<svg xmlns='http:" "//www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='#0F766E'/>"
         "<rect x='8.5' y='8.5' width='15' height='15' rx='3' fill='none' stroke='#fff' stroke-width='2.6'/></svg>")
ICON = "data:image/svg+xml;base64," + base64.b64encode(_MARK.encode()).decode()
# A host may serve the page at its address without the final slash, and every relative file link would then point
# one folder too high. This first script in the head points them at the page's own folder in that case alone. It
# does nothing on a page opened from a file or at an address that ends in a slash or in .html.
SLASH_GUARD = ("<script>(function(){var l=location,p=l.pathname;if(l.protocol!==\"file:\"&&p.slice(-1)!==\"/\"&&"
               "!/\\.html?$/.test(p)){var b=document.createElement(\"base\");b.href=p+\"/\";document.head.appendChild(b);}"
               "})();</script>")
STEPS = ("problem", "run", "error", "lookalike", "intake", "upload",          # Portfolio
         "deal", "model", "returns", "checks", "claims", "memo", "gate", "pass",  # Deal
         "board", "hours", "how", "routing", "code", "results", "plan")


def site_cfg():
    """config/site.json: the page's address once it's hosted and the two links in its footer, each empty until set."""
    cfg = json.loads(SITE_CFG.read_text()) if SITE_CFG.exists() else {}
    return {k: (cfg.get(k) or "").rstrip("/") for k in ("url", "repo", "home")}


def footer_links(w):
    """The footer's links to the code and to the author's site, from config/site.json. They're the only links that leave the
    page, and the tests hold every link to them."""
    cfg, e = site_cfg(), render.esc
    host = cfg["home"].split("//", 1)[-1].removeprefix("www.")    # the link's text leaves out www
    parts = []
    if cfg["repo"]:
        parts.append(e(w["page.footer.code"]).format(link=f"<a href=\"{e(cfg['repo'])}\">{e(w['page.footer.github'])}</a>"))
    if cfg["home"]:
        parts.append(e(w["page.footer.home"]).format(link=f"<a href=\"{e(cfg['home'])}/\">{e(host)}</a>"))
    return " ".join(parts)


def meta_tags(w):
    """The search and link-card tags. The page's address goes in config/site.json once it's hosted, which adds the
    canonical link and makes the image's address absolute. The image appears once a screenshot run has made it."""
    url = site_cfg()["url"]
    title, desc, e = render.esc(w["page.title"]), render.esc(w["page.description"]), render.esc
    tags = [f"<meta name=\"description\" content=\"{desc}\">", "<meta property=\"og:type\" content=\"website\">",
            f"<meta property=\"og:title\" content=\"{title}\">", f"<meta property=\"og:description\" content=\"{desc}\">",
            "<meta name=\"twitter:card\" content=\"summary_large_image\">"]
    if url:
        tags += [f"<link rel=\"canonical\" href=\"{e(url)}/\">", f"<meta property=\"og:url\" content=\"{e(url)}/\">"]
    if PREVIEW.exists():
        img = e(f"{url}/preview.png" if url else "preview.png")
        tags += [f"<meta property=\"og:image\" content=\"{img}\">", "<meta property=\"og:image:width\" content=\"1200\">",
                 "<meta property=\"og:image:height\" content=\"630\">", f"<meta name=\"twitter:image\" content=\"{img}\">"]
    return "".join(tags)


def font_css():
    """@font-face rules for Inter, served from the site's own fonts/ folder once its files are in app/ui/fonts/, so
    lines wrap the same on every machine. Without the files the page falls back to the system font."""
    return "".join(f"@font-face {{ font-family: \"Inter\"; src: url(\"fonts/{name}\") format(\"woff2\"); "
                   f"font-weight: 100 900; font-style: {style}; font-display: swap; }}\n"
                   for name, style in FONT_FACES if FONTS.joinpath(name).exists())


def steps_for(routes_html):
    """Presenter mode's steps. The routing step is there once a model comparison has put its panel on the page."""
    return [s for s in STEPS if s != "routing" or routes_html]


def header_html(w, today):
    """The hours back today, which shows once the morning has run. The header carries no date of its own, since the
    page stays up long after its demo morning."""
    h = hours.out(today, "today")
    return (f"<p class=\"hours-today\" id=\"hours-today\" hidden>{render.icon('spark')}<span>"
            f"{render.esc(w['header.hours']).replace('{h}', h)}</span></p>")


def controls_html(w):
    plant = "".join(f"<li><button type=\"button\" data-state=\"{c}\">{render.esc(w['plant.' + c])}</button></li>"
                    for c in ("E1", "E2", "E3", "E4", "E5", "E6"))
    look = "".join(f"<li><button type=\"button\" data-state=\"{c}\">{render.esc(w['lookalike.' + c])}</button></li>"
                   for c in ("L1", "L2", "L3"))
    i = render.icon
    labels = "".join(f"<span data-lbl=\"{k}\">{render.esc(w['controls.' + k])}</span>" for k in ("run", "replay", "skip"))
    icons = i("play").replace("<svg ", "<svg data-ico=\"play\" ") + i("skip").replace("<svg ", "<svg data-ico=\"skip\" ")
    return (f"<div class=\"controls\" role=\"toolbar\"><button type=\"button\" class=\"btn primary\" id=\"run\" "
            f"data-mode=\"run\"><span class=\"run-icons\">{icons}</span><span class=\"run-labels\">{labels}</span></button>"
            f"<div class=\"menu\"><button type=\"button\" class=\"btn menu-toggle\" "
            f"aria-haspopup=\"true\" aria-expanded=\"false\">{render.esc(w['controls.plant'])}{i('down')}</button>"
            f"<ul class=\"menu-list\" hidden>{plant}</ul></div><div class=\"menu\"><button type=\"button\" class=\"btn menu-toggle\" "
            f"aria-haspopup=\"true\" aria-expanded=\"false\">{render.esc(w['controls.lookalike'])}{i('down')}</button>"
            f"<ul class=\"menu-list\" hidden>{look}</ul></div><button type=\"button\" class=\"btn\" data-state=\"intake\">"
            f"{render.esc(w['controls.newfile'])}</button><button type=\"button\" class=\"btn\" id=\"upload\">"
            f"{render.esc(w['controls.upload'])}</button><span class=\"spacer\"></span><button type=\"button\" "
            f"class=\"btn ghost\" id=\"csv\">{render.esc(w['controls.csv'])}</button><button type=\"button\" "
            f"class=\"btn ghost\" id=\"print\">{render.esc(w['controls.print'])}</button><button type=\"button\" "
            f"class=\"btn ghost\" id=\"reset\">{i('reset')}<span>{render.esc(w['controls.reset'])}</span></button></div>")


def report_csv(desk, b):
    """The facts and derived values behind the clean report, one row per ID."""
    lines = ["id,kind,label,period,value,unit,source,locator"]
    for ref, t in sorted(b["traces"].items()):
        if t["k"] not in ("fact", "derived") or not (ref.startswith("clean:") or ":" not in ref):
            continue
        raw = desk.ledger.get(ref.split(":")[-1])
        cells = [ref.split(":")[-1], t["k"], t["title"], t["period"], f"{raw['value']}", raw["unit"],
                 (t.get("source") or {}).get("path", ""), t.get("locator", "")]
        lines.append(",".join("\"" + str(c).replace("\"", "\"\"") + "\"" for c in cells))
    return "\n".join(lines) + "\n"


def write_readme_results(table):
    """The README's results table, written from the same files the How it works tab reads. It changes only once this
    machine has run both the tests and the LibreOffice check, so a fresh clone's first build leaves the README as it
    came and the table never loses a row it can't remake."""
    path = HERE.joinpath("README.md")
    if not (path.exists() and HERE.joinpath("data", "test_results.json").exists() and how.RECALC.exists()):
        return
    text = path.read_text()
    start, end = "<!-- results start -->\n", "<!-- results end -->"
    if start in text and end in text:
        head, rest = text.split(start, 1)
        path.write_text(head + start + table + rest[rest.index(end):])


def clear_leftovers(out, written):
    """Removes anything in the output folder this build didn't write, like a file from an older build under an old
    name, so the folder that goes live holds only the page's own files."""
    for p in sorted(out.rglob("*"), key=lambda q: len(q.parts), reverse=True):
        rel = p.relative_to(out).as_posix()
        if p.is_file() and rel not in written:
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()


def build(out=None, quiet=False, runs=None, write_data=True, comparison=None):
    """comparison is the model comparison to show, read from evals/model_comparison.json unless given."""
    t0 = time.time()
    out = Path(out) if out else SITE
    w = words_mod.load()
    desk = Desk(runs=runs)
    t_model = time.time()
    deal = desk.deal_model()
    book = Book(deal, w, None)
    model_seconds = time.time() - t_model
    hour_rows = hours.rows(desk, model_seconds)
    workbook = book.workbook()          # also in site/, where the Deal tab's download link finds it once the page is hosted
    if write_data:
        gen.write_world(desk.world)
        desk.ledger.save(HERE.joinpath("data", "ledger.sqlite"))
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        OUTPUTS.joinpath("Brightrow_model.xlsx").write_bytes(workbook)
        RECALC.mkdir(parents=True, exist_ok=True)
        RECALC.joinpath("Brightrow_model_formulas.xlsx").write_bytes(book.workbook(cached=False))
    b = bundle.make(desk, w, tabs={"deal": lambda R: deal_tab.render(desk, deal, book, w, R, memo.render(desk, deal, w, R)),
                                     "board": lambda R: deck.render(desk, w, R)})
    code_files = code_view.collect()
    hours_html = hours.render(hour_rows, w)
    routes_html = routing_view.render(routing.load() if comparison is None else comparison, w)
    how_html = how.render(desk, book, w, code=code_view.render(w, code_files), routes=routes_html)
    if write_data:
        write_readme_results(how.plain_results(desk, book, w))
    tabs_html = {k: render.glue(v) for k, v in b.pop("tabs").items()}
    for s in b["states"].values():
        s["portfolio"], s["strip"] = render.glue(s["portfolio"]), render.glue(s["strip"])
    hours_html, how_html = render.glue(hours_html), render.glue(how_html)
    b["csv"] = report_csv(desk, b)
    b["ui"] = {k: w[k] for k in ("drawer.source", "drawer.fingerprint", "drawer.received", "drawer.layout",
                                 "drawer.location", "drawer.steps", "drawer.checks", "drawer.inputs", "drawer.more",
                                 "drawer.quarantined", "drawer.preview", "drawer.kicker", "drawer.kicker.file", "controls.run", "controls.replay", "controls.skip",
                                 "deal.formula.hint", "deal.formula.input", "deal.formula.trace", "hours.unit",
                                 "hours.legend.manual", "hours.legend.auto",
                                 "presenter.label") + tuple("presenter.s." + s for s in STEPS)
                                + tuple("presenter.c." + s for s in STEPS)}
    b["meta"]["steps"] = steps_for(routes_html)
    portfolio_section = (f"<section class=\"tab\" id=\"t-portfolio\" data-tab-panel=\"portfolio\" role=\"tabpanel\">"
                         f"<div class=\"strip\" id=\"strip\">{b['states']['pre']['strip']}</div>{controls_html(w)}{render.glue(uploads.render(desk, w))}<div id=\"portfolio-body\">"
                         f"{b['states']['pre']['portfolio']}</div></section>")
    deal_section = (f"<section class=\"tab\" id=\"t-deal\" data-tab-panel=\"deal\" role=\"tabpanel\">{tabs_html['deal']}"
                    f"</section>")
    board_section = (f"<section class=\"tab\" id=\"t-board\" data-tab-panel=\"board\" role=\"tabpanel\">"
                     f"{tabs_html['board']}</section>")
    extra = [f"<section class=\"tab\" id=\"t-{k}\" data-tab-panel=\"{k}\" role=\"tabpanel\">{html_}</section>"
             for k, html_ in (("hours", hours_html), ("how", how_html))]
    body = render.page(w, header_html(w, hours.today(hour_rows)),
                       [portfolio_section, deal_section, board_section] + extra, TABS, footer_links(w))
    body += ("<div id=\"presenter\" class=\"presenter\" role=\"status\" aria-live=\"polite\" hidden>"
             "<span class=\"pn\"></span><span class=\"pl\"></span><span class=\"pc\"></span></div>")
    head = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"{SLASH_GUARD}<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<meta name=\"referrer\" content=\"no-referrer\">{meta_tags(w)}"
            f"<title>{render.esc(w['page.title'])}</title><link rel=\"icon\" href=\"{ICON}\">"
            f"<link rel=\"stylesheet\" href=\"app.css\"></head><body>")
    out.mkdir(parents=True, exist_ok=True)
    out.joinpath("index.html").write_text(head + body + "<script src=\"data.js\"></script><script src=\"code.js\"></script>"
                                          "<script src=\"app.js\"></script>"
                                          "</body></html>\n")
    out.joinpath("data.js").write_text(bundle.js_assign("AD", b))
    out.joinpath("code.js").write_text(bundle.js_assign("AD_CODE", code_view.payload(w, code_files)))
    out.joinpath("Brightrow_model.xlsx").write_bytes(workbook)
    shutil.copyfile(UI.joinpath("app.js"), out.joinpath("app.js"))
    fonts = font_css()
    out.joinpath("app.css").write_text(fonts + UI.joinpath("app.css").read_text())
    if fonts:
        out.joinpath("fonts").mkdir(exist_ok=True)
        for p in FONTS.iterdir():
            if p.suffix in (".woff2", ".txt"):
                shutil.copyfile(p, out.joinpath("fonts", p.name))
    if PREVIEW.exists():
        shutil.copyfile(PREVIEW, out.joinpath("preview.png"))
    written = {"index.html", "data.js", "code.js", "Brightrow_model.xlsx", "app.js", "app.css"}
    written |= {f"fonts/{p.name}" for p in FONTS.iterdir() if fonts and p.suffix in (".woff2", ".txt")}
    written |= {"preview.png"} if PREVIEW.exists() else set()
    clear_leftovers(out, written)
    if not quiet:
        sizes = {p.name: p.stat().st_size for p in sorted(out.iterdir()) if p.is_file()}
        print(f"built in {time.time() - t0:.1f} s: " + ", ".join(f"{n} {s / 1024:.0f} KB" for n, s in sizes.items())
              + f"; {len(b['traces'])} traces, {len(b['states'])} states")
        if not desk.runs:
            print("note: data/ai_runs/ holds no recorded runs, so the AI steps show as missing")
    return {"desk": desk, "bundle": b, "words": w, "deal": deal, "book": book, "hours": hour_rows}


if __name__ == "__main__":
    build()
