"""The prompt files in prompts/: front matter (id, version, purpose, output) and the system prompt below it."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
FOLDER = HERE.joinpath("prompts")


def load(task):
    text = FOLDER.joinpath(f"{task}.md").read_text(encoding="utf-8")
    meta, body = {}, text
    if text.startswith("---\n"):
        head, body = text[4:].split("\n---\n", 1)
        for line in head.splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return {"id": meta.get("id", task), "version": meta.get("version"), "purpose": meta.get("purpose"),
            "output": meta.get("output"), "system": body.strip(), "sha256": hashlib.sha256(text.encode()).hexdigest()}


def user_message(task_input, problems=None):
    """The user turn: the input as JSON, and on a repair, what was wrong with the last reply."""
    import json
    text = "Input:\n" + json.dumps(task_input, indent=1, ensure_ascii=False)
    if problems:
        text += ("\n\nYour last reply can't be used yet. Fix these problems and reply again with the whole JSON "
                 "object:\n- " + "\n- ".join(problems[:25]))
    return text + "\n\nReply with exactly one JSON object and nothing else."
