"""The page's wording for the notes the frozen detector files write into the ledger.

engine/checks.py, engine/intake.py and engine/pipeline.py decide detection. The held-out score in
evals/check_runs.json was taken on their exact bytes, and their text can't change without a new frozen run on fresh
seeds. A few of the notes they write under How it became this number predate the page's writing rules or show a date
the way the file wrote it. The drawer shows those few in the page's own words, and the ledger keeps what the engine
wrote. A test runs the writing rules over every note the drawer shows, so a new note that needs words here fails it.
"""
import re

from engine import fmt

DAY = r"(\d{4}-\d\d-\d\d)"
REWRITES = (
    (r"count of (\d+) load rows, credit rows left out", r"count of \1 load rows with the credit rows left out"),
    (r"sum of (\d+) rows, text amounts converted to cents", r"sum of \1 rows with text amounts converted to cents"),
    (r"linehaul, fuel and accessorials summed over (\d+) rows, credits included",
     r"linehaul, fuel, and accessorials summed over \1 rows with credits included"),
    (r"loaded plus empty miles on the (\d+) loads with no carrier cost, which are the company's own trucks",
     r"loaded plus empty miles on the \1 loads with no carrier cost because the company's own trucks hauled them"),
    (r"read as dollars, deposited " + DAY,
     lambda m: f"read as dollars from the deposit that landed {fmt.day_label(m.group(1))}"),
    (r"the budget row for " + DAY, lambda m: f"the budget row for {fmt.day_label(m.group(1))}"),
    (r"a budget rate, the same every day", "a budget rate that stays the same every day"),
    (r"capacity times the day's sunlight per square meter, the most the site could make",
     "the most the site could make from its capacity times the day's sunlight per square meter"),
)
COMPILED = tuple((re.compile(pattern), words) for pattern, words in REWRITES)


def page_note(text):
    """A ledger note as the drawer shows it. Anything without words here shows as the engine wrote it."""
    for rx, words in COMPILED:
        m = rx.fullmatch(text or "")
        if m:
            return words(m) if callable(words) else m.expand(words)
    return text
