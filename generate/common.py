"""Shared pieces of the generator: the calendar, seeded random streams, money as text, and CSV output.

Each morning run receives yesterday's files: the folder date is the morning the files land, and the data inside
covers the operating day before it. The demo morning is Wednesday 2026-11-04, and it carries Tuesday's numbers.
November to date runs through the 3rd, and the board deck covers October, the last full month.
The window holds 96 mornings, 2026-08-01 to 2026-11-04, and every other date in the build comes from DEMO.
"""
import csv
import io
import random
from datetime import date, timedelta

DEMO_SEED = 2026
DEV_SEED = 11
FIRST_MORNING = date(2026, 8, 1)
DEMO = date(2026, 11, 4)
MORNINGS = [FIRST_MORNING + timedelta(days=i) for i in range((DEMO - FIRST_MORNING).days + 1)]
SIM_START = date(2026, 7, 1)          # simulated from here so remittances and balances have a past
BUDGET_START, BUDGET_END = date(2026, 7, 1), date(2026, 12, 31)
HOLIDAYS = {date(2026, 9, 7): "Labor Day"}


def ops_day(morning):
    return morning - timedelta(days=1)


def morning_of(ops):
    return ops + timedelta(days=1)


def days(first, last):
    out, d = [], first
    while d <= last:
        out.append(d)
        d += timedelta(days=1)
    return out


SIM_DAYS = days(SIM_START, ops_day(DEMO))
OPS_DAYS = [ops_day(m) for m in MORNINGS]
BOARD_MONTH = (ops_day(DEMO).replace(day=1) - timedelta(days=1)).replace(day=1)   # the last full month, for the board


def stream(seed, name):
    """A random stream for one part of the world. String seeds hash with SHA-512, so they're stable everywhere."""
    return random.Random(f"{seed}:{name}")


def half_up(num, den):
    if den < 0:
        num, den = -num, -den
    if num < 0:
        return -half_up(-num, den)
    return (2 * num + den) // (2 * den)


def money(cents, style="text"):
    """Cents as the text a system would export. text: $1,234.56 and -$250.00. plain: 1234.56 and -250.00.
    paren: 1,234.56 and (250.00)."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    if style == "text":
        return f"{sign}${whole:,}.{frac:02d}"
    if style == "plain":
        return f"{sign}{whole}.{frac:02d}"
    if style == "paren":
        body = f"{whole:,}.{frac:02d}"
        return f"({body})" if cents < 0 else body
    raise ValueError(style)


def csv_text(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue()


def month_days(d):
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (nxt - date(d.year, d.month, 1)).days
