"""Every visible word on the page lives in WORDS.md, so the wording changes in one place.

Each `## key` heading starts an entry, and the text under it, up to the next heading, is its value. Lines inside
a paragraph join with spaces and paragraphs stay apart. A key the page asks for that WORDS.md lacks fails the
build, so nothing ships blank. Curly-brace names are filled by fill() from values the build passes in.
"""
import re
import string
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PATH = HERE.joinpath("WORDS.md")
KEY = re.compile(r"^##\s+([A-Za-z0-9_.]+)\s*$")


class MissingWord(KeyError):
    pass


RAW = {}


def parse(text):
    """{key: value} from the text of WORDS.md. A key used twice is an error. Raw lines stay in RAW for tables."""
    out, key, buf = {}, None, []

    def flush():
        if key is None:
            return
        if key in out:
            raise ValueError(f"WORDS.md uses the key {key} twice")
        paras = [" ".join(p.split()) for p in "\n".join(buf).strip().split("\n\n") if p.strip()]
        out[key] = "\n\n".join(paras)
        RAW[key] = "\n".join(buf)

    for line in text.splitlines():
        m = KEY.match(line)
        if m:
            flush()
            key, buf = m.group(1), []
        elif key is not None:
            buf.append(line)
    flush()
    return out


class Words:
    def __init__(self, entries):
        self.entries = dict(entries)
        self.used = set()

    def __getitem__(self, key):
        if key not in self.entries:
            raise MissingWord(f"WORDS.md has no entry for {key}")
        self.used.add(key)
        return self.entries[key]

    def get(self, key, default=None):
        return self[key] if key in self.entries else default

    def fill(self, key, **values):
        """The entry with its {names} filled. A name the entry uses that isn't passed is an error."""
        text = self[key]
        names = {f for _, f, _, _ in string.Formatter().parse(text) if f}
        missing = names - set(values)
        if missing:
            raise MissingWord(f"{key} needs {', '.join(sorted(missing))}")
        return text.format(**values)

    def paragraphs(self, key):
        return self[key].split("\n\n")

    def table(self, key):
        """{name: label} from an entry written as lines of '- name = label'."""
        self[key]
        out = {}
        for line in RAW.get(key, "").splitlines():
            line = line.strip()
            if line.startswith("- ") and " = " in line:
                name, _, label = line[2:].partition(" = ")
                out[name.strip()] = label.strip()
        return out


def load(path=None):
    return Words(parse(Path(path or PATH).read_text(encoding="utf-8")))
