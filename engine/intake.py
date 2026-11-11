"""Intake: recognize each file's layout, parse it into ledger facts, and map the files no parser knows.

Every known layout has a deterministic parser that writes facts with a locator (a CSV row and column, a sheet and
cell range, or a line of text), the raw text, and the plain-language step that turned it into a number. A TMS
export whose headers match no known or saved layout needs a mapping of its columns to the schema, which comes from
the intake agent's recorded run. The mapping is applied and then validated by the same checks every TMS file
gets, and it's accepted only if all of them pass. Otherwise the file is quarantined with the reasons. An accepted
mapping is saved as a layout, so the next file in that layout parses without the agent.
"""
import csv
import io
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from engine import xlsx

FIELDS = ("load_id", "date", "customer", "lane", "miles", "empty_miles", "linehaul_rev", "fuel_surcharge",
          "accessorials", "carrier_cost", "on_time")
MONEY = ("linehaul_rev", "fuel_surcharge", "accessorials", "carrier_cost")
TMS_V1 = {"layout": "tms_v1", "header_rows": 2,
          "columns": [["Load #", "load_id"], ["Ship Date", "date"], ["Customer", "customer"], ["Lane", "lane"],
                      ["Loaded Miles", "miles"], ["Empty Miles", "empty_miles"], ["Linehaul Rev", "linehaul_rev"],
                      ["Fuel Surcharge", "fuel_surcharge"], ["Accessorials", "accessorials"],
                      ["Carrier Cost", "carrier_cost"], ["On Time", "on_time"]],
          "date_format": "%m/%d/%Y", "money_format": "text", "on_time": {"true": "Y", "false": "N"},
          "totals_label": "TOTAL"}
SITE_HEADER = ["date", "site_id", "generation_kwh", "availability_pct", "curtailment_kwh", "insolation_kwh_m2",
               "inverter_faults"]
BATTERY_HEADER = ["date", "asset_id", "cycles", "charge_kwh", "discharge_kwh", "arbitrage_revenue_cents"]
SETTLEMENT_HEADER = ["operating_date", "asset_id", "delivered_kwh", "price_usd_per_mwh", "amount_usd", "memo"]
PRICE_HEADER = ["date", "hub", "avg_price_usd_per_mwh"]
INVOICING_HEADER = ["batch_date", "batch_id", "invoice_count", "invoiced_usd", "cash_applied_usd", "ar_balance_usd"]
DEPOSITS_HEADER = ["deposit_date", "batch_date", "gross_usd", "fees_usd", "net_usd", "reference"]
AUDIT_LINES = {"Rooms available": ("rooms_available", "count"), "Rooms sold": ("rooms_sold", "count"),
               "Complimentary rooms": ("comp_rooms", "count"), "ADR": ("adr_reported", "cents"),
               "Room revenue": ("room_revenue", "cents"), "Food and beverage": ("fb_revenue", "cents"),
               "Spa, golf and other": ("other_revenue", "cents"), "Total revenue": ("total_revenue", "cents"),
               "Card settlements": ("card_settlements", "cents"), "Direct bill and cash": ("direct_bill", "cents")}
AUDIT_LINE = re.compile(r"^\s+(.+?) \.+ +(\S.*?)\s*$")


class ParseError(ValueError):
    pass


# ---------------------------------------------------------------------- values
def dec(text):
    try:
        return Decimal(str(text).strip())
    except InvalidOperation:
        raise ParseError(f"{text!r} isn't a number")


def scaled(text, factor):
    """A decimal text times factor, rounded half up to a whole number: '99.7' x 100 -> 9970."""
    return int((dec(text) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def money(v):
    """Whole cents from $1,234.56, -$250.00, (250.00), 1234.56 or a number cell. Blank is None."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise ParseError(f"{v!r} isn't an amount")
    if isinstance(v, (int, float)):
        return scaled(repr(v) if isinstance(v, float) else v, 100)
    s, neg = v.strip(), False
    if s.startswith("(") and s.endswith(")"):
        s, neg = s[1:-1], True
    if s.startswith("-"):
        s, neg = s[1:], not neg
    s = s.replace("$", "").replace(",", "").strip()
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        raise ParseError(f"{v!r} isn't an amount")
    c = scaled(s, 100)
    return -c if neg else c


def whole(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise ParseError(f"{v!r} isn't a whole number")
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, int):
        return v
    s = str(v).replace(",", "").strip()
    if not re.fullmatch(r"-?\d+", s):
        raise ParseError(f"{v!r} isn't a whole number")
    return int(s)


def csv_table(data):
    """(header, [(line number, row dict, raw line)]). The header is line 1."""
    text = data.decode("utf-8")
    lines = text.splitlines()
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    out = []
    for n, values in enumerate(reader, 2):
        out.append((n, dict(zip(header, values)), lines[n - 1]))
    return header, out


def table_text(data, lines=None):
    """The raw text lines of a text file, for excerpts."""
    return data.decode("utf-8").splitlines()


# ---------------------------------------------------------------------- TMS mappings
def tms_sheet(data):
    book = xlsx.read(data)
    return next(iter(book.values()))


def header_texts(sheet, row):
    return [str(v).strip() if v is not None else "" for v in sheet.rows()[row - 1]] if sheet.max_row() >= row else []


def matches(sheet, mapping):
    want = [h for h, _ in mapping["columns"]]
    got = header_texts(sheet, mapping["header_rows"])
    while got and not got[-1]:
        got.pop()
    return got == want


def recognize(sheet, layouts):
    """The known or saved mapping whose header matches, or None."""
    for m in layouts:
        if matches(sheet, m):
            return m
    return None


def sample_for_agent(sheet, n=10):
    """What the intake agent sees: the first two rows, the next ten and the last two, as text."""
    rows = sheet.rows()
    show = lambda r: ["" if v is None else str(v) for v in r]  # noqa: E731
    return {"top_rows": [show(r) for r in rows[:2]], "sample_rows": [show(r) for r in rows[2:2 + n]],
            "last_rows": [show(r) for r in rows[-2:]], "row_count": len(rows)}


def apply_mapping(sheet, mapping, ops_date):
    """Typed rows, the totals row if the layout has one, and every value that didn't parse.

    Rows are {field: value, 'row': sheet row}. A mapping that leaves a column unexplained, or names a schema
    field twice, is a problem before any row is read."""
    problems = []
    cols = mapping.get("columns") or []
    headers = header_texts(sheet, mapping.get("header_rows", 1))
    while headers and not headers[-1]:
        headers.pop()
    by_header = {}
    for h, f in cols:
        if f is not None and f not in FIELDS:
            problems.append(("mapping", f"{f} isn't a schema field"))
        by_header[str(h).strip()] = f
    fields = [by_header.get(h, "?") for h in headers]
    unexplained = [h for h, f in zip(headers, fields) if f == "?"]
    if unexplained:
        problems.append(("mapping", f"the mapping doesn't cover {', '.join(unexplained)}"))
    named = [f for f in fields if f not in (None, "?")]
    for f in FIELDS:
        if named.count(f) != 1:
            problems.append(("mapping", f"{f} is mapped {named.count(f)} times"))
    if problems:
        return [], None, problems
    col_of = {f: i for i, f in enumerate(fields) if f}
    label = (mapping.get("totals_label") or "").strip().lower()
    on_true, on_false = str(mapping["on_time"]["true"]), str(mapping["on_time"]["false"])
    rows, totals = [], None
    all_rows = sheet.rows()
    for r in range(mapping.get("header_rows", 1) + 1, len(all_rows) + 1):
        values = all_rows[r - 1]
        if not any(v is not None and str(v).strip() for v in values):
            continue
        get = lambda f: values[col_of[f]] if col_of[f] < len(values) else None  # noqa: E731
        if label and any(isinstance(v, str) and v.strip().lower() == label for v in values):
            totals = {"row": r}
            for f in ("miles", "empty_miles") + MONEY:
                try:
                    totals[f] = money(get(f)) if f in MONEY else whole(get(f))
                except ParseError as e:
                    problems.append(("types", f"totals row {r}: {e}"))
            continue
        row = {"row": r}
        try:
            row["load_id"] = None if get("load_id") is None else str(get("load_id")).strip()
            raw_date = get("date")
            row["date"] = None if raw_date is None else datetime.strptime(str(raw_date).strip(),
                                                                          mapping["date_format"]).date().isoformat()
            row["customer"] = None if get("customer") is None else str(get("customer")).strip()
            row["lane"] = "" if get("lane") is None else str(get("lane")).strip()
            row["miles"] = whole(get("miles")) or 0
            row["empty_miles"] = whole(get("empty_miles")) or 0
            for f in MONEY:
                row[f] = money(get(f))
            for f in ("linehaul_rev", "fuel_surcharge", "accessorials"):
                row[f] = row[f] or 0
            ot = get("on_time")
            row["on_time"] = None if ot is None else True if str(ot).strip() == on_true else \
                False if str(ot).strip() == on_false else "?"
            if row["on_time"] == "?":
                raise ParseError(f"on-time value {ot!r} is neither {on_true!r} nor {on_false!r}")
        except (ParseError, ValueError) as e:
            problems.append(("types", f"row {r}: {e}"))
            continue
        row["credit"] = row["miles"] == 0 and (row["linehaul_rev"] + row["fuel_surcharge"] + row["accessorials"]) < 0
        rows.append(row)
    return rows, totals, problems


def save_layout(mapping, folder, layout_id):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    m = dict(mapping, layout=layout_id)
    folder.joinpath(f"{layout_id}.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    return m


def load_layouts(folder):
    out = [TMS_V1]
    folder = Path(folder)
    if folder.exists():
        for p in sorted(folder.glob("*.json")):
            out.append(json.loads(p.read_text()))
    return out


# ---------------------------------------------------------------------- facts per file type
class Intake:
    """Writes one file's facts into the ledger. Each method returns the source ID and what it parsed."""

    def __init__(self, ledger):
        self.ledger = ledger
        self.budget = {}

    def site(self, sid_source, data):
        header, rows = csv_table(data)
        if header != SITE_HEADER:
            raise ParseError("the site file's columns don't match the known layout")
        n, r, raw = rows[0]
        ent, day = f"sideoats/{r['site_id']}", r["date"]
        L = self.ledger
        out = {"site": r["site_id"], "date": day, "row": n}
        for metric, col, unit, value, step in (
                ("generation_kwh", "generation_kwh", "kwh", scaled(r["generation_kwh"], 1), "read as kWh"),
                ("curtailment_kwh", "curtailment_kwh", "kwh", scaled(r["curtailment_kwh"], 1), "read as kWh"),
                ("availability", "availability_pct", "bp", scaled(r["availability_pct"], 100),
                 "read as a percent with one decimal"),
                ("insolation", "insolation_kwh_m2", "wh_m2", scaled(r["insolation_kwh_m2"], 1000),
                 "read as kWh per square meter"),
                ("inverter_faults", "inverter_faults", "count", whole(r["inverter_faults"]), "read as a count")):
            out[metric] = L.fact(ent, day, metric, value, unit, sid_source, f"row {n}, column {col}", step, raw=raw)
        return out

    def battery(self, src, data):
        header, rows = csv_table(data)
        if header != BATTERY_HEADER:
            raise ParseError("the battery file's columns don't match the known layout")
        n, r, raw = rows[0]
        ent, day = f"sideoats/{r['asset_id']}", r["date"]
        out = {"asset": r["asset_id"], "date": day}
        for metric, unit in (("cycles", "count"), ("charge_kwh", "kwh"), ("discharge_kwh", "kwh"),
                             ("arbitrage_revenue_cents", "cents")):
            name = "arbitrage_revenue" if metric == "arbitrage_revenue_cents" else metric
            out[name] = self.ledger.fact(ent, day, name, whole(r[metric]), unit, src, f"row {n}, column {metric}",
                                         "read as cents" if unit == "cents" else "read as kWh" if unit == "kwh"
                                         else "read as a count", raw=raw)
        return out

    def settlement(self, src, data):
        header, rows = csv_table(data)
        if header != SETTLEMENT_HEADER:
            raise ParseError("the settlement statement's columns don't match the known layout")
        out = {"assets": {}, "remittance": None}
        for n, r, raw in rows:
            day = r["operating_date"]
            if r["asset_id"] == "REMIT":
                out["remittance"] = self.ledger.fact(
                    "sideoats", day, "remittance", money(r["amount_usd"]), "cents", src, f"row {n}, column amount_usd",
                    f"read as dollars, a utility payment ({r['memo']})", raw=raw)
                out["remittance_memo"] = r["memo"]
                continue
            ent = f"sideoats/{r['asset_id']}"
            out["assets"][r["asset_id"]] = {
                "delivered_kwh": self.ledger.fact(ent, day, "delivered_kwh", whole(r["delivered_kwh"]), "kwh", src,
                                                  f"row {n}, column delivered_kwh", "read as kWh delivered to the grid",
                                                  raw=raw),
                "settlement": self.ledger.fact(ent, day, "settlement", money(r["amount_usd"]), "cents", src,
                                               f"row {n}, column amount_usd", "read as dollars and converted to cents",
                                               raw=raw)}
            out["date"] = day
        return out

    def market_price(self, src, data):
        header, rows = csv_table(data)
        if header != PRICE_HEADER:
            raise ParseError("the price file's columns don't match the known layout")
        n, r, raw = rows[0]
        return {"date": r["date"], "price": self.ledger.fact(
            "sideoats", r["date"], "market_price", money(r["avg_price_usd_per_mwh"]), "cents_per_mwh", src,
            f"row {n}, column avg_price_usd_per_mwh", "read as dollars per MWh", raw=raw)}

    def invoicing(self, src, data):
        header, rows = csv_table(data)
        if header != INVOICING_HEADER:
            raise ParseError("the invoicing batch file's columns don't match the known layout")
        n, r, raw = rows[0]
        day = r["batch_date"]
        L = self.ledger
        loc = lambda c: f"row {n}, column {c}"  # noqa: E731
        return {"date": day, "row": n,
                "invoice_count": L.fact("kiskadee", day, "invoice_count", whole(r["invoice_count"]), "count", src,
                                        loc("invoice_count"), "read as a count", raw=raw),
                "invoiced": L.fact("kiskadee", day, "invoiced", money(r["invoiced_usd"]), "cents", src,
                                   loc("invoiced_usd"), "read as dollars and converted to cents", raw=raw),
                "cash_applied": L.fact("kiskadee", day, "cash_applied", money(r["cash_applied_usd"]), "cents", src,
                                       loc("cash_applied_usd"), "read as dollars and converted to cents", raw=raw),
                "ar_balance": L.fact("kiskadee", day, "ar_balance", money(r["ar_balance_usd"]), "cents", src,
                                     loc("ar_balance_usd"), "read as dollars and converted to cents", raw=raw)}

    def tms_facts(self, src, sheet, mapping, rows, ops_date):
        """Day totals from parsed TMS rows, each a fact over its column range."""
        col = {f: xlsx.col_letter(i + 1) for i, (_, f) in enumerate(mapping["columns"]) if f}
        loads = [r for r in rows if not r["credit"]]
        credits = [r for r in rows if r["credit"]]
        first, last = (rows[0]["row"], rows[-1]["row"]) if rows else (0, 0)
        rng = lambda f: f"{sheet.name}!{col[f]}{first}:{col[f]}{last}"  # noqa: E731
        L, ent = self.ledger, "kiskadee"
        nums = [r["row"] for r in rows]
        out = {"loads": L.fact(ent, ops_date, "loads", len(loads), "count", src, rng("load_id"),
                               f"count of {len(loads)} load rows, credit rows left out", rows=nums),
               "credit_rows": L.fact(ent, ops_date, "credit_rows", len(credits), "count", src, rng("load_id"),
                                     f"count of {len(credits)} credit rows", rows=[r["row"] for r in credits])}
        for f, metric in (("linehaul_rev", "linehaul"), ("fuel_surcharge", "fuel_surcharge"),
                          ("accessorials", "accessorials"), ("carrier_cost", "carrier_cost")):
            out[metric] = L.fact(ent, ops_date, metric, sum(r[f] or 0 for r in rows), "cents", src, rng(f),
                                 f"sum of {len(rows)} rows, text amounts converted to cents", rows=nums)
        out["revenue"] = L.fact(ent, ops_date, "revenue",
                                sum(r["linehaul_rev"] + r["fuel_surcharge"] + r["accessorials"] for r in rows), "cents",
                                src, f"{rng('linehaul_rev')} to {rng('accessorials')}",
                                f"linehaul, fuel and accessorials summed over {len(rows)} rows, credits included", rows=nums)
        out["loaded_miles"] = L.fact(ent, ops_date, "loaded_miles", sum(r["miles"] for r in loads), "miles", src,
                                     rng("miles"), f"sum of {len(loads)} load rows", rows=nums)
        out["empty_miles"] = L.fact(ent, ops_date, "empty_miles", sum(r["empty_miles"] for r in loads), "miles", src,
                                    rng("empty_miles"), f"sum of {len(loads)} load rows", rows=nums)
        asset = [r for r in loads if r["carrier_cost"] is None]
        out["asset_miles"] = L.fact(ent, ops_date, "asset_miles", sum(r["miles"] + r["empty_miles"] for r in asset),
                                    "miles", src, f"{rng('miles')} and {rng('empty_miles')}",
                                    f"loaded plus empty miles on the {len(asset)} loads with no carrier cost, "
                                    f"which are the company's own trucks", rows=[r["row"] for r in asset])
        out["on_time_loads"] = L.fact(ent, ops_date, "on_time_loads", sum(1 for r in loads if r["on_time"]), "count",
                                      src, rng("on_time"), f"count of load rows marked on time", rows=nums)
        return out

    def night_audit(self, src, data):
        lines = table_text(data)
        m = re.search(r"Business date (\d\d/\d\d/\d{4})", lines[1] if len(lines) > 1 else "")
        if not lines or not lines[0].startswith("POSSUMHAW LODGE") or not m:
            raise ParseError("the night audit doesn't match the known report layout")
        day = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat()
        out = {"date": day}
        for n, line in enumerate(lines, 1):
            mm = AUDIT_LINE.match(line)
            if not mm or mm.group(1) not in AUDIT_LINES:
                continue
            metric, unit = AUDIT_LINES[mm.group(1)]
            value = money(mm.group(2)) if unit == "cents" else whole(mm.group(2))
            out[metric] = self.ledger.fact("possumhaw", day, metric, value, unit, src, f"line {n}",
                                           "read from the report line" + (" and converted to cents" if unit == "cents"
                                                                          else ""), raw=line)
        missing = [k for k, (metric, _) in AUDIT_LINES.items() if metric not in out]
        if missing:
            raise ParseError(f"the night audit is missing {', '.join(missing)}")
        return out

    def deposits(self, src, data):
        header, rows = csv_table(data)
        if header != DEPOSITS_HEADER:
            raise ParseError("the deposit file's columns don't match the known layout")
        n, r, raw = rows[0]
        day = r["batch_date"]
        L = self.ledger
        return {"batch_date": day, "deposit_date": r["deposit_date"],
                "gross": L.fact("possumhaw", day, "deposit_gross", money(r["gross_usd"]), "cents", src,
                                f"row {n}, column gross_usd", f"read as dollars, deposited {r['deposit_date']}", raw=raw),
                "fees": L.fact("possumhaw", day, "deposit_fees", money(r["fees_usd"]), "cents", src,
                               f"row {n}, column fees_usd", "read as dollars", raw=raw),
                "net": L.fact("possumhaw", day, "deposit_net", money(r["net_usd"]), "cents", src,
                              f"row {n}, column net_usd", "read as dollars", raw=raw)}

    def asset_register(self, src, data):
        """Sideoats's asset register: each asset's name, capacity and offtake."""
        header, rows = csv_table(data)
        if header != ["asset_id", "name", "capacity_kw", "offtake", "ppa_price_usd_per_mwh"]:
            raise ParseError("the asset register's columns don't match the known layout")
        out = {}
        for n, r, raw in rows:
            out[r["asset_id"]] = {
                "name": r["name"], "offtake": r["offtake"],
                "capacity": self.ledger.fact(f"sideoats/{r['asset_id']}", "register", "capacity_kw", whole(r["capacity_kw"]),
                                             "kw", src, f"row {n}, column capacity_kw", "read from the asset register",
                                             raw=raw)}
        return out

    def budget_file(self, company, src, data):
        """Budgets load as rows, and facts are made from them as each period is needed."""
        header, rows = csv_table(data)
        self.budget[company] = {"source": src, "header": header, "rows": rows}

    def budget_fact(self, company, column, first, last, asset=None, entity=None):
        """The budget for a day range as one fact over its rows, made once and then reused."""
        b = self.budget[company]
        period = first if first == last else f"{first}..{last}"
        metric = f"budget_{column}"
        ent = entity or (f"{company}/{asset}" if asset else company)
        found = self.ledger.find("F", ent, metric, period)
        if found:
            return found
        picked = [(n, r) for n, r, _ in b["rows"]
                  if first <= r["date"] <= last and (asset is None or r.get("asset_id") == asset) and r.get(column)]
        if not picked:
            return None
        unit = "cents" if column.endswith("_cents") else "kwh" if column.endswith("_kwh") else \
            "bp" if column.endswith("_bp") else "miles" if column == "asset_miles" else "count"
        nums = [n for n, _ in picked]
        days = len({r["date"] for _, r in picked})
        step = (f"the budget row for {first}" if days == 1 else f"sum of {days} daily budget rows")
        if column in ("std_cost_per_mile_cents", "room_cost_per_occupied_cents", "fb_cost_bp", "other_cost_bp"):
            value, step = whole(picked[0][1][column]), "a budget rate, the same every day"
        else:
            value = sum(whole(r[column]) for _, r in picked)
        loc = f"rows {min(nums)} to {max(nums)}, column {column}" if len(nums) > 1 else f"row {nums[0]}, column {column}"
        return self.ledger.fact(ent, period, metric, value, unit, b["source"], loc, step, rows=nums)

    # ------------------------------------------------------------------ the data room
    def financials(self, src, data):
        book = xlsx.read(data)
        pl = book["P&L"]
        months = {}
        for c in range(2, pl.max_col() + 1):
            label = pl.value((4, c))
            if label:
                months[c] = datetime.strptime(label, "%b %Y").strftime("%Y-%m")
        section, out = None, {}
        heads = {"Revenue": "revenue", "Direct labor": "labor", "Materials": "materials", "Subcontractors": "subs",
                 "Selling, general and administrative": "sga"}
        lines = {"Preventive maintenance contracts": "pm", "Corrective repairs": "cr", "Module cleaning": "mc",
                 "Monitoring subscriptions": "ms", "Salaries and benefits": "salaries", "Facilities": "facilities",
                 "IT and software": "it", "Insurance": "insurance", "Corporate overhead allocation (parent)": "allocation"}
        totals = {"Total revenue": "total_revenue", "Total cost of services": "total_cost", "Gross profit": "gross_profit",
                  "Total SG&A": "total_sga", "Legal settlement (one-time)": "settlement",
                  "Reported EBITDA": "reported_ebitda"}
        memo = {"Revenue": "revenue", "Direct labor": "labor", "Materials": "materials", "Subcontractors": "subs"}
        for r in range(5, pl.max_row() + 1):
            label = pl.value((r, 1))
            if not label:
                continue
            text = label.strip()
            if text.startswith("Memo:"):
                section = "memo"
                continue
            if section == "memo" and text in memo:
                metric = "memo:" + memo[text]
            elif text in heads:
                section = heads[text]
                continue
            elif text in totals:
                metric = totals[text]
            elif text in lines:
                metric = f"{section}:{lines[text]}"
            else:
                continue
            for c, month in months.items():
                v = pl.value((r, c))
                if v is None:
                    continue
                cell = xlsx.ref(r, c)
                out[(metric, month)] = self.ledger.fact(
                    "brightrow", month, metric, money(v), "cents", src, f"P&L!{cell}",
                    "read as dollars and converted to cents", raw=f"{text}, {pl.value((4, c))}: {v:,.2f}")
        annual = book["Annual summary"]
        for r in range(3, annual.max_row() + 1):
            label = annual.value((r, 1))
            for c in range(2, 5):
                fy = annual.value((2, c))
                metric = "annual:" + {"Total revenue": "total_revenue", "Gross profit": "gross_profit",
                                      "Reported EBITDA": "reported_ebitda"}[label]
                out[(metric, fy)] = self.ledger.fact("brightrow", fy, metric, money(annual.value((r, c))), "cents", src,
                                                     f"Annual summary!{xlsx.ref(r, c)}",
                                                     "read as dollars and converted to cents",
                                                     raw=f"{label}, {fy}: {annual.value((r, c)):,.2f}")
        if "Working capital and capex" in book:
            wc = book["Working capital and capex"]
            keys = {"Accounts receivable": "receivables", "Unbilled services": "unbilled", "Accounts payable": "payables",
                    "Accrued liabilities": "accrued", "Capital expenditures": "capex",
                    "Depreciation and amortization": "da"}
            for r in range(3, wc.max_row() + 1):
                label = wc.value((r, 1))
                if label not in keys:
                    continue
                for c in range(2, 5):
                    fy = wc.value((2, c))
                    out[(f"balance:{keys[label]}", fy)] = self.ledger.fact(
                        "brightrow", fy, f"balance:{keys[label]}", money(wc.value((r, c))), "cents", src,
                        f"Working capital and capex!{xlsx.ref(r, c)}", "read as dollars and converted to cents",
                        raw=f"{label}, {fy}: {wc.value((r, c)):,.2f}")
        notes = book["Notes"]
        for r in range(1, notes.max_row() + 1):
            text = notes.value((r, 1)) or ""
            m = re.search(r"standalone Brightrow would spend \$([\d,]+) a month", text)
            if m:
                out[("standalone_cost_month", "notes")] = self.ledger.fact(
                    "brightrow", "per month", "standalone_cost_month", money(m.group(1)), "cents", src,
                    f"Notes!A{r}", "read from management's note", raw=text)
        return out

    def customers(self, src, data):
        sheet = xlsx.read(data)["Revenue by customer"]
        fys = [sheet.value((1, c)) for c in range(2, 5)]
        out = {}
        for r in range(2, sheet.max_row() + 1):
            name = sheet.value((r, 1))
            for c, fy in zip(range(2, 5), fys):
                ent = "brightrow" if name == "Total" else f"brightrow/customer/{name}"
                metric = "customers_total" if name == "Total" else "customer_revenue"
                out[(name, fy)] = self.ledger.fact(ent, fy, metric, money(sheet.value((r, c))), "cents", src,
                                                   f"Revenue by customer!{xlsx.ref(r, c)}",
                                                   "read as dollars and converted to cents",
                                                   raw=f"{name}, {fy}: {sheet.value((r, c)):,.2f}")
        return out

    def kpis(self, src, data):
        header, rows = csv_table(data)
        out = {}
        for n, r, raw in rows:
            for col, unit, value in (("mw_under_contract", "mw", whole(r["mw_under_contract"])),
                                     ("technicians", "count", whole(r["technicians"])),
                                     ("tickets_closed", "count", whole(r["tickets_closed"])),
                                     ("avg_response_hours", "hours_tenths", scaled(r["avg_response_hours"], 10)),
                                     ("contracts_expiring", "count", whole(r["contracts_expiring"])),
                                     ("contracts_renewed", "count", whole(r["contracts_renewed"]))):
                out[(col, r["month"])] = self.ledger.fact("brightrow", r["month"], col, value, unit, src,
                                                          f"row {n}, column {col}", "read from the KPI file", raw=raw)
        return out
