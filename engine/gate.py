"""The tie-out gate: agent text may carry figures only as placeholders that cite ledger IDs.

An agent writes `Revenue reached {D:1023} and came in {D:1031}.` and the renderer puts in the verified values,
writing a variance's direction itself ("$12.4K above budget"). scan() fails a deliverable for any digit that
didn't come from a placeholder, unless it's a year, a date, a fiscal year or a quarter, and for any placeholder
whose ID doesn't exist, wasn't in the agent's input, or sits next to a unit word that disagrees with it. Each
failure carries its location, so the page can point at it.
"""
import re

from engine import fmt

PLACEHOLDER = re.compile(r"\{([FDC]):(\d+)\}")
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|" \
        r"Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
YEAR = r"(?<![$€£\d.,])\b20[0-3]\d\b(?![.,]\d)(?!\s?(?:%|percent|loads|rooms|miles|MWh|kWh|[KMB]\b|million|billion))"
ALLOWED = [re.compile(MONTH + r"\.? \d{1,2}(?:, 20[0-3]\d)?\b"), re.compile(r"\bFY ?20[0-3]\d\b"),
           re.compile(r"\bQ[1-4](?: 20[0-3]\d)?\b"), re.compile(YEAR)]
NUMBER = re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|percent|[KMB]\b|million|billion|thousand))?")
UNIT_WORDS = {"mwh": "kwh", "kwh": "kwh", "percent": "ratio", "%": "ratio", "dollars": "cents", "loads": "count",
              "rooms": "count", "miles": "miles", "days": "days", "x": "multiple", "times": "multiple"}
COMPATIBLE = {"kwh": {"kwh"}, "ratio": {"ratio", "bp", "pct_points"}, "cents": {"cents"}, "count": {"count", "rooms"},
              "miles": {"miles"}, "days": {"days"}, "multiple": {"multiple"}}


def ref_of(kind, n):
    return f"{kind}{n}"


def scan(text, ledger, allowed_ids=None):
    """{'unsupported': [{token, at}], 'mismatch': [{placeholder, reason, at}]} for one piece of agent text."""
    unsupported, mismatch = [], []
    for m in PLACEHOLDER.finditer(text):
        ref = ref_of(m.group(1), m.group(2))
        if not ledger.exists(ref):
            mismatch.append({"placeholder": m.group(0), "reason": "no such ID in the ledger", "at": m.start()})
            continue
        if allowed_ids is not None and ref not in allowed_ids:
            mismatch.append({"placeholder": m.group(0), "reason": "an ID the agent wasn't given", "at": m.start()})
            continue
        if m.group(1) != "C":
            after = re.match(r"\s*(%|[A-Za-z]+)", text[m.end():])
            word = after.group(1).lower() if after else ""
            if word in UNIT_WORDS:
                unit = ledger.unit(ref)
                if unit not in COMPATIBLE.get(UNIT_WORDS[word], set()):
                    mismatch.append({"placeholder": m.group(0), "reason": f"'{after.group(1)}' follows a value in {unit}",
                                     "at": m.start()})
    masked = PLACEHOLDER.sub(lambda m: "§" * len(m.group(0)), text)
    for pattern in ALLOWED:
        masked = pattern.sub(lambda m: "§" * len(m.group(0)), masked)
    for m in NUMBER.finditer(masked):
        unsupported.append({"token": text[m.start():m.end()], "at": m.start()})
    return {"unsupported": unsupported, "mismatch": mismatch}


def check(pieces, ledger, allowed_ids=None):
    """pieces is [(location, text)]. Returns {passed, failures: [{location, kind, token or placeholder, reason}]}."""
    failures = []
    for location, text in pieces:
        r = scan(text, ledger, allowed_ids)
        for u in r["unsupported"]:
            failures.append({"location": location, "kind": "unsupported", "token": u["token"], "at": u["at"],
                             "reason": "a number that no placeholder supplied"})
        for x in r["mismatch"]:
            failures.append({"location": location, "kind": "mismatch", "token": x["placeholder"], "at": x["at"],
                             "reason": x["reason"]})
    return {"passed": not failures, "failures": failures}


def display(ledger, ref, short=True):
    """A ledger value written for prose. A variance writes its own direction."""
    row = ledger.get(ref)
    if ref.startswith("C"):
        return row["status"]
    v, unit = row["value"], row["unit"]
    extra = row.get("extra") or {}
    if row.get("op") == "variance":
        vs = extra.get("vs", "budget")
        if v == 0:
            return f"on {vs}"
        amount = fmt.value(unit, abs(v), short=short) if unit != "ratio" else f"{abs(v) * 100:.1f} points"
        return f"{amount} {'above' if v > 0 else 'below'} {vs}"
    if unit == "cents" and v is not None and abs(v) < 1000000 and not short:
        return fmt.value(unit, v)
    return fmt.value(unit, v, short=short)


def render(text, ledger, wrap=None, short=True):
    """The text with every placeholder replaced by its value. wrap(ref, shown) can mark each one up as the page's
    trace links do. Text outside placeholders is left exactly as written except for one case. A claims check
    renders as its verdict, and that verdict shows once when the agent already wrote it just before the citation
    the way "is supported {C:1}" does."""
    out, last = [], 0
    for m in PLACEHOLDER.finditer(text):
        before = text[last:m.start()]
        ref = ref_of(m.group(1), m.group(2))
        shown = display(ledger, ref, short=short) if ledger.exists(ref) else m.group(0)
        said = re.search(r"(\w+)\s+$", before) if ref.startswith("C") and ledger.exists(ref) else None
        if said and said.group(1).lower() == shown.lower():
            before, shown = before[:said.start()], said.group(1)
        out.append(before if wrap is None else _escape(before))
        out.append(wrap(ref, shown) if wrap else shown)
        last = m.end()
    out.append(text[last:] if wrap is None else _escape(text[last:]))
    return "".join(out)


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
