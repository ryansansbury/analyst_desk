"""After the recalc check: LibreOffice's values for every formula in the model equal the Python model's.

scripts/recalc_check.sh has LibreOffice recalculate a copy of the workbook with no stored values, so each value here
is LibreOffice's own. Money must match to the cent and ratios to a millionth. The test skips until that file exists.
"""
import unittest

from engine import xlsx
from tests import helpers

RECALC = helpers.HERE.joinpath("scripts", "out", "recalc", "Brightrow_model_formulas.xlsx")


@unittest.skipUnless(RECALC.exists(), "runs after bash scripts/recalc_check.sh")
class LibreOffice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = helpers.real_book()
        cls.lo = xlsx.read(RECALC.read_bytes())

    def test_every_formula_matches_to_the_cent(self):
        checked, bad = self.book.against(self.lo)
        self.assertEqual(bad[:10], [])
        self.assertGreater(checked, 300)

    def test_libreoffice_says_every_check_passes(self):
        checks = self.lo["Checks"]
        self.assertEqual(checks.value("F3"), "OK")
        self.assertTrue(all(checks.value(f"F{n}") == "OK" for n in range(5, 16)))
