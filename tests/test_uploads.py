"""Uploads: the morning's checks on any freight export, and the Upload panel's views of the twelve recorded layouts.
No model is called and nothing reaches the network."""
import unittest

from agents import validate
from app import uploads
from engine import intake
from tests import helpers


def eval_file(vid):
    w = helpers.world()
    path = next(p for p in sorted(w["files"]) if p.startswith(f"kiskadee/eval/{vid}_"))
    return path.split("/")[-1], w["files"][path], w["key"]["intake"][vid]


class CheckFile(unittest.TestCase):
    def setUp(self):
        from app.desk import Desk
        self.desk = Desk(runs={})

    def test_an_eval_file_under_its_answer_key_passes_every_morning_check(self):
        name, data, key = eval_file("V03")
        chk = uploads.check_file(intake.tms_sheet(data), validate.mapping_of(key), self.desk.ledger)
        self.assertTrue(chk["accepted"], chk["reasons"])
        self.assertEqual([r for r, _ in chk["results"]], ["dates", "key_unique", "sum_of_parts", "unit_range",
                                                          "control_total"])
        self.assertEqual(chk["revenue"], chk["invoiced"])

    def test_a_wrong_mapping_is_held_with_its_reasons(self):
        name, data, key = eval_file("V03")
        broken = validate.mapping_of(key)
        broken["columns"] = [[h, "miles" if f == "empty_miles" else f] for h, f in broken["columns"]]
        chk = uploads.check_file(intake.tms_sheet(data), broken, self.desk.ledger)
        self.assertFalse(chk["accepted"])
        self.assertTrue(chk["reasons"])


class Panel(unittest.TestCase):
    def test_the_panel_shows_all_twelve_layouts_with_their_checks(self):
        index = helpers.site().joinpath("index.html").read_text()
        panel = index.split("id=\"upload-panel\"", 1)[1].split("id=\"portfolio-body\"", 1)[0]
        self.assertEqual(panel.count("data-upload=\""), 12)
        self.assertEqual(panel.count("data-upload-detail=\""), 12)
        self.assertIn("data-default=\"V03\"", index)
        self.assertEqual(panel.count("Accepted. Every check passed."), 12)


if __name__ == "__main__":
    unittest.main()
