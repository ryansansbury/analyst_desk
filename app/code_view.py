"""The code excerpts on How it works. They're copies kept in excerpts/, apart from the code that runs the desk.

Each excerpt is a .txt file of verbatim slices of one module, or a whole prompt, named for the file it came from
(excerpts/engine/gate.py.txt shows as engine/gate.py). The page reads only these copies and never the desk's own
source, and tests/test_code.py checks every slice still matches its module. An excerpt holding a word from the never
list stops the build. The words come from the local list the writing rules read, which is gitignored and never
ships, plus the home folder of whoever builds. The excerpts go to site/code.js as data, apart from the page's script,
and the page shows them as text.
"""
import html
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SUFFIXES = (".py", ".js", ".css", ".md", ".sh")
GAP = "# ..."
DEFAULT = "engine/gate.py"
FEATURED = (("engine/gate.py", "gate"), ("engine/checks.py", "checks"), ("agents/validate.py", "validate"),
            ("agents/routing.py", "routing"), ("engine/model.py", "model"), ("agents/replay.py", "replay"))
BOXES = {"files": "generate/portfolio.py", "dataroom": "generate/dataroom.py", "intake": "engine/intake.py",
         "checks": "engine/checks.py", "ledger": "engine/ledger.py", "gate": "engine/gate.py",
         "report": "prompts/daily_commentary.md", "model": "engine/model.py", "memo": "prompts/memo_writer.md",
         "deck": "prompts/board_deck.md"}
esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731


class Private(ValueError):
    """A file that holds a never-list word, which the code section refuses."""


def never_words():
    home = str(Path.home()).lower()
    words = [home] if home.count("/") >= 2 else []
    tool = HERE.joinpath("tools", "lint_copy.py")
    if tool.exists():
        spec = importlib.util.spec_from_file_location("lint_copy_words", str(tool))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        words += list(mod.NEVER)
    return tuple(words)


def collect(root=HERE, never=None):
    """{path: text} for every excerpt, keyed by the file it was copied from. Raises Private if one holds a never-list
    word."""
    folder, never = Path(root).joinpath("excerpts"), never if never is not None else never_words()
    files = {}
    for p in sorted(folder.rglob("*.txt")) if folder.exists() else []:
        rel = p.relative_to(folder).as_posix()[:-len(".txt")]
        if not rel.endswith(SUFFIXES):
            continue
        text = p.read_text(encoding="utf-8")
        low = text.lower()
        hit = sorted({w for w in never if w in low})
        if hit:
            raise Private(f"the excerpt of {rel} holds a word from the never list, so the code section won't ship it")
        files[rel] = text
    return files


def slices(text):
    """An excerpt's verbatim pieces: its header and any "# ..." lines where code was left out come away, and what's
    left between them must appear in the real file exactly."""
    body = text.split("\n", 2)[2] if text.startswith(("# An excerpt", "<!-- A copy")) else text
    parts, cur = [], []
    for line in body.split("\n"):
        if line.strip() == GAP:
            parts.append("\n".join(cur).strip("\n"))
            cur = []
        else:
            cur.append(line)
    parts.append("\n".join(cur).strip("\n"))
    return [p for p in parts if p.strip()]


def tree(files):
    """The file tree: each top folder once, with its files beneath it."""
    out, folder = [], None
    for rel in sorted(files, key=lambda r: (r.split("/")[0] if "/" in r else "", r)):
        top = rel.split("/")[0] + "/" if "/" in rel else ""
        if top != folder:
            folder = top
            if top:
                out.append(f"<p class=\"code-folder\">{esc(top)}</p>")
        name = rel[len(top):]
        out.append(f"<button type=\"button\" class=\"code-file\" data-file=\"{esc(rel)}\">{esc(name)}</button>")
    return "".join(out)


def render(w, files):
    feats = "".join(f"<button type=\"button\" class=\"cfeat\" data-file=\"{esc(path)}\"><strong>{esc(w['code.feat.' + key])}"
                    f"</strong><code>{esc(path)}</code></button>" for path, key in FEATURED if path in files)
    return (f"<section class=\"panel\" id=\"how-code\" data-default=\"{esc(DEFAULT)}\"><h3>{esc(w['code.title'])}</h3>"
            f"<p>{esc(w['code.text'])}</p><div class=\"code-featured\">{feats}</div><div class=\"code-view\">"
            f"<nav class=\"code-tree\" aria-label=\"{esc(w['code.tree'])}\">{tree(files)}</nav><div class=\"code-pane\">"
            f"<div class=\"code-head\"><code id=\"code-path\"></code><span id=\"code-note\" class=\"muted\"></span></div>"
            f"<pre class=\"code\"><code id=\"code-body\"></code></pre></div></div></section>")


def payload(w, files):
    """What site/code.js holds: every file's text, the notes for the featured files, and the diagram's links."""
    return {"files": files, "notes": {path: w["code.note." + key] for path, key in FEATURED if path in files},
            "boxes": BOXES, "default": DEFAULT}
