"""Validators for every agent's output: its schema, the limits the spec puts on it, the gate and the writing rules.

Nothing an agent returns reaches the page unless validate() comes back with no problems. Problems read as plain
sentences, because the recorder sends them back to the model once as a repair request. The gate runs on the
agent's own text after its local IDs are translated to ledger IDs, and the writing-rules check runs on the text
as the page would render it.
"""
import importlib.util
import json
import re
from pathlib import Path

from engine import gate
from engine.intake import FIELDS

HERE = Path(__file__).resolve().parent.parent
LOCAL = re.compile(r"\{([FDC]):?(\d+)\}")      # {D:7}, and {D7} since the ID itself reads D7
_lint = []


def lint_module():
    if not _lint:
        spec = importlib.util.spec_from_file_location("lint_copy", str(HERE.joinpath("tools", "lint_copy.py")))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _lint.append(mod)
    return _lint[0]


COMMA_SO = re.compile(r",\s+so\b", re.IGNORECASE)


def rule_issues(mod, sent):
    """tools/lint_copy.py's issues for one sentence, plus the rule it leaves out. A comma never comes before so."""
    issues = list(mod.check(sent))
    if COMMA_SO.search(sent):
        issues.append("a comma before the word so")
    return issues


def lint(text):
    """Every writing-rules problem in a piece of rendered prose."""
    mod = lint_module()
    out = []
    for sent in mod.sentences(" ".join(text.split())):
        out += [f"{i} in: {sent}" for i in rule_issues(mod, sent)]
    return out


def extract_json(text):
    """The first JSON object in a reply, or None."""
    text = re.sub(r"```(?:json)?", "", text or "")
    decoder = json.JSONDecoder()
    i = text.find("{")
    while i >= 0:
        try:
            obj, _ = decoder.raw_decode(text, i)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        i = text.find("{", i + 1)
    return None


# ---------------------------------------------------------------------- local IDs to ledger IDs
def resolve(ledger, keys):
    """{local ID: ledger ref or None} from the meanings recorded with an input."""
    out = {}
    for local, item in keys.items():
        k = item["key"]
        if k[0] == "C":
            row = ledger.conn.execute("SELECT claim_id FROM claims WHERE deliverable = ? AND COALESCE(metric, '') = ? AND "
                                      "location = ? ORDER BY claim_id DESC LIMIT 1", (k[1], k[2], k[3])).fetchone()
            out[local] = f"C{row[0]}" if row else None
        else:
            out[local] = ledger.find(k[0], k[1], k[2], k[3])
    return out


def to_ledger(text, mapping):
    """Agent text with each local placeholder rewritten to its ledger ID. Unknown locals stay as they are."""
    def sub(m):
        ref = mapping.get(f"{m.group(1)}{m.group(2)}")
        return "{" + ref[0] + ":" + ref[1:] + "}" if ref else m.group(0).replace("{", "{?")
    return LOCAL.sub(sub, text)


def prose_problems(pieces, ledger, mapping, render_lint=True):
    """Gate and writing-rule problems for [(location, agent text)], as sentences for a repair request."""
    problems = []
    allowed = {r for r in mapping.values() if r}
    for location, text in pieces:
        for m in LOCAL.finditer(text):
            if not mapping.get(f"{m.group(1)}{m.group(2)}"):
                problems.append(f"{location}: {m.group(0)} isn't one of the IDs you were given")
        translated = to_ledger(text, mapping)
        for f in gate.check([(location, translated)], ledger, allowed)["failures"]:
            if f["kind"] == "unsupported":
                problems.append(f"{location}: the number {f['token']!r} is typed in. Use a placeholder from the input "
                                f"or write it in words if it isn't a figure")
            elif "wasn't given" not in f["reason"] and "no such ID" not in f["reason"]:
                problems.append(f"{location}: {f['token']} {f['reason']}")
        if render_lint:
            rendered = gate.render(translated, ledger)
            problems += [f"{location}: {p}" for p in lint(rendered)]
    return problems


# ---------------------------------------------------------------------- the five tasks
def intake_mapper(out, inp):
    p = []
    if not isinstance(out, dict):
        return ["the reply isn't a JSON object"]
    header_rows = out.get("header_rows")
    if header_rows not in (1, 2):
        p.append("header_rows must be 1 or 2")
    cols = out.get("columns")
    if not isinstance(cols, list) or not all(isinstance(c, list) and len(c) == 2 for c in cols):
        return p + ["columns must be a list of [source column, schema field or null] pairs"]
    headers = inp["top_rows"][header_rows - 1] if header_rows in (1, 2) and len(inp["top_rows"]) >= header_rows else []
    headers = [h for h in headers if h]
    if [c[0] for c in cols] != headers:
        p.append(f"columns must list every column of header row {header_rows} in order: {headers}")
    named = [c[1] for c in cols if c[1] is not None]
    for f in named:
        if f not in FIELDS:
            p.append(f"{f} isn't a schema field")
    for f in FIELDS:
        if named.count(f) != 1:
            p.append(f"{f} must be mapped exactly once, and it's mapped {named.count(f)} times")
    if not isinstance(out.get("date_format"), str) or "%" not in out.get("date_format", ""):
        p.append("date_format must be a strptime format string")
    if out.get("money_format") not in ("text", "plain", "paren"):
        p.append("money_format must be text, plain or paren")
    ot = out.get("on_time")
    if not (isinstance(ot, dict) and isinstance(ot.get("true"), str) and isinstance(ot.get("false"), str)):
        p.append("on_time must be {\"true\": value, \"false\": value} with both values as strings")
    if out.get("totals_label") is not None and not isinstance(out.get("totals_label"), str):
        p.append("totals_label must be a string or null")
    conf = out.get("confidence", {})
    if not isinstance(conf, dict) or any(not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in conf.values()):
        p.append("confidence must map fields to numbers between 0 and 1")
    return p


def mapping_of(out):
    """The engine's mapping from a validated intake reply."""
    return {"header_rows": out["header_rows"], "columns": [list(c) for c in out["columns"]],
            "date_format": out["date_format"], "money_format": out["money_format"],
            "on_time": {"true": str(out["on_time"]["true"]), "false": str(out["on_time"]["false"])},
            "totals_label": out.get("totals_label")}


def exact_match(out, key):
    """Whether an intake reply matches the frozen answer key in every part."""
    m = mapping_of(out)
    return (m["header_rows"] == key["header_rows"] and [list(c) for c in m["columns"]] == [list(c) for c in key["columns"]]
            and m["date_format"] == key["date_format"] and m["money_format"] == key["money_format"]
            and m["on_time"] == key["on_time"] and (m["totals_label"] or None) == (key["totals_label"] or None))


def daily_commentary(out, inp, ledger, mapping):
    if not isinstance(out, dict) or not isinstance(out.get("companies"), list):
        return ["the reply needs a companies list"]
    p, want = [], [c["company"] for c in inp["companies"]]
    got = [c.get("company") for c in out["companies"] if isinstance(c, dict)]
    if got != want:
        p.append(f"companies must be {want} in that order")
    pieces = []
    for c in out["companies"]:
        sents = c.get("sentences") if isinstance(c, dict) else None
        if not isinstance(sents, list) or not 2 <= len(sents) <= 4 or not all(isinstance(s, str) for s in sents):
            p.append(f"{c.get('company') if isinstance(c, dict) else c}: write two to four sentences")
            continue
        pieces += [(f"{c['company']} sentence {i}", s) for i, s in enumerate(sents, 1)]
    return p + prose_problems(pieces, ledger, mapping)


def deal_analyst(out, inp, ledger, mapping):
    if not isinstance(out, dict) or not isinstance(out.get("assumptions"), list):
        return ["the reply needs an assumptions list"]
    p = []
    want = {a["key"]: a["allowed_range"] for a in inp["propose"]}
    got = {}
    for a in out["assumptions"]:
        if not isinstance(a, dict) or a.get("key") not in want:
            p.append(f"unknown assumption {a.get('key') if isinstance(a, dict) else a}")
            continue
        got[a["key"]] = a
    for k in want:
        if k not in got:
            p.append(f"propose a value for {k}")
    pieces = []
    for k, a in got.items():
        v, (lo, hi) = a.get("value"), want[k]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
            p.append(f"{k}: the value must be a decimal fraction between {lo} and {hi}")
        cites = a.get("cites")
        if not isinstance(cites, list) or not cites or any(not mapping.get(c) for c in cites):
            p.append(f"{k}: cite at least one ID from the input, and only IDs from the input")
        if not isinstance(a.get("rationale"), str) or len(a["rationale"].split()) < 6:
            p.append(f"{k}: give a one- or two-sentence rationale")
        else:
            pieces.append((f"{k} rationale", a["rationale"]))
    return p + prose_problems(pieces, ledger, mapping)


MEMO_SECTIONS = ("recommendation", "business", "why_now", "historicals", "adjustments", "customers", "projections",
                 "returns", "debt", "risks", "next_steps")


def memo_writer(out, inp, ledger, mapping):
    if not isinstance(out, dict) or not isinstance(out.get("sections"), list):
        return ["the reply needs a sections list"]
    p, pieces = [], []
    ids = [s.get("id") for s in out["sections"] if isinstance(s, dict)]
    if ids != list(MEMO_SECTIONS):
        p.append(f"sections must be {list(MEMO_SECTIONS)} in that order")
    for s in out["sections"]:
        paras = s.get("paragraphs") if isinstance(s, dict) else None
        if not isinstance(paras, list) or not 1 <= len(paras) <= 4 or not all(isinstance(x, str) for x in paras):
            p.append(f"{s.get('id') if isinstance(s, dict) else s}: write one to four paragraphs")
            continue
        pieces += [(f"section {s['id']} paragraph {i}", x) for i, x in enumerate(paras, 1)]
    risks = " ".join(" ".join(s.get("paragraphs", [])) for s in out["sections"] if isinstance(s, dict) and s.get("id") == "risks")
    cited = {f"{m.group(1)}{m.group(2)}" for m in LOCAL.finditer(risks)}
    for c in [x for x in mapping if x.startswith("C")]:
        if c not in cited:
            p.append(f"the risks section must cite the claims check result {{C:{c[1:]}}}")
    conds = out.get("conditions")
    if not isinstance(conds, list) or not 2 <= len(conds) <= 4 or not all(isinstance(x, str) for x in conds):
        p.append("conditions must list two to four conditions for the next round")
    else:
        pieces += [(f"condition {i}", x) for i, x in enumerate(conds, 1)]
    return p + prose_problems(pieces, ledger, mapping)


def board_deck(out, inp, ledger, mapping):
    if not isinstance(out, dict) or not isinstance(out.get("slides"), list):
        return ["the reply needs a slides list"]
    p, pieces = [], []
    if [s.get("n") for s in out["slides"] if isinstance(s, dict)] != [1, 2, 3, 4, 5]:
        p.append("slides must be numbered 1 to 5 in order")
    charts = {s["n"]: s["charts"] for s in inp["slides"]}
    for s in out["slides"]:
        if not isinstance(s, dict):
            continue
        n = s.get("n")
        if not isinstance(s.get("headline"), str) or not s["headline"].strip():
            p.append(f"slide {n}: write a headline")
        else:
            pieces.append((f"slide {n} headline", s["headline"]))
        bullets = s.get("bullets")
        if not isinstance(bullets, list) or not 2 <= len(bullets) <= 3 or not all(isinstance(b, str) for b in bullets):
            p.append(f"slide {n}: write two or three bullets")
        else:
            pieces += [(f"slide {n} bullet {i}", b) for i, b in enumerate(bullets, 1)]
        if s.get("chart") not in charts.get(n, []):
            p.append(f"slide {n}: chart must be one of {charts.get(n, [])}")
    return p + prose_problems(pieces, ledger, mapping)


def validate(task, out, inp, ledger=None, mapping=None):
    if task == "intake_mapper":
        return intake_mapper(out, inp)
    fn = {"daily_commentary": daily_commentary, "deal_analyst": deal_analyst, "memo_writer": memo_writer,
          "board_deck": board_deck}[task]
    return fn(out, inp, ledger, mapping or {})
