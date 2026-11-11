"""How every number is written, so the page, the trace drawer and the agents' rendered text agree.

Units in the ledger: cents, kwh, count, bp (basis points), wh_m2, miles, cents_per_mwh, ratio (a fraction),
multiple (like 8.0x), pct_points and days. Energy is stored in kWh and shown in MWh.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

DESK_TZ = ZoneInfo("America/Chicago")      # the desk runs at 7 AM Central
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def local_date(stamp):
    """A recording's UTC timestamp as the desk's own date, in Central time. A run at 6:53 PM Pacific is still that
    day here, though UTC has already moved to the next one."""
    if not stamp:
        return ""
    try:
        return datetime.fromisoformat(stamp).astimezone(DESK_TZ).date().isoformat()
    except ValueError:
        return stamp[:10]


def usd(cents, decimals=0):
    if cents is None:
        return "no value"
    sign = "-" if cents < 0 else ""
    v = abs(cents) / 100
    return f"{sign}${v:,.{decimals}f}"


def usd_short(cents):
    """$1.2M, $812K, $940. Used where space is tight."""
    if cents is None:
        return "no value"
    sign = "-" if cents < 0 else ""
    v = abs(cents) / 100
    if v >= 1e9:
        return f"{sign}${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"{sign}${v / 1e6:.1f}M"
    if v >= 1e4:
        return f"{sign}${v / 1e3:.0f}K"
    if v >= 1e3:
        return f"{sign}${v / 1e3:.1f}K"
    return f"{sign}${v:,.0f}"


def mwh(kwh, decimals=None):
    """Energy in MWh, or in kWh when it's under one MWh, so a unit mix-up shows as 47 kWh and not 0.0 MWh."""
    if kwh is None:
        return "no value"
    if abs(kwh) < 1000:
        return f"{kwh:,.0f} kWh"
    v = kwh / 1000
    if decimals is None:
        decimals = 0 if abs(v) >= 1000 else 1
    return f"{v:,.{decimals}f} MWh"


def pct(ratio, decimals=1):
    return "no value" if ratio is None else f"{ratio * 100:.{decimals}f}%"


def count(v, noun=None):
    if v is None:
        return "no value"
    text = f"{int(round(v)):,}"
    return f"{text} {noun}" if noun else text


def items(seq):
    """A list the way the copy rules want it: "A", "A and B", or "A, B, and C"."""
    seq = [str(x) for x in seq]
    if len(seq) <= 2:
        return " and ".join(seq)
    return ", ".join(seq[:-1]) + ", and " + seq[-1]


def day_label(iso, weekday=False, year=False):
    """2026-10-27 as October 27, with the weekday or year when asked."""
    from datetime import date
    d = date.fromisoformat(iso)
    text = f"{MONTHS[d.month - 1]} {d.day}"
    if year:
        text += f", {d.year}"
    if weekday:
        text = d.strftime("%A") + " " + text
    return text


def value(unit, v, short=False, decimals=None):
    """A ledger value written the way the page shows it."""
    if v is None:
        return "no value"
    if unit == "cents":
        return usd_short(v) if short else usd(v, 0 if decimals is None else decimals)
    if unit == "kwh":
        return mwh(v, decimals)
    if unit == "ratio":
        return pct(v, 1 if decimals is None else decimals)
    if unit == "pct_points":
        return f"{v * 100:+.1f} pts"
    if unit == "bp":
        return pct(v / 10000, 1 if decimals is None else decimals)
    if unit == "count":
        return count(v)
    if unit == "miles":
        return f"{int(round(v)):,} mi"
    if unit == "wh_m2":
        return f"{v / 1000:.2f} kWh/m²"
    if unit == "cents_per_mwh":
        return f"${v / 100:,.2f}/MWh"
    if unit == "cents_per_kwh":
        return f"{v:.2f}¢/kWh"
    if unit == "multiple":
        return f"{v:.1f}x"
    if unit == "days":
        return f"{v:,.0f} days"
    if unit == "rooms":
        return f"{int(round(v)):,} rooms"
    if unit == "hours":
        return f"{v:,.1f} hours"
    if unit == "hours_tenths":
        return f"{v / 10:,.1f} hours"
    if unit == "kw":
        return f"{v / 1000:,.0f} MWac"
    if unit == "multiple_x10":
        return f"{v / 10:.1f}x"
    if unit == "multiple_x100":
        return f"{v / 100:.2f}x"
    if unit == "dollars":
        return usd_short(v * 100) if short else usd(v * 100)
    if unit == "mw":
        return f"{int(round(v)):,} MW"
    raise ValueError(f"no format for unit {unit}")
