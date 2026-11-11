"""The public edition never calls a model. No file the build, the page or the scripts run holds a model client, an
endpoint, a key lookup, or a network call, and neither does the built site."""
import unittest

from tests import helpers

FOLDERS = ("agents", "app", "deliverables", "engine", "evals", "excerpts", "generate", "prompts", "scripts", "tools")
SUFFIXES = (".py", ".js", ".css", ".sh", ".md", ".txt")

# Each sign is written in two pieces so this file never holds the thing it looks for.
SIGNS = tuple(a + b for a, b in (
    ("api.anth", "ropic.com"), ("api.open", "ai.com"), ("generativelanguage", ".googleapis"), ("api.x", ".ai"),
    ("api.mis", "tral.ai"), ("api.deep", "seek.com"), ("x-api", "-key"), ("anthropic-", "version"),
    ("generic-", "password"), ("url", "open("), ("http", ".client"), ("import ", "socket"), ("import ", "requests"),
    ("\"claude\", ", "\"-p\""), ("XMLHttp", "Request"), ("Web", "Socket("), ("send", "Beacon("), ("fet", "ch(")))


def signs_in(text):
    return [s for s in SIGNS if s in text]


def shipped():
    """{path: text} for every source file that ships, outside tests/, which names these signs to check they're absent."""
    files = {"build.py": helpers.HERE.joinpath("build.py").read_text()}
    for folder in FOLDERS:
        for p in sorted(helpers.HERE.joinpath(folder).rglob("*")):
            rel = p.relative_to(helpers.HERE).as_posix()
            if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in rel and not rel.startswith("scripts/out/"):
                files[rel] = p.read_text()
    return files


class ReplayOnly(unittest.TestCase):
    def test_no_shipped_file_can_reach_a_model(self):
        files = shipped()
        self.assertGreater(len(files), 60)
        found = {path: signs_in(text) for path, text in files.items() if signs_in(text)}
        self.assertEqual(found, {})
        self.assertFalse(helpers.HERE.joinpath("agents", "llm.py").exists())

    def test_the_built_site_holds_no_way_to_reach_one(self):
        """code.js is the source shown as text, and the tests in it name these signs, so it's left out."""
        site = helpers.site()
        found = {name: signs_in(site.joinpath(name).read_text()) for name in ("index.html", "app.js", "app.css", "data.js")
                 if signs_in(site.joinpath(name).read_text())}
        self.assertEqual(found, {})


if __name__ == "__main__":
    unittest.main()
