"""The built page: privacy tags and the footer, no network, every visible figure inside a trace link, every trace
link answered, the writing rules on every visible sentence, and the node check through every state and control."""
import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

from tests import helpers

URL = re.compile(r"https?://|//cdn|www\.")
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
ALLOWED = [re.compile(MONTH + r" \d{1,2}\b(?: to \d{1,2})?(?:, 20\d\d)?"), re.compile(r"\b\d{1,2} AM\b"),
           re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2} to \d{1,2}\b"),
           re.compile(r"\b20[0-3]\d\b"), re.compile(r"\b[ELV]\d{1,2}\b"), re.compile(r"\btms_v\d+\b"),
           re.compile(r"\bFY20\d\d[AE]?\b")]
SKIP = {"script", "style", "svg", "code", "title"}


class Visible(HTMLParser):
    """Text the reader sees, each piece marked by whether it sits inside a trace link or build metadata."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.out, self.sources = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("br", "img", "input", "meta", "link"):
            return
        self.stack.append((tag, "data-ref" in a or "data-src" in a or "data-trace" in a, a.get("data-src")))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not data.strip() or any(t in SKIP for t, _, _ in self.stack):
            return
        self.out.append((data, any(ref for _, ref, _ in self.stack)))
        self.sources.append(next((s for _, _, s in reversed(self.stack) if s), None))


def pieces(html):
    v = Visible()
    v.feed(html)
    return v.out


def prose(html):
    """Visible copy for the writing rules: everything but quoted source text and the workbook's own cells."""
    v = Visible()
    v.feed(html)
    return " ".join(text for (text, _), src in zip(v.out, v.sources) if src not in ("quote", "model", "grid"))


def main_html(index):
    return index.split("<main", 1)[1].split(">", 1)[1].split("</main>", 1)[0]


def stray_digits(html):
    out = []
    for text, traced in pieces(html):
        if traced:
            continue
        rest = text
        for pattern in ALLOWED:
            rest = pattern.sub(" ", rest)
        if re.search(r"\d", rest):
            out.append(text.strip()[:90])
    return out


def blocks(html):
    """The visible text of each paragraph, list item, and heading on its own, with spaces closed up before
    punctuation, so two words count as a pair only when they sit together in one sentence."""
    for m in re.finditer(r"<(p|li|h3|h4)\b[^>]*>(.*?)</\1>", html, re.S):
        yield re.sub(r"\s+([,.])", r"\1", " ".join(prose(m.group(2)).split()))


def load_bundle(site):
    text = site.joinpath("data.js").read_text()
    return json.loads(text[len("window.AD = "):].rstrip().rstrip(";"))


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = helpers.site()
        cls.index = cls.site.joinpath("index.html").read_text()
        cls.bundle = load_bundle(cls.site)

    def test_search_tags_and_footer(self):
        head = self.index.split("</head>")[0]
        self.assertNotIn("noindex", head)
        self.assertIn("<meta name=\"referrer\" content=\"no-referrer\">", head)
        for tag in ("<meta name=\"description\" content=\"A working demo of an AI operations desk for a fund.",
                    "<meta property=\"og:title\" content=\"Analyst Desk\">", "<meta property=\"og:description\"",
                    "<meta name=\"twitter:card\" content=\"summary_large_image\">"):
            self.assertIn(tag, head)
        footer = self.index.rsplit("<footer>", 1)[1].split("</footer>", 1)[0]
        self.assertIn("Built by Ryan Sansbury. Every company, number, and document here is synthetic.", footer)
        self.assertNotIn("recorded on", footer)

    def test_the_only_links_off_the_page_are_the_footers_two(self):
        """Every link stays on the page, opens a file the build put beside the page, or is one of the footer's links
        from config/site.json. The header's mark links to the page itself. A file link never climbs out of the page's folder, which a host won't serve."""
        import build
        cfg = build.site_cfg()
        allowed = {cfg["repo"], cfg["home"] + "/"} - {"", "/"}
        hrefs = re.findall(r"<a [^>]*href=\"([^\"]*)\"", self.index)
        files = {h for h in hrefs if not h.startswith("#") and "://" not in h}
        self.assertEqual(files, {"Brightrow_model.xlsx", "index.html"})
        for f in files:
            self.assertTrue(self.site.joinpath(f).is_file(), f)
        self.assertEqual({h for h in hrefs if "://" in h}, allowed)
        footer = self.index.rsplit("<footer>", 1)[1].split("</footer>", 1)[0]
        for href in allowed:
            self.assertEqual(self.index.count(f"href=\"{href}\""), 1, href)
            self.assertIn(f"href=\"{href}\"", footer)
        if cfg["url"]:
            self.assertIn(f"<link rel=\"canonical\" href=\"{cfg['url']}/\">", self.index)
            self.assertIn(f"<meta property=\"og:image\" content=\"{cfg['url']}/preview.png\">", self.index)

    def test_nothing_reaches_the_network(self):
        """A page address inside a meta tag or the canonical link never loads anything, and neither does a link the
        reader clicks, so those are left out once the test above has held the links to the footer's two."""
        for name in ("index.html", "app.js", "app.css", "data.js"):
            text = re.sub(r"<meta [^>]*>|<link rel=\"canonical\"[^>]*>|<a [^>]*href=\"https://[^\"]*\"", "",
                          self.site.joinpath(name).read_text())
            self.assertIsNone(URL.search(text), name)
        self.assertNotIn("<link rel=\"preconnect\"", self.index)
        self.assertNotIn("fetch(", self.site.joinpath("app.js").read_text())

    def test_the_header_carries_no_date(self):
        """The page stays up long after its demo morning, so the header holds only the hours back today and no data
        date that would read as stale."""
        bar = self.index.split("<div class=\"bar-right\">", 1)[1].split("</div>", 1)[0]
        self.assertIn("id=\"hours-today\"", bar)
        months = "January|February|March|April|May|June|July|August|September|October|November|December"
        self.assertIsNone(re.search(rf"\b(?:{months})\b|\bthrough\b|\b20\d\d\b", re.sub(r"<[^>]+>", " ", bar)), bar)

    @unittest.skipUnless(shutil.which("node"), "the slash check needs node on the path")
    def test_the_files_load_with_or_without_the_final_slash(self):
        """A host may serve the page at its address without the final slash. The head's first script then points
        every relative file link at the page's folder before the stylesheet loads, and it does nothing anywhere else."""
        head = self.index.split("</head>", 1)[0]
        scripts = re.findall(r"<script>(.*?)</script>", head, re.S)
        self.assertEqual(len(scripts), 1)
        self.assertLess(head.index("<script>"), head.index("<link rel=\"stylesheet\""))
        cases = [["https:", "/analyst-desk", "/analyst-desk/"], ["https:", "/analyst-desk/", None],
                 ["https:", "/analyst-desk/index.html", None], ["file:", "/srv/site/index.html", None]]
        js = ("const vm = require('vm'); const cases = JSON.parse(process.argv[1]), guard = process.argv[2];"
              "console.log(JSON.stringify(cases.map(([protocol, pathname]) => { const added = [];"
              "vm.runInNewContext(guard, {location: {protocol, pathname}, document: {createElement: () => ({}),"
              "head: {appendChild: (el) => added.push(el.href)}}}); return added.length ? added[0] : null; })));")
        out = subprocess.run(["node", "-e", js, json.dumps(cases), scripts[0]], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr[-1000:])
        self.assertEqual(json.loads(out.stdout), [c[2] for c in cases])

    def test_the_font_ships_with_the_page_once_its_files_are_in(self):
        import build
        css = self.site.joinpath("app.css").read_text()
        present = [name for name, _ in build.FONT_FACES if build.FONTS.joinpath(name).exists()]
        self.assertEqual(css.count("@font-face"), len(present))
        for name in present:
            self.assertIn(f"url(\"fonts/{name}\")", css)
            self.assertTrue(self.site.joinpath("fonts", name).exists(), name)

    def test_every_visible_figure_is_a_trace_link(self):
        for name, s in self.bundle["states"].items():
            for part in ("portfolio", "strip"):
                self.assertEqual(stray_digits(s[part]), [], f"{name} {part}")
        self.assertEqual(stray_digits(self.index.split("<main")[0]), [])
        self.assertEqual(stray_digits(main_html(self.index)), [])

    def test_every_trace_link_is_answered(self):
        refs = set()
        for s in self.bundle["states"].values():
            refs |= set(re.findall(r"data-ref=\"([^\"]+)\"", s["portfolio"] + s["strip"]))
        missing = sorted(r for r in refs if r not in self.bundle["traces"])
        self.assertEqual(missing, [])
        self.assertGreater(len(refs), 150)

    def test_traces_reach_their_inputs_and_excerpts(self):
        traces, excerpts = self.bundle["traces"], self.bundle["excerpts"]
        for ref, t in traces.items():
            if t["k"] == "fact":
                self.assertIn(t["x"], excerpts, ref)
                self.assertTrue(t["source"]["sha"], ref)
            if t["k"] == "derived":
                self.assertTrue(all(i in traces for i in t["inputs"][:3]), ref)

    def test_a_metric_name_never_splits_on_a_slide(self):
        from app.render import keep_terms
        marked = keep_terms("Targets for <span data-tip=\"gross margin\">on-time delivery</span>, empty miles, and days "
                            "sales outstanding. On-time Delivery holds.")
        self.assertIn("<span class=\"nw\">on-time delivery</span>", marked)
        self.assertIn("<span class=\"nw\">days sales outstanding</span>", marked)
        self.assertIn("<span class=\"nw\">On-time Delivery</span>", marked)
        self.assertIn("data-tip=\"gross margin\"", marked)

    def test_agent_text_never_ends_on_one_or_two_words(self):
        from app.render import keep_last_words, keep_terms
        nb = "\u00a0"
        marked = keep_last_words(keep_terms("The open questions concern service, empty miles, and collections."))
        self.assertTrue(marked.endswith(f"</span>,{nb}and{nb}collections."), marked)
        linked = keep_last_words("Revenue reached <a class=\"ref\" data-ref=\"D1\">$2.7M</a> in October. ")
        self.assertIn(f"</a>{nb}in{nb}October. ", linked)
        self.assertIn("<a class=\"ref\" data-ref=\"D1\">$2.7M</a>", linked)
        self.assertEqual(keep_last_words("Done."), "Done.")

    def test_the_writing_rules_hold_on_every_state(self):
        for name, s in self.bundle["states"].items():
            self.assertEqual(helpers.text_problems(prose(s["portfolio"])), [], name)
        self.assertEqual(helpers.text_problems(prose(main_html(self.index))), [], "the tabs")

    def test_the_writing_rules_hold_in_the_trace_drawer(self):
        """Each step under How it became this number, capitalized the way the drawer shows it, and each check's
        sentence. The titles are labels like "Revenue, Kiskadee Freight" and stay out of it."""
        texts = set()
        for t in self.bundle["traces"].values():
            texts.update(s[:1].upper() + s[1:] for s in t.get("steps") or [])
            if t.get("html"):
                texts.add(prose(t["html"]))
        problems = [p for s in sorted(texts) for p in helpers.text_problems(s)]
        self.assertEqual(problems, [])
        self.assertGreater(len(texts), 300)
        self.assertEqual([s for s in texts if re.search(r"\b20\d\d-\d\d-\d\d\b", s)], [], "dates read like November 3")

    def test_the_volume_note_names_the_day_the_budget_planned(self):
        from app.portfolio import day_plan
        self.assertEqual([day_plan(d) for d in ("2026-09-07", "2026-10-31", "2026-11-01", "2026-11-02")],
                         ["Labor Day", "Saturday", "Sunday", None])
        notes = [prose(t["html"]) for t in self.bundle["traces"].values()
                 if t.get("k") == "check" and "loads on" in (t.get("html") or "")]
        self.assertGreater(len(notes), 30)
        self.assertFalse([n for n in notes if "holiday" in n])
        self.assertTrue(any("on November 1 against a Sunday budget" in n for n in notes))
        self.assertIn("on September 7 against a Labor Day budget", prose(self.bundle["states"]["L3"]["portfolio"]))

    def test_no_word_repeats_itself_in_a_sentence(self):
        """Every paragraph, item, and heading in the tabs, the states, and the traces."""
        parts = ([main_html(self.index)] + [s["portfolio"] for s in self.bundle["states"].values()]
                 + [t.get("html") or "" for t in self.bundle["traces"].values()])
        doubled = [m.group(0) for h in parts for s in blocks(h) for m in re.finditer(r"(?i)(?<![\w-])([a-z]+) \1\b", s)]
        self.assertEqual(doubled, [])

    def test_the_recorded_memo_names_each_verdict_once(self):
        """The memo agent wrote "is supported {C:1}" on October 28, and a claims citation shows as its verdict, so
        the verdict read twice until gate.render folded the two together."""
        from agents import replay, validate
        from engine import gate
        desk = helpers.real_desk()
        run = desk.runs.get("memo_writer")
        mapping = replay.check(run, desk.ledger)["mapping"]
        risks = next(s for s in replay.final(run)["sections"] if s["id"] == "risks")
        text = " ".join(gate.render(validate.to_ledger(p, mapping), desk.ledger) for p in risks["paragraphs"])
        self.assertIn("threshold is supported, and", text)
        self.assertEqual(text.count("threshold is contradicted."), 2)
        self.assertIsNone(re.search(r"(?i)\b(supported|contradicted) \1\b", text), text)

    def test_a_count_of_one_reads_in_the_singular(self):
        states = {k: " ".join(blocks(s["portfolio"])) for k, s in self.bundle["states"].items()}
        self.assertEqual([(k, m.group(0)) for k, t in states.items()
                          for m in re.finditer(r"\b1 (rows|files|checks|flags|loads)\b", t)], [])
        self.assertIn("1 row in the freight export carries a date other than the business day.", states["E3"])
        self.assertIn("1 row in the freight export has no load ID.", states["E3"])
        self.assertIn("It's listed on its company's card", prose(self.bundle["states"]["E4"]["portfolio"]))
        self.assertIn("Each one is listed on its company's card", prose(self.bundle["states"]["E1"]["portfolio"]))

    def test_every_trace_link_in_the_tabs_is_answered(self):
        refs = set(re.findall(r"data-(?:ref|trace)=\"([^\"]+)\"", main_html(self.index)))
        self.assertEqual(sorted(r for r in refs if r not in self.bundle["traces"]), [])
        self.assertGreater(len(refs), 300)

    def test_the_states_differ_where_they_should(self):
        st = self.bundle["states"]
        self.assertTrue("banner held" in st["E1"]["portfolio"], "E1 is held")
        self.assertTrue("banner ok" in st["clean"]["portfolio"], "the clean morning publishes")
        self.assertTrue("banner ok" in st["L1"]["portfolio"], "a look-alike publishes")
        self.assertTrue(st["E2"]["portfolio"] != st["clean"]["portfolio"], "E2 differs")
        self.assertTrue("panel intake" in st["intake"]["portfolio"], "the intake panel shows")
        self.assertTrue("Accepted and saved as tms_v2" in st["intake"]["portfolio"], "the mapping is accepted")

    @unittest.skipUnless(shutil.which("node"), "the node check needs node on the path")
    def test_node_check_through_every_state_and_control(self):
        out = subprocess.run(["node", str(helpers.HERE.joinpath("tests", "js", "check_app.js")), str(self.site)],
                             capture_output=True, text=True, timeout=180)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        report = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(report["errors"], [])
        failed = [c for c in report["checks"] if not c["ok"]]
        self.assertEqual(failed, [], json.dumps(failed, indent=1)[:3000])
        self.assertGreater(len(report["checks"]), 30)


if __name__ == "__main__":
    unittest.main()
