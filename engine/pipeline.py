"""The morning run: receive each file, recognize its layout, parse it into the ledger, and run the checks.

History is every morning before the demo morning, ingested once. Each demo state (the clean morning, each planted
error) copies that ledger and runs one more morning, so every state is computed the same way the real run is.
A TMS export in an unknown layout asks mapping_for() for a mapping. On the page that's the intake agent's recorded
run, and in scoring and tests it's the answer key standing in for an accepted mapping. Either way the mapping only
counts if the validation passes.
"""
import hashlib
import time

from engine import checks as checks_mod
from engine import intake as intake_mod
from engine.ledger import Ledger

SITE_PREFIX = "sideoats_CR"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Pipeline:
    def __init__(self, files, mapping_for=None):
        """files maps a path under data/sources to bytes. mapping_for(path, sheet) returns a mapping or None."""
        self.files = files
        self.mapping_for = mapping_for or (lambda path, sheet: None)

    def morning_files(self, morning, override=None):
        m = morning if isinstance(morning, str) else morning.isoformat()
        out = {p: d for p, d in self.files.items() if f"/{m}/" in p}
        for p, d in (override or {}).items():
            if d is None:
                out.pop(p, None)
            else:
                out[p] = d
        return out

    # ------------------------------------------------------------------ the static sources
    def base(self):
        L = Ledger()
        intake = intake_mod.Intake(L)
        state = {"ledger": L, "intake": intake, "card_by_date": {}, "runs": [], "layouts": [intake_mod.TMS_V1],
                 "accepted": []}
        f = self.files
        reg_path = "sideoats/register/sideoats_asset_register.csv"
        src = L.source("sideoats", None, reg_path, sha(f[reg_path]), "register", "asset_register_v1")
        state["register"] = intake.asset_register(src, f[reg_path])
        for company in ("sideoats", "kiskadee", "possumhaw"):
            path = f"{company}/budget/{company}_budget_2026.csv"
            s = L.source(company, None, path, sha(f[path]), "budget", f"{company}_budget_v1", "accepted")
            intake.budget_file(company, s, f[path])
        ids = {}
        for name, kind in (("financials.xlsx", "data room"), ("customers.xlsx", "data room"), ("kpis.csv", "data room"),
                           ("teaser.md", "data room")):
            path = f"brightrow/dataroom/{name}"
            ids[name.split(".")[0]] = L.source("brightrow", None, path, sha(f[path]), kind, name.split(".")[0] + "_v1")
        state["fin"] = intake.financials(ids["financials"], f["brightrow/dataroom/financials.xlsx"])
        state["cust"] = intake.customers(ids["customers"], f["brightrow/dataroom/customers.xlsx"])
        state["kpis"] = intake.kpis(ids["kpis"], f["brightrow/dataroom/kpis.csv"])
        state["dataroom_ids"] = ids
        checks_mod.Checker(L, intake).dataroom(state["fin"], state["cust"], ids)
        return state

    def history(self, mornings):
        state = self.base()
        for m in mornings:
            self.run(state, m)
        return state

    def fork(self, state):
        """A copy of a state to run one more morning on, leaving the original as it was."""
        L = state["ledger"].copy()
        intake = intake_mod.Intake(L)
        intake.budget = state["intake"].budget
        out = dict(state, ledger=L, intake=intake, card_by_date=dict(state["card_by_date"]), runs=list(state["runs"]),
                   layouts=list(state["layouts"]), accepted=list(state["accepted"]),
                   tms_status=dict(state.get("tms_status", {})))
        return out

    # ------------------------------------------------------------------ one morning
    def run(self, state, morning, override=None):
        m = morning if isinstance(morning, str) else morning.isoformat()
        t0 = time.perf_counter()
        L, intake = state["ledger"], state["intake"]
        chk = checks_mod.Checker(L, intake)
        files = self.morning_files(m, override)
        received = []

        def register(path, company, kind, layout, status="accepted", note=None):
            sid = L.source(company, m, path, sha(files[path]) if path in files else None, kind, layout, status, note)
            received.append({"path": path, "company": company, "kind": kind, "layout": layout, "status": status,
                             "note": note, "source": sid})
            return sid

        def path_like(company, token):
            return sorted(p for p in files if p.startswith(f"{company}/{m}/") and token in p)

        # Sideoats
        register_ = state["register"]
        sites, src = {}, {}
        ops = None
        for sid_, asset in register_.items():
            if asset["offtake"] == "arbitrage":
                continue
            found = path_like("sideoats", f"{SITE_PREFIX}{sid_[2:]}_")
            if not found:
                continue
            p = found[0]
            s = register(p, "sideoats", "daily feed", "solar_site_v1")
            src[sid_] = s
            sites[sid_] = intake.site(s, files[p])
            ops = sites[sid_]["date"]
        battery = settlement = None
        for p in path_like("sideoats", "_battery_"):
            src["battery"] = register(p, "sideoats", "daily feed", "battery_v1")
            battery = intake.battery(src["battery"], files[p])
            ops = battery["date"]
        for p in path_like("sideoats", "_settlement_"):
            src["settlement"] = register(p, "sideoats", "control", "settlement_v1")
            settlement = intake.settlement(src["settlement"], files[p])
            ops = settlement.get("date", ops)
        price = None
        for p in path_like("sideoats", "_market_price_"):
            src["price"] = register(p, "sideoats", "daily feed", "market_price_v1")
            price = intake.market_price(src["price"], files[p])
        if ops is None:
            from datetime import date, timedelta
            ops = (date.fromisoformat(m) - timedelta(days=1)).isoformat()
        chk.sideoats(m, ops, register_, sites, battery, settlement, src)

        # Kiskadee
        bsrc, tms_out, invoicing = {}, None, None
        for p in path_like("kiskadee", "_invoicing_"):
            bsrc["invoicing"] = register(p, "kiskadee", "control", "invoicing_v1")
            invoicing = intake.invoicing(bsrc["invoicing"], files[p])
        tms_status = None
        for p in path_like("kiskadee", "_tms_"):
            sheet = intake_mod.tms_sheet(files[p])
            mapping, via = intake_mod.recognize(sheet, state["layouts"]), "known"
            if mapping is None:
                mapping, via = self.mapping_for(p, sheet), "agent"
            if mapping is None:
                bsrc["tms"] = register(p, "kiskadee", "daily feed", None, "quarantined",
                                       "no known layout matches, and no mapping is recorded for it yet")
                L.check("kiskadee", "layout", "flag", "error", "kiskadee/tms", ops, m, {"state": "no_mapping"}, [],
                        [bsrc["tms"]])
                tms_status = {"via": None, "accepted": False, "reasons": ["no mapping"], "path": p}
                continue
            rows, totals, problems = intake_mod.apply_mapping(sheet, mapping, ops)
            inv_count = L.value(invoicing["invoice_count"]) if invoicing else -1
            inv_total = L.value(invoicing["invoiced"]) if invoicing else -1
            results = checks_mod.tms_results(rows, totals, mapping, ops, inv_count, inv_total) if not problems else []
            ok, reasons = checks_mod.tms_accepts(results, problems)
            layout_id = mapping.get("layout") or "tms_v2"
            quarantined = via == "agent" and not ok
            if via == "agent" and ok:
                layout_id = f"tms_v{len(state['layouts']) + 1}"
                saved = dict(mapping, layout=layout_id)
                state["layouts"].append(saved)
                state["accepted"].append({"morning": m, "path": p, "layout": saved})
            bsrc["tms"] = register(p, "kiskadee", "daily feed", layout_id, "quarantined" if quarantined else "accepted",
                                   "; ".join(reasons) if quarantined else None)
            tms_status = {"via": via, "accepted": ok, "reasons": reasons, "path": p, "mapping": mapping,
                          "layout": layout_id, "quarantined": quarantined}
            if problems:
                L.check("kiskadee", "types", "flag", "error", "kiskadee/tms", ops, m,
                        {"problems": [x[1] for x in problems][:8]}, [], [bsrc["tms"]])
                continue
            tms_out = intake.tms_facts(bsrc["tms"], sheet, mapping, rows, ops)
            chk.kiskadee(m, ops, results, tms_out, invoicing or {}, bsrc, quarantined=quarantined, reasons=reasons)
        state.setdefault("tms_status", {})[m] = tms_status

        # Possumhaw
        psrc, audit, deposit = {}, None, None
        for p in path_like("possumhaw", "_night_audit_"):
            psrc["audit"] = register(p, "possumhaw", "daily feed", "night_audit_v1")
            audit = intake.night_audit(psrc["audit"], files[p])
        for p in path_like("possumhaw", "_deposits_"):
            psrc["deposits"] = register(p, "possumhaw", "control", "deposits_v1")
            deposit = intake.deposits(psrc["deposits"], files[p])
        if audit:
            chk.possumhaw(m, audit, deposit, state["card_by_date"], psrc)
            state["card_by_date"][audit["date"]] = audit["card_settlements"]

        seconds = time.perf_counter() - t0
        run = {"morning": m, "ops": ops, "files": received, "seconds": round(seconds, 4),
               "held": {k: len(v) for k, v in checks_mod.held(L, m).items()}, "tms": tms_status,
               "parsed": {"sites": sites, "battery": battery, "settlement": settlement, "price": price,
                          "tms": tms_out, "invoicing": invoicing, "audit": audit, "deposit": deposit}}
        state["runs"].append(run)
        state["last"] = run
        return run
