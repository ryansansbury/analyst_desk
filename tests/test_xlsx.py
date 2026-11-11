"""The XLSX writer and reader: values, formulas and cached values, merges, fonts, byte-identical output, and a
real spreadsheet library (openpyxl, after bootstrap) opening what the writer makes."""
import importlib.util
import io
import unittest
import zipfile

from engine import xlsx

BLUE = xlsx.Style(color="0000FF", num_fmt="#,##0")


def sample(recalc=False):
    wb = xlsx.Workbook(recalc_on_load=recalc)
    s = wb.sheet("Sources")
    s.set("A1", "Load")
    s.merge("A1", "C1")
    s.set("A2", "Revenue")
    s.set("B2", 1234, style=BLUE)
    s.set("C2", 0.25)
    s.set("D2", True)
    s.set("A3", "  padded & <odd> \"text\"  ")
    s.set((4, 2), 2468.5, formula="=B2*2+0.5")
    s.set("E4", "OK", formula="IF(B4>0,\"OK\",\"CHECK\")")
    s.width("A", 30)
    s.freeze = "B2"
    s.highlight_equal("E4:E4", "OK", "C6EFCE", "006100")
    t = wb.sheet("Returns & Checks")
    t.set("A1", 1234, formula="'Sources'!B2")
    return wb


class Writer(unittest.TestCase):
    def test_round_trip(self):
        book = xlsx.read(sample().to_bytes())
        self.assertEqual(list(book), ["Sources", "Returns & Checks"])
        s = book["Sources"]
        self.assertEqual(s.value("A1"), "Load")
        self.assertEqual(s.value("B2"), 1234)
        self.assertEqual(s.value("C2"), 0.25)
        self.assertIs(s.value("D2"), True)
        self.assertEqual(s.value("A3"), "  padded & <odd> \"text\"  ")
        self.assertEqual(s.value("B4"), 2468.5)
        self.assertEqual(s.formulas[(4, 2)], "B2*2+0.5")
        self.assertEqual(s.value("E4"), "OK")
        self.assertEqual(s.merges, ["A1:C1"])
        self.assertEqual(s.fonts[(2, 2)]["color"], "0000FF")
        self.assertEqual(book["Returns & Checks"].formulas[(1, 1)], "'Sources'!B2")

    def test_byte_identical(self):
        self.assertEqual(sample().to_bytes(), sample().to_bytes())

    def test_formulas_only_copy_has_no_cached_values(self):
        s = xlsx.read(sample().to_bytes(cached=False))["Sources"]
        self.assertEqual(s.formulas[(4, 2)], "B2*2+0.5")
        self.assertIsNone(s.value("B4"))
        self.assertIsNone(s.value("E4"))
        self.assertEqual(s.value("B2"), 1234)

    def test_recalc_flag_only_when_asked(self):
        def workbook_xml(wb):
            return zipfile.ZipFile(io.BytesIO(wb.to_bytes())).read("xl/workbook.xml").decode()
        self.assertNotIn("fullCalcOnLoad", workbook_xml(sample()))
        self.assertIn("fullCalcOnLoad=\"1\"", workbook_xml(sample(recalc=True)))

    def test_references(self):
        self.assertEqual(xlsx.col_letter(1), "A")
        self.assertEqual(xlsx.col_letter(27), "AA")
        self.assertEqual(xlsx.col_index("AB"), 28)
        self.assertEqual(xlsx.parse_ref("$C$12"), (12, 3))
        self.assertEqual(xlsx.quote_sheet("Debt"), "Debt")
        self.assertEqual(xlsx.quote_sheet("Returns & Checks"), "'Returns & Checks'")

    def test_bad_values_are_refused(self):
        wb = xlsx.Workbook()
        wb.sheet("S").set("A1", float("nan"))
        with self.assertRaises(ValueError):
            wb.to_bytes()
        with self.assertRaises(ValueError):
            xlsx.Workbook().sheet("bad/name")


@unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl arrives with scripts/bootstrap.sh")
class RealLibrary(unittest.TestCase):
    def test_openpyxl_opens_it_with_values_formulas_and_styles(self):
        import openpyxl
        data = sample().to_bytes()
        values = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        formulas = openpyxl.load_workbook(io.BytesIO(data))
        self.assertEqual(values.sheetnames, ["Sources", "Returns & Checks"])
        self.assertEqual(values["Sources"]["B4"].value, 2468.5)
        self.assertEqual(formulas["Sources"]["B4"].value, "=B2*2+0.5")
        self.assertEqual(values["Sources"]["E4"].value, "OK")
        self.assertEqual(formulas["Sources"]["B2"].font.color.rgb, "FF0000FF")
        self.assertEqual(formulas["Sources"]["B2"].number_format, "#,##0")
        self.assertIn("A1:C1", [str(r) for r in formulas["Sources"].merged_cells.ranges])


if __name__ == "__main__":
    unittest.main()
