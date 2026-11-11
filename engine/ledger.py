"""The ledger: every number the fund uses lives here once, tied to the file, row or cell it came from.

sources   every file received: company, morning, path, SHA-256, layout, kind, and whether it was accepted
facts     values read from a source, each with its locator (sheet and cell range, row, or line), the raw text and
          the plain-language step that turned it into a number
derived   values computed from facts or other derived values, each with its operation over IDs
checks    every check's result: rule, status (pass, flag, expected or info), severity, and the IDs involved
claims    statements in documents set against the ledger, with their status

IDs read F12, D7, K3, C2 and S5. Everything is inserted in a fixed order, so the same files always get the same
IDs, and a copy of the ledger lets each planted-error scenario branch from the same 95 mornings of history.
"""
import json
import sqlite3

SCHEMA = """
CREATE TABLE sources (source_id INTEGER PRIMARY KEY, company TEXT NOT NULL, morning TEXT, path TEXT NOT NULL,
  sha256 TEXT, layout_id TEXT, kind TEXT NOT NULL, status TEXT NOT NULL, note TEXT);
CREATE TABLE facts (fact_id INTEGER PRIMARY KEY, entity TEXT NOT NULL, period TEXT NOT NULL, metric TEXT NOT NULL,
  value INTEGER, unit TEXT NOT NULL, source_id INTEGER NOT NULL, locator TEXT NOT NULL, transform TEXT NOT NULL,
  raw TEXT, rows TEXT);
CREATE TABLE derived (derived_id INTEGER PRIMARY KEY, entity TEXT NOT NULL, period TEXT NOT NULL, metric TEXT NOT NULL,
  op TEXT NOT NULL, inputs TEXT NOT NULL, value REAL, unit TEXT NOT NULL, transform TEXT NOT NULL, extra TEXT);
CREATE TABLE checks (check_id INTEGER PRIMARY KEY, company TEXT NOT NULL, rule TEXT NOT NULL, status TEXT NOT NULL,
  severity TEXT NOT NULL, scope TEXT NOT NULL, ops_date TEXT, morning TEXT, params TEXT NOT NULL, refs TEXT NOT NULL,
  source_ids TEXT NOT NULL);
CREATE TABLE claims (claim_id INTEGER PRIMARY KEY, deliverable TEXT NOT NULL, location TEXT NOT NULL, text TEXT NOT NULL,
  metric TEXT, stated REAL, refs TEXT NOT NULL, status TEXT NOT NULL, params TEXT NOT NULL);
CREATE INDEX facts_lookup ON facts (entity, metric, period);
CREATE INDEX facts_by_source ON facts (source_id);
CREATE INDEX derived_lookup ON derived (entity, metric, period);
CREATE INDEX checks_by_morning ON checks (morning, company);
"""
PREFIX = {"F": ("facts", "fact_id"), "D": ("derived", "derived_id"), "K": ("checks", "check_id"),
          "C": ("claims", "claim_id"), "S": ("sources", "source_id")}


def split(ref):
    """'F12' -> ('F', 12)."""
    return ref[0], int(ref[1:])


class Ledger:
    def __init__(self, conn=None):
        if conn is None:
            conn = sqlite3.connect(":memory:")
            conn.executescript(SCHEMA)
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def copy(self):
        """A full copy. The open transaction is committed first, since SQLite's backup waits on it forever."""
        self.conn.commit()
        dst = sqlite3.connect(":memory:")
        self.conn.backup(dst)
        return Ledger(dst)

    def save(self, path):
        self.conn.commit()
        dst = sqlite3.connect(str(path))
        self.conn.backup(dst)
        dst.close()

    # ------------------------------------------------------------------ writing
    def source(self, company, morning, path, sha256, kind, layout_id=None, status="accepted", note=None):
        cur = self.conn.execute("INSERT INTO sources (company, morning, path, sha256, layout_id, kind, status, note) "
                                "VALUES (?,?,?,?,?,?,?,?)", (company, morning, path, sha256, layout_id, kind, status, note))
        return f"S{cur.lastrowid}"

    def set_source(self, sid, **fields):
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE sources SET {cols} WHERE source_id = ?", list(fields.values()) + [split(sid)[1]])

    def fact(self, entity, period, metric, value, unit, source_id, locator, transform, raw=None, rows=None):
        cur = self.conn.execute(
            "INSERT INTO facts (entity, period, metric, value, unit, source_id, locator, transform, raw, rows) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (entity, period, metric, value, unit, split(source_id)[1], locator, transform, raw,
             json.dumps(rows) if rows is not None else None))
        return f"F{cur.lastrowid}"

    def derive(self, entity, period, metric, op, inputs, value, unit, transform, extra=None):
        cur = self.conn.execute(
            "INSERT INTO derived (entity, period, metric, op, inputs, value, unit, transform, extra) VALUES (?,?,?,?,?,?,?,?,?)",
            (entity, period, metric, op, json.dumps(list(inputs)), value, unit, transform,
             json.dumps(extra) if extra is not None else None))
        return f"D{cur.lastrowid}"

    def check(self, company, rule, status, severity, scope, ops_date=None, morning=None, params=None, refs=(),
              source_ids=()):
        assert status in ("pass", "flag", "expected", "info"), status
        assert severity in ("error", "info"), severity
        cur = self.conn.execute(
            "INSERT INTO checks (company, rule, status, severity, scope, ops_date, morning, params, refs, source_ids) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (company, rule, status, severity, scope, ops_date, morning, json.dumps(params or {}, sort_keys=True),
             json.dumps(list(refs)), json.dumps(list(source_ids))))
        return f"K{cur.lastrowid}"

    def claim(self, deliverable, location, text, metric, stated, refs, status, params=None):
        cur = self.conn.execute(
            "INSERT INTO claims (deliverable, location, text, metric, stated, refs, status, params) VALUES (?,?,?,?,?,?,?,?)",
            (deliverable, location, text, metric, stated, json.dumps(list(refs)), status,
             json.dumps(params or {}, sort_keys=True)))
        return f"C{cur.lastrowid}"

    # ------------------------------------------------------------------ reading
    def get(self, ref):
        kind, n = split(ref)
        table, key = PREFIX[kind]
        row = self.conn.execute(f"SELECT * FROM {table} WHERE {key} = ?", (n,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        for k in ("inputs", "refs", "source_ids", "params", "rows", "extra"):
            if k in out and isinstance(out[k], str):
                out[k] = json.loads(out[k])
        out["ref"] = ref
        return out

    def exists(self, ref):
        try:
            kind, _ = split(ref)
        except (ValueError, IndexError):
            return False
        return kind in PREFIX and self.get(ref) is not None

    def value(self, ref):
        return self.get(ref)["value"]

    def unit(self, ref):
        return self.get(ref)["unit"]

    def find(self, kind, entity, metric, period):
        """The newest fact or derived value for (entity, metric, period), or None."""
        table, key = PREFIX[kind]
        row = self.conn.execute(f"SELECT {key} FROM {table} WHERE entity = ? AND metric = ? AND period = ? "
                                f"ORDER BY {key} DESC LIMIT 1", (entity, metric, period)).fetchone()
        return f"{kind}{row[0]}" if row else None

    def facts_for(self, entity, metric, periods):
        """{period: ref} for one metric over many periods, newest fact per period."""
        marks = ",".join("?" * len(periods))
        out = {}
        for fid, period in self.conn.execute(
                f"SELECT fact_id, period FROM facts WHERE entity = ? AND metric = ? AND period IN ({marks}) "
                f"ORDER BY fact_id", [entity, metric] + list(periods)):
            out[period] = f"F{fid}"
        return out

    def checks(self, **where):
        sql = "SELECT check_id FROM checks"
        if where:
            sql += " WHERE " + " AND ".join(f"{k} = ?" for k in where)
        return [self.get(f"K{r[0]}") for r in self.conn.execute(sql + " ORDER BY check_id", list(where.values()))]

    def sources(self, **where):
        sql = "SELECT source_id FROM sources"
        if where:
            sql += " WHERE " + " AND ".join(f"{k} = ?" for k in where)
        return [self.get(f"S{r[0]}") for r in self.conn.execute(sql + " ORDER BY source_id", list(where.values()))]

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
