"""Look at the page in real Chrome: screenshots, the line rule, overlaps, console errors, network requests, and the
PDFs. It needs Chrome installed and calls nothing but the browser.

    bash scripts/screenshots.sh            (from the build folder)

It opens site/index.html straight from the file system in headless Chrome with a fresh profile, drives it over
the DevTools pipe, and writes everything to scripts/out/, which is gitignored:

    screens/<width>-<state>.png   every state of the Portfolio tab at 1440 and 1280 pixels, plus the trace drawer
    screens/<width>-tab-<tab>.png every tab at full length, at 1440 and 1280 and at 1024, 768 and 390 for a phone
    screens/<width>-stepNN-*.png  what the shared screen shows after each presenter step, at 1440x900 and 1280x720
    screens/<width>-preview-*.png the Model routing panel built from the tests' stand-in comparison, until a real one exists
    layout.json                   last lines of one or two words, text overlapping text, anything wider than the window,
                                  and the architecture diagram's boxes on How it works
    console.json                  anything the page logged as an error
    network.json                  every request, which should all be file:// requests
    browser_check.json            the summary this prints, which also says whether both Inter fonts loaded and holds
                                  a fingerprint of every file of the page it checked

It also prints the report, the memo and the deck to PDF in outputs/ when the page has them, and it takes the README's
screenshots into docs/screenshots/ at 1440 by 900 and twice the pixel density, with presenter mode's caption hidden.
Standard library only.
"""
import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT.joinpath("site")
OUT = HERE.joinpath("out")
SHOTS = OUT.joinpath("screens")
OUTPUTS = ROOT.joinpath("outputs")
PREVIEW = ROOT.joinpath("app", "ui", "preview.png")     # the link-card image the build puts in the page's head
README_SHOTS = ROOT.joinpath("docs", "screenshots")     # the README's pictures, which ship with the code
APPS = Path("/").joinpath("Applications")
CHROMES = (APPS.joinpath("Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
           APPS.joinpath("Chromium.app", "Contents", "MacOS", "Chromium"))
WIDTHS = (1440, 1280)
HEIGHTS = {1440: 900, 1280: 720}
SMALL = ((1024, 768), (768, 1024), (390, 844))
TABS = ("portfolio", "deal", "board", "hours", "how")
TRAMPOLINE = 'exec "$@" 3<&0 4>&1 0</dev/null 1>&2'

LAYOUT_JS = """(function () {
  var W = window.innerWidth, out = {wider_than_window: document.documentElement.scrollWidth > W + 1, overlaps: [], lines: []};
  var root = document.querySelector('.tab.active');
  out.lines = ADP.spillReport(root).concat(ADP.spillReport(document.getElementById('top')));
  // The left and right edges each element's text can show between, inside every box that hides its overflow. Text an
  // ellipsis cuts short counts only up to the cut. The rest of it isn't on the screen.
  var clips = new Map();
  function shown(el) {
    if (!el || el === document.body) { return {l: -Infinity, r: Infinity}; }
    if (clips.has(el)) { return clips.get(el); }
    var up = shown(el.parentElement), cs = getComputedStyle(el), edges = up;
    if (/^(hidden|clip)$/.test(cs.overflowX) && !/^(inline|contents)$/.test(cs.display)) {
      var box = el.getBoundingClientRect();
      edges = {l: Math.max(up.l, box.left + parseFloat(cs.borderLeftWidth)),
               r: Math.min(up.r, box.right - parseFloat(cs.borderRightWidth))};
    }
    clips.set(el, edges);
    return edges;
  }
  var frags = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node, range = document.createRange();
  while ((node = walker.nextNode())) {
    var el = node.parentElement;
    if (!/\\S/.test(node.data) || !el || el.closest('svg, script, style, .menu-list, pre.code, .code-tree, .sheets') ||
        !el.checkVisibility({visibilityProperty: true})) { continue; }
    range.selectNodeContents(node);
    var edges = shown(el);
    Array.prototype.forEach.call(range.getClientRects(), function (x) {
      var l = Math.max(x.left, edges.l), r = Math.min(x.right, edges.r);
      if (r - l < 1 || x.height < 1) { return; }
      var h = x.bottom - x.top;
      frags.push({el: el, l: l, r: r, t: x.top + h * 0.2, b: x.bottom - h * 0.2, text: node.data.trim().slice(0, 40)});
    });
  }
  frags.sort(function (a, b) { return a.t - b.t; });
  for (var i = 0; i < frags.length && out.overlaps.length < 20; i++) {
    for (var j = i + 1; j < frags.length && frags[j].t < frags[i].b; j++) {
      var f = frags[i], g = frags[j];
      if (f.el === g.el || f.el.contains(g.el) || g.el.contains(f.el)) { continue; }
      if (Math.min(f.r, g.r) - Math.max(f.l, g.l) > 2) { out.overlaps.push(f.text + ' / ' + g.text); }
    }
  }
  return out;
})()"""

# Ask for both Inter faces and report where each one ended up. A face the browser couldn't decode reports "error".
FONTS_JS = """Promise.all(['16px Inter', 'italic 16px Inter'].map(function (f) {
  return document.fonts.load(f).catch(function () { return []; });
})).then(function () {
  var out = {};
  document.fonts.forEach(function (f) { out[f.family.replace(/"/g, '') + ' ' + f.style] = f.status; });
  return out;
})"""


# The architecture diagram at the How it works step, in page pixels: each box's rect and its title's top, the
# deliverables column, and the middle of each arrow. The four input boxes should share one size, and the gate box
# should run the ledger's full height.
ARCH_JS = """(function () {
  function k(v) { return Math.round(v * 100) / 100; }
  function r(e) {
    var b = e.getBoundingClientRect();
    return {x: k(b.left), y: k(b.top + window.scrollY), w: k(b.width), h: k(b.height)};
  }
  var boxes = {};
  document.querySelectorAll('.arch .abox').forEach(function (e) {
    var t = e.querySelector('.abox-t'), b = r(e);
    b.text_top = r(t).y;
    boxes[t.textContent.trim()] = b;
  });
  var arrows = Array.prototype.map.call(document.querySelectorAll('.arch .aflow svg'), function (e) {
    var b = r(e);
    return k(b.y + b.h / 2);
  });
  var out = document.querySelector('.arch .acol.out');
  return {boxes: boxes, arrow_middles: arrows, deliverables: out && r(out)};
})()"""

# The README's screenshots. Each starts from a presenter step, which sets up its exact state, and the ones that name
# an element scroll it to the top of the window. (file name, step, element or None)
README_VIEWS = (("portfolio", "run", None), ("held", "error", None), ("model", "returns", None),
                ("gate", "gate", ".memo-head"), ("board", "board", None), ("how", "how", None))

# One element just under the sticky header, which is measured each time since it shrinks to the tab row once the page
# scrolls.
TO_TOP_JS = """(function (sel) {
  var el = document.querySelector(sel), bar = document.getElementById('top');
  if (!el) { return false; }
  window.scrollTo(0, Math.max(0, el.getBoundingClientRect().top + window.scrollY - bar.getBoundingClientRect().height - 14));
  return true;
})(%s)"""

# In the open trace drawer, click the first input whose row holds the given text, or else the first input.
PICK_JS = """(function (text) {
  var rows = Array.prototype.slice.call(document.querySelectorAll('#drawer-body .inputs li'));
  var row = rows.filter(function (li) { return text && li.textContent.indexOf(text) >= 0; })[0] || rows[0];
  var btn = row && row.querySelector('button.num');
  if (btn) { btn.click(); }
  return btn ? btn.textContent : null;
})(%s)"""


# Scatter labels against each other and against every dot but their own, and the labels that gave way to the tip.
LABELS_JS = """(function () {
  var out = [], hidden = [];
  document.querySelectorAll('.sc-plot').forEach(function (plot) {
    plot.querySelectorAll('.sc-lbl.crowded').forEach(function (e) { hidden.push(e.textContent); });
    var marks = Array.prototype.map.call(plot.querySelectorAll('.sc-lbl:not(.crowded), .sc-pt'), function (e) {
      var r = e.getBoundingClientRect();
      return {e: e, l: r.left, r: r.right, t: r.top, b: r.bottom, id: e.getAttribute('data-for') || e.getAttribute('data-id'),
        lbl: e.classList.contains('sc-lbl')};
    });
    marks.forEach(function (a, i) {
      marks.slice(i + 1).forEach(function (b) {
        if (!a.lbl && !b.lbl || a.id === b.id && a.lbl !== b.lbl) { return; }
        if (Math.min(a.r, b.r) - Math.max(a.l, b.l) > 1 && Math.min(a.b, b.b) - Math.max(a.t, b.t) > 1) {
          out.push((a.lbl ? a.e.textContent : 'dot ' + a.id) + ' / ' + (b.lbl ? b.e.textContent : 'dot ' + b.id));
        }
      });
    });
  });
  return {collisions: out, hidden: hidden};
})()"""


def routing_preview():
    """The page built with the tests' stand-in model comparison into scripts/out/routing_preview, so the Model routing
    panel can be looked at before the model comparison exists. None once a real comparison is on the page."""
    sys.path.insert(0, str(ROOT))
    from agents import routing
    if routing.load():
        return None
    import build
    from tests import helpers
    out = OUT.joinpath("routing_preview")
    build.build(out=out, quiet=True, write_data=False, comparison=helpers.stand_in_comparison())
    return out.joinpath("index.html").resolve().as_uri()


def find_chrome(given=None):
    if given:
        return str(given)
    for p in CHROMES:
        if p.exists():
            return str(p)
    for n in ("google-chrome", "chromium"):
        if shutil.which(n):
            return shutil.which(n)
    raise SystemExit("Chrome wasn't found. Run again with --chrome and the path to the Chrome program.")


class CDP:
    """The DevTools protocol over Chrome's pipe: JSON messages, each ended by a zero byte."""

    def __init__(self, proc, on_event=None):
        self.proc, self.on_event = proc, on_event
        self.next_id, self.responses, self.events = 0, {}, []
        self.cond, self.wlock = threading.Condition(), threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            chunk = self.proc.stdout.read1(1 << 16)
            if not chunk:
                break
            buf += chunk
            while b"\0" in buf:
                raw, buf = buf.split(b"\0", 1)
                msg = json.loads(raw)
                with self.cond:
                    if "id" in msg:
                        self.responses[msg["id"]] = msg
                    else:
                        self.events.append(msg)
                    self.cond.notify_all()
                if "id" not in msg and self.on_event:
                    self.on_event(msg)

    def send(self, method, params=None, session=None, timeout=60):
        with self.cond:
            self.next_id += 1
            mid = self.next_id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        with self.wlock:
            self.proc.stdin.write(json.dumps(msg).encode() + b"\0")
            self.proc.stdin.flush()
        deadline = time.time() + timeout
        with self.cond:
            while mid not in self.responses:
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)
            reply = self.responses.pop(mid)
        if "error" in reply:
            raise RuntimeError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result", {})

    def mark(self):
        with self.cond:
            return len(self.events)

    def wait_event(self, method, session, since, timeout=60):
        deadline = time.time() + timeout
        with self.cond:
            while True:
                for e in self.events[since:]:
                    if e.get("method") == method and e.get("sessionId") == session:
                        return e
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)


class Browser:
    def __init__(self, chrome):
        self.requests, self.console = [], []
        profile = OUT.joinpath("chrome-profile")
        shutil.rmtree(profile, ignore_errors=True)
        flags = ["--headless=new", "--remote-debugging-pipe", f"--user-data-dir={profile}", "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--mute-audio",
                 "--disable-background-networking", "--disable-sync", "--disable-component-update",
                 "--allow-file-access-from-files"]
        self.log = OUT.joinpath("chrome.log").open("wb")
        self.proc = subprocess.Popen(["bash", "-c", TRAMPOLINE, "chrome", chrome, *flags], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log)
        self.cdp = CDP(self.proc, self.event)
        target = self.cdp.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.s = self.cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        for m in ("Page.enable", "Runtime.enable", "Network.enable", "Log.enable"):
            self.cdp.send(m, session=self.s)

    def event(self, e):
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            self.requests.append(p["request"]["url"])
        elif m == "Runtime.exceptionThrown":
            d = p["exceptionDetails"]
            self.console.append({"kind": "exception", "text": (d.get("exception") or {}).get("description") or d.get("text")})
        elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "assert"):
            self.console.append({"kind": "console.error", "text": " ".join(str(a.get("value", a.get("description")))
                                                                           for a in p.get("args", []))})
        elif m == "Log.entryAdded" and p["entry"].get("level") == "error":
            self.console.append({"kind": "log", "text": p["entry"].get("text"), "url": p["entry"].get("url")})

    def view(self, width, height=900, mobile=False, scale=1):
        self.cdp.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": scale,
                                                             "mobile": mobile}, self.s)

    def load(self, url):
        since = self.cdp.mark()
        self.cdp.send("Page.navigate", {"url": url}, self.s)
        self.cdp.wait_event("Page.loadEventFired", self.s, since)
        self.pause(0.4)

    def js(self, expr, wait=False):
        r = self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": wait}, self.s)
        if "exceptionDetails" in r:
            raise RuntimeError(f"{expr[:60]}: {r['exceptionDetails'].get('text')}")
        return r.get("result", {}).get("value")

    def pause(self, seconds):
        self.js(f"new Promise(r => requestAnimationFrame(() => setTimeout(r, {int(seconds * 1000)})))", wait=True)

    def shot(self, name, width, full=True):
        params = {"format": "png"}
        if full:
            size = self.cdp.send("Page.getLayoutMetrics", session=self.s)["cssContentSize"]
            params.update(captureBeyondViewport=True, clip={"x": 0, "y": 0, "width": width,
                                                            "height": min(size["height"], 9000), "scale": 1})
        data = self.cdp.send("Page.captureScreenshot", params, self.s, timeout=120)["data"]
        SHOTS.joinpath(f"{name}.png").write_bytes(base64.b64decode(data))

    def capture(self, path):
        """What the window shows, saved to path."""
        data = self.cdp.send("Page.captureScreenshot", {"format": "png"}, self.s, timeout=120)["data"]
        path.write_bytes(base64.b64decode(data))

    def shot_of(self, name, selector):
        """One element at full size, wherever it sits on the page."""
        r = self.js(f"(function () {{ var e = document.querySelector({json.dumps(selector)}); if (!e) {{ return null; }} "
                    "var b = e.getBoundingClientRect(); return {x: b.left + scrollX, y: b.top + scrollY, w: b.width, "
                    "h: b.height}; })()")
        if not r:
            return False
        clip = {"x": r["x"], "y": r["y"], "width": r["w"], "height": min(r["h"], 9000), "scale": 1}
        data = self.cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True, "clip": clip},
                             self.s, timeout=120)["data"]
        SHOTS.joinpath(f"{name}.png").write_bytes(base64.b64decode(data))
        return True

    def pdf(self, path, landscape=True):
        data = self.cdp.send("Page.printToPDF", {"printBackground": True, "landscape": landscape,
                                                 "preferCSSPageSize": True}, self.s, timeout=120)["data"]
        path.write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.cdp.send("Browser.close", timeout=10)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


def show(b, tab):
    """One tab at full length: the clean morning for the Portfolio tab, and every step revealed on the Deal tab."""
    b.js("ADP.go && ADP.go(0, false)")
    if tab == "portfolio":
        b.js("ADP.setState('clean')")
    else:
        b.js(f"ADP.showTab({json.dumps(tab)})")
    if tab == "deal":
        b.js("ADP.reveal('model'); ADP.reveal('claims'); ADP.reveal('memo'); window.scrollTo(0, 0)")
    b.pause(0.6)


def readme_shots(b, url):
    """The README's pictures at 1440 by 900 and twice the pixel density with presenter mode's caption hidden, and the
    trace drawer two levels down from the fund's revenue to one day of the freight company's file. Returns what each
    one shows for the summary."""
    README_SHOTS.mkdir(parents=True, exist_ok=True)
    b.view(1440, 900, scale=2)
    b.load(url)
    done = {}
    for name, step, top in README_VIEWS:
        b.js(f"ADP.go(ADP.steps().indexOf({json.dumps(step)}), false)")
        b.pause(0.8)
        if top:
            for _ in range(2):
                b.js(TO_TOP_JS % json.dumps(top))
                b.pause(0.4)
        b.js("document.getElementById('presenter').hidden = true")
        b.pause(0.2)
        b.capture(README_SHOTS.joinpath(f"{name}.png"))
        done[name] = step
    b.js("ADP.go(ADP.steps().indexOf('run'), false); document.getElementById('presenter').hidden = true; "
         "window.scrollTo(0, 0)")
    b.pause(0.6)
    b.js("document.querySelector('#portfolio-body .tile .num').click()")
    b.pause(0.4)
    path = [b.js("document.getElementById('drawer-title').textContent")]
    for text in ("Kiskadee", ""):
        b.js(PICK_JS % json.dumps(text))
        b.pause(0.4)
        path.append(b.js("document.getElementById('drawer-title').textContent"))
    b.capture(README_SHOTS.joinpath("trace.png"))
    done["trace"] = " > ".join(p or "" for p in path)
    return done


def site_sha256():
    """Every file of the built page this run checks. Two builds of one seed write the same bytes, so a later step
    can tell the page it's about to send is the one Chrome saw."""
    return {p.relative_to(SITE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(SITE.rglob("*")) if p.is_file() and p.name != ".DS_Store"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the page in real Chrome and take its screenshots.")
    ap.add_argument("--chrome", help="the path to the Chrome program, if it isn't in the usual place")
    a = ap.parse_args(argv)
    shutil.rmtree(SHOTS, ignore_errors=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    url = SITE.joinpath("index.html").resolve().as_uri()
    checked = site_sha256()
    b = Browser(find_chrome(a.chrome))
    layout, t0 = {}, time.time()
    try:
        for width in WIDTHS:
            b.view(width, HEIGHTS[width])
            b.load(url)
            first = b.js("performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd")
            layout[f"first_paint_ms_{width}"] = round(first or 0)
            layout[f"fonts_{width}"] = b.js(FONTS_JS, wait=True)
            states = b.js("AD.meta.states")
            for name in states:
                b.js(f"ADP.setState({json.dumps(name)})")
                b.pause(0.25)
                b.shot(f"{width}-{name}", width)
                layout[f"{width}-{name}"] = b.js(LAYOUT_JS)
            b.js("ADP.setState('clean')")
            b.js("document.querySelector('#portfolio-body .tile .num').click()")
            b.pause(0.3)
            b.shot(f"{width}-drawer", width, full=False)
            b.js("document.getElementById('drawer-close').click()")
            b.js("ADP.runMorning()")
            b.pause(1.6)
            b.shot(f"{width}-replay", width, full=False)
            b.pause(4.0)
            for tab in TABS[1:]:
                show(b, tab)
                b.shot(f"{width}-tab-{tab}", width)
                layout[f"{width}-tab-{tab}"] = b.js(LAYOUT_JS)
            # the menu sits in the same place on every tab, and the code panes scroll on their own
            layout[f"menu_top_{width}"] = {tab: b.js(f"ADP.showTab({json.dumps(tab)}); window.scrollTo(0, 0); "
                                                    "Math.round(document.querySelector('#top .tabs').getBoundingClientRect().top)")
                                             for tab in TABS}
            layout[f"code_scrolls_{width}"] = b.js("ADP.showTab('how'); (function () { var p = document.querySelector('pre.code'), "
                                                  "t = document.querySelector('.code-tree'); return {code: p.scrollHeight > "
                                                  "p.clientHeight + 4, files: t.scrollHeight > t.clientHeight + 4}; })()")
            # the data room's files open whole in the drawer: the financials and the teaser with its claims marked
            for i, name in ((0, "financials"), (3, "teaser")):
                show(b, "deal")
                b.js(f"window.scrollTo(0, 0); document.querySelectorAll('.dfile')[{i}].click()")
                b.pause(0.4)
                b.shot(f"{width}-drawer-{name}", width, full=False)
                b.js("document.getElementById('drawer-close').click()")
            # presenter mode: exactly what the shared screen shows after each press of the right arrow
            b.load(url)
            steps = b.js("ADP.steps()") or []
            b.js("ADP.go(0, false)")
            for i, step in enumerate(steps):
                if i:
                    b.js(f"ADP.go({i}, true)")
                b.pause(5.4 if step == "run" else 1.2)
                b.shot(f"{width}-step{i + 1:02d}-{step}", width, full=False)
                layout[f"{width}-step{i + 1:02d}-{step}"] = b.js(LAYOUT_JS)
                if step == "how":
                    layout[f"arch_{width}"] = b.js(ARCH_JS)
        for width, height in SMALL:
            b.view(width, height, mobile=width < 500)
            b.load(url)
            for tab in TABS:
                show(b, tab)
                b.shot(f"{width}-tab-{tab}", width)
                layout[f"{width}-tab-{tab}"] = b.js(LAYOUT_JS)
        b.view(1440)
        b.load(url)
        b.js("ADP.setState('clean')")
        b.pause(0.3)
        b.pdf(OUTPUTS.joinpath("report.pdf"))
        for tab, name in (("deal", "memo.pdf"), ("board", "deck.pdf")):
            if b.js(f"!!document.querySelector('[data-tab-panel=\"{tab}\"]')"):
                b.js(f"ADP.showTab({json.dumps(tab)}); ADP.printMode && ADP.printMode({json.dumps(tab)})")
                b.pause(0.4)
                b.pdf(OUTPUTS.joinpath(name), landscape=(tab == "board"))
        # The 1280 layout scaled to the 1200 by 630 a link card wants, so the control row stays on one line. It starts
        # from presenter mode's run step, so the morning's button reads the way it does after a run.
        b.cdp.send("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 672, "deviceScaleFactor": 0.9375,
                                                          "mobile": False}, b.s)
        b.load(url)
        b.js("ADP.go(ADP.steps().indexOf('run'), false); document.getElementById('presenter').hidden = true; "
             "window.scrollTo(0, 0)")
        b.pause(0.4)
        PREVIEW.write_bytes(base64.b64decode(b.cdp.send("Page.captureScreenshot", {"format": "png"}, b.s, timeout=120)["data"]))
        try:
            layout["readme_shots"] = readme_shots(b, url)
        except Exception as err:  # noqa: BLE001  (a miss here shouldn't cost the rest of the run's report)
            layout["readme_shots"] = {"error": f"{type(err).__name__}: {err}"}
        preview = routing_preview()
        if preview:
            for width, height in ((1440, 900), (1280, 720), (768, 1024), (390, 844)):
                b.view(width, height, mobile=width < 500)
                b.load(preview)
                b.js("ADP.showTab('how')")
                b.pause(0.5)
                b.shot_of(f"{width}-preview-routing", "#how-routing")
                layout[f"{width}-preview-routing"] = b.js(LAYOUT_JS)
                layout[f"labels_{width}"] = b.js(LABELS_JS)
                if width in HEIGHTS:
                    b.js("ADP.go(ADP.steps().indexOf('routing'), false)")
                    b.pause(1.2)
                    b.shot(f"{width}-preview-step-routing", width, full=False)
    finally:
        b.close()
    not_file = [u for u in b.requests if not u.startswith(("file:", "data:", "blob:", "about:"))]
    OUT.joinpath("layout.json").write_text(json.dumps(layout, indent=1))
    OUT.joinpath("console.json").write_text(json.dumps(b.console, indent=1))
    OUT.joinpath("network.json").write_text(json.dumps(b.requests, indent=1))
    screens = {k: v for k, v in layout.items() if isinstance(v, dict) and "lines" in v}
    ours = {k: [x for x in v["lines"] if not x.get("agent")] for k, v in screens.items()}
    ours = {k: v for k, v in ours.items() if v}
    agents = sum(1 for v in screens.values() for x in v["lines"] if x.get("agent"))
    overlaps = {k: v["overlaps"] for k, v in screens.items() if v["overlaps"]}
    wide = [k for k, v in screens.items() if v["wider_than_window"]]
    summary = {"seconds": round(time.time() - t0, 1), "screens": len(list(SHOTS.glob("*.png"))),
               "console_errors": len(b.console), "requests_not_file": not_file,
               "fonts": {k: v for k, v in layout.items() if k.startswith("fonts_")}, "spills_in_our_copy": ours,
               "spills_in_agent_text": agents,
               "menu_tops": {k: v for k, v in layout.items() if k.startswith("menu_top")},
               "code_scrolls": {k: v for k, v in layout.items() if k.startswith("code_scrolls")},
               "chart_label_collisions": {k: v["collisions"] for k, v in layout.items()
                                          if k.startswith("labels_") and v["collisions"]},
               "chart_labels_hidden": {k: v["hidden"] for k, v in layout.items() if k.startswith("labels_") and v["hidden"]},
               "overlaps": overlaps, "wider_than_window": wide,
               "first_paint_ms": {k: v for k, v in layout.items() if k.startswith("first_paint")},
               "arch_boxes": {k: v for k, v in layout.items() if k.startswith("arch_")},
               "readme_shots": layout.get("readme_shots", {}), "site_sha256": checked}
    OUT.joinpath("browser_check.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: (v if k not in ("spills_in_our_copy", "overlaps", "site_sha256") else len(v))
                      for k, v in summary.items()}, indent=1))
    print(f"Screenshots are in {SHOTS}, and the README's pictures are in {README_SHOTS}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
