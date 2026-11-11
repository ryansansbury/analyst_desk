"""Kiskadee Freight's TMS export layouts and the writer that renders a day's loads in any of them.

tms_v1 is the layout the parser knows: two header rows (merged group labels over column names), currency stored
as text and a TOTAL row at the bottom. V00 is the new layout that arrives on the demo morning. V01 to V12 are the
intake agent's eval set, from plain renames up to decoy columns and an inverted on-time flag. Each layout's
answer key says which schema field every column holds, which the agent never sees.
"""
from engine import xlsx
from generate import common as C

FIELDS = ("load_id", "date", "customer", "lane", "miles", "empty_miles", "linehaul_rev", "fuel_surcharge",
          "accessorials", "carrier_cost", "on_time")
MONEY = ("linehaul_rev", "fuel_surcharge", "accessorials", "carrier_cost")
SUMMED = ("miles", "empty_miles") + MONEY
GROUP_OF = {"load_id": "LOAD", "date": "LOAD", "customer": "LOAD", "lane": "LOAD", "miles": "MILES",
            "empty_miles": "MILES", "linehaul_rev": "REVENUE", "fuel_surcharge": "REVENUE", "accessorials": "REVENUE",
            "carrier_cost": "COST", "on_time": "SERVICE"}
BOLD = xlsx.Style(bold=True)


def L(columns, date_format, money, on_time, totals, header_rows=1, ops=None):
    return {"columns": columns, "date_format": date_format, "money_format": money, "on_time": on_time,
            "totals_label": totals, "header_rows": header_rows, "ops_date": ops}


LAYOUTS = {
    "tms_v1": L([("Load #", "load_id"), ("Ship Date", "date"), ("Customer", "customer"), ("Lane", "lane"),
                 ("Loaded Miles", "miles"), ("Empty Miles", "empty_miles"), ("Linehaul Rev", "linehaul_rev"),
                 ("Fuel Surcharge", "fuel_surcharge"), ("Accessorials", "accessorials"), ("Carrier Cost", "carrier_cost"),
                 ("On Time", "on_time")], "%m/%d/%Y", "text", ("Y", "N"), "TOTAL", header_rows=2),
    "V00": L([("Load ID", "load_id"), ("Pickup Date", "date"), ("Customer", "customer"), ("Origin-Destination", "lane"),
              ("Line Haul Revenue", "linehaul_rev"), ("Fuel Surcharge", "fuel_surcharge"),
              ("Accessorial Charges", "accessorials"), ("Carrier Pay", "carrier_cost"), ("Loaded Miles", "miles"),
              ("Deadhead Miles", "empty_miles"), ("On Time", "on_time"), ("Trailer Type", "x:trailer")],
             "%Y-%m-%d", "text", ("Y", "N"), "Grand Total", ops=C.ops_day(C.DEMO).isoformat()),
    "V01": L([("Load Number", "load_id"), ("Ship Date", "date"), ("Customer", "customer"), ("Lane", "lane"),
              ("Miles", "miles"), ("Empty Miles", "empty_miles"), ("Linehaul", "linehaul_rev"),
              ("Fuel Surcharge", "fuel_surcharge"), ("Accessorials", "accessorials"), ("Carrier Cost", "carrier_cost"),
              ("On Time", "on_time")], "%m/%d/%Y", "text", ("Y", "N"), "TOTAL", ops="2026-10-05"),
    "V02": L([("Shipment ID", "load_id"), ("Date Shipped", "date"), ("Shipper", "customer"), ("Route", "lane"),
              ("Loaded Mi", "miles"), ("Empty Mi", "empty_miles"), ("LH Revenue", "linehaul_rev"), ("FSC", "fuel_surcharge"),
              ("Other Charges", "accessorials"), ("Carrier $", "carrier_cost"), ("OTD", "on_time")],
             "%Y-%m-%d", "plain", ("Yes", "No"), None, ops="2026-10-06"),
    "V03": L([("Client", "customer"), ("Load ID", "load_id"), ("Load Date", "date"), ("Lane Code", "lane"),
              ("Freight Charges", "linehaul_rev"), ("Fuel", "fuel_surcharge"), ("Accessorial $", "accessorials"),
              ("Purchased Transportation", "carrier_cost"), ("Trip Miles", "miles"), ("Deadhead", "empty_miles"),
              ("On-Time Delivery", "on_time")], "%m/%d/%y", "text", ("On Time", "Late"), "Totals", ops="2026-10-07"),
    "V04": L([("Pro #", "load_id"), ("PU Date", "date"), ("Bill To", "customer"), ("O/D", "lane"),
              ("Billed Miles", "miles"), ("Unloaded Miles", "empty_miles"), ("Base Rate", "linehaul_rev"),
              ("Fuel Adj", "fuel_surcharge"), ("Extras", "accessorials"), ("Buy Rate", "carrier_cost"),
              ("Service Met", "on_time")], "%d-%b-%y", "paren", ("TRUE", "FALSE"), "TOTAL", header_rows=2,
             ops="2026-10-08"),
    "V05": L([("Order No", "load_id"), ("Ship Date", "date"), ("Dispatcher", "x:dispatcher"), ("Account", "customer"),
              ("Lane", "lane"), ("Equipment ID", "x:equipment"), ("Miles", "miles"), ("Empty Miles", "empty_miles"),
              ("Linehaul $", "linehaul_rev"), ("FSC $", "fuel_surcharge"), ("Accessorials", "accessorials"),
              ("Carrier Pay", "carrier_cost"), ("On Time", "on_time")], "%Y%m%d", "plain", (1, 0), None,
             ops="2026-10-09"),
    "V06": L([("BOL #", "load_id"), ("Pickup Date", "date"), ("Shipper", "customer"), ("Origin-Destination", "lane"),
              ("Commodity", "x:commodity"), ("Weight (lbs)", "x:weight"), ("Loaded Miles", "miles"),
              ("Deadhead Mi", "empty_miles"), ("Line Haul Revenue", "linehaul_rev"), ("Fuel Surcharge", "fuel_surcharge"),
              ("Accessorial Charges", "accessorials"), ("Carrier Cost", "carrier_cost"), ("OTD", "on_time")],
             "%B %d, %Y", "text", ("Y", "N"), "Grand Total", ops="2026-10-12"),
    "V07": L([("Load #", "load_id"), ("Date", "date"), ("Customer", "customer"), ("Lane", "lane"),
              ("PO Number", "x:po"), ("Loaded Miles", "miles"), ("Empty Miles", "empty_miles"),
              ("Linehaul Rev", "linehaul_rev"), ("Fuel Surcharge", "fuel_surcharge"), ("Accessorials", "accessorials"),
              ("Carrier Cost", "carrier_cost"), ("On Time", "on_time")], "%d/%m/%Y", "paren", ("Y", "N"), "TOTAL",
             header_rows=2, ops="2026-10-20"),
    "V08": L([("Ref", "load_id"), ("Ship Date", "date"), ("Customer Name", "customer"), ("Lane", "lane"),
              ("Miles Loaded", "miles"), ("Miles Empty", "empty_miles"), ("Revenue - Linehaul", "linehaul_rev"),
              ("Revenue - Fuel", "fuel_surcharge"), ("Revenue - Accessorial", "accessorials"),
              ("Cost - Carrier", "carrier_cost"), ("On Time Y/N", "on_time")], "%m-%d-%Y", "text", ("Y", "N"), None,
             ops="2026-10-13"),
    "V09": L([("Load ID", "load_id"), ("Ship Date", "date"), ("Shipper", "customer"), ("Lane", "lane"),
              ("Miles", "miles"), ("Deadhead", "empty_miles"), ("Linehaul", "linehaul_rev"), ("Fuel Index", "x:fuel_index"),
              ("FSC", "fuel_surcharge"), ("Accessorials", "accessorials"), ("Carrier Cost", "carrier_cost"),
              ("On Time", "on_time")], "%Y-%m-%d", "plain", ("Y", "N"), "TOTAL", ops="2026-10-14"),
    "V10": L([("Load Number", "load_id"), ("Pickup Date", "date"), ("Customer", "customer"), ("Route", "lane"),
              ("Loaded Miles", "miles"), ("Empty Miles", "empty_miles"), ("Rate per Mile", "x:rate_per_mile"),
              ("Linehaul Revenue", "linehaul_rev"), ("Fuel Surcharge", "fuel_surcharge"), ("Accessorials", "accessorials"),
              ("Total Revenue", "x:total_revenue"), ("Carrier Pay", "carrier_cost"), ("OTD", "on_time")],
             "%m/%d/%Y", "text", ("Yes", "No"), "Grand Total", ops="2026-10-15"),
    "V11": L([("Pro #", "load_id"), ("Ship Date", "date"), ("Bill To", "customer"), ("O/D", "lane"),
              ("Trip Miles", "miles"), ("Deadhead Miles", "empty_miles"), ("LH $", "linehaul_rev"), ("Fuel $", "fuel_surcharge"),
              ("Acc $", "accessorials"), ("Carrier $", "carrier_cost"), ("Late?", "on_time")], "%d-%b-%Y", "paren",
             ("N", "Y"), "TOTAL", header_rows=2, ops="2026-10-16"),
    "V12": L([("LOAD", "load_id"), ("DT", "date"), ("CUST", "customer"), ("LANE", "lane"), ("LD MI", "miles"),
              ("MT MI", "empty_miles"), ("LH", "linehaul_rev"), ("FSC", "fuel_surcharge"), ("ACC", "accessorials"),
              ("PT", "carrier_cost"), ("OT", "on_time"), ("EQUIP", "x:equipment"), ("DISP", "x:dispatcher")],
             "%Y%m%d", "plain", (1, 0), None, ops="2026-10-19"),
}
EVAL_IDS = tuple(f"V{i:02d}" for i in range(1, 13))
TRAILERS = ("53' Dry Van", "53' Reefer", "48' Flatbed")
DISPATCHERS = ("A. Ruiz", "K. Tran", "M. Okafor", "J. Bell", "S. Patel")
COMMODITIES = ("Building materials", "Packaged food", "Paper goods", "Auto parts", "Plastics", "Beverages")


def answer_key(layout_id):
    """What a correct mapping of this layout says. The agent never sees it."""
    spec = LAYOUTS[layout_id]
    t, f = spec["on_time"]
    return {"layout": layout_id, "header_rows": spec["header_rows"],
            "columns": [[h, None if fld.startswith("x:") else fld] for h, fld in spec["columns"]],
            "date_format": spec["date_format"], "money_format": spec["money_format"],
            "on_time": {"true": str(t), "false": str(f)}, "totals_label": spec["totals_label"]}


def extra(row, kind):
    if row.get("credit"):
        return None
    rng = C.stream(row["load_id"], kind)
    if kind == "trailer":
        return rng.choice(TRAILERS)
    if kind == "dispatcher":
        return rng.choice(DISPATCHERS)
    if kind == "equipment":
        return f"TRK-{rng.randint(1001, 1180)}"
    if kind == "commodity":
        return rng.choice(COMMODITIES)
    if kind == "weight":
        return rng.randint(180, 440) * 100
    if kind == "po":
        return f"PO-{rng.randint(100000, 999999)}"
    if kind == "fuel_index":
        return round(rng.uniform(3.62, 4.08), 3)
    if kind == "rate_per_mile":
        return round(row["linehaul_rev"] / 100 / row["miles"], 2) if row["miles"] else None
    if kind == "total_revenue":
        return row["linehaul_rev"] + row["fuel_surcharge"] + row["accessorials"]
    raise ValueError(kind)


def money_cell(cents, style):
    if cents is None:
        return None
    if style == "plain":
        return cents / 100
    return C.money(cents, style)


def cell(row, field, spec, ops):
    if field.startswith("x:"):
        v = extra(row, field[2:])
        return money_cell(v, spec["money_format"]) if field == "x:total_revenue" and v is not None else v
    if field == "date":
        return ops.strftime(spec["date_format"])
    if field == "on_time":
        if row.get("credit"):
            return None
        return spec["on_time"][0] if row["on_time"] else spec["on_time"][1]
    if field in MONEY:
        return money_cell(row[field], spec["money_format"])
    v = row[field]
    return v if v != "" else None


def groups(columns):
    """Merged group labels over runs of columns in the same group."""
    out = []
    for i, (_, f) in enumerate(columns, 1):
        g = "OTHER" if f.startswith("x:") else GROUP_OF[f]
        if out and out[-1][0] == g:
            out[-1][2] = i
        else:
            out.append([g, i, i])
    return out


KEEP = object()


def render(layout_id, rows, ops, totals_label=KEEP):
    """One day's loads as an .xlsx in the given layout. totals_label='' plants E3, a TOTAL row with no label."""
    spec = LAYOUTS[layout_id]
    wb = xlsx.Workbook()
    s = wb.sheet("Loads")
    cols = spec["columns"]
    r = 1
    if spec["header_rows"] == 2:
        for label, a, b in groups(cols):
            s.set((1, a), label, style=BOLD)
            if b > a:
                s.merge(xlsx.ref(1, a), xlsx.ref(1, b))
        r = 2
    for i, (h, _) in enumerate(cols, 1):
        s.set((r, i), h, style=BOLD)
    for row in rows:
        r += 1
        for i, (_, f) in enumerate(cols, 1):
            v = cell(row, f, spec, ops)
            if v is not None:
                s.set((r, i), v)
    if spec["totals_label"] is not None:
        r += 1
        label = spec["totals_label"] if totals_label is KEEP else totals_label
        if label:
            s.set((r, 1), label, style=BOLD)
        for i, (_, f) in enumerate(cols, 1):
            if f in SUMMED:
                total = sum(row[f] or 0 for row in rows)
                s.set((r, i), money_cell(total, spec["money_format"]) if f in MONEY else total, style=BOLD)
    for i in range(1, len(cols) + 1):
        s.width(i, 16)
    return wb.to_bytes()
