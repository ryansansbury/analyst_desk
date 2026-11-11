"""The claims check: each numeric claim in the seller's teaser, set against the ledger.

A claim is a sentence that pairs a measure the ledger keeps with a percentage threshold. Three kinds are
recognized: an EBITDA margin floor, a cap on any one customer's share of revenue, and a contract renewal floor.
Each comes out supported, contradicted, or unverifiable when the ledger has no measure for it, and the result
cites the derived values it used. Every other percentage in the teaser would come out unverifiable.
"""
import re

PATTERNS = [
    ("ebitda_margin", re.compile(r"EBITDA margins? (?:of |above |over |exceeding |more than )+(\d+(?:\.\d+)?)%", re.I),
     "above"),
    ("customer_concentration",
     re.compile(r"No customer accounts for more than (\d+(?:\.\d+)?)% of revenue", re.I), "at_most"),
    ("renewal_rate", re.compile(r"renewal rates? (?:have |has )?(?:stayed |remained |been )?(?:above|over) (\d+(?:\.\d+)?)%",
                                re.I), "above"),
]
PERCENT = re.compile(r"(\d+(?:\.\d+)?)%")


def extract(text):
    """[{line, sentence, metric, comparator, threshold}] for every percentage claim in the document."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if not PERCENT.search(sentence):
                continue
            found = False
            for metric, pattern, comparator in PATTERNS:
                m = pattern.search(sentence)
                if m:
                    out.append({"line": n, "sentence": sentence.strip(" -*").replace("**", ""), "metric": metric,
                                "comparator": comparator, "threshold": float(m.group(1)) / 100})
                    found = True
            if not found:
                for m in PERCENT.finditer(sentence):
                    out.append({"line": n, "sentence": sentence.strip(" -*").replace("**", ""), "metric": None,
                                "comparator": None, "threshold": float(m.group(1)) / 100})
    return out


def check(ledger, text, measures):
    """Write each claim to the ledger's claims table and return the claim refs in order."""
    refs = []
    use = {"ebitda_margin": ("adjusted_margin_FY2026", "seller_margin_FY2026"),
           "customer_concentration": ("largest_share_FY2026", "largest_customer_FY2026"),
           "renewal_rate": ("renewal_rate_FY2026", None)}
    for c in extract(text):
        if c["metric"] is None:
            refs.append(ledger.claim("teaser", f"line {c['line']}", c["sentence"], None, c["threshold"], [],
                                     "unverifiable", {"reason": "no ledger measure"}))
            continue
        main, extra = use[c["metric"]]
        ref = measures[main]
        v = ledger.value(ref)
        ok = v > c["threshold"] if c["comparator"] == "above" else v <= c["threshold"]
        params = {"ledger": ref, "threshold": c["threshold"], "comparator": c["comparator"]}
        cited = [ref]
        if extra:
            params["context"] = measures[extra]
            cited.append(measures[extra])
        refs.append(ledger.claim("teaser", f"line {c['line']}", c["sentence"], c["metric"], c["threshold"], cited,
                                 "supported" if ok else "contradicted", params))
    return refs
