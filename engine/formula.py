"""A small evaluator for the deal model's spreadsheet formulas.

It reads the formulas the workbook actually uses: arithmetic, comparisons, & for text, cell references with or
without a sheet name, ranges, and SUM, MIN, MAX, ABS, IF, AND, OR, NOT, ROUND and IRR. The build uses it to write
each formula's cached value, so the file shows its numbers in any viewer, and the tests hold every result equal
to the Python model before LibreOffice recalculates the same formulas again.
"""
import math
import re

TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
  | (?P<str>"(?:[^"]|"")*")
  | (?P<ref>(?:(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_]*)!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)
  | (?P<func>[A-Z][A-Z0-9.]*(?=\())
  | (?P<bool>TRUE|FALSE)
  | (?P<op><>|<=|>=|[-+*/^&=<>(),])
""", re.X)
CELL = re.compile(r"\$?([A-Z]{1,3})\$?(\d+)")


class FormulaError(ValueError):
    pass


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def col_letter(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def split_ref(text, here):
    """'Debt'!C5:C9 -> (sheet, ((5, 3), (9, 3)))."""
    sheet = here
    if "!" in text:
        sheet, text = text.rsplit("!", 1)
        if sheet.startswith("'"):
            sheet = sheet[1:-1].replace("''", "'")
    parts = text.split(":")
    cells = []
    for p in parts:
        m = CELL.fullmatch(p)
        if not m:
            raise FormulaError(f"bad reference {text}")
        cells.append((int(m.group(2)), col_index(m.group(1))))
    return sheet, tuple(cells)


def tokens(formula):
    out, i = [], 0
    text = formula.lstrip("=")
    while i < len(text):
        m = TOKEN.match(text, i)
        if not m:
            raise FormulaError(f"can't read {text[i:i + 20]!r} in {formula}")
        kind = m.lastgroup
        if kind != "ws":
            out.append((kind, m.group(kind)))
        i = m.end()
    return out


class Parser:
    def __init__(self, toks):
        self.toks, self.i = toks, 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, value=None):
        tok = self.peek()
        if value is not None and tok[1] != value:
            raise FormulaError(f"expected {value}, found {tok[1]}")
        self.i += 1
        return tok

    def parse(self):
        node = self.compare()
        if self.i != len(self.toks):
            raise FormulaError(f"unexpected {self.peek()[1]}")
        return node

    def compare(self):
        node = self.concat()
        while self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.take()[1]
            node = ("bin", op, node, self.concat())
        return node

    def concat(self):
        node = self.additive()
        while self.peek()[1] == "&":
            self.take()
            node = ("bin", "&", node, self.additive())
        return node

    def additive(self):
        node = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            node = ("bin", op, node, self.term())
        return node

    def term(self):
        node = self.power()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            node = ("bin", op, node, self.power())
        return node

    def power(self):
        node = self.unary()
        while self.peek()[1] == "^":
            self.take()
            node = ("bin", "^", node, self.unary())
        return node

    def unary(self):
        if self.peek()[1] in ("-", "+"):
            op = self.take()[1]
            return ("neg", self.unary()) if op == "-" else self.unary()
        return self.atom()

    def atom(self):
        kind, value = self.take()
        if kind == "num":
            return ("num", float(value))
        if kind == "str":
            return ("str", value[1:-1].replace("\"\"", "\""))
        if kind == "bool":
            return ("bool", value == "TRUE")
        if kind == "ref":
            return ("ref", value)
        if kind == "func":
            self.take("(")
            args = []
            if self.peek()[1] != ")":
                args.append(self.compare())
                while self.peek()[1] == ",":
                    self.take()
                    args.append(self.compare())
            self.take(")")
            return ("func", value, args)
        if value == "(":
            node = self.compare()
            self.take(")")
            return node
        raise FormulaError(f"unexpected {value}")


def irr(flows, guess=0.1):
    """The rate that sets the flows' present value to zero, by Newton's method with bisection as a fallback."""
    def npv(r):
        return sum(cf / (1 + r) ** t for t, cf in enumerate(flows))

    r = guess
    for _ in range(100):
        f = npv(r)
        d = sum(-t * cf / (1 + r) ** (t + 1) for t, cf in enumerate(flows))
        if d == 0:
            break
        nxt = r - f / d
        if abs(nxt - r) < 1e-12:
            return nxt
        r = nxt
    lo, hi = -0.99, 10.0
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


class Evaluator:
    """Evaluates every formula in a book. book maps a sheet name to {(row, col): Cell} with .value and .formula."""

    def __init__(self, book):
        self.book, self.memo, self.active = book, {}, set()

    def cell(self, sheet, rc):
        key = (sheet, rc)
        if key in self.memo:
            return self.memo[key]
        if key in self.active:
            raise FormulaError(f"circular reference at {sheet}!{col_letter(rc[1])}{rc[0]}")
        c = self.book.get(sheet, {}).get(rc)
        if c is None:
            return None
        if c.formula is None:
            v = c.value
        else:
            self.active.add(key)
            try:
                v = self.eval(Parser(tokens(c.formula)).parse(), sheet)
            except FormulaError as e:
                raise FormulaError(f"{sheet}!{col_letter(rc[1])}{rc[0]}: {e}")
            finally:
                self.active.discard(key)
        self.memo[key] = v
        return v

    def values(self, node, here):
        """A range as a flat list of values, or a single value."""
        if node[0] == "ref":
            sheet, cells = split_ref(node[1], here)
            if len(cells) == 2:
                (r1, c1), (r2, c2) = cells
                return [self.cell(sheet, (r, c)) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
        return [self.eval(node, here)]

    def eval(self, node, here):
        kind = node[0]
        if kind in ("num", "str", "bool"):
            return node[1]
        if kind == "ref":
            sheet, cells = split_ref(node[1], here)
            if len(cells) != 1:
                raise FormulaError("a range where a single value belongs")
            return self.cell(sheet, cells[0])
        if kind == "neg":
            return -num(self.eval(node[1], here))
        if kind == "bin":
            op = node[1]
            a, b = self.eval(node[2], here), self.eval(node[3], here)
            if op == "&":
                return f"{text(a)}{text(b)}"
            if op in ("=", "<>", "<", ">", "<=", ">="):
                if isinstance(a, str) or isinstance(b, str):
                    a, b = text(a), text(b)
                else:
                    a, b = num(a), num(b)
                return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            a, b = num(a), num(b)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    raise FormulaError("division by zero")
                return a / b
            if op == "^":
                return a ** b
        if kind == "func":
            name, args = node[1], node[2]
            if name == "IF":
                cond = self.eval(args[0], here)
                return self.eval(args[1], here) if truth(cond) else (self.eval(args[2], here) if len(args) > 2 else False)
            flat = [v for a in args for v in self.values(a, here)]
            if name == "SUM":
                return sum(num(v) for v in flat if v is not None and not isinstance(v, str))
            if name == "MIN":
                return min(num(v) for v in flat if v is not None and not isinstance(v, str))
            if name == "MAX":
                return max(num(v) for v in flat if v is not None and not isinstance(v, str))
            if name == "ABS":
                return abs(num(flat[0]))
            if name == "AND":
                return all(truth(v) for v in flat)
            if name == "OR":
                return any(truth(v) for v in flat)
            if name == "NOT":
                return not truth(flat[0])
            if name == "ROUND":
                v, d = num(flat[0]), int(num(flat[1]))
                q = 10 ** d
                return math.floor(abs(v) * q + 0.5) / q * (1 if v >= 0 else -1)
            if name == "IRR":
                return irr([num(v) for v in flat if v is not None])
            raise FormulaError(f"the evaluator doesn't know {name}")
        raise FormulaError(f"can't evaluate {kind}")

    def all(self):
        for sheet, cells in self.book.items():
            for rc in cells:
                self.cell(sheet, rc)
        return self.memo


def num(v):
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    raise FormulaError(f"{v!r} isn't a number")


def text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def truth(v):
    if isinstance(v, str):
        raise FormulaError(f"{v!r} isn't true or false")
    return bool(num(v))
