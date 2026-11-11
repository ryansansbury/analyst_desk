"""The core: parsers and their quirks, mappings and validation, every check against the catalog on the two
development seeds, the gate, the claims check, the report's arithmetic and lineage down to the file."""
import unittest

from engine import checks, claims, gate, intake
from engine.deal import DataRoomMeasures
from engine.ledger import Ledger
from engine.lineage import Lineage
from engine.metrics import Report
from evals import score_checks
from generate import common as C
from tests import helpers

DEMO = C.DEMO.isoformat()
OPS = C.ops_day(C.DEMO).isoformat()


class Values(unittest.TestCase):
    def test_money_in_every_format(self):
        for text, cents in (("$1,234.56", 123456), ("-$250.00", -25000), ("(250.00)", -25000), ("1234.56", 123456),
                            (1234.56, 123456), (12, 1200), ("", None), (None, None)):
            self.assertEqual(intake.money(text), cents, text)
        for bad in ("12 dollars", "$1,2a"):
            with self.assertRaises(intake.ParseError):
                intake.money(bad)

    def test_decimal_text_rounds_half_up(self):
        self.assertEqual(intake.scaled("99.75", 10), 998)
        self.assertEqual(intake.scaled("193.485", 1), 193)


class Mappings(unittest.TestCase):
    def setUp(self):
        self.w = helpers.world(2026)
        self.sheet = intake.tms_sheet(self.w["files"][f"kiskadee/{DEMO}/kiskadee_tms_{DEMO}.xlsx"])
        self.key = self.w["key"]["intake"]["V00"]
        day = self.w["portfolio"].kiskadee[C.ops_day(C.DEMO)]
        self.count, self.total = day["invoice_count"], day["invoiced"]

    def validate(self, mapping):
        rows, totals, problems = intake.apply_mapping(self.sheet, mapping, OPS)
        results = checks.tms_results(rows, totals, mapping, OPS, self.count, self.total) if not problems else []
        return checks.tms_accepts(results, problems)

    def test_the_known_layout_is_recognized_and_the_new_one_is_not(self):
        self.assertIsNone(intake.recognize(self.sheet, [intake.TMS_V1]))
        old = intake.tms_sheet(self.w["files"]["kiskadee/2026-10-20/kiskadee_tms_2026-10-20.xlsx"])
        self.assertEqual(intake.recognize(old, [intake.TMS_V1])["layout"], "tms_v1")

    def test_the_right_mapping_is_accepted(self):
        self.assertEqual(self.validate(dict(self.key)), (True, []))

    def test_swapped_revenue_columns_are_rejected(self):
        m = dict(self.key, columns=[[h, {"linehaul_rev": "fuel_surcharge", "fuel_surcharge": "linehaul_rev"}.get(f, f)]
                                    for h, f in self.key["columns"]])
        ok, reasons = self.validate(m)
        self.assertFalse(ok)
        self.assertIn("unit_range", reasons)

    def test_an_inverted_on_time_flag_is_rejected(self):
        m = dict(self.key, on_time={"true": "N", "false": "Y"})
        self.assertFalse(self.validate(m)[0])

    def test_a_wrong_date_format_is_rejected(self):
        m = dict(self.key, date_format="%m/%d/%Y")
        self.assertFalse(self.validate(m)[0])

    def test_an_unexplained_column_is_rejected(self):
        m = dict(self.key, columns=[c for c in self.key["columns"] if c[0] != "Trailer Type"])
        ok, reasons = self.validate(m)
        self.assertFalse(ok)
        self.assertTrue(any("Trailer Type" in r for r in reasons))


class DevelopmentSeeds(unittest.TestCase):
    """The checks against the frozen catalog on the two seeds they were written on. The held-out score is in
    evals/check_runs.json."""

    def check_seed(self, seed):
        s = score_checks.score(seed)
        self.assertEqual(s["false_alarms"], 0, s["false_alarm_list"])
        self.assertEqual(s["caught"], 6, s["errors"])
        self.assertEqual(s["diagnosed"], 6, s["errors"])
        self.assertEqual(s["lookalikes_left_alone"], 3, s["lookalikes"])
        for code in ("E2", "E3", "E6"):
            self.assertTrue(s["errors"][code]["quarantined"], code)

    def test_demo_seed(self):
        self.check_seed(2026)

    def test_dev_seed(self):
        self.check_seed(11)

    def test_the_checks_are_the_code_their_held_out_score_was_taken_on(self):
        """The score on the page holds only for the exact bytes it was taken on, or for a recorded rename of the invented
        names, which swaps words and leaves detection alone. Any other change to a detector file needs a new frozen
        run on fresh seeds, and the page's words for the engine's notes live in app/notes.py instead."""
        import json
        from app.how import scored_hashes
        from evals.freeze_checks import RUNS, detectors_sha256
        self.assertIn(detectors_sha256(), scored_hashes(json.loads(RUNS.read_text())))

    def test_the_drawer_words_the_frozen_notes_without_changing_them(self):
        from app.notes import page_note
        self.assertEqual(page_note("read as dollars, deposited 2026-11-03"),
                         "read as dollars from the deposit that landed November 3")
        self.assertEqual(page_note("count of 46 load rows, credit rows left out"),
                         "count of 46 load rows with the credit rows left out")
        self.assertEqual(page_note("sum of the four sites"), "sum of the four sites")


class Morning(unittest.TestCase):
    def test_clean_demo_morning_publishes_with_the_new_layout_accepted(self):
        st = helpers.demo_state()
        self.assertEqual(checks.held(st["ledger"], DEMO), {})
        tms = st["tms_status"][DEMO]
        self.assertEqual((tms["via"], tms["accepted"], tms["layout"]), ("agent", True, "tms_v2"))

    def test_no_mapping_quarantines_the_file(self):
        from engine import pipeline
        w, _, hist = helpers.desk()
        p = pipeline.Pipeline(w["files"])
        st = p.fork(hist)
        p.run(st, DEMO)
        self.assertIn("kiskadee", checks.held(st["ledger"], DEMO))
        self.assertEqual(st["tms_status"][DEMO]["reasons"], ["no mapping"])

    def test_e1_marks_the_site(self):
        st = helpers.demo_state(scenario="E1")
        flags = checks.held(st["ledger"], DEMO)["sideoats"]
        site = helpers.world()["scenarios"]["E1"]["key"]["site"]
        self.assertTrue(any(f["scope"] == f"sideoats/{site}" and f["rule"] == "unit_range" for f in flags))


class Report_(unittest.TestCase):
    def setUp(self):
        self.st = helpers.demo_state()
        self.k = Report(self.st, DEMO).build()
        self.L = self.st["ledger"]

    def test_the_fund_adds_up(self):
        v = self.L.value
        for name in ("revenue", "revenue_budget", "ebitda", "cash"):
            parts = sum(v(self.k[c][name]) for c in ("sideoats", "kiskadee", "possumhaw"))
            self.assertAlmostEqual(v(self.k["fund"][name]), parts, places=6)
        self.assertAlmostEqual(v(self.k["fund"]["revenue_var"]),
                               v(self.k["fund"]["revenue"]) - v(self.k["fund"]["revenue_budget"]), places=6)

    def test_the_month_to_date_runs_through_the_day_before_the_demo(self):
        gen = self.L.get(self.k["sideoats"]["generation"])
        for site in gen["inputs"]:
            self.assertEqual(len(self.L.get(site)["inputs"]), C.ops_day(C.DEMO).day)

    def test_every_kpi_walks_down_to_files(self):
        lin = Lineage(self.L, helpers.world()["files"])
        seen, todo = set(), [r for c in self.k.values() for r in c.values()]
        while todo:
            ref = todo.pop()
            if ref in seen:
                continue
            seen.add(ref)
            t = lin.trace(ref, max_inputs=10000)
            self.assertIsNotNone(t, ref)
            if t["kind"] == "derived":
                todo += t["inputs"]
                if t["op"] not in ("constant", "count"):     # a sum of nothing is zero, like cash before the 20th's remittance
                    self.assertTrue(t["inputs"] or (t["op"] == "sum" and t["value"] == 0), ref)
            elif t["kind"] == "fact":
                self.assertIn(t["source"]["path"], helpers.world()["files"])
                self.assertNotEqual(t["excerpt"]["kind"], "none", ref)
        self.assertGreater(len([r for r in seen if r.startswith("F")]), 100)     # three days of November to date

    def test_a_quarantined_file_never_reaches_a_total(self):
        st = helpers.demo_state(scenario="E2")
        k = Report(st, DEMO).build()
        loads = st["ledger"].get(k["kiskadee"]["loads"])
        self.assertEqual(len(loads["inputs"]), C.ops_day(C.DEMO).day - 1)     # every day this month but the held one
        self.assertIn("held for review", loads["transform"])


class Gate(unittest.TestCase):
    def setUp(self):
        self.st = helpers.demo_state()
        self.k = Report(self.st, DEMO).build()
        self.L = self.st["ledger"]
        self.rev, self.var = self.k["fund"]["revenue"], self.k["fund"]["revenue_var"]

    def ph(self, ref):
        return "{" + ref[0] + ":" + ref[1:] + "}"

    def test_clean_text_passes_and_renders(self):
        text = f"Revenue reached {self.ph(self.rev)} and came in {self.ph(self.var)} through October 27, 2026 in FY2026."
        self.assertTrue(gate.check([("s1", text)], self.L)["passed"])
        shown = gate.render(text, self.L)
        self.assertTrue("above budget" in shown or "below budget" in shown, shown)
        self.assertNotIn("{", shown)

    def test_every_raw_number_fails_with_its_location(self):
        for raw in ("$61.2 million", "18.4%", "2,882 loads", "$2026", "1.2M", "twelve or 12"):
            r = gate.check([("memo 7.2", f"Revenue grows to {raw} by 2031.")], self.L)
            self.assertFalse(r["passed"], raw)
            self.assertEqual(r["failures"][0]["location"], "memo 7.2")

    def test_ids_must_exist_be_given_and_match_their_unit(self):
        self.assertFalse(gate.check([("x", "Revenue was {D:999999}.")], self.L)["passed"])
        self.assertFalse(gate.check([("x", f"Revenue was {self.ph(self.rev)}.")], self.L, allowed_ids={"D1"})["passed"])
        self.assertFalse(gate.check([("x", f"Revenue was {self.ph(self.rev)} MWh.")], self.L)["passed"])
        self.assertTrue(gate.check([("x", f"Revenue was {self.ph(self.rev)} in total.")], self.L,
                                   allowed_ids={self.rev})["passed"])

    def test_a_variance_writes_its_own_direction(self):
        v = self.L.value(self.var)
        self.assertTrue(gate.display(self.L, self.var).endswith("below budget" if v < 0 else "above budget"))


class Claims(unittest.TestCase):
    def test_exactly_two_claims_contradicted_and_one_supported(self):
        st = helpers.demo_state()
        dm = DataRoomMeasures(st).build()
        teaser = helpers.world()["files"]["brightrow/dataroom/teaser.md"].decode()
        refs = claims.check(st["ledger"], teaser, dm)
        got = {st["ledger"].get(r)["metric"]: st["ledger"].get(r)["status"] for r in refs}
        self.assertEqual(got, {"ebitda_margin": "contradicted", "customer_concentration": "contradicted",
                               "renewal_rate": "supported"})
        self.assertEqual(gate.display(st["ledger"], dm["adjusted_margin_FY2026"]), "18.4%")
        self.assertEqual(gate.display(st["ledger"], dm["largest_share_FY2026"]), "12.7%")

    def test_a_verdict_the_agent_already_wrote_shows_once(self):
        """A claims citation renders as its verdict. The memo agent wrote "is supported {C:1}", and the page shows
        the word once with the citation's trace on it, in the agent's own capitals."""
        st = helpers.demo_state()
        dm = DataRoomMeasures(st).build()
        teaser = helpers.world()["files"]["brightrow/dataroom/teaser.md"].decode()
        L = st["ledger"]
        by = {L.get(r)["status"]: "{C:" + r[1:] + "}" for r in claims.check(L, teaser, dm)}
        sup, con = by["supported"], by["contradicted"]
        self.assertEqual(gate.render(f"The claim is supported {sup}, and it holds.", L),
                         "The claim is supported, and it holds.")
        self.assertEqual(gate.render(f"The claim is {con}.", L), "The claim is contradicted.")
        self.assertEqual(gate.render(f"Contradicted {con} by the ledger.", L), "Contradicted by the ledger.")
        marked = gate.render(f"It is supported {sup}.", L, wrap=lambda ref, shown: f"[{ref} {shown}]")
        self.assertEqual(marked, f"It is [C{sup[3:-1]} supported].")
        self.assertEqual(gate.render(f"It is contradicted {sup}.", L), "It is contradicted supported.")

    def test_an_unknown_percentage_is_unverifiable(self):
        found = claims.extract("Margins expanded every year.\nThe backlog grew 30% last year.\n")
        self.assertEqual([(c["metric"], c["threshold"]) for c in found], [(None, 0.3)])


class DataRoom(unittest.TestCase):
    def test_the_data_room_checks_pass(self):
        L = helpers.demo_state()["ledger"]
        for rule in ("annual_tie", "sum_of_parts", "reclass", "customer_tie"):
            cs = [c for c in L.checks(company="brightrow", rule=rule)]
            self.assertTrue(cs, rule)
            self.assertTrue(all(c["status"] == "pass" for c in cs), rule)

    def test_the_restatement_moves_cleaning_out_of_repairs(self):
        st = helpers.demo_state()
        dm = DataRoomMeasures(st).build()
        L = st["ledger"]
        fy24 = sum(L.value(dm[f"rev_{x}_FY2024"]) for x in ("pm", "cr", "mc", "ms"))
        self.assertEqual(fy24, L.value(dm["revenue_FY2024"]))
        self.assertGreater(L.value(dm["rev_mc_FY2024"]), 0)


class LedgerBasics(unittest.TestCase):
    def test_copy_is_independent(self):
        L = Ledger()
        s = L.source("x", None, "p", "h", "daily feed")
        f = L.fact("e", "2026-10-01", "m", 5, "count", s, "row 2", "read")
        c = L.copy()
        c.fact("e", "2026-10-02", "m", 6, "count", s, "row 2", "read")
        self.assertEqual(L.count("facts"), 1)
        self.assertEqual(c.count("facts"), 2)
        self.assertEqual(c.value(f), 5)


if __name__ == "__main__":
    unittest.main()
