"""The synthetic world: byte-identical rebuilds, the 11 files a morning, the data room's exact targets, the TMS
quirks, and every planted error and look-alike where the key says it is."""
import csv
import hashlib
import importlib.util
import io
import json
import unittest
from datetime import date, timedelta

from engine import xlsx
from generate import catalog, layouts, run
from generate import common as C
from generate.dataroom import DataRoom
from tests import helpers

DEMO = C.DEMO.isoformat()


def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode())))


class Determinism(unittest.TestCase):
    def test_same_seed_same_bytes(self):
        a, b = helpers.world(2026), run.build(2026)
        self.assertEqual(run.manifest(a), run.manifest(b))
        self.assertEqual(run.key_text(a), run.key_text(b))

    def test_another_seed_is_another_world(self):
        self.assertNotEqual(run.manifest(helpers.world(2026))["files"], run.manifest(helpers.world(11))["files"])


class Mornings(unittest.TestCase):
    def setUp(self):
        self.files = helpers.world(2026)["files"]

    def test_eleven_files_land_every_morning(self):
        self.assertEqual(len(C.MORNINGS), 96)
        for m in C.MORNINGS:
            day = [p for p in self.files if f"/{m.isoformat()}/" in p]
            self.assertEqual(len(day), 11, m)

    def test_the_demo_morning_brings_the_new_tms_layout(self):
        book = xlsx.read(self.files[f"kiskadee/{DEMO}/kiskadee_tms_{DEMO}.xlsx"])["Loads"]
        self.assertEqual(book.value("A1"), "Load ID")
        self.assertEqual(book.value("E1"), "Line Haul Revenue")
        self.assertEqual(book.value("L1"), "Trailer Type")
        self.assertEqual(book.merges, [])
        last = book.rows()[-1]
        self.assertEqual(last[0], "Grand Total")

    def test_the_known_layout_has_its_quirks(self):
        m = "2026-10-20"
        book = xlsx.read(self.files[f"kiskadee/{m}/kiskadee_tms_{m}.xlsx"])["Loads"]
        self.assertIn("A1:D1", book.merges)
        self.assertEqual(book.value("A2"), "Load #")
        data = book.rows()[2:-1]
        self.assertTrue(all(str(r[6]).startswith("$") for r in data))
        total = book.rows()[-1]
        self.assertEqual(total[0], "TOTAL")
        cents = lambda s: int(s.replace("$", "").replace(",", "").replace(".", ""))  # noqa: E731
        self.assertEqual(cents(total[6]), sum(cents(r[6]) for r in data))

    def test_the_invoicing_total_equals_the_tms_revenue(self):
        p = helpers.world(2026)["portfolio"]
        for ops in (date(2026, 10, 27), date(2026, 9, 7)):
            day = p.kiskadee[ops]
            self.assertEqual(day["invoiced"], sum(r["linehaul_rev"] + r["fuel_surcharge"] + r["accessorials"]
                                                  for r in day["rows"]))

    def test_settlement_carries_line_losses_of_one_to_two_percent(self):
        p = helpers.world(2026)["portfolio"]
        for day in p.sideoats.values():
            for s in day["sites"].values():
                if s["generation_kwh"]:
                    loss = 1 - s["delivered_kwh"] / s["generation_kwh"]
                    self.assertTrue(0.0095 <= loss <= 0.0205, loss)

    def test_budgets_cover_july_to_december(self):
        for company in ("sideoats", "kiskadee", "possumhaw"):
            r = rows(self.files[f"{company}/budget/{company}_budget_2026.csv"])
            self.assertEqual(r[0]["date"], "2026-07-01")
            self.assertEqual(r[-1]["date"], "2026-12-31")

    def test_the_market_price_file_is_the_eleventh(self):
        self.assertIn(f"sideoats/{DEMO}/sideoats_market_price_{DEMO}.csv", self.files)


class DataRoomTargets(unittest.TestCase):
    def test_exact_targets_on_several_seeds(self):
        for seed in (2026, 11, 4242):
            d = DataRoom(seed)
            rev = d.fy_sum(d.total_revenue, 2)
            self.assertEqual(d.adjusted_ebitda(2), C.half_up(rev * 184, 1000))
            self.assertEqual(max(v[2] for v in d.customers.values()), C.half_up(rev * 127, 1000))
            seller = d.fy_sum(d.reported_ebitda, 2) + sum(d.sga["allocation"][24:])
            self.assertGreater(seller * 100, rev * 20)
            renewed = sum(r["contracts_renewed"] for r in d.kpis[24:])
            expiring = sum(r["contracts_expiring"] for r in d.kpis[24:])
            self.assertGreater(renewed * 100, expiring * 90)
            for y in range(3):
                self.assertEqual(sum(v[y] for v in d.customers.values()), d.fy_sum(d.total_revenue, y))

    def test_the_reclassification_is_in_the_file(self):
        p = xlsx.read(helpers.world(2026)["files"]["brightrow/dataroom/financials.xlsx"])["P&L"]
        labels = {p.value((r, 1)): r for r in range(1, p.max_row() + 1) if p.value((r, 1))}
        mc = labels["Module cleaning"]
        self.assertIsNone(p.value((mc, 2)))
        self.assertIsNone(p.value((mc, 19)))
        self.assertIsNotNone(p.value((mc, 20)))
        self.assertIn("Memo: module cleaning included in corrective repairs through March 2025", labels)

    def test_the_teaser_has_three_numeric_claims_and_only_years_besides(self):
        import re
        text = helpers.world(2026)["files"]["brightrow/dataroom/teaser.md"].decode()
        self.assertEqual(sorted(re.findall(r"(\d+)%", text)), ["10", "20", "90"])
        others = [n for n in re.findall(r"\d+", text) if n not in ("10", "20", "90")]
        self.assertTrue(all(1990 <= int(n) <= 2035 for n in others), others)


class Catalog(unittest.TestCase):
    def setUp(self):
        self.w = helpers.world(2026)

    def scenario(self, code):
        return self.w["scenarios"][code]

    def test_e1_is_a_thousand_times_off(self):
        s = self.scenario("E1")
        r = rows(s["files"][s["key"]["file"]])[0]
        true = self.w["portfolio"].sideoats[C.ops_day(C.DEMO)]["sites"][s["key"]["site"]]["generation_kwh"]
        self.assertAlmostEqual(float(r["generation_kwh"]) * 1000, true, delta=1)

    def test_e2_duplicates_rows(self):
        s = self.scenario("E2")
        book = xlsx.read(s["files"][s["key"]["file"]])["Loads"]
        ids = [r[0] for r in book.rows()[1:-1]]
        for lid in s["key"]["load_ids"]:
            self.assertEqual(ids.count(lid), 2)

    def test_e3_loses_the_total_label(self):
        s = self.scenario("E3")
        book = xlsx.read(s["files"][s["key"]["file"]])["Loads"]
        self.assertIsNone(book.rows()[-1][0])
        self.assertIsNotNone(book.rows()[-1][4])

    def test_e4_removes_a_site_file(self):
        s = self.scenario("E4")
        self.assertIsNone(s["files"][s["key"]["file"]])

    def test_e5_breaks_adr_times_rooms(self):
        s = self.scenario("E5")
        text = s["files"][s["key"]["file"]].decode()
        self.assertIn(C.money(s["key"]["adr_cents"]), text)
        self.assertGreater(abs(s["key"]["adr_cents"] - s["key"]["true_adr_cents"]) * s["key"]["rooms_sold"],
                           s["key"]["rooms_sold"])

    def test_e6_flips_a_credit(self):
        s = self.scenario("E6")
        book = xlsx.read(s["files"][s["key"]["file"]])["Loads"]
        row = next(r for r in book.rows() if r[0] == s["key"]["load_id"])
        self.assertFalse(str(row[6]).startswith("-"))
        self.assertGreater(s["key"]["amount_cents"], 0)

    def test_held_out_seeds_move_the_targets(self):
        other = helpers.world(11)["scenarios"]
        self.assertNotEqual((self.scenario("E2")["key"]["load_ids"]), other["E2"]["key"]["load_ids"])

    def test_l2_days_carry_their_curtailment(self):
        p = self.w["portfolio"]
        for d in self.w["key"]["lookalikes"]["L2"]["days"]:
            s = p.sideoats[date.fromisoformat(d["ops_date"])]["sites"][d["site"]]
            self.assertGreater(s["curtailment_kwh"], 0.4 * s["generation_kwh"])

    def test_l3_labor_day_sits_inside_its_budget(self):
        p = self.w["portfolio"]
        budget = {r["date"]: r for r in rows(self.w["files"]["kiskadee/budget/kiskadee_budget_2026.csv"])}
        labor = date(2026, 9, 7)
        loads = sum(1 for r in p.kiskadee[labor]["rows"] if not r.get("credit"))
        weekday = sum(1 for r in p.kiskadee[date(2026, 9, 9)]["rows"] if not r.get("credit"))
        self.assertLess(loads, 0.7 * weekday)
        self.assertEqual(budget["2026-09-07"]["day_type"], "holiday")
        ratio = loads / int(budget["2026-09-07"]["loads"])
        self.assertTrue(0.75 <= ratio <= 1.25, ratio)

    def test_l1_deposits_settle_the_audit_from_two_mornings_back(self):
        r = rows(self.w["files"][f"possumhaw/{DEMO}/possumhaw_deposits_{DEMO}.csv"])[0]
        self.assertEqual(r["deposit_date"], C.ops_day(C.DEMO).isoformat())
        self.assertEqual(r["batch_date"], (C.ops_day(C.DEMO) - timedelta(days=1)).isoformat())

    def test_the_demo_morning_is_the_wednesday_of_the_call(self):
        self.assertEqual(DEMO, helpers.DEMO_DAY)
        self.assertEqual(f"{C.DEMO:%A}", "Wednesday")
        self.assertEqual(C.BOARD_MONTH.isoformat(), "2026-10-01")


class Frozen(unittest.TestCase):
    """The catalog and the intake answer keys were frozen before any check or prompt existed."""

    def test_the_catalog_matches_its_freeze(self):
        from evals import freeze_catalog
        frozen = json.loads(freeze_catalog.CATALOG_OUT.read_text())
        self.assertEqual(freeze_catalog.catalog_sha256(), frozen["catalog_sha256"])

    def test_the_intake_answer_keys_match_their_freeze(self):
        from evals import freeze_catalog
        frozen = json.loads(freeze_catalog.INTAKE_OUT.read_text())
        self.assertEqual(freeze_catalog.answer_keys_sha256(), frozen["answer_keys_sha256"])
        for vid, sha in frozen["files"].items():
            path = next(p for p in self.files() if p.startswith(f"kiskadee/eval/{vid}_"))
            self.assertEqual(hashlib.sha256(self.files()[path]).hexdigest(), sha, vid)

    def files(self):
        return helpers.world(2026)["files"]


@unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl arrives with scripts/bootstrap.sh")
class RealLibrary(unittest.TestCase):
    def test_openpyxl_opens_every_generated_workbook(self):
        import openpyxl
        w = helpers.world(2026)
        books = [v for k, v in w["files"].items() if k.endswith(".xlsx")]
        books += [v for s in w["scenarios"].values() for k, v in s["files"].items() if v and k.endswith(".xlsx")]
        self.assertGreater(len(books), 100)
        for data in books:
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
            self.assertTrue(wb.sheetnames)


if __name__ == "__main__":
    unittest.main()
