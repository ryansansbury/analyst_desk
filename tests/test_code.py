"""The code excerpts: only the copies in excerpts/ ship, each slice still matches its module, the guard stops a private
word, and code.js is plain data."""
import json
import shutil
import unittest
from pathlib import Path

from app import code_view
from tests import helpers


class Collect(unittest.TestCase):
    def setUp(self):
        self.files = code_view.collect()

    def test_only_the_excerpts_ship_and_each_says_it_is_a_copy(self):
        wanted = {path for path, _ in code_view.FEATURED} | set(code_view.BOXES.values())
        self.assertEqual(set(self.files), wanted)
        for path, text in self.files.items():
            self.assertTrue(text.startswith((f"# An excerpt of {path}, copied", f"<!-- A copy of {path}, made")), path)

    def test_every_featured_file_and_diagram_link_exists(self):
        for path, _ in code_view.FEATURED:
            self.assertIn(path, self.files)
        for path in code_view.BOXES.values():
            self.assertIn(path, self.files)
        self.assertIn(code_view.DEFAULT, self.files)

    def test_every_slice_of_every_excerpt_still_matches_its_module(self):
        for path, text in self.files.items():
            source = helpers.HERE.joinpath(path).read_text()
            pieces = code_view.slices(text)
            self.assertTrue(pieces, path)
            for piece in pieces:
                self.assertIn(piece, source, f"{path} no longer matches. Copy the changed lines into its excerpt.")

    def test_an_excerpt_with_a_never_list_word_stops_the_build(self):
        root = helpers.TMP.joinpath("code_guard")
        shutil.rmtree(root, ignore_errors=True)
        root.joinpath("excerpts", "engine").mkdir(parents=True)
        root.joinpath("excerpts", "engine", "clean.py.txt").write_text("x = 1\n")
        never = ("zebrafinch holdings",)
        self.assertEqual(sorted(code_view.collect(root, never)), ["engine/clean.py"])
        root.joinpath("excerpts", "engine", "leak.py.txt").write_text("# a note about Zebrafinch Holdings\n")
        with self.assertRaises(code_view.Private):
            code_view.collect(root, never)

    def test_the_guard_reads_the_local_list_and_the_home_folder(self):
        lint = helpers.load_module("lint_copy", helpers.HERE.joinpath("tools", "lint_copy.py"))
        words = code_view.never_words()
        self.assertTrue(set(lint.NEVER) <= set(words))
        self.assertTrue(all(w == w.lower() for w in words))
        if str(Path.home()).count("/") >= 2:
            self.assertIn(str(Path.home()).lower(), words)

    def test_the_local_list_is_read_by_section_and_decodes_rot13(self):
        lint = helpers.load_module("lint_copy", helpers.HERE.joinpath("tools", "lint_copy.py"))
        path = helpers.TMP.joinpath("words_test.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# a note\n[never]\nZebrafinch\nrot13:bfcerl\n[retired]\nold claim\n")
        self.assertEqual(lint.local_words(path), (("zebrafinch", "osprey"), ("old claim",)))
        self.assertEqual(lint.local_words(helpers.TMP.joinpath("no_such_list.txt")), ((), ()))


class Shipped(unittest.TestCase):
    def test_code_js_is_one_data_assignment_and_the_page_loads_it(self):
        site = helpers.site()
        text = site.joinpath("code.js").read_text()
        self.assertTrue(text.startswith("window.AD_CODE = "))
        data = json.loads(text[len("window.AD_CODE = "):].rstrip().rstrip(";"))
        self.assertEqual(sorted(data), ["boxes", "default", "files", "notes"])
        index = site.joinpath("index.html").read_text()
        self.assertIn("<script src=\"code.js\"></script>", index)
        self.assertLess(index.index("<script src=\"code.js\">"), index.index("<script src=\"app.js\">"))


if __name__ == "__main__":
    unittest.main()
