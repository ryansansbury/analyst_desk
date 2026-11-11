#!/usr/bin/env python3
"""Check copy against the desk's writing rules. Standalone, no dependencies.

    python3 tools/lint_copy.py <file> [<file> ...]

Works on .md, .txt and .html files. HTML loses its tags first, and Markdown skips headings,
code fences and table rules. Each sentence is checked for:
- a pause comma (a comma belongs only between list items or before a conjunction joining two clauses);
- colons, semicolons and dashes in prose;
- "rather than," which reads as filler;
- words on the local never list, and claims on the local list to read twice.
First person and missing closing periods are fine. Exits 1 when anything is flagged.

The two word lists live in private_words.txt beside the build, which is gitignored and never ships. The rules run
the same without it.
"""
import codecs
import html
import re
import sys
from pathlib import Path

CONJ = re.compile(r",\s+(?:and|but|or|so|yet|nor)\b")
NUMBER_COMMA = re.compile(r"\d,\d")
SALUTATION = re.compile(r"^(?:Hi|Hello|Hey|Dear)\b[^.!?]{0,60},$")
LOCAL = Path(__file__).resolve().parent.parent.joinpath("private_words.txt")


def local_words(path=LOCAL):
    """(never, retired) from the local list. A [never] or [retired] line starts a list, a # line is a note, and a word
    written rot13:... is decoded first, for a word that shouldn't appear in any file even here."""
    lists, current = {"never": [], "retired": []}, None
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("[") and s.endswith("]"):
                current = s[1:-1].strip().lower()
            elif current in lists:
                lists[current].append((codecs.decode(s[6:], "rot13") if s.startswith("rot13:") else s).lower())
    return tuple(lists["never"]), tuple(lists["retired"])


NEVER, RETIRED = local_words()


def prose(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".html", ".htm"):
        text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", "\n", text)
        text = html.unescape(text)
    out, fence = [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            fence = not fence
            continue
        if fence or not s or s.startswith("#") or set(s) <= set("|-: "):
            continue
        s = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", s).replace("**", "").replace("`", "")
        out.append(s)
    return out


def sentences(line):
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", line) if len(p.split()) >= 3]


def check(sent):
    if SALUTATION.match(sent):
        return []
    found, low, commas = [], sent.lower(), sent.count(",")
    if commas == 1 and not CONJ.search(sent) and not NUMBER_COMMA.search(sent):
        found.append("one comma that reads as a pause")
    if commas >= 2 and not CONJ.search(sent) and not NUMBER_COMMA.search(sent):
        found.append(f"{commas} commas and no conjunction after any of them")
    if ":" in sent.replace("://", ""):
        found.append("colon")
    if ";" in sent:
        found.append("semicolon")
    if re.search(r"—|–| - ", sent):
        found.append("dash")
    if "rather than" in low:
        found.append('"rather than"')
    found += [f'"{w}" never goes out' for w in NEVER if w in low]
    found += [f'"{w}" is on the list of claims to read twice' for w in RETIRED if w in low]
    return found


def main(paths):
    flagged = checked = 0
    for p in map(Path, paths):
        for line in prose(p):
            for sent in sentences(line):
                checked += 1
                if issues := check(sent):
                    flagged += 1
                    print(f"{p}: {'; '.join(issues)}\n    {sent}")
    print(f"{checked} sentences checked, {flagged} flagged")
    return 1 if flagged else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 tools/lint_copy.py <file> [<file> ...]")
    sys.exit(main(sys.argv[1:]))
