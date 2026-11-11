"""The deal model: hand-worked cases for the debt schedule, MOIC and IRR; the workbook's formulas against the
Python model on every value; the Checks tab; the colors; and the file a real library opens."""
import importlib.util
import io
import unittest

from engine import model, xlsx
from engine.formula import Evaluator, FormulaError, irr
from tests import helpers

BASE = {"rev_pm": 100.0, "rev_cr": 0.0, "rev_mc": 0.0, "rev_ms": 0.0, "gross_profit": 50.0, "sga_ex": 10.0,
        "standalone": 10.0, "adjusted_ebitda": 30.0}
FLAT = {"growth_pm": 0.0, "growth_cr": 0.0, "growth_mc": 0.0, "growth_ms": 0.0, "gross_margin": 0.5, "sga_pct": 0.1,
        "da_pct": 0.0, "capex_pct": 0.0, "nwc_pct": 0.0}
TERMS = {"escalation": 0.0, "leverage": 1.0, "rate": 0.1, "amortization": 0.1, "sweep": 0.5, "tax": 0.0, "entry": 5.0,
         "exit": 5.0, "fees": 0.0, "covenant_leverage": [2.0] * 5, "covenant_coverage": 1.0}


class HandWorked(unittest.TestCase):
    """Small numbers worked by hand on paper, so a mistake in the model can't hide behind its own arithmetic."""

    def setUp(self):
        self.r = model.compute(BASE, FLAT, TERMS)

    def test_year_one_debt_schedule(self):
        r = self.r
        self.assertEqual(r["ebitda"][1], 30.0)                  # 50 gross profit less 10 SG&A less 10 standalone
        self.assertEqual((r["opening"][1], r["interest"][1], r["mandatory"][1]), (30.0, 3.0, 3.0))
        self.assertEqual(r["avail"][1], 24.0)                   # 30 less 3 interest less 3 amortization
        self.assertEqual(r["sweep"][1], 12.0)                   # half of 24, under the 27 still owed
        self.assertEqual((r["closing"][1], r["cash"][1], r["net_debt"][1]), (15.0, 12.0, 3.0))

    def test_year_two_pays_the_loan_off(self):
        r = self.r
        self.assertEqual((r["opening"][2], r["interest"][2], r["mandatory"][2]), (15.0, 1.5, 3.0))
        self.assertEqual(r["sweep"][2], 12.0)                   # capped at the 12 still owed after amortization
        self.assertEqual((r["closing"][2], r["cash"][2]), (0.0, 25.5))
        self.assertIsNone(r["coverage"][3])                     # no interest once the loan is gone

    def test_returns(self):
        r = self.r
        self.assertEqual((r["ev"], r["debt0"], r["equity0"]), (150.0, 30.0, 120.0))
        self.assertEqual(r["cash"][5], 115.5)                   # 25.5 then 30 a year for three more years
        self.assertEqual(r["equity_exit"], 265.5)               # 150 exit value plus 115.5 net cash
        self.assertAlmostEqual(r["moic"], 2.2125, places=12)
        self.assertAlmostEqual(r["irr"], 2.2125 ** 0.2 - 1, places=12)
        self.assertAlmostEqual(irr(r["flows"]), r["irr"], places=9)

    def test_taxes_never_go_negative(self):
        r = model.compute(BASE, dict(FLAT, gross_margin=0.25), dict(TERMS, tax=0.25, rate=0.3))
        self.assertEqual(r["ebit"][1], 5.0)                     # 25 gross profit less 10 and 10
        self.assertEqual(r["interest"][1], 9.0)                 # more than EBIT, so there's no taxable profit
        self.assertEqual(r["taxes"][1], 0.0)


class Formulas(unittest.TestCase):
    def evaluate(self, cells):
        class C:
            def __init__(self, value=None, formula=None):
                self.value, self.formula = value, formula
        book = {"S": {xlsx.parse_ref(k): C(*v) for k, v in cells.items()}, "T": {(1, 1): C(10.0)}}
        return Evaluator(book)

    def test_arithmetic_ranges_and_functions(self):
        e = self.evaluate({"A1": (2.0,), "A2": (3.0,), "A3": (None, "SUM(A1:A2)*T!A1-2^3"),
                           "A4": (None, "IF(AND(A1<A2,A3>0),\"OK\",\"CHECK\")"), "A5": (None, "MAX(0,MIN(A1,A2)-5)"),
                           "A6": (None, "-A1+ABS(-4)"), "A7": (None, "ROUND(2.345,2)")})
        self.assertEqual(e.cell("S", (3, 1)), 42.0)
        self.assertEqual(e.cell("S", (4, 1)), "OK")
        self.assertEqual(e.cell("S", (5, 1)), 0.0)
        self.assertEqual(e.cell("S", (6, 1)), 2.0)
        self.assertEqual(e.cell("S", (7, 1)), 2.35)

    def test_a_circular_reference_is_an_error(self):
        e = self.evaluate({"A1": (None, "A2+1"), "A2": (None, "A1+1")})
        with self.assertRaises(FormulaError):
            e.cell("S", (1, 1))

    def test_irr_matches_the_closed_form(self):
        self.assertAlmostEqual(irr([-100.0, 0, 0, 0, 0, 250.0]), 2.5 ** 0.2 - 1, places=10)
        self.assertAlmostEqual(irr([-100.0, 10, 10, 110]), 0.10, places=10)


class Workbook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = helpers.real_book()
        cls.r = cls.book.deal.results

    def v(self, sheet, cell):
        return self.book.value(sheet, cell)

    def test_formulas_equal_the_python_model_to_the_cent(self):
        from deliverables.model_xlsx import parity, parity_gaps
        pairs = parity(self.r)
        for sheet, cell, py, tol in pairs:
            self.assertLess(abs(self.v(sheet, cell) - py), tol, f"{sheet}!{cell}")
        self.assertEqual(parity_gaps(self.book), (len(pairs), []))
        self.assertEqual(len(pairs), 74)

    def test_every_check_is_green(self):
        self.assertEqual(self.v("Checks", "F3"), "OK")
        self.assertEqual([self.v("Checks", f"F{n}") for n in range(5, 16)], ["OK"] * 11)

    def test_the_adjusted_margin_ties_to_the_claims_check(self):
        margin = self.v("Adjustments", "E10")
        self.assertEqual(round(margin, 3), 0.184)

    def test_inputs_are_blue_formulas_black_links_green(self):
        data = xlsx.read(self.book.workbook())
        a = data["Assumptions"]
        self.assertEqual(a.fonts[(6, 4)]["color"], "0000FF")
        self.assertEqual(a.fonts[(6, 3)]["color"], "008000")
        self.assertIn(data["Projections"].fonts[(15, 4)]["color"], (None, ""))
        self.assertEqual(data["Projections"].formulas[(15, 4)], "D12-D13-D14")

    def test_only_sources_and_inputs_hold_hard_coded_numbers(self):
        for name, sheet in self.book.sheets.items():
            for rc, cell in sheet.cells.items():
                if cell.formula is None and isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                    allowed = name == "Sources" or cell.kind == "input" or (name == "Returns" and rc[0] == 19) or \
                        (name == "Checks" and rc[1] == 4)
                    self.assertTrue(allowed, f"{name}!{xlsx.ref(*rc)} is a hard-coded number")

    def test_the_formulas_only_copy_carries_no_values(self):
        data = xlsx.read(self.book.workbook(cached=False))
        self.assertIsNone(data["Returns"].value("C16"))
        self.assertEqual(data["Returns"].formulas[xlsx.parse_ref("C20")], "IRR(C19:H19)")

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl arrives with scripts/bootstrap.sh")
    def test_openpyxl_opens_it_with_formulas_and_values(self):
        import openpyxl
        data = self.book.workbook()
        f = openpyxl.load_workbook(io.BytesIO(data))
        v = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        self.assertEqual(f.sheetnames[:3], ["README", "Sources", "Historicals"])
        self.assertEqual(f["Returns"]["C16"].value, "=C15/C10")
        self.assertAlmostEqual(v["Returns"]["C16"].value, self.r["moic"], places=9)
        self.assertEqual(v["Checks"]["F3"].value, "OK")


class ModelView(unittest.TestCase):
    """The page's Model view shows exactly the workbook: every cell, its formula and its value as formatted."""

    def test_the_view_matches_the_workbook_cell_for_cell(self):
        import html
        import re
        from app.model_view import show
        r = helpers.built()
        book = helpers.TMP
        index = helpers.site().joinpath("index.html").read_text()
        cells = re.findall(r"<td class=\"([^\"]*)\" data-cell=\"([^\"]+)\" data-src=\"model\"((?: data-[a-z]+=\"[^\"]*\")*)>"
                           r"([^<]*)</td>", index)
        self.assertGreater(len(cells), 1000)
        wb = r["book"]
        for _, where, attrs, text in cells:
            sheet, ref = where.split("!")
            cell = wb.sheets[sheet].cells[xlsx.parse_ref(ref)]
            f = re.search(r"data-f=\"([^\"]*)\"", attrs)
            self.assertEqual(html.unescape(f.group(1)) if f else None, "=" + cell.formula if cell.formula else None, where)
            value = wb.values.get((sheet, xlsx.parse_ref(ref))) if cell.formula else cell.value
            self.assertEqual(html.unescape(text), show(value, cell.fmt), where)
        self.assertTrue(book.exists())


if __name__ == "__main__":
    unittest.main()
