"""The desk: the generated world, the ledger's history, every demo state and the recorded agent runs, built the
same way every time. input_for gives exactly what each agent saw when its run was recorded, and the page replays the
run against the same ledger.
"""
from agents import inputs, replay
from engine import claims, intake
from engine import pipeline as pipeline_mod
from engine.deal import DataRoomMeasures
from engine.metrics import BoardMonth, Report
from generate import common as C
from generate import run as gen

DEMO = C.DEMO.isoformat()
DEMO_TMS = f"kiskadee/{DEMO}/kiskadee_tms_{DEMO}.xlsx"


class NotReady(Exception):
    pass


class Desk:
    def __init__(self, seed=C.DEMO_SEED, runs=None):
        self.seed = seed
        self.world = gen.build(seed)
        self.files = self.world["files"]
        self.runs = replay.load() if runs is None else runs
        self.mapping = replay.intake_mapping(self.runs)
        self.pipeline = pipeline_mod.Pipeline(self.files, mapping_for=self.mapping_for)
        self.history = self.pipeline.history([m.isoformat() for m in C.MORNINGS[:-1]])
        self.clean = self.state()
        self.report = Report(self.clean, DEMO).build()
        self.board = BoardMonth(self.clean, f"{C.BOARD_MONTH:%Y-%m}").build()
        self.deal = DataRoomMeasures(self.clean).build()
        teaser = self.files["brightrow/dataroom/teaser.md"].decode()
        self.claims = claims.check(self.clean["ledger"], teaser, self.deal)

    def mapping_for(self, path, sheet):
        """The recorded intake mapping, for the demo morning's file only. Everything else needs a known layout."""
        return dict(self.mapping) if self.mapping and path.endswith(f"kiskadee_tms_{DEMO}.xlsx") else None

    def state(self, scenario=None):
        st = self.pipeline.fork(self.history)
        override = self.world["scenarios"][scenario]["files"] if scenario else None
        self.pipeline.run(st, DEMO, override=override)
        return st

    @property
    def ledger(self):
        return self.clean["ledger"]

    # ------------------------------------------------------------------ what each agent task sees
    def intake_path(self, task_id):
        if task_id == "intake_demo":
            return DEMO_TMS
        vid = task_id.split("_", 1)[1]
        return next(p for p in sorted(self.files) if p.startswith(f"kiskadee/eval/{vid}_"))

    def input_for(self, task_id):
        """(input, Ids or None) for one task."""
        if task_id.startswith("intake_"):
            path = self.intake_path(task_id)
            sheet = intake.tms_sheet(self.files[path])
            return inputs.intake(path.split("/")[-1], intake.sample_for_agent(sheet)), None
        if task_id == "daily_commentary":
            ops = C.ops_day(C.DEMO)
            return inputs.commentary(self.ledger, self.report, DEMO, f"{ops:%A}, {ops:%B} {ops.day}, and {ops:%B} to date",
                                     self.check_notes())
        if task_id == "deal_analyst":
            return inputs.deal(self.ledger, self.deal)
        if task_id == "board_deck":
            return inputs.deck(self.ledger, self.board, f"{C.BOARD_MONTH:%B %Y}")
        if task_id == "memo_writer":
            return inputs.memo(self.ledger, self.deal, self.deal_model(), self.claims, self.memo_kpis())
        raise KeyError(task_id)

    def deal_model(self):
        """The deal model on this desk's clean ledger, built once."""
        if not hasattr(self, "_deal_model"):
            from app.deal import Deal
            self._deal_model = Deal(self)
        return self._deal_model

    def memo_kpis(self):
        """Brightrow's latest month of operating KPIs from the data room, for the memo."""
        k = self.clean["kpis"]
        last = max(m for (_, m) in k)
        return [(k[("mw_under_contract", last)], "MW under contract in September 2026"),
                (k[("mw_under_contract", "2023-10")], "MW under contract in October 2023"),
                (k[("technicians", last)], "field technicians in September 2026"),
                (k[("avg_response_hours", last)], "average response time in September 2026")]

    def check_notes(self):
        """Plain notes on this morning's checks for the commentary agent. They're its input, not page copy."""
        L = self.ledger
        out = {}
        for company in ("sideoats", "kiskadee", "possumhaw"):
            cs = L.checks(morning=DEMO, company=company)
            flags = [c for c in cs if c["status"] == "flag" and c["severity"] == "error"]
            notes = []
            if flags:
                notes.append(f"{len(flags)} checks flagged this morning's files, so the report is held for review.")
            else:
                notes.append("Every check on this morning's files passed.")
            if company == "kiskadee":
                tms = self.clean["tms_status"].get(DEMO) or {}
                if tms.get("via") == "agent" and tms.get("accepted"):
                    notes.append("The freight export arrived in a new layout, and the intake agent's mapping passed "
                                 "every check before it was accepted.")
                elif tms.get("quarantined") or tms.get("via") is None:
                    notes.append("The freight export arrived in a new layout and is held until a mapping passes.")
            if company == "possumhaw" and any(c["rule"] == "deposit_tie" and c["status"] == "expected" for c in cs):
                notes.append("Yesterday's card settlements reach the bank tomorrow, which the deposit check expects.")
            out[company] = notes
        return out
