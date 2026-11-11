"""The skeleton holds together: WORDS.md parses and passes the writing rules, and the build runs."""
import hashlib
import shutil
import subprocess
import sys
import unittest
from unittest import mock

from app import words
from tests import helpers


class Words(unittest.TestCase):
    def test_words_parse_with_the_page_keys(self):
        w = words.load()
        for key in ("page.title", "page.line", "page.footer", "page.description", "tab.portfolio", "tab.deal",
                    "tab.board", "tab.hours", "tab.how"):
            self.assertTrue(w[key], key)

    def test_a_key_used_twice_is_an_error(self):
        with self.assertRaises(ValueError):
            words.parse("## a\none\n\n## a\ntwo\n")

    def test_paragraphs_stay_apart_and_lines_join(self):
        w = words.Words(words.parse("## k\nfirst line\nsame paragraph\n\nsecond paragraph\n"))
        self.assertEqual(w.paragraphs("k"), ["first line same paragraph", "second paragraph"])

    def test_fill_needs_every_name(self):
        w = words.Words(words.parse("## k\nRecorded on {date}.\n"))
        self.assertEqual(w.fill("k", date="October 28"), "Recorded on October 28.")
        with self.assertRaises(words.MissingWord):
            w.fill("k")

    def test_words_md_passes_the_writing_rules(self):
        self.assertEqual(helpers.copy_problems(words.PATH), [])

    def test_the_footer_names_the_author_and_says_synthetic(self):
        footer = words.load()["page.footer"]
        self.assertIn("Built by Ryan Sansbury.", footer)
        self.assertIn("synthetic", footer)


class Build(unittest.TestCase):
    def test_the_build_runs(self):
        site = helpers.site()
        self.assertTrue(site.joinpath("index.html").exists())
        self.assertTrue(site.joinpath("data.js").exists())

    def test_two_builds_write_the_same_bytes(self):
        """Python orders a set differently in every run, so two builds under different hash seeds have to match file for
        file. That's what lets the release compare the page Chrome checked with the page that goes live."""
        sums = []
        for seed in ("1", "2"):
            out = helpers.TMP.joinpath(f"repeat_{seed}")
            code = f"import build; build.build(out={str(out)!r}, quiet=True, write_data=False)"
            r = subprocess.run([sys.executable, "-c", code], cwd=helpers.HERE, capture_output=True, text=True,
                               env={"PYTHONHASHSEED": seed}, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            sums.append({p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(out.rglob("*")) if p.is_file()})
            shutil.rmtree(out)
        self.assertGreater(len(sums[0]), 8)
        self.assertEqual(sums[0], sums[1])

    def test_the_build_clears_files_it_did_not_write(self):
        """A file from an older build, like a workbook under an old name, never stays beside the page."""
        out = helpers.TMP.joinpath("leftover_case")
        shutil.rmtree(out, ignore_errors=True)
        out.joinpath("old").mkdir(parents=True)
        out.joinpath("Old_model.xlsx").write_bytes(b"old")
        out.joinpath("old", "stale.js").write_text("old")
        r = subprocess.run([sys.executable, "-c", f"import build; build.build(out={str(out)!r}, quiet=True, write_data=False)"],
                           cwd=helpers.HERE, capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        self.assertFalse(out.joinpath("Old_model.xlsx").exists())
        self.assertFalse(out.joinpath("old").exists())
        self.assertTrue(out.joinpath("index.html").exists())
        shutil.rmtree(out)

    def test_the_readme_table_waits_for_the_tests_and_the_recalculation(self):
        """A fresh clone's first build has neither result, and it leaves the README as it came."""
        import build
        root = helpers.TMP.joinpath("readme_case")
        shutil.rmtree(root, ignore_errors=True)
        root.joinpath("data").mkdir(parents=True)
        readme = root.joinpath("README.md")
        readme.write_text("Intro\n<!-- results start -->\n| old |\n<!-- results end -->\nMore\n")
        with mock.patch.object(build, "HERE", root), mock.patch.object(build.how, "RECALC", root.joinpath("r.xlsx")):
            build.write_readme_results("| new |\n")
            self.assertIn("| old |", readme.read_text())
            root.joinpath("data", "test_results.json").write_text("{}")
            build.write_readme_results("| new |\n")
            self.assertIn("| old |", readme.read_text())
            root.joinpath("r.xlsx").write_bytes(b"")
            build.write_readme_results("| new |\n")
        self.assertEqual(readme.read_text(), "Intro\n<!-- results start -->\n| new |\n<!-- results end -->\nMore\n")
        shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
