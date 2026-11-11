"""The deal model's inputs, assembled and traced: the data room's FY2026 through the ledger, the deal analyst's
accepted assumptions from the recorded run, the manual overrides, and the deal team's terms.

An assumption is the agent's proposal when its recording validates, a manual override when one is set, and the
FY2026 value from history when neither exists, and the page says which. Overrides always win. Terms and overrides
are files in deal/, registered in the ledger as sources, so every input traces like any other number.
"""
import hashlib
import json
from pathlib import Path

from agents import replay, validate
from agents.inputs import ASSUMPTIONS
from engine import model

HERE = Path(__file__).resolve().parent.parent
TERMS = HERE.joinpath("deal", "deal_terms.json")
OVERRIDES = HERE.joinpath("deal", "overrides.json")
HISTORY = {"growth_pm": "growth_pm_FY2026", "growth_cr": "growth_cr_FY2026", "growth_mc": "growth_mc_FY2026",
           "growth_ms": "growth_ms_FY2026", "gross_margin": "gross_margin_FY2026", "sga_pct": "sga_pct_FY2026",
           "da_pct": "da_pct_FY2026", "capex_pct": "capex_pct_FY2026", "nwc_pct": "nwc_pct_FY2026"}
TERM_UNITS = {"x10": ("multiple_x10", 10), "bp": ("bp", 10000), "x100": ("multiple_x100", 100)}


def unit_of(key):
    for suffix, (unit, scale) in TERM_UNITS.items():
        if key.endswith(suffix):
            return unit, scale
    raise KeyError(key)


class Deal:
    def __init__(self, desk):
        self.desk = desk
        L = self.L = desk.ledger
        dm = desk.deal
        self.terms = self.load_terms()
        self.overrides = self.load_overrides()
        self.assumptions = self.assemble()
        self.base = {"gross_profit": L.value(dm["gross_profit_FY2026"]) / 100, "sga_ex": L.value(dm["sga_ex_FY2026"]) / 100,
                     "standalone": L.value(dm["standalone_year"]) / 100,
                     "adjusted_ebitda": L.value(dm["adjusted_ebitda_FY2026"]) / 100}
        for line in model.LINES:
            self.base[f"rev_{line}"] = L.value(dm[f"rev_{line}_FY2026"]) / 100
        t = {k: v["value"] for k, v in self.terms.items()}
        self.term_values = {"entry": t["entry_multiple_x10"], "exit": t["exit_multiple_x10"], "fees": t["fees_bp"],
                            "leverage": t["leverage_x10"], "rate": t["rate_bp"], "amortization": t["amortization_bp"],
                            "sweep": t["sweep_bp"], "tax": t["tax_bp"], "escalation": t["standalone_escalation_bp"],
                            "covenant_leverage": t["covenant_leverage_x100"], "covenant_coverage": t["covenant_coverage_x100"]}
        self.results = model.compute(self.base, {k: v["value"] for k, v in self.assumptions.items()}, self.term_values)
        term_refs = {"entry": self.terms["entry_multiple_x10"]["ref"], "exit": self.terms["exit_multiple_x10"]["ref"],
                     "fees": self.terms["fees_bp"]["ref"], "leverage": self.terms["leverage_x10"]["ref"],
                     "rate": self.terms["rate_bp"]["ref"], "sweep": self.terms["sweep_bp"]["ref"],
                     "covenant_leverage": self.terms["covenant_leverage_x100"]["ref"]}
        self.refs = model.register(L, self.results, {"ebitda0": dm["adjusted_ebitda_FY2026"], "terms": term_refs,
                                                     "assumptions": {k: v["ref"] for k, v in self.assumptions.items()}})

    def source(self, path, kind):
        data = path.read_bytes()
        return self.L.source("deal team", None, str(path.relative_to(HERE)), hashlib.sha256(data).hexdigest(), kind,
                             f"{kind.replace(' ', '_')}_v1")

    def load_terms(self):
        raw = json.loads(TERMS.read_text())["terms"]
        src = self.source(TERMS, "deal terms")
        out = {}
        for key, v in raw.items():
            unit, scale = unit_of(key)
            if isinstance(v, list):
                refs = [self.L.fact("brightrow/deal", f"FY{2027 + i}", f"term:{key}", x, unit, src, f"terms.{key}[{i}]",
                                    "read from the deal team's terms file") for i, x in enumerate(v)]
                out[key] = {"value": [x / scale for x in v], "ref": refs[0], "refs": refs, "raw": v}
            else:
                ref = self.L.fact("brightrow/deal", "terms", f"term:{key}", v, unit, src, f"terms.{key}",
                                  "read from the deal team's terms file")
                out[key] = {"value": v / scale, "ref": ref, "raw": v}
        return out

    def load_overrides(self):
        raw = json.loads(OVERRIDES.read_text()).get("overrides", {})
        out = {}
        if raw:
            src = self.source(OVERRIDES, "overrides")
            for key, v in sorted(raw.items()):
                bp = round(float(v) * 10000)
                out[key] = {"value": bp / 10000, "ref": self.L.fact("brightrow/deal", "overrides", f"override:{key}", bp,
                                                                   "bp", src, f"overrides.{key}", "Manual override")}
        return out

    def assemble(self):
        L, dm = self.L, self.desk.deal
        run = self.desk.runs.get("deal_analyst")
        proposals, mapping, recorded = {}, {}, None
        if run:
            chk = replay.check(run, L)
            if chk["status"] in ("valid", "stale"):
                mapping = chk["mapping"]
                proposals = {a["key"]: a for a in replay.final(run)["assumptions"]}
                recorded = run.get("recorded_at")
        out = {}
        for key, meaning in ASSUMPTIONS:
            hist = dm[HISTORY[key]]
            prop = proposals.get(key)
            item = {"key": key, "meaning": meaning, "history": hist, "proposed": prop["value"] if prop else None,
                    "rationale": validate.to_ledger(prop["rationale"], mapping) if prop else None,
                    "cites": [mapping[c] for c in prop["cites"] if mapping.get(c)] if prop else []}
            if key in self.overrides:
                o = self.overrides[key]
                item.update(source="override", value=o["value"])
                item["ref"] = L.derive("brightrow/deal", "assumption", key, "assumption", [o["ref"]], o["value"], "ratio",
                                       "A manual override, which wins over the agent's proposal", {"source": "override"})
            elif prop:
                item.update(source="agent", value=float(prop["value"]))
                item["ref"] = L.derive("brightrow/deal", "assumption", key, "assumption", item["cites"] or [hist],
                                       float(prop["value"]), "ratio",
                                       "proposed by the deal analyst agent and accepted inside the range its history allows",
                                       {"source": "agent", "recorded_at": recorded})
            else:
                item.update(source="history", value=L.value(hist))
                item["ref"] = L.derive("brightrow/deal", "assumption", key, "assumption", [hist], L.value(hist), "ratio",
                                       "the FY2026 value because no agent run is recorded", {"source": "history"})
            out[key] = item
        return out
