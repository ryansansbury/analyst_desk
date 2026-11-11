"""Lineage: from any number to the file, row or cell it came from.

trace(ref) is what the trace drawer shows. A fact gives its source file and fingerprint, the exact row, cell or
line with an excerpt of the raw file, the step that made it a number, and every check that ran on it or its file.
A derived value gives its operation and its inputs, and each input traces the same way, down to the files.
"""
import csv
import io
import re

from engine import xlsx

RANGE = re.compile(r"^(?P<sheet>[^!]+)!(?P<col>[A-Z]+)(?P<first>\d+)(?::[A-Z]+(?P<last>\d+))?")
ROW = re.compile(r"row (\d+)")
ROWS = re.compile(r"rows (\d+) to (\d+)")
LINE = re.compile(r"line (\d+)")


class Lineage:
    def __init__(self, ledger, files):
        """files maps a source path to its bytes, including any scenario's replaced files."""
        self.L, self.files = ledger, files
        self._sheets = {}
        self._by_ref, self._by_source = {}, {}
        for c in ledger.checks():
            for r in c["refs"]:
                self._by_ref.setdefault(r, []).append(c["ref"])
            for s in c["source_ids"]:
                if s:
                    self._by_source.setdefault(s, []).append(c["ref"])

    def checks_on(self, ref, source=None):
        out = list(self._by_ref.get(ref, []))
        if source:
            out += [k for k in self._by_source.get(source, []) if k not in out]
        return out

    def trace(self, ref, max_inputs=40):
        row = self.L.get(ref)
        if row is None:
            return None
        if ref.startswith("F"):
            src = self.L.get(f"S{row['source_id']}")
            return {"ref": ref, "kind": "fact", "entity": row["entity"], "period": row["period"], "metric": row["metric"],
                    "value": row["value"], "unit": row["unit"], "locator": row["locator"], "transform": row["transform"],
                    "source": {"ref": src["ref"], "path": src["path"], "sha256": src["sha256"], "company": src["company"],
                               "morning": src["morning"], "kind": src["kind"], "layout": src["layout_id"],
                               "status": src["status"], "note": src["note"]},
                    "excerpt": self.excerpt(src["path"], row), "checks": self.checks_on(ref, src["ref"])}
        if ref.startswith("D"):
            inputs = row["inputs"]
            return {"ref": ref, "kind": "derived", "entity": row["entity"], "period": row["period"], "metric": row["metric"],
                    "value": row["value"], "unit": row["unit"], "op": row["op"], "transform": row["transform"],
                    "extra": row.get("extra"), "inputs": inputs[:max_inputs], "more_inputs": max(0, len(inputs) - max_inputs),
                    "input_count": len(inputs), "checks": self.checks_on(ref)}
        if ref.startswith("C"):
            return {"ref": ref, "kind": "claim", "text": row["text"], "status": row["status"], "location": row["location"],
                    "metric": row["metric"], "stated": row["stated"], "refs": row["refs"], "params": row["params"]}
        if ref.startswith("S"):
            return {"ref": ref, "kind": "source", "path": row["path"], "sha256": row["sha256"], "company": row["company"],
                    "morning": row["morning"], "source_kind": row["kind"], "layout": row["layout_id"],
                    "status": row["status"], "note": row["note"], "checks": self._by_source.get(ref, [])}
        if ref.startswith("K"):
            return {"ref": ref, "kind": "check", "company": row["company"], "rule": row["rule"], "status": row["status"],
                    "severity": row["severity"], "scope": row["scope"], "ops_date": row["ops_date"],
                    "params": row["params"], "refs": row["refs"]}
        return None

    # ------------------------------------------------------------------ a whole file, opened from the data room
    def preview(self, path, rows=14, cols=7):
        """The top of a file for the drawer: a workbook's first sheet from its header row, a CSV's first rows, or a
        text file's every line with the lines the claims check quotes marked."""
        data = self.files.get(path)
        if data is None:
            return {"kind": "missing"}
        if path.endswith(".csv"):
            lines = data.decode("utf-8").splitlines()
            body = [{"n": n, "cells": next(csv.reader(io.StringIO(lines[n - 1]))), "hit": False}
                    for n in range(2, min(len(lines), rows + 1) + 1)]
            return {"kind": "csv", "header": next(csv.reader(io.StringIO(lines[0]))), "column": None, "rows": body,
                    "skipped": max(0, len(lines) - 1 - len(body)), "preview": True}
        if path.endswith((".md", ".txt")):
            quoted = {int(m.group(1)) for (loc,) in self.L.conn.execute("SELECT location FROM claims")
                      for m in [LINE.search(loc)] if m}
            lines = data.decode("utf-8").splitlines()
            return {"kind": "text", "lines": [{"n": i, "text": t, "hit": i in quoted} for i, t in enumerate(lines, 1)]}
        if path.endswith(".xlsx"):
            s = next(iter(xlsx.read(data).values()))
            width = min(s.max_col(), cols)
            filled = lambda r: sum(1 for c in range(1, width + 1) if s.value((r, c)) not in (None, ""))  # noqa: E731
            head = next((r for r in range(1, min(s.max_row(), 10) + 1) if filled(r) >= 3), 1)
            show = lambda r: [_cell(s.value((r, c))) for c in range(1, width + 1)]  # noqa: E731
            last = min(s.max_row(), head + rows)
            return {"kind": "xlsx", "sheet": s.name, "column": None, "header": show(head), "header_row": head,
                    "rows": [{"n": r, "cells": show(r), "hit": False} for r in range(head + 1, last + 1)],
                    "skipped": max(0, s.max_row() - last), "letters": [xlsx.col_letter(c) for c in range(1, width + 1)],
                    "preview": True}
        return {"kind": "none"}

    # ------------------------------------------------------------------ excerpts of the raw file
    def sheet(self, path, name):
        if path not in self._sheets:
            self._sheets[path] = xlsx.read(self.files[path])
        return self._sheets[path][name]

    def excerpt(self, path, fact):
        data = self.files.get(path)
        if data is None:
            return {"kind": "missing"}
        loc = fact["locator"]
        if path.endswith(".csv"):
            text = data.decode("utf-8")
            lines = text.splitlines()
            header = next(csv.reader(io.StringIO(lines[0])))
            m = ROWS.search(loc)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                picks = [a, a + 1, b] if b - a > 2 else list(range(a, b + 1))
            else:
                m1 = ROW.search(loc)
                n = int(m1.group(1)) if m1 else 2
                picks = sorted({x for x in (n - 1, n, n + 1) if 2 <= x <= len(lines)}) if len(lines) > 4 else \
                    list(range(2, len(lines) + 1))
            col = loc.split("column ")[-1] if "column " in loc else None
            rows = [{"n": n, "cells": next(csv.reader(io.StringIO(lines[n - 1]))),
                     "hit": bool(ROW.search(loc) and int(ROW.search(loc).group(1)) == n) or (m is not None and n in (
                         int(m.group(1)), int(m.group(2))))}
                    for n in picks if n <= len(lines)]
            skipped = (int(m.group(2)) - int(m.group(1)) + 1 - len(rows)) if m else 0
            return {"kind": "csv", "header": header, "column": col, "rows": rows, "skipped": max(0, skipped)}
        if path.endswith(".txt") or path.endswith(".md"):
            lines = data.decode("utf-8").splitlines()
            m = LINE.search(loc)
            n = int(m.group(1)) if m else 1
            return {"kind": "text", "lines": [{"n": i, "text": lines[i - 1], "hit": i == n}
                                              for i in range(max(1, n - 2), min(len(lines), n + 2) + 1)]}
        if path.endswith(".xlsx"):
            m = RANGE.match(loc)
            if not m:
                return {"kind": "none"}
            s = self.sheet(path, m.group("sheet"))
            col = xlsx.col_index(m.group("col"))
            first = int(m.group("first"))
            last = int(m.group("last") or first)
            width = s.max_col()
            show = lambda r: [_cell(s.value((r, c))) for c in range(1, width + 1)]  # noqa: E731
            if m.group("last"):
                head_row = first - 1
                picks = [first, first + 1, first + 2, last] if last - first > 3 else list(range(first, last + 1))
                after = last + 1 if s.max_row() > last else None
                rows = [{"n": r, "cells": show(r), "hit": True} for r in picks]
                if after:
                    rows.append({"n": after, "cells": show(after), "hit": False, "total": True})
                return {"kind": "xlsx", "sheet": s.name, "column": xlsx.col_letter(col),
                        "header": show(head_row) if head_row >= 1 else [], "header_row": head_row, "rows": rows,
                        "skipped": max(0, last - first + 1 - len(picks)), "letters": [xlsx.col_letter(c)
                                                                                    for c in range(1, width + 1)]}
            label = s.value((first, 1))
            head = None
            for r in range(first - 1, 0, -1):
                if s.value((r, col)) is not None and isinstance(s.value((r, col)), str):
                    head = s.value((r, col))
                    break
            return {"kind": "cell", "sheet": s.name, "cell": f"{xlsx.col_letter(col)}{first}", "row_label": label,
                    "column_label": head, "value": _cell(s.value((first, col)))}
        return {"kind": "none"}


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)
