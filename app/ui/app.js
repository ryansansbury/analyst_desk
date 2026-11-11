/* Analyst Desk. The page script: tabs, the precomputed states, the "Run the morning" replay, the trace drawer,
   hover tips, the CSV export and the line rule. Everything it shows comes from window.AD, which the build wrote,
   so no click waits on anything and nothing reaches the network. Pure helpers sit on window.ADP for the node check. */
(function () {
  "use strict";
  var win = window, doc = document;
  var AD = win.AD || {}, S = AD.states || {}, T = AD.traces || {}, U = AD.ui || {};
  var ADP = win.ADP = {};
  var state = {name: "pre", ran: false, timer: null, stack: []};
  /* True while presenter mode replays the steps before the one a link or the left arrow opens. Those steps set up
     the state without scrolling, so only the last one scrolls and no two smooth scrolls race to place the page. */
  var QUIET = false;

  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[c];
    });
  }
  function capital(s) { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); }
  function $(sel, root) { return (root || doc).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(sel)); }
  function word(key, fill) {
    var s = U[key] || "";
    Object.keys(fill || {}).forEach(function (k) { s = s.split("{" + k + "}").join(fill[k]); });
    return s;
  }
  ADP.esc = esc;

  /* ------------------------------------------------------------------ the trace drawer's contents */
  function excerptHtml(x, column) {
    if (!x || x.kind === "none") { return ""; }
    if (column !== undefined && column !== null) { x = Object.assign({}, x, {column: column}); }
    if (x.kind === "missing") { return "<p class=\"muted\">The file isn't in this state.</p>"; }
    if (x.kind === "text") {
      return "<div class=\"excerpt\"><pre>" + x.lines.map(function (l) {
        return "<span class=\"" + (l.hit ? "hit" : "") + "\">" + esc(String(l.n).padStart(3, " ") + "  " + l.text) + "</span>";
      }).join("\n") + "</pre></div>";
    }
    if (x.kind === "cell") {
      return "<div class=\"excerpt\"><table><tr><th>" + esc(x.sheet) + "!" + esc(x.cell) + "</th><th>" + esc(x.column_label || "") +
        "</th></tr><tr><td>" + esc(x.row_label || "") + "</td><td class=\"hit\">" + esc(x.value) + "</td></tr></table></div>";
    }
    var head = x.header || [], col = -1;
    if (x.kind === "csv" && x.column) { col = head.indexOf(x.column); }
    if (x.kind === "xlsx" && x.letters) { col = x.letters.indexOf(x.column); }
    var rows = (x.rows || []).map(function (r) {
      var cells = r.cells.map(function (c, j) {
        return "<td class=\"" + (j === col && r.hit ? "hit" : "") + "\">" + esc(c) + "</td>";
      }).join("");
      return "<tr class=\"" + (r.hit ? "hit" : "") + "\"><td class=\"rn\">" + esc(r.n) + "</td>" + cells + "</tr>";
    });
    if (x.skipped) {
      var at = x.preview ? rows.length : x.kind === "xlsx" ?
        Math.max(0, rows.length - ((x.rows[x.rows.length - 1] || {}).total ? 2 : 1)) : rows.length - 1;
      rows.splice(at, 0, "<tr class=\"gap\"><td></td><td colspan=\"" + head.length + "\">" + esc(word("drawer.more", {n: x.skipped})) +
        "</td></tr>");
    }
    return "<div class=\"excerpt\"><table><thead><tr><th class=\"rn\">" + (x.header_row ? esc(x.header_row) : "") + "</th>" +
      head.map(function (h) { return "<th>" + esc(h) + "</th>"; }).join("") + "</tr></thead><tbody>" + rows.join("") +
      "</tbody></table></div>";
  }
  function checksHtml(refs) {
    var items = (refs || []).map(function (r) { return T[r]; }).filter(Boolean);
    if (!items.length) { return ""; }
    return "<section><h3>" + esc(U["drawer.checks"]) + "</h3><ul class=\"notes\">" + items.map(function (c) {
      return "<li class=\"note s-" + esc(c.status) + "\"><span>" + (c.status === "pass" ? "✓" : c.status === "flag" ? "!" : "i") +
        "</span><span><strong>" + esc(c.title) + "</strong> · " + esc(c.status_label) + (c.html ? ". " + c.html : "") + "</span></li>";
    }).join("") + "</ul></section>";
  }
  function traceHtml(ref) {
    var t = T[ref];
    if (!t) { return {title: "", value: "", body: "<p class=\"muted\">No trace for " + esc(ref) + ".</p>"}; }
    var body = "";
    if (t.k === "fact") {
      var s = t.source || {};
      body += "<section><h3>" + esc(U["drawer.source"]) + "</h3><dl><dt>File</dt><dd><code>" + esc(s.name) + "</code></dd><dt>" +
        esc(U["drawer.fingerprint"]) + "</dt><dd><code>" + esc(s.sha) + "</code></dd><dt>" + esc(U["drawer.received"]) + "</dt><dd>" +
        esc(s.morning) + "</dd><dt>" + esc(U["drawer.layout"]) + "</dt><dd>" + esc(s.layout || "") + "</dd></dl>" +
        (s.status === "quarantined" ? "<p class=\"quarantine\">" + esc(U["drawer.quarantined"]) + "</p>" : "") + "</section>";
      body += "<section><h3>" + esc(U["drawer.location"]) + "</h3><p><code>" + esc(t.locator) + "</code></p>" +
        excerptHtml((AD.excerpts || {})[t.x], t.col) + "</section>";
      body += "<section><h3>" + esc(U["drawer.steps"]) + "</h3><ol class=\"steps-list\">" + t.steps.map(function (x) {
        return "<li>" + esc(capital(x)) + "</li>"; }).join("") + "</ol></section>";
      body += checksHtml(t.checks);
    } else if (t.k === "derived") {
      body += "<section><h3>" + esc(U["drawer.steps"]) + "</h3><ol class=\"steps-list\">" + t.steps.map(function (x) {
        return "<li>" + esc(capital(x)) + "</li>"; }).join("") + "</ol></section>";
      if (t.inputs && t.inputs.length) {
        body += "<section><h3>" + esc(U["drawer.inputs"]) + "</h3><ul class=\"inputs\">" + t.inputs.map(function (r) {
          var i = T[r];
          if (!i) { return ""; }
          var label = i.k === "check" ? i.title + ", " + i.status_label : i.title + (i.period ? ", " + i.period : "");
          var shownText = i.k === "fact" || i.k === "derived" ? i.shown : i.k === "source" ? i.morning : i.who;
          return "<li><span>" + esc(label) + "</span><button type=\"button\" class=\"num\" data-ref=\"" + esc(r) + "\">" +
            esc(shownText || "") + "</button></li>";
        }).join("") + (t.more ? "<li><span>" + esc(word("drawer.more", {n: t.more})) + "</span><span></span></li>" : "") +
          "</ul></section>";
      }
      body += checksHtml(t.checks);
    } else if (t.k === "check") {
      body += "<section><p><strong>" + esc(t.status_label) + "</strong> · " + esc(t.who) + "</p><p>" + (t.html || "") + "</p></section>";
    } else if (t.k === "source") {
      body += "<section><dl><dt>File</dt><dd><code>" + esc(t.title) + "</code></dd><dt>" + esc(U["drawer.fingerprint"]) +
        "</dt><dd><code>" + esc(t.sha) + "</code></dd>" +
        (t.morning ? "<dt>" + esc(U["drawer.received"]) + "</dt><dd>" + esc(t.morning) + "</dd>" : "") + "<dt>" +
        esc(U["drawer.layout"]) + "</dt><dd>" + esc(t.layout || "") + "</dd></dl>" +
        (t.status === "quarantined" ? "<p class=\"quarantine\">" + esc(U["drawer.quarantined"]) + "</p>" : "") + "</section>";
      if (t.x) { body += "<section><h3>" + esc(U["drawer.preview"]) + "</h3>" + excerptHtml((AD.excerpts || {})[t.x]) + "</section>"; }
    } else if (t.k === "claim") {
      body += "<section><p>" + esc(t.title) + "</p></section>";
    }
    var title = t.title + (t.period ? ", " + t.period : "");
    return {title: title, value: t.shown || (t.k === "check" ? t.title : ""), body: body};
  }
  ADP.traceHtml = traceHtml;
  ADP.excerptHtml = excerptHtml;

  /* Each crumb after the first names only what changed from the one before it, so a walk from the fund to one company
     to one day reads "Revenue, the fund", "Kiskadee Freight", "November 1, 2026" instead of the same word three
     times. */
  function crumbParts(t) {
    var parts = String(t.title || "").split(", ");
    if (t.period) { parts.push(t.period); }
    return parts;
  }
  function crumbLabel(i) {
    var r = state.stack[i], t = T[r] || {};
    if (i === 0) { return t.title || r; }
    var before = crumbParts(T[state.stack[i - 1]] || {});
    var changed = crumbParts(t).filter(function (p, j) { return p !== before[j]; });
    return changed.length ? changed.join(", ") : t.title || r;
  }
  function crumbs() {
    if (state.stack.length < 2) { return ""; }
    return "<div class=\"crumbs\">" + state.stack.map(function (r, i) {
      return "<button type=\"button\" data-crumb=\"" + i + "\">" + esc(crumbLabel(i)) + "</button>";
    }).join("") + "</div>";
  }
  function openTrace(ref, keep) {
    if (!keep) { state.stack = []; }
    state.stack.push(ref);
    var d = $("#drawer"), h = traceHtml(ref), kicker = $("#drawer .kicker");
    if (kicker) { kicker.textContent = (T[ref] || {}).k === "source" ? U["drawer.kicker.file"] : U["drawer.kicker"]; }
    $("#drawer-title").textContent = h.title;
    $("#drawer-value").textContent = h.value;
    $("#drawer-body").innerHTML = crumbs() + h.body;
    d.hidden = false;
    $("#drawer-body").scrollTop = 0;
    rebalance();
  }
  function closeTrace() { $("#drawer").hidden = true; state.stack = []; }
  ADP.openTrace = openTrace;

  /* ------------------------------------------------------------------ states */
  function setState(name) {
    var s = S[name];
    if (!s) { return false; }
    state.name = name;
    $("#portfolio-body").innerHTML = s.portfolio;
    $("#strip").innerHTML = s.strip;
    $$(".controls [data-state]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-state") === name); });
    $("#run").setAttribute("data-mode", state.ran ? "replay" : "run");
    var today = $("#hours-today");
    if (today) { today.hidden = name === "pre"; }
    headerPad();
    closeMenus();
    rebalance();
    return true;
  }
  ADP.setState = setState;
  ADP.state = function () { return state.name; };

  function stopReplay() {
    if (state.timer) { win.clearTimeout(state.timer); state.timer = null; }
  }
  /* The replay: each step lights in order over about four seconds, a pace set for reading on a shared screen. While it
     plays, the Run button itself reads "Skip to the result". Its three labels share one spot, so nothing in the row moves.
     The run itself takes well under a second per morning. */
  var STEP_MS = [700, 1100, 900, 800, 600];
  function runMorning() {
    stopReplay();
    setState("pre");
    var steps = $$("#strip .step"), i = 0;
    $("#run").setAttribute("data-mode", "skip");
    function finish() { stopReplay(); state.ran = true; setState("clean"); }
    state.finish = finish;
    function next() {
      if (i > 0) { steps[i - 1].className = "step " + (steps[i - 1].getAttribute("data-final") || "done"); }
      if (i >= steps.length) { state.timer = win.setTimeout(finish, 350); return; }
      steps[i].className = "step active";
      state.timer = win.setTimeout(next, STEP_MS[i] || 700);
      i += 1;
    }
    next();
  }
  ADP.runMorning = runMorning;

  /* ------------------------------------------------------------------ the Deal tab */
  /* quiet leaves the scrolling to a caller that scrolls somewhere else next. */
  function reveal(step, quiet) {
    var shown = $$("[data-step=\"" + step + "\"]");
    shown.forEach(function (s) { s.hidden = false; });
    $$("[data-reveal=\"" + step + "\"]").forEach(function (b) { b.classList.add("on"); });
    if (!quiet && !QUIET && shown[0] && shown[0].scrollIntoView) {
      shown[0].scrollIntoView({behavior: "smooth", block: "start"});
    }
    rebalance();
    return shown.length;
  }
  function hideDeal() {
    /* Only the Deal tab's steps. The run strip's steps carry data-step too and stay as they are. */
    $$("[data-tab-panel=\"deal\"] [data-step]").forEach(function (s) { s.hidden = true; });
    $$("[data-reveal]").forEach(function (b) { b.classList.remove("on"); });
  }
  ADP.reveal = reveal;
  /* A sheet opens at its top left the way a spreadsheet's tab does. All the sheets scroll inside one box, so without
     this a short sheet would open wherever the last one was scrolled, with its first rows out of sight. */
  function showSheet(name) {
    var was = $(".sheet-tab.active"), box = $(".sheets");
    $$(".sheet-tab").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-sheet") === name); });
    $$("[data-sheet-pane]").forEach(function (p) { p.classList.toggle("active", p.getAttribute("data-sheet-pane") === name); });
    if (box && (!was || was.getAttribute("data-sheet") !== name)) { box.scrollTop = 0; box.scrollLeft = 0; }
  }
  ADP.showSheet = showSheet;
  var REF = /((?:'[^']+'|[A-Za-z][A-Za-z0-9_]*)!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?/g;
  function formulaHtml(f, here) {
    var out = "", last = 0, m;
    REF.lastIndex = 0;
    while ((m = REF.exec(f))) {
      out += esc(f.slice(last, m.index));
      var text = m[0], sheet = m[1] ? m[1].slice(0, -1).replace(/^'|'$/g, "") : here;
      var first = text.replace(/^.*!/, "").split(":")[0].replace(/\$/g, "");
      out += "<button type=\"button\" class=\"fref\" data-goto=\"" + esc(sheet + "!" + first) + "\">" + esc(text) + "</button>";
      last = m.index + text.length;
    }
    return out + esc(f.slice(last));
  }
  ADP.formulaHtml = formulaHtml;
  function selectCell(td) {
    $$("td.sel").forEach(function (x) { x.classList.remove("sel"); });
    td.classList.add("sel");
    var addr = td.getAttribute("data-cell"), f = td.getAttribute("data-f"), tr = td.getAttribute("data-trace");
    $("#fx-cell").textContent = addr;
    $("#fx-text").innerHTML = f ? formulaHtml(f, addr.split("!")[0]) : esc(td.textContent) + " <span class=\"muted\">" +
      esc(U["deal.formula.input"]) + "</span>";
    $("#fx-trace").innerHTML = tr ? "<button type=\"button\" class=\"btn sm\" data-ref=\"" + esc(tr) + "\">" +
      esc(U["deal.formula.trace"]) + "</button>" : "";
  }
  ADP.selectCell = selectCell;
  function goTo(where) {
    var td = $("td[data-cell=\"" + where + "\"]");
    if (!td) { return false; }
    showSheet(where.split("!")[0]);
    selectCell(td);
    if (!QUIET && td.scrollIntoView) { td.scrollIntoView({block: "nearest", inline: "nearest"}); }
    return true;
  }
  ADP.goTo = goTo;
  /* The gate moment: a labeled test types one figure into the memo, and the gate fails it with its location. */
  function inject(on) {
    var ids = {"memo-clean": !on, "memo-injected": on, "gate-pass": !on, "gate-fail": on, "inject": !on, "uninject": on};
    Object.keys(ids).forEach(function (id) { var el = doc.getElementById(id); if (el) { el.hidden = !ids[id]; } });
    var fail = doc.getElementById("gate-fail");
    if (on && !QUIET && fail && fail.scrollIntoView) { fail.scrollIntoView({block: "center"}); }
    rebalance();
    return on;
  }
  ADP.inject = inject;
  /* Print one deliverable on its own: the memo or the board deck. */
  function printMode(tab) {
    doc.body.classList.remove("print-memo", "print-deck");
    if (tab === "deal") { reveal("memo"); inject(false); doc.body.classList.add("print-memo"); }
    if (tab === "board") { doc.body.classList.add("print-deck"); }
    return true;
  }
  ADP.printMode = printMode;
  win.addEventListener("afterprint", function () { doc.body.classList.remove("print-memo", "print-deck"); });

  /* ------------------------------------------------------------------ menus, buttons and keys */
  function closeMenus() {
    $$(".menu-list").forEach(function (m) { m.hidden = true; });
    $$(".menu-toggle").forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
  }
  function download(name, text) {
    var blob = new Blob([text], {type: "text/csv"});
    var a = doc.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    doc.body.appendChild(a);
    a.click();
    a.remove();
  }
  /* The header is the brand and the menu on every tab, so the menu never moves. Once the page scrolls, the brand
     scrolls away and only the menu stays pinned, which matters on a 720px shared screen. Anything scrolled into view
     stops just below it. */
  function headerPad() {
    var top = $("#top"), nav = $("#top .tabs");
    if (!top || !nav || !top.offsetHeight || !doc.documentElement || !doc.documentElement.style) { return; }
    var lift = nav.offsetTop || 0;
    top.style.top = (-lift) + "px";
    doc.documentElement.style.scrollPaddingTop = (top.offsetHeight - lift + 12) + "px";
  }
  function showTab(name) {
    $$(".tabs [data-tab]").forEach(function (b) { b.setAttribute("aria-selected", b.getAttribute("data-tab") === name ? "true" : "false"); });
    $$("[data-tab-panel]").forEach(function (p) { p.classList.toggle("active", p.getAttribute("data-tab-panel") === name); });
    headerPad();
    rebalance();
  }
  ADP.showTab = showTab;

  doc.addEventListener("click", function (e) {
    var cell = e.target.closest ? e.target.closest("td[data-cell]") : null;
    if (cell) { selectCell(cell); return; }
    var box = e.target.closest ? e.target.closest("[data-code]") : null;
    if (box) { openCode(box.getAttribute("data-code")); into($("#how-code")); return; }
    var home = e.target.closest ? e.target.closest("[data-home]") : null;
    if (home && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
      if (e.preventDefault) { e.preventDefault(); }
      goHome();
      return;
    }
    var t = e.target.closest ? e.target.closest("button, [data-ref]") : null;
    if (!t) { if (!e.target.closest || !e.target.closest(".menu")) { closeMenus(); } return; }
    var crumb = t.getAttribute("data-crumb");
    if (crumb !== null) {
      var keepTo = parseInt(crumb, 10), ref = state.stack[keepTo];
      state.stack = state.stack.slice(0, keepTo);
      openTrace(ref, true);
      return;
    }
    var ref2 = t.getAttribute("data-ref");
    if (ref2) { openTrace(ref2, !$("#drawer").hidden && !!t.closest("#drawer")); return; }
    if (t.id === "drawer-close") { closeTrace(); return; }
    if (t.id === "run") {
      if (t.getAttribute("data-mode") === "skip" && state.finish) { state.finish(); } else { runMorning(); }
      return;
    }
    if (t.id === "reset") { resetAll(); P.i = 0; remember(0); return; }
    if (t.id === "upload") {
      var panel = $("#upload-panel");
      if (panel && !panel.hidden) { closeUpload(); } else { openUpload(); into(panel); }
      return;
    }
    if (t.id === "upload-close") { closeUpload(); return; }
    var up = t.getAttribute("data-upload");
    if (up) { showUpload(up); return; }
    var file = t.getAttribute("data-file");
    if (file) { openCode(file); return; }
    var step = t.getAttribute("data-reveal");
    if (step) { reveal(step); return; }
    if (t.id === "inject" || t.id === "uninject") { inject(t.id === "inject"); return; }
    if (t.id === "print-memo") { printMode("deal"); win.print(); return; }
    if (t.id === "print-deck") { printMode("board"); win.print(); return; }
    var sheet = t.getAttribute("data-sheet");
    if (sheet) { showSheet(sheet); return; }
    var go = t.getAttribute("data-goto");
    if (go) { goTo(go); return; }
    if (t.id === "csv") { download("analyst-desk-report-facts.csv", AD.csv || ""); return; }
    if (t.id === "print") { win.print(); return; }
    var tab = t.getAttribute("data-tab");
    if (tab) { showTab(tab); return; }
    var st = t.getAttribute("data-state");
    if (st) { stopReplay(); state.ran = true; setState(st); return; }
    if (t.classList.contains("menu-toggle")) {
      var list = t.parentElement.querySelector(".menu-list"), open = list.hidden;
      closeMenus();
      list.hidden = !open;
      t.setAttribute("aria-expanded", open ? "true" : "false");
    }
  });
  doc.addEventListener("keydown", function (e) {
    var t = e.target || {}, typing = /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || "") || t.isContentEditable;
    if ((e.key === "Enter" || e.key === " ") && t.getAttribute && t.getAttribute("data-code")) {
      if (e.preventDefault) { e.preventDefault(); }
      openCode(t.getAttribute("data-code"));
      into($("#how-code"));
      return;
    }
    if (e.key === "Escape") {
      closeMenus();
      if (!$("#drawer").hidden) { closeTrace(); }
      if (typing && t.blur) { t.blur(); }
      return;
    }
    if (typing || e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented || !STEPS.length) { return; }
    var k = e.key === "ArrowRight" ? P.i + 1 : e.key === "ArrowLeft" ? P.i - 1 : e.key === "r" || e.key === "R" ? 0 : null;
    if (k === null) { return; }
    if (e.preventDefault) { e.preventDefault(); }
    go(k, e.key === "ArrowRight");
  });

  /* ------------------------------------------------------------------ the code
     The desk's real source, from code.js, shown as text with line numbers and a light syntax color. Every value goes
     through esc() before it becomes HTML. */
  var CODE = win.AD_CODE || {files: {}, notes: {}};
  var KEYWORDS = {
    py: /\b(def|class|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|import|from|as|with|try|except|finally|raise|lambda|yield|pass|break|continue|assert|del|global)\b/g,
    js: /\b(var|let|const|function|return|if|else|for|while|in|of|new|this|true|false|null|undefined|typeof|try|catch|finally|throw|break|continue)\b/g,
    sh: /\b(if|then|else|fi|for|do|done|set|cd|echo|exit)\b/g
  };
  function codeSpan(cls, s) { return "<span class=\"hl-" + cls + "\">" + esc(s) + "</span>"; }
  function keywords(s, lang) {
    var re = KEYWORDS[lang];
    if (!re) { return esc(s); }
    var out = "", last = 0, m;
    re.lastIndex = 0;
    while ((m = re.exec(s))) {
      out += esc(s.slice(last, m.index)) + codeSpan("k", m[0]);
      last = m.index + m[0].length;
    }
    return out + esc(s.slice(last));
  }
  function codeLine(line, lang, open) {
    var html = "", rest = line;
    if (open) {
      var end = line.indexOf(open);
      if (end < 0) { return {html: codeSpan("s", line), open: open}; }
      html = codeSpan("s", line.slice(0, end + 3));
      rest = line.slice(end + 3);
    }
    if (lang === "md") { return {html: html + (/^#/.test(rest) ? codeSpan("k", rest) : esc(rest)), open: null}; }
    var re = lang === "py" || lang === "sh" ?
      /("""|'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#.*$|\b\d+(?:\.\d+)?\b)/g :
      /(\/\/.*$|\/\*.*?\*\/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b\d+(?:\.\d+)?\b)/g;
    var last = 0, m;
    while ((m = re.exec(rest))) {
      html += keywords(rest.slice(last, m.index), lang);
      var t = m[0];
      if (t === "\"\"\"" || t === "'''") {
        var close = rest.indexOf(t, m.index + 3);
        if (close < 0) { return {html: html + codeSpan("s", rest.slice(m.index)), open: t}; }
        html += codeSpan("s", rest.slice(m.index, close + 3));
        re.lastIndex = last = close + 3;
        continue;
      }
      html += codeSpan(t.charAt(0) === "#" || t.slice(0, 2) === "//" || t.slice(0, 2) === "/*" ? "c" : /^\d/.test(t) ? "n" : "s", t);
      last = re.lastIndex;
    }
    return {html: html + keywords(rest.slice(last), lang), open: null};
  }
  function codeHtml(text, path) {
    var lang = /\.py$/.test(path) ? "py" : /\.js$/.test(path) ? "js" : /\.css$/.test(path) ? "css" : /\.sh$/.test(path) ? "sh" : "md";
    var lines = String(text).split("\n"), out = [], open = null;
    if (lines.length && lines[lines.length - 1] === "") { lines.pop(); }
    for (var i = 0; i < lines.length; i++) {
      var r = codeLine(lines[i], lang, open);
      open = r.open;
      out.push("<span class=\"ln\">" + (i + 1) + "</span>" + r.html);
    }
    return out.join("\n");
  }
  ADP.codeHtml = codeHtml;
  function openCode(path) {
    var text = (CODE.files || {})[path];
    if (text === undefined || !$("#code-body")) { return false; }
    $("#code-path").textContent = path;
    $("#code-note").textContent = (CODE.notes || {})[path] || "";
    $("#code-body").innerHTML = codeHtml(text, path);
    $$("[data-file]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-file") === path); });
    var pre = $("pre.code");
    if (pre) { pre.scrollTop = 0; }
    return true;
  }
  ADP.openCode = openCode;

  /* ------------------------------------------------------------------ the Upload panel
     The panel shows what the intake agent did with each of the twelve layouts it had never seen, from the recorded
     eval runs. Nothing leaves the page. */
  function showUpload(id) {
    var panel = $("#upload-panel");
    if (!panel) { return false; }
    var found = false;
    $$("[data-upload-detail]", panel).forEach(function (d) {
      var on = d.getAttribute("data-upload-detail") === id;
      d.hidden = !on;
      found = found || on;
    });
    $$("[data-upload]", panel).forEach(function (b) {
      var on = b.getAttribute("data-upload") === id;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    rebalance();
    return found;
  }
  function openUpload(id) {
    var panel = $("#upload-panel");
    if (!panel) { return false; }
    panel.hidden = false;
    if ($("#upload")) { $("#upload").classList.add("on"); }
    return showUpload(id || panel.getAttribute("data-default"));
  }
  function closeUpload() {
    var panel = $("#upload-panel");
    if (panel) { panel.hidden = true; }
    if ($("#upload")) { $("#upload").classList.remove("on"); }
  }
  ADP.openUpload = openUpload;
  ADP.showUpload = showUpload;

  /* ------------------------------------------------------------------ the Hours tab
     Hours back is the runs times the hours by hand less the review and the run time. The hours by hand and the
     review minutes are estimates anyone can change, and every total, bar and the header follow them. */
  function hoursNum(v) { var n = parseFloat(v); return isFinite(n) && n > 0 ? n : 0; }
  function setOut(root, name, v) {
    $$("[data-out=\"" + name + "\"]", root).forEach(function (el) { el.textContent = v.toFixed(1); });
  }
  function hoursRecalc() {
    var rows = $$("tr[data-row]");
    if (!rows.length) { return null; }
    var t = {week: 0, today: 0, manual: 0, review: 0}, pairs = [], most = 1e-9;
    rows.forEach(function (tr) {
      var key = tr.getAttribute("data-row"), runs = hoursNum(tr.getAttribute("data-runs"));
      var secs = hoursNum(tr.getAttribute("data-seconds"));
      var base = hoursNum(tr.querySelector("[data-k=\"baseline\"]").value);
      var rev = hoursNum(tr.querySelector("[data-k=\"review\"]").value);
      var each = Math.max(0, base - rev / 60 - secs / 3600);
      setOut(tr, "back", runs * each);
      t.week += runs * each;
      t.manual += runs * base;
      t.review += runs * rev / 60;
      if ((key === "daily_report" || key === "intake") && runs) { t.today += each; }
      pairs.push({key: key, manual: runs * base, auto: runs * (rev / 60 + secs / 3600), back: runs * each});
      most = Math.max(most, runs * base, runs * (rev / 60 + secs / 3600));
    });
    ["week", "today", "manual", "review"].forEach(function (k) { setOut(doc, k, t[k]); });
    setOut(doc, "total", t.week);
    pairs.forEach(function (p) {
      var row = $("[data-bar=\"" + p.key + "\"]");
      if (!row) { return; }
      ["manual", "auto"].forEach(function (k) {
        var bar = $("[data-out=\"bar-" + k + "\"]", row);
        if (!bar) { return; }
        bar.style.width = (p[k] / most * 100).toFixed(1) + "%";
        bar.setAttribute("data-tip", (U["hours.legend." + k] || "") + " " + word("hours.unit", {h: p[k].toFixed(1)}));
      });
      setOut(row, "back-row", p.back);
    });
    return t;
  }
  ADP.hoursRecalc = hoursRecalc;
  doc.addEventListener("input", function (e) {
    if (e.target && e.target.closest && e.target.closest("table.hours")) { hoursRecalc(); }
  });

  /* ------------------------------------------------------------------ presenter mode
     The right arrow steps through the tour and the left arrow steps back. R resets, and #step-N in the address
     opens any step directly. Each step puts the page in that step's exact state, so a step never depends on what was
     clicked before it, and normal clicking still works between steps for questions. */
  var STEPS = (AD.meta && AD.meta.steps) || [];
  var P = {i: 0, timer: null};
  var SHEET0 = (function () { var b = $(".sheet-tab.active"); return b ? b.getAttribute("data-sheet") : null; })();
  function toTop() { if (!QUIET && win.scrollTo) { win.scrollTo(0, 0); } }
  function into(el) { if (!QUIET && el && el.scrollIntoView) { el.scrollIntoView({behavior: "smooth", block: "start"}); } }
  function pulse(el) {
    if (!el) { return; }
    el.classList.add("pressed");
    win.setTimeout(function () { el.classList.remove("pressed"); }, 1400);
  }
  function resetAll() {
    stopReplay();
    state.ran = false;
    closeTrace();
    setState("pre");
    hideDeal();
    inject(false);
    closeUpload();
    if (SHEET0) { showSheet(SHEET0); }
    $$("td.sel").forEach(function (x) { x.classList.remove("sel"); });
    if ($("#fx-cell")) { $("#fx-cell").textContent = ""; $("#fx-text").textContent = U["deal.formula.hint"] || ""; $("#fx-trace").innerHTML = ""; }
    showTab("portfolio");
    toTop();
  }
  /* The mark in the header goes back to the start, the way the page looks when it opens: the Portfolio tab before the
     run, the drawer and menus closed, no presenter caption, and no step in the address. A click from the keyboard or
     the mouse does it in place, and opening the link in a new tab loads the page fresh. */
  function goHome() {
    resetAll();
    closeMenus();
    P.i = 0;
    if (P.timer) { win.clearTimeout(P.timer); P.timer = null; }
    var box = $("#presenter");
    if (box) { box.hidden = true; }
    openCode(CODE.default);
    try {
      if (win.history && win.history.replaceState && win.location) {
        win.history.replaceState(null, "", win.location.pathname + win.location.search);
        return;
      }
    } catch (err) { /* a page opened from a file may refuse, and the hash below still clears */ }
    if (win.location && win.location.hash) { win.location.hash = ""; }
  }
  ADP.goHome = goHome;
  function portfolioState(name, live, from) {
    showTab("portfolio");
    stopReplay();
    state.ran = true;
    setState(name);
    toTop();
    if (live) { pulse(from); }
  }
  function tabStep(name, live) {
    showTab(name);
    toTop();
    if (live) { pulse($(".tabs [data-tab=\"" + name + "\"]")); }
  }
  function dealStep(step, live) {
    showTab("deal");
    reveal(step);
    if (live) { pulse($("[data-reveal=\"" + step + "\"]")); }
  }
  var ACT = {
    problem: function () { resetAll(); },
    run: function (live) {
      showTab("portfolio");
      toTop();
      if (live) { runMorning(); pulse($("#run")); } else { stopReplay(); state.ran = true; setState("clean"); }
    },
    error: function (live) { portfolioState("E1", live, $$(".menu-toggle")[0]); },
    lookalike: function (live) { portfolioState("L1", live, $$(".menu-toggle")[1]); },
    intake: function (live) { portfolioState("intake", live, $(".controls [data-state=\"intake\"]")); },
    upload: function (live) {
      showTab("portfolio");
      openUpload();
      into($("#upload-panel"));
      if (live) { pulse($("#upload")); }
    },
    deal: function (live) { tabStep("deal", live); },
    model: function (live) { dealStep("model", live); },
    returns: function () { showTab("deal"); reveal("model", true); goTo("Returns!C20"); into($(".modelview")); },
    checks: function () { showTab("deal"); reveal("model", true); showSheet("Checks"); into($(".modelview")); },
    claims: function (live) { dealStep("claims", live); },
    memo: function (live) { dealStep("memo", live); },
    gate: function () { showTab("deal"); reveal("memo", true); inject(true); },
    pass: function () {
      showTab("deal");
      reveal("memo", true);
      inject(false);
      var pass = $("#gate-pass");
      if (!QUIET && pass && pass.scrollIntoView) { pass.scrollIntoView({behavior: "smooth", block: "center"}); }
    },
    board: function (live) { tabStep("board", live); },
    hours: function (live) { tabStep("hours", live); },
    how: function (live) { tabStep("how", live); },
    routing: function () { showTab("how"); into($("#how-routing")); },
    code: function () { showTab("how"); openCode(CODE.default || "engine/gate.py"); into($("#how-code")); },
    results: function () { showTab("how"); into($("#how-results")); },
    plan: function () { showTab("how"); into($("#how-plan")); }
  };
  function indicate(k) {
    var box = $("#presenter");
    if (!box) { return; }
    $(".pn", box).textContent = word("presenter.label", {n: k + 1, total: STEPS.length});
    $(".pl", box).textContent = U["presenter.s." + STEPS[k]] || "";
    var caption = U["presenter.c." + STEPS[k]] || "";
    $(".pc", box).textContent = caption;
    box.hidden = false;
    box.classList.remove("fade");
    if (P.timer) { win.clearTimeout(P.timer); }
    P.timer = win.setTimeout(function () { box.classList.add("fade"); }, caption ? 9000 : 2000);
  }
  function remember(k) {
    var hash = "#step-" + (k + 1);
    try {
      if (win.history && win.history.replaceState) { win.history.replaceState(null, "", hash); return; }
    } catch (err) { /* a page opened from a file may refuse, and the hash below still works */ }
    if (win.location && win.location.hash !== hash) { win.location.hash = hash; }
  }
  function stepFromHash() {
    var m = /^#step-(\d+)$/.exec((win.location && win.location.hash) || "");
    return m ? Math.max(0, Math.min(STEPS.length - 1, parseInt(m[1], 10) - 1)) : null;
  }
  function go(k, live) {
    if (!STEPS.length) { return -1; }
    k = Math.max(0, Math.min(STEPS.length - 1, k));
    if (live && k === P.i) { indicate(k); return k; }
    var forward = live && k === P.i + 1;
    P.i = k;
    closeTrace();
    closeMenus();
    if (forward) {
      ACT[STEPS[k]](true);
    } else {
      resetAll();
      QUIET = true;
      try {
        for (var i = 1; i < k; i++) { ACT[STEPS[i]](false); }
      } finally {
        QUIET = false;
      }
      if (k > 0) { ACT[STEPS[k]](false); }
    }
    indicate(k);
    remember(k);
    return k;
  }
  ADP.go = go;
  ADP.step = function () { return P.i; };
  ADP.steps = function () { return STEPS.slice(); };
  win.addEventListener("hashchange", function () {
    var n = stepFromHash();
    if (n !== null && n !== P.i) { go(n, false); }
  });

  /* tips: data-tip on any mark, shown on hover and on keyboard focus alike */
  var tip = $("#tip");
  function showTip(e) {
    var el = e.target && e.target.closest ? e.target.closest("[data-tip]") : null;
    if (!el || !tip) { if (tip) { tip.hidden = true; } return; }
    tip.textContent = el.getAttribute("data-tip");
    tip.hidden = false;
    var r = el.getBoundingClientRect();
    tip.style.left = Math.min(win.innerWidth - 330, Math.max(8, r.left)) + "px";
    tip.style.top = (r.top - 36) + "px";
  }
  doc.addEventListener("mouseover", showTip);
  doc.addEventListener("focusin", showTip);
  doc.addEventListener("focusout", function () { if (tip) { tip.hidden = true; } });

  /* ------------------------------------------------------------------ the spill rule
     Paragraphs run the full width of their section, and CSS's pretty wrapping keeps a single word from standing alone
     on a last line. The rule is that no paragraph ends with one or two stranded words, and a paragraph here is any
     block of six or more words. keepLast() holds the last three together, and spillReport() lists any block that still
     ends short, with the words on its last line and whether an agent wrote it. */
  var NOT_TEXT = /^(SCRIPT|STYLE|PRE|CODE|TEXTAREA|INPUT|SELECT|OPTION|BR|IMG|TABLE|THEAD|TBODY|TFOOT|TR|COLGROUP|COL|BUTTON)$/;
  var AGENT_TEXT = ".commentary, .memo-body, .slide-h, .slide-bullets, td.why";
  function canMeasure() { return !!(doc.createRange && doc.createTreeWalker && win.getComputedStyle); }
  function shown(el) {
    for (var p = el; p && p.parentElement; p = p.parentElement) {
      var up = p.parentElement;
      if (up.tagName === "DETAILS" && !up.open && p.tagName !== "SUMMARY") { return false; }
    }
    if (el.checkVisibility) { return el.checkVisibility({visibilityProperty: true}); }
    return el.getClientRects().length > 0;
  }
  function textBlock(el, hiddenToo) {
    if (el.namespaceURI && el.namespaceURI.indexOf("svg") >= 0) { return false; }
    if (NOT_TEXT.test(el.tagName) || (!hiddenToo && !shown(el)) || el.closest(".sheets, .code-view")) { return false; }
    var cs = win.getComputedStyle(el);
    if (/^(inline|contents|none)$/.test(cs.display) || /^(nowrap|pre)$/.test(cs.whiteSpace)) { return false; }
    var text = false;
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3) { text = text || /\S/.test(n.data); continue; }
      if (n.nodeType !== 1) { continue; }
      if (/^(INPUT|SELECT|TEXTAREA|BR)$/.test(n.tagName) || !/^inline/.test(win.getComputedStyle(n).display)) { return false; }
      text = text || /\S/.test(n.textContent);
    }
    return text;
  }
  function blocks(root) {
    var all = root.querySelectorAll("*"), out = [];
    for (var i = 0; i < all.length; i++) { if (textBlock(all[i])) { out.push(all[i]); } }
    return out;
  }
  function wordLines(el) {
    var lines = [], range = doc.createRange(), walker = doc.createTreeWalker(el, 4), node, re = /\S+/g, m;
    while ((node = walker.nextNode())) {
      re.lastIndex = 0;
      while ((m = re.exec(node.data))) {
        range.setStart(node, m.index);
        range.setEnd(node, m.index + m[0].length);
        var rects = range.getClientRects(), r = rects[rects.length - 1];
        if (!r || r.width < 0.5) { continue; }
        var mid = (r.top + r.bottom) / 2, h = r.bottom - r.top, line = null;
        for (var j = 0; j < lines.length && !line; j++) {
          if (Math.abs(lines[j].mid - mid) < Math.max(h, lines[j].h) / 2) { line = lines[j]; }
        }
        if (line) {
          line.words.push(m[0]);
          line.l = Math.min(line.l, r.left);
          line.r = Math.max(line.r, r.right);
        } else {
          lines.push({mid: mid, h: h, words: [m[0]], l: r.left, r: r.right});
        }
      }
    }
    lines.sort(function (a, b) { return a.mid - b.mid; });
    return lines;
  }
  function spillReport(root) {
    if (!canMeasure() || !root) { return []; }
    return blocks(root).map(function (el) {
      var lines = wordLines(el), words = lines.reduce(function (n, l) { return n + l.words.length; }, 0);
      if (lines.length < 2 || words < 6 || lines[lines.length - 1].words.length > 2) { return null; }
      var cs = win.getComputedStyle(el);
      return {text: el.textContent.replace(/\s+/g, " ").trim().slice(0, 160), tag: el.tagName.toLowerCase(),
        cls: String(el.className || ""), lines: lines.length, last: lines[lines.length - 1].words.join(" "),
        agent: !!el.closest(AGENT_TEXT) && !el.closest(".ai-label"), font: cs.fontSize,
        inner: Math.round(el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)),
        widths: lines.map(function (l) { return Math.round(l.r - l.l); })};
    }).filter(Boolean);
  }
  ADP.spillReport = spillReport;
  /* A hyphenated word like mix-up or one-day never splits across two lines. Text outside code gets
     non-breaking hyphens, which read the same. */
  var NB = /([A-Za-z0-9])-(?=[A-Za-z0-9])/g;
  function nbText(root) {
    if (!root || !doc.createTreeWalker) { return; }
    var walker = doc.createTreeWalker(root, 4), node;
    while ((node = walker.nextNode())) {
      var p = node.parentElement, t = node.data.replace(NB, "$1‑");
      if (t !== node.data && p && !p.closest("pre, code, script, style")) { node.data = t; }
    }
  }
  /* Scatter labels sit beside their dots. Each one takes the first spot that stays inside the plot and clear of every
     dot and every label placed before it: right, left, above, below, then the corners. The build lists the ringed
     dot's label first. A label with no clear spot gives way to the tip and the table view, except the ringed one,
     which is placed anyway. */
  function overlaps(a, b) { return a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b; }
  function labelSpot(x, y, w, h, W, H, taken, force) {
    var g = 10, spots = [[x + g, y - h / 2], [x - g - w, y - h / 2], [x - w / 2, y - g - h], [x - w / 2, y + g],
      [x + g, y - h - 3], [x + g, y + 3], [x - g - w, y - h - 3], [x - g - w, y + 3]];
    var inside = spots.filter(function (s) { return s[0] >= 0 && s[1] >= 0 && s[0] + w <= W && s[1] + h <= H; });
    var free = inside.filter(function (s) {
      var box = {l: s[0], t: s[1], r: s[0] + w, b: s[1] + h};
      return !taken.some(function (t) { return overlaps(box, t); });
    });
    var pick = free[0] || (force ? inside[0] || spots[0] : null);
    return pick ? pick.slice() : null;
  }
  ADP.labelSpot = labelSpot;
  function placeLabels(root) {
    $$(".sc-plot", root).forEach(function (plot) {
      var W = plot.clientWidth, H = plot.clientHeight;
      if (!W || !H) { return; }
      var at = plot.getBoundingClientRect(), taken = [], dots = {};
      $$(".sc-pt, .sc-line span", plot).forEach(function (el) {
        var r = el.getBoundingClientRect(), box = {l: r.left - at.left, t: r.top - at.top, r: r.right - at.left, b: r.bottom - at.top};
        taken.push(box);
        if (el.classList.contains("sc-pt")) { dots[el.getAttribute("data-id")] = box; }
      });
      $$(".sc-lbl", plot).forEach(function (lbl) {
        var d = dots[lbl.getAttribute("data-for")];
        if (!d) { return; }
        lbl.classList.add("placed");
        var w = lbl.offsetWidth, h = lbl.offsetHeight,
          s = labelSpot((d.l + d.r) / 2, (d.t + d.b) / 2, w, h, W, H, taken, lbl.classList.contains("on"));
        lbl.classList.toggle("crowded", !s);
        if (!s) { return; }
        lbl.style.left = s[0] + "px";
        lbl.style.top = s[1] + "px";
        lbl.style.bottom = "auto";
        taken.push({l: s[0], t: s[1], r: s[0] + w, b: s[1] + h});
      });
    });
  }
  ADP.placeLabels = placeLabels;
  /* A paragraph never ends on one or two words alone, at any width. In a block of six or more words the last three wrap
     as one, so only the places a line may break change and the words stay as written. A label shorter than that wraps
     as it needs to in a narrow box. A block is found the way spillReport finds one, hidden tabs included, and code,
     the model's grid, and agent text the build already joined are left alone. */
  function keepLast(root) {
    if (!root || !canMeasure()) { return; }
    var all = root.querySelectorAll("*");
    for (var k = 0; k < all.length; k++) {
      var el = all[k];
      if (!textBlock(el, true) || el.closest("pre, code")) { continue; }
      var text = el.textContent.trim();
      if (text.split(/\s+/).length < 6 || /\u00a0\S+$/.test(text)) { continue; }
      var nodes = [], walker = doc.createTreeWalker(el, 4), node;
      while ((node = walker.nextNode())) { nodes.push(node); }
      var left = 2, seen = false;
      for (var i = nodes.length - 1; i >= 0 && left; i--) {
        var chars = nodes[i].data.split("");
        for (var j = chars.length - 1; j >= 0 && left; j--) {
          if (chars[j] === " ") {
            if (seen) { chars[j] = "\u00a0"; left--; }
          } else if (/\S/.test(chars[j])) { seen = true; }
        }
        nodes[i].data = chars.join("");
      }
    }
  }
  ADP.keepLast = keepLast;
  function rebalance() {
    [$("#portfolio-body"), $("#strip"), $("#drawer-body")].forEach(function (root) { nbText(root); keepLast(root); });
    placeLabels(doc);
  }
  win.addEventListener("resize", headerPad);
  win.addEventListener("resize", function () { placeLabels(doc); });

  /* ------------------------------------------------------------------ start */
  keepLast(doc.body);
  showTab("portfolio");
  setState("pre");
  hoursRecalc();
  openCode(CODE.default);
  var first = stepFromHash();
  if (first !== null) { go(first, false); }
})();
