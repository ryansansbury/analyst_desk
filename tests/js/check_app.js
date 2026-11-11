/* The node check. It runs the built page's own script against a small DOM (dom.js), goes
   through every precomputed state, opens every figure's trace and every input inside it, and clicks the controls.
   It prints one JSON report, and tests/test_page.py fails on any check that doesn't pass.

       node tests/js/check_app.js <site folder>

   It can't see layout, color or real timing. scripts/screenshots.sh covers those in Chrome. */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const {Document} = require("./dom.js");

const SITE = path.resolve(process.argv[2]);
const report = {checks: [], errors: []};
function check(name, ok, detail) {
  report.checks.push({name: name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 400)});
}

const doc = new Document(fs.readFileSync(path.join(SITE, "index.html"), "utf8"));
check("index.html parses with every tag closed", doc.errors.length === 0, doc.errors.slice(0, 5).join("; "));
const timers = [];
const win = {document: doc, innerWidth: 1440, innerHeight: 900, addEventListener() {}, print() {},
  setTimeout(fn, ms) { timers.push(fn); return timers.length; }, clearTimeout(id) { timers[id - 1] = null; },
  location: {hash: "", pathname: "/analyst-desk/", search: ""},
  history: {replaceState(s, t, url) { const i = String(url).indexOf("#"); win.location.hash = i >= 0 ? String(url).slice(i) : ""; }},
  scrollTo() {}};
win.window = win;
/* the figures the build wrote on the Hours tab, before the page's script recalculates them */
const builtHours = {};
for (const k of ["week", "today", "manual", "review", "total"]) {
  const el = doc.querySelector("[data-out=\"" + k + "\"]");
  builtHours[k] = el ? el.textContent : null;
}
const ctx = vm.createContext(win);
try {
  vm.runInContext(fs.readFileSync(path.join(SITE, "data.js"), "utf8"), ctx, {filename: "data.js"});
  vm.runInContext(fs.readFileSync(path.join(SITE, "code.js"), "utf8"), ctx, {filename: "code.js"});
  vm.runInContext(fs.readFileSync(path.join(SITE, "app.js"), "utf8"), ctx, {filename: "app.js"});
} catch (e) {
  report.errors.push("the page's script threw: " + (e && e.stack || e));
}
const AD = win.AD, ADP = win.ADP;
function flush() {
  for (let guard = 0; guard < 200 && timers.some(Boolean); guard++) {
    const i = timers.findIndex(Boolean), fn = timers[i];
    timers[i] = null;
    fn();
  }
}
const click = (el) => doc.dispatch("click", el);

if (ADP && AD) {
  check("the page opens before the run", ADP.state() === "pre");
  const states = AD.meta.states;
  check("every state the controls name exists", ["pre", "clean", "E1", "E2", "E3", "E4", "E5", "E6", "L1", "L2", "L3",
    "intake"].every((s) => states.indexOf(s) >= 0), states.join(","));
  let opened = 0;
  for (const name of states) {
    const ok = ADP.setState(name);
    check("state " + name + " renders", ok && doc.getElementById("portfolio-body").innerHTML.length > 200);
    const figures = doc.querySelectorAll("#portfolio-body [data-ref], #strip [data-ref]");
    const missing = figures.map((b) => b.getAttribute("data-ref")).filter((r) => !AD.traces[r]);
    check("every figure in " + name + " has a trace", missing.length === 0, missing.slice(0, 5).join(", "));
    const bad = [];
    for (const b of figures.slice(0, 400)) {
      const ref = b.getAttribute("data-ref");
      try {
        ADP.openTrace(ref);
        opened++;
        const body = doc.getElementById("drawer-body").innerHTML;
        if (!body || body.indexOf("No trace") >= 0) { bad.push(ref); }
        for (const inner of doc.querySelectorAll("#drawer-body [data-ref]").slice(0, 6)) {
          const r2 = inner.getAttribute("data-ref");
          if (!AD.traces[r2]) { bad.push(ref + " -> " + r2); }
        }
      } catch (e) { bad.push(ref + ": " + e); }
    }
    check("every trace in " + name + " opens, and so does every input inside it", bad.length === 0, bad.slice(0, 4).join("; "));
  }
  check("the drawer opened traces", opened > 100, opened);

  ADP.setState("pre");
  const run = doc.getElementById("run");
  check("the strip sits at the top of the Portfolio tab, below the menu",
    !!doc.querySelector("[data-tab-panel=\"portfolio\"] #strip") && !doc.querySelector("#top #strip"));
  check("the Run button carries all three labels in place", run.querySelectorAll("[data-lbl]").length === 3 &&
    run.getAttribute("data-mode") === "run");
  click(run);
  check("Run the morning starts the replay, and the same button now skips", run.getAttribute("data-mode") === "skip" &&
    ADP.state() === "pre" && doc.getElementById("skip") === null);
  flush();
  check("the replay ends on the clean morning", ADP.state() === "clean" && run.getAttribute("data-mode") === "replay");
  click(run);
  click(run);
  check("Skip jumps straight to the result", ADP.state() === "clean" && run.getAttribute("data-mode") === "replay");

  const menuButton = doc.querySelector(".menu .btn");
  click(menuButton);
  check("a menu opens", !doc.querySelector(".menu-list").hidden);
  click(doc.querySelector("[data-state=\"E1\"]"));
  check("Plant an error switches state and closes the menu", ADP.state() === "E1" && doc.querySelector(".menu-list").hidden);
  check("the planted state is held", doc.getElementById("portfolio-body").innerHTML.indexOf("banner held") >= 0);
  click(doc.querySelector("[data-state=\"intake\"]"));
  check("New file arrives shows the intake panel", doc.getElementById("portfolio-body").innerHTML.indexOf("panel intake") >= 0);
  click(doc.getElementById("reset"));
  check("Reset returns to before the run", ADP.state() === "pre");
  check("and the run strip keeps its five steps", doc.querySelectorAll("#strip .step").length === 5 &&
    doc.querySelectorAll("#strip .step").every((s) => !s.hidden));

  ADP.setState("clean");
  const derived = doc.querySelectorAll("#portfolio-body [data-ref]").find((b) => (AD.traces[b.getAttribute("data-ref")] || {}).k === "derived");
  click(derived);
  check("a click on a figure opens the drawer", !doc.getElementById("drawer").hidden);
  const input = doc.querySelector("#drawer-body [data-ref]");
  if (input) {
    click(input);
    check("an input inside the drawer opens its own trace with a way back", doc.getElementById("drawer-body").innerHTML.indexOf("crumbs") >= 0);
    const crumbLabels = doc.querySelectorAll("#drawer-body [data-crumb]").map((b) => b.textContent);
    check("each crumb names what changed, so no two read the same", crumbLabels.length === 2 && crumbLabels[0] !== crumbLabels[1]);
    click(doc.querySelector("[data-crumb=\"0\"]"));
    check("the way back returns to the first trace", doc.getElementById("drawer-title").textContent === ADP.traceHtml(derived.getAttribute("data-ref")).title);
  }
  doc.dispatch("keydown", doc.body, {key: "Escape"});
  check("Escape closes the drawer", doc.getElementById("drawer").hidden);

  /* the Deal tab */
  click(doc.querySelector("[data-tab=\"deal\"]"));
  check("the Deal tab opens on the data room", doc.querySelector("[data-tab-panel=\"deal\"]").classList.contains("active") &&
    doc.querySelector("[data-step=\"model\"]").hidden);
  click(doc.querySelector("[data-reveal=\"model\"]"));
  check("Build the model reveals the assumptions and the model", doc.querySelectorAll("[data-step=\"model\"]").every((s) => !s.hidden));
  const moic = doc.querySelector("td[data-cell=\"Returns!C16\"]");
  click(moic);
  check("a cell shows its formula in the formula bar", doc.getElementById("fx-text").innerHTML.indexOf("C15") >= 0 &&
    doc.getElementById("fx-cell").textContent === "Returns!C16");
  const link = doc.querySelector("td[data-cell=\"Returns!C11\"]");
  click(link);
  const ref = doc.querySelector("#fx-text [data-goto]");
  click(ref);
  check("a reference in a formula jumps to its cell on another sheet", doc.getElementById("fx-cell").textContent === "Projections!H15" &&
    doc.querySelector("[data-sheet-pane=\"Projections\"]").classList.contains("active"));
  const inputCell = doc.querySelector("td[data-trace]");
  click(inputCell);
  const trace = doc.querySelector("#fx-trace [data-ref]");
  check("an input cell from the ledger offers its trace", !!trace && !!AD.traces[trace.getAttribute("data-ref")]);
  click(trace);
  check("and the trace opens in the drawer", !doc.getElementById("drawer").hidden);
  doc.dispatch("keydown", doc.body, {key: "Escape"});
  const cells = doc.querySelectorAll("td[data-trace]");
  const untraced = cells.map((c) => c.getAttribute("data-trace")).filter((r) => !AD.traces[r]);
  check("every model cell from the ledger has a trace", cells.length > 100 && untraced.length === 0, untraced.slice(0, 3).join(", "));
  click(doc.querySelector("[data-reveal=\"claims\"]"));
  check("Check the teaser's claims reveals two contradicted and one supported",
    doc.querySelector("[data-step=\"claims\"]").innerHTML.split("note s-flag").length - 1 === 2 &&
    doc.querySelector("[data-step=\"claims\"]").innerHTML.split("note s-pass").length - 1 === 1);
  click(doc.querySelector("[data-reveal=\"memo\"]"));
  check("Draft the memo reveals the memo with its gate passing",
    !doc.querySelector("[data-step=\"memo\"]").hidden && !doc.getElementById("gate-pass").hidden &&
    doc.getElementById("gate-pass").className.indexOf("pass") >= 0);
  const memoRefs = doc.querySelectorAll("#memo-clean [data-ref]");
  check("every figure in the memo opens a trace", memoRefs.length > 40 && memoRefs.every((b) => !!AD.traces[b.getAttribute("data-ref")]),
    memoRefs.length);
  click(doc.getElementById("inject"));
  check("Inject an unsupported number fails the gate at its location", !doc.getElementById("gate-fail").hidden &&
    doc.getElementById("gate-pass").hidden && doc.getElementById("memo-injected").innerHTML.indexOf("<mark") >= 0 &&
    doc.getElementById("gate-fail").innerHTML.indexOf("61.2") >= 0);
  click(doc.getElementById("uninject"));
  check("Remove it passes the gate again", doc.getElementById("gate-fail").hidden && !doc.getElementById("gate-pass").hidden &&
    !doc.getElementById("memo-clean").hidden);
  check("print mode shows the memo on its own", ADP.printMode("deal") && doc.body.classList.contains("print-memo"));
  ADP.printMode("none");
  click(doc.getElementById("reset"));
  check("Reset hides the deal's steps again", doc.querySelector("[data-step=\"model\"]").hidden);

  /* the data room's files open in the drawer */
  click(doc.querySelector("[data-tab=\"deal\"]"));
  const roomFiles = doc.querySelectorAll(".dfile");
  const previewed = roomFiles.filter((b) => { click(b); const h = doc.getElementById("drawer-body").innerHTML;
    return !doc.getElementById("drawer").hidden && h.indexOf("excerpt") >= 0; });
  check("every data room file opens with a look at the file", roomFiles.length === 4 && previewed.length === 4,
    previewed.length);
  click(roomFiles[3]);
  check("the teaser opens with its three claims marked",
    doc.getElementById("drawer-body").innerHTML.split("class=\"hit\"").length - 1 === 3);
  doc.dispatch("keydown", doc.body, {key: "Escape"});
  click(doc.querySelector("[data-tab=\"portfolio\"]"));

  /* the code section */
  const codeFiles = Object.keys(win.AD_CODE.files);
  check("the code section opens on the gate with line numbers and color",
    doc.getElementById("code-path").textContent === "engine/gate.py" &&
    doc.getElementById("code-body").innerHTML.indexOf("class=\"ln\"") >= 0 &&
    doc.getElementById("code-body").innerHTML.indexOf("hl-k") >= 0);
  check("it holds only the thirteen excerpts, each marked as a copy", codeFiles.length === 13 &&
    codeFiles.indexOf("agents/replay.py") >= 0 && codeFiles.every((f) => /^(engine|agents|generate|prompts)\//.test(f) &&
    /^(# An excerpt|<!-- A copy)/.test(win.AD_CODE.files[f])), codeFiles.length);
  click(doc.querySelector(".cfeat[data-file=\"agents/replay.py\"]"));
  check("a featured file opens with its note", doc.getElementById("code-path").textContent === "agents/replay.py" &&
    doc.getElementById("code-note").textContent.length > 10);
  click(doc.querySelector(".code-file[data-file=\"engine/ledger.py\"]"));
  check("a file in the tree opens", doc.getElementById("code-path").textContent === "engine/ledger.py");
  const gateBox = doc.querySelector(".abox[data-code=\"engine/gate.py\"]");
  click(gateBox);
  check("a box in the diagram opens its code", !!gateBox && doc.getElementById("code-path").textContent === "engine/gate.py");
  const bad = codeFiles.filter((f) => { try { ADP.codeHtml(win.AD_CODE.files[f], f); return false; } catch (e) { return true; } });
  check("every file renders", bad.length === 0, bad.slice(0, 3).join(", "));
  const sample = ADP.codeHtml("x = '<b>' # <i>\n", "t.py");
  check("code is shown as text, never as markup", sample.indexOf("<b>") < 0 && sample.indexOf("&lt;b&gt;") >= 0);

  /* the Upload panel */
  click(doc.getElementById("upload"));
  const upPanel = doc.getElementById("upload-panel"), upDefault = upPanel.getAttribute("data-default");
  check("Try a new layout opens the panel on its default layout", !upPanel.hidden &&
    !doc.querySelector("[data-upload-detail=\"" + upDefault + "\"]").hidden);
  const chips = doc.querySelectorAll("[data-upload]");
  const other = chips.map((c) => c.getAttribute("data-upload")).find((id) => id !== upDefault);
  click(doc.querySelector("[data-upload=\"" + other + "\"]"));
  check("picking another layout shows only that one", chips.length >= 12 &&
    !doc.querySelector("[data-upload-detail=\"" + other + "\"]").hidden &&
    doc.querySelector("[data-upload-detail=\"" + upDefault + "\"]").hidden &&
    doc.querySelectorAll("[data-upload-detail]").filter((d) => !d.hidden).length === 1);
  click(doc.getElementById("upload-close"));
  check("Close hides the panel", upPanel.hidden);
  click(doc.getElementById("upload"));
  click(doc.getElementById("reset"));
  check("Reset hides it too", upPanel.hidden);

  /* the Hours tab and the header */
  const out = (k) => (doc.querySelector("[data-out=\"" + k + "\"]") || {}).textContent;
  check("the page's hours math agrees with the build's", ["week", "today", "manual", "review", "total"].every((k) =>
    builtHours[k] !== null && out(k) === builtHours[k]), JSON.stringify(builtHours));
  check("the header's hours back today waits for the run", doc.getElementById("hours-today").hidden);
  ADP.setState("clean");
  check("and shows once the morning has run", !doc.getElementById("hours-today").hidden);
  const deal = doc.querySelector("tr[data-row=\"deal_model\"]");
  const base = deal.querySelector("[data-k=\"baseline\"]");
  const before = parseFloat(out("week")), backBefore = parseFloat(deal.querySelector("[data-out=\"back\"]").textContent);
  base.value = String(parseFloat(base.value) + 4);
  doc.dispatch("input", base);
  check("a changed estimate recalculates the row, the total and the tiles",
    Math.abs(parseFloat(deal.querySelector("[data-out=\"back\"]").textContent) - (backBefore + 4)) < 0.051 &&
    Math.abs(parseFloat(out("week")) - (before + 4)) < 0.051 && out("total") === out("week"), out("week"));
  const bar = doc.querySelector("[data-bar=\"deal_model\"] [data-out=\"bar-manual\"]");
  check("and the bars follow", !!bar && bar.style.width === "100.0%", bar && bar.style.width);
  base.value = String(parseFloat(base.value) - 4);
  doc.dispatch("input", base);
  check("putting it back restores the build's figures", out("week") === builtHours.week);

  /* model routing */
  const rp = doc.getElementById("how-routing");
  check("the routing panel has its chart, one ringed dot, and a route for each of the five agents", !!rp &&
    rp.querySelectorAll(".sc-pt").length >= 2 && rp.querySelectorAll(".sc-pt.on").length === 1 &&
    rp.querySelectorAll(".sc-lbl").length === rp.querySelectorAll(".sc-pt").length &&
    rp.querySelectorAll("table.routes tbody tr").length === 5);
  const dot = rp && rp.querySelector(".sc-pt"), tipEl = doc.getElementById("tip");
  doc.dispatch("focusin", dot);
  const focused = !tipEl.hidden && tipEl.textContent === dot.getAttribute("data-tip");
  doc.dispatch("focusout", dot);
  check("a dot's tip shows on keyboard focus as it does on hover, and goes on blur", focused && tipEl.hidden);
  const spot = (taken, x, force) => String(ADP.labelSpot(x || 50, 50, 40, 16, 300, 200, taken, force));
  check("a scatter label sits right of its dot when that side is free", spot([]) === "60,42", spot([]));
  check("it moves left when another label holds the right", spot([{l: 58, t: 40, r: 120, b: 60}]) === "0,42");
  check("and it stays inside the plot at the right edge", spot([], 290) === "240,42", spot([], 290));
  const full = [{l: 0, t: 0, r: 300, b: 200}];
  check("a crowded label gives way, and the ringed one is placed anyway", spot(full) === "null" &&
    spot(full, 50, true) === "60,42", spot(full) + " " + spot(full, 50, true));

  /* presenter mode */
  const steps = ADP.steps();
  const key = (k, target) => doc.dispatch("keydown", target || doc.body, {key: k});
  const panel = (t) => doc.querySelector("[data-tab-panel=\"" + t + "\"]").classList.contains("active");
  const shown = (sel) => { const el = doc.querySelector(sel); return !!el && !el.hidden; };
  const last = steps.length - 1;
  check("presenter mode has a step for every beat, each with a label", steps.length >= 17 &&
    steps.every((s) => !!AD.ui["presenter.s." + s]), steps.join(","));
  key("r");
  check("R resets to the first step", ADP.step() === 0 && ADP.state() === "pre" && panel("portfolio"));
  const expect = {
    run: () => ADP.state() === "clean",
    error: () => ADP.state() === "E1" && doc.getElementById("portfolio-body").innerHTML.indexOf("banner held") >= 0,
    lookalike: () => ADP.state() === "L1",
    intake: () => ADP.state() === "intake",
    upload: () => shown("#upload-panel") && shown("[data-upload-detail=\"" + doc.getElementById("upload-panel").getAttribute("data-default") + "\"]"),
    deal: () => panel("deal") && doc.querySelector("[data-step=\"model\"]").hidden,
    model: () => panel("deal") && shown(".modelview"),
    returns: () => doc.getElementById("fx-cell").textContent === "Returns!C20",
    checks: () => doc.querySelector("[data-sheet-pane=\"Checks\"]").classList.contains("active"),
    claims: () => shown("[data-step=\"claims\"]"),
    memo: () => shown("[data-step=\"memo\"]") && shown("#gate-pass"),
    gate: () => shown("#gate-fail") && !shown("#gate-pass"),
    pass: () => !shown("#gate-fail") && shown("#gate-pass"),
    board: () => panel("board"),
    hours: () => panel("hours"),
    how: () => panel("how"),
    routing: () => panel("how") && doc.scrolled[doc.scrolled.length - 1] === doc.getElementById("how-routing"),
    code: () => panel("how") && doc.getElementById("code-path").textContent === win.AD_CODE.default,
    results: () => panel("how"),
    plan: () => panel("how"),
  };
  const wrong = [];
  for (let i = 1; i < steps.length; i++) {
    key("ArrowRight");
    flush();
    if (ADP.step() !== i || !(expect[steps[i]] || (() => false))()) { wrong.push(i + " " + steps[i]); }
  }
  check("the right arrow walks every step into its exact state", wrong.length === 0, wrong.join("; "));
  check("each step's address is remembered for a reload", win.location.hash === "#step-" + steps.length, win.location.hash);
  check("the step shows in the corner", doc.querySelector("#presenter .pn").textContent === "Step " + steps.length + " of " + steps.length &&
    doc.querySelector("#presenter .pl").textContent === AD.ui["presenter.s." + steps[last]]);
  key("ArrowRight");
  check("the right arrow stops at the last step, on the plan", ADP.step() === last && panel("how") &&
    steps[last] === "plan" && doc.scrolled[doc.scrolled.length - 1] === doc.getElementById("how-plan"));
  key("ArrowLeft");
  check("the left arrow steps back into the earlier state", ADP.step() === last - 1 && shown("[data-step=\"memo\"]"));
  const backWrong = [];
  for (let i = steps.length - 1; i >= 0; i--) {
    ADP.go(i, false);
    flush();
    if (i > 0 && !(expect[steps[i]] || (() => false))()) { backWrong.push(i + " " + steps[i]); }
  }
  check("every step opens directly, as a deep link does", backWrong.length === 0, backWrong.join("; "));
  check("step one is the page before the run", ADP.state() === "pre" && panel("portfolio") &&
    doc.querySelector("[data-step=\"model\"]").hidden && doc.getElementById("hours-today").hidden &&
    !doc.getElementById("strip").hidden && doc.querySelectorAll("#strip .step").every((s) => !s.hidden));
  /* Two smooth scrolls in a row race in Chrome, and the first can win. So each step scrolls once, to its own place,
     whether the right arrow moves to it or a link opens it and the steps before it replay. */
  const scrollsTo = (step, live) => {
    ADP.go(steps.indexOf(step) - 1, false);
    const from = doc.scrolled.length;
    ADP.go(steps.indexOf(step), live);
    return doc.scrolled.slice(from).filter((el) => el.localName !== "td");
  };
  const once = {returns: ".modelview", checks: ".modelview", gate: "#gate-fail", pass: "#gate-pass", claims: "[data-step=\"claims\"]"};
  const raced = [];
  for (const step of Object.keys(once)) {
    for (const live of [true, false]) {
      const moved = scrollsTo(step, live);
      if (moved.length !== 1 || moved[0] !== doc.querySelector(once[step])) {
        raced.push(step + (live ? " by the arrow " : " by a link ") + moved.map((el) => el.id || el.className).join(","));
      }
    }
  }
  check("each step scrolls once, so no two scrolls race to place the page", raced.length === 0, raced.join("; "));
  ADP.go(steps.indexOf("returns"), false);
  const sheets = doc.querySelector(".sheets");
  sheets.scrollTop = 140;
  click(doc.querySelector(".sheet-tab[data-sheet=\"Checks\"]"));
  check("a sheet opens at its top, wherever the last one was scrolled", sheets.scrollTop === 0);
  ADP.go(11, false);
  key("ArrowRight", doc.querySelector("table.hours input"));
  check("arrow keys inside an input stay in the input", ADP.step() === 11);
  doc.dispatch("keydown", doc.body, {key: "ArrowRight", metaKey: true});
  check("arrow keys with a modifier are left to the browser", ADP.step() === 11);
  click(doc.getElementById("reset"));
  check("the Reset button resets presenter mode too", ADP.step() === 0 && win.location.hash === "#step-1");
  ADP.go(8, false);
  ADP.openTrace(Object.keys(AD.traces)[0]);
  const home = doc.querySelector("[data-home]");
  check("the header's mark links to the page itself", !!home && home.getAttribute("href") === "index.html" &&
    !!home.getAttribute("aria-label"));
  click(home);
  check("and a click on it goes back to the start", ADP.step() === 0 && ADP.state() === "pre" && panel("portfolio") &&
    doc.getElementById("drawer").hidden && doc.getElementById("presenter").hidden && win.location.hash === "");
}

process.stdout.write(JSON.stringify(report) + "\n");
