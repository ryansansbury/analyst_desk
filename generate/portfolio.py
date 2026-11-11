"""The fund's three portfolio companies: their daily operations, the files they send each morning, and budgets.

Operations are simulated from July 1 through December so budgets and balances have a past and a plan. Files
are written only for the 96 mornings in the window. Every amount is whole cents and every quantity whole kWh,
miles or rooms. Look-alike L2 (a curtailed day) is planted here, since it's part of normal operations. L1 (the
deposit lag) and L3 (the Labor Day dip) are structural.
"""
from datetime import date, timedelta

from generate import common as C
from generate import layouts

SIM_END = date(2026, 12, 31)
SIM = C.days(C.SIM_START, SIM_END)
HOLIDAYS = dict(C.HOLIDAYS, **{"2026-11-26": "Thanksgiving", "2026-12-25": "Christmas"})
HOLIDAY_DATES = {d if isinstance(d, date) else date.fromisoformat(d) for d in HOLIDAYS}

# ---------------------------------------------------------------------- Sideoats Renewables
SITES = [  # id, name, MWac, offtake, PPA price in cents per MWh, base line loss in basis points
    ("CR1", "Tarbush Flat Solar", 80, "ppa", 3450, 140),
    ("CR2", "Yucca Draw Solar", 60, "ppa", 3625, 170),
    ("CR3", "Burrograss Solar", 45, "ppa", 3800, 120),
    ("CR4", "Tascate Hill Solar", 20, "merchant", None, 190),
]
BATTERY = ("CB1", "Coyotillo Storage", 50, 200)
OPEX_PER_MW_YEAR = 1500000          # cents, solar O&M and site costs
BATTERY_OPEX_YEAR = 140000000
MERCHANT_BUDGET_PRICE = 3000        # cents per MWh
HUB = "West hub"

# ---------------------------------------------------------------------- Kiskadee Freight
SHIPPERS = ["Pecan Valley Foods", "Lone Oak Building Supply", "Red River Plastics", "Cedar Ridge Paper",
            "Brazos Bottling", "Hill Country Home Goods", "Gulf Coast Chemical Supply", "Prairie Star Feed",
            "Caddo Lake Lumber", "Blue Mesa Appliances", "Llano Stone Works", "Comal Kitchen Brands",
            "Sabine Steel Fabricators", "Allthorn Tile", "Frio Farms", "Mustang Auto Parts", "Big Thicket Furniture",
            "Pedregal Packaging", "Guadalupe Grocers", "San Gabriel Glassworks", "Nueces Tire", "Palo Duro Pet Supply",
            "Bluestem Beverage", "Rio Bravo Produce", "Wichita Falls Wire", "Sulphur Springs Snacks",
            "Bosque Building Products", "Navasota Nursery", "Laredo Labelworks", "Marfa Mattress Co",
            "Kerrville Kitchenware", "Pecos Pipe Supply", "Lampasas Lighting", "Medina Mills", "Tyler Textile",
            "Waco Warehouse Supply"]
LANES = [("DAL-HOU", 239), ("HOU-DAL", 239), ("HOU-SAT", 197), ("SAT-HOU", 197), ("AUS-DAL", 195), ("DAL-AUS", 195),
         ("SAT-LRD", 157), ("LRD-SAT", 157), ("DAL-OKC", 206), ("OKC-DAL", 206), ("HOU-NOL", 348), ("NOL-HOU", 348),
         ("FTW-ELP", 597), ("ELP-FTW", 597), ("DAL-SHV", 189), ("HOU-BPT", 85)]
DAY_WEIGHT = {"weekday": 1.0, "saturday": 0.35, "sunday": 0.29, "holiday": 0.56}
STD_COST_PER_MILE = 185             # cents per asset mile, from the budget
FIXED_COST_DAY_FREIGHT = 1700000    # cents

# ---------------------------------------------------------------------- Possumhaw Lodge
ROOMS = 180
ROOM_COST_PER_OCCUPIED = 4100       # cents
FB_COST_BP = 3300
OTHER_COST_BP = 2600
FIXED_COST_DAY_HOTEL = 3500000      # cents, which puts the resort near a 30% EBITDA margin
OCC_BY_MONTH = {7: 0.84, 8: 0.80, 9: 0.72, 10: 0.79, 11: 0.70, 12: 0.66}
ADR_BY_MONTH = {7: 600, 8: 400, 9: -800, 10: 1200, 11: -400, 12: 900}


def day_type(d):
    if d in HOLIDAY_DATES:
        return "holiday"
    return {5: "saturday", 6: "sunday"}.get(d.weekday(), "weekday")


def insolation_mean(d):
    """Seasonal daily insolation in kWh per square meter for West Texas, falling from late July into winter."""
    doy = d.timetuple().tm_yday
    return max(3.6, 7.35 - (doy - 211) * 0.0262)


class Portfolio:
    def __init__(self, seed):
        self.seed = seed
        self.l2 = self._pick_l2()
        self.sideoats = self._sideoats()
        self.kiskadee = self._kiskadee()
        self.possumhaw = self._possumhaw()

    # ------------------------------------------------------------------ look-alike L2
    def _pick_l2(self):
        """One curtailed day in the month to date and up to two earlier in the window, each at a seed-chosen site."""
        rng = C.stream(self.seed, "L2")
        ops = C.ops_day(C.DEMO)
        this_month = [d for d in C.OPS_DAYS if d.month == ops.month and d < ops]
        earlier = [d for d in C.OPS_DAYS if C.FIRST_MORNING.month <= d.month < ops.month]
        picks = [rng.choice(this_month)] + rng.sample(earlier, rng.randint(0, 2))
        return {d: rng.choice([s[0] for s in SITES]) for d in sorted(picks)}

    # ------------------------------------------------------------------ Sideoats
    def _sideoats(self):
        weather = C.stream(self.seed, "weather")
        site_rng = {s[0]: C.stream(self.seed, f"site:{s[0]}") for s in SITES}
        price_rng = C.stream(self.seed, "price")
        batt_rng = C.stream(self.seed, "battery")
        days = {}
        for d in SIM:
            mean = insolation_mean(d)
            cloudy = weather.random() < 0.13
            wfac = weather.uniform(0.35, 0.75) if cloudy else weather.uniform(0.93, 1.04)
            month_base = {7: 3300, 8: 3900, 9: 3000, 10: 2500, 11: 2400, 12: 2700}[d.month]
            price = round(month_base * price_rng.uniform(0.75, 1.3))
            if price_rng.random() < 0.04:
                price = round(price * price_rng.uniform(3, 7))
            sites = {}
            for sid, _, mw, offtake, ppa, loss_base in SITES:
                rng = site_rng[sid]
                insol = round(mean * wfac * rng.uniform(0.97, 1.03), 2)
                if rng.random() < 0.06:
                    avail = round(rng.uniform(94.0, 98.0), 1)
                    faults = rng.randint(1, 4)
                else:
                    avail = round(rng.uniform(99.2, 100.0), 1)
                    faults = 1 if rng.random() < 0.1 else 0
                pr = rng.uniform(0.81, 0.85)
                potential = mw * 1000 * insol * pr * avail / 100
                if self.l2.get(d) == sid:
                    frac = rng.uniform(0.30, 0.60)
                elif rng.random() < 0.08:
                    frac = rng.uniform(0.01, 0.06)
                else:
                    frac = 0.0
                curtail = round(potential * frac)
                gen = round(potential) - curtail
                loss = min(200, max(100, loss_base + rng.randint(-20, 20)))
                delivered = C.half_up(gen * (10000 - loss), 10000)
                unit_price = ppa if offtake == "ppa" else price
                sites[sid] = {"generation_kwh": gen, "availability_pct": avail, "curtailment_kwh": curtail,
                              "insolation_kwh_m2": insol, "inverter_faults": faults, "delivered_kwh": delivered,
                              "price": unit_price, "amount": C.half_up(delivered * unit_price, 1000)}
            r = batt_rng.random()
            cycles = 0 if r < 0.05 else 1 if r < 0.85 else 2
            charge = sum(batt_rng.randint(186000, 199000) for _ in range(cycles))
            discharge = round(charge * batt_rng.uniform(0.855, 0.875))
            spread = batt_rng.uniform(10, 25) if batt_rng.random() < 0.05 else batt_rng.uniform(2.0, 6.5)
            revenue = round(discharge * spread)
            battery = {"cycles": cycles, "charge_kwh": charge, "discharge_kwh": discharge, "arbitrage_revenue": revenue,
                       "delivered_kwh": C.half_up(discharge * 9920, 10000)}
            days[d] = {"price": price, "sites": sites, "battery": battery}
        for d in SIM:
            if C.morning_of(d).day == 20:
                m = C.morning_of(d)
                prev = date(m.year - (m.month == 1), (m.month - 2) % 12 + 1, 1)
                days[d]["remittance"] = {"month": prev.strftime("%B %Y"), "amount": sum(
                    sum(s["amount"] for s in days[x]["sites"].values()) + days[x]["battery"]["arbitrage_revenue"]
                    for x in SIM if (x.year, x.month) == (prev.year, prev.month))}
        return days

    def sideoats_budget(self):
        rows = []
        by_month = {}
        for d, day in self.sideoats.items():
            for sid, s in day["sites"].items():
                b = by_month.setdefault((d.month, sid), [0, 0, 0])
                b[0] += s["generation_kwh"]
                b[1] += s["amount"] if sid != "CR4" else C.half_up(s["delivered_kwh"] * MERCHANT_BUDGET_PRICE, 1000)
                b[2] += 1
        for d in SIM:
            for sid, _, mw, *_ in SITES:
                gen, rev, n = by_month[(d.month, sid)]
                rows.append((d.isoformat(), sid, round(gen / n * 1.03), round(rev / n * 1.03),
                             round(mw * OPEX_PER_MW_YEAR / 365)))
            rows.append((d.isoformat(), BATTERY[0], None, 900000, round(BATTERY_OPEX_YEAR / 365)))
        return C.csv_text(["date", "asset_id", "generation_kwh", "revenue_cents", "opex_cents"], rows)

    # ------------------------------------------------------------------ Kiskadee
    def _kiskadee(self):
        rng = C.stream(self.seed, "freight")
        weights = [1 / (i + 1) ** 0.7 for i in range(len(SHIPPERS))]
        counter = 418000 + rng.randint(0, 900)
        ar = 0
        days = {}
        for d in SIM:
            kind = day_type(d)
            n = {"weekday": rng.randint(118, 152), "saturday": rng.randint(40, 55), "sunday": rng.randint(32, 46),
                 "holiday": rng.randint(70, 81)}[kind]
            rows = []
            for _ in range(n):
                counter += 1
                lane, base = rng.choice(LANES)
                miles = round(base * rng.uniform(0.97, 1.03))
                brokered = rng.random() < 0.40
                lh = miles * rng.randint(205, 315)
                fsc = miles * rng.randint(44, 58)
                acc = rng.choice([5000, 7500, 10000, 15000, 25000, 35000]) if rng.random() < 0.14 else 0
                rows.append({"load_id": f"BB{counter}", "customer": rng.choices(SHIPPERS, weights)[0], "lane": lane,
                             "miles": miles, "empty_miles": 0 if brokered else round(miles * rng.uniform(0.06, 0.22)),
                             "linehaul_rev": lh, "fuel_surcharge": fsc, "accessorials": acc,
                             "carrier_cost": round((lh + fsc) * rng.uniform(0.80, 0.88)) if brokered else None,
                             "on_time": rng.random() < 0.94, "brokered": brokered})
            if rng.random() < 0.25 or d == C.ops_day(C.DEMO):
                counter += 1
                rows.insert(rng.randint(len(rows) // 3, len(rows) - 1),
                            {"load_id": f"BB{counter}-CR", "customer": rng.choices(SHIPPERS, weights)[0], "lane": "",
                             "miles": 0, "empty_miles": 0, "linehaul_rev": 0, "fuel_surcharge": 0,
                             "accessorials": -rng.randint(30, 120) * 500, "carrier_cost": None, "on_time": None,
                             "brokered": False, "credit": True})
            invoiced = sum(r["linehaul_rev"] + r["fuel_surcharge"] + r["accessorials"] for r in rows)
            if not ar:
                ar = invoiced * 38
            cash = 0 if kind in ("saturday", "sunday") else round(ar * rng.uniform(0.036, 0.046))
            ar += invoiced - cash
            days[d] = {"rows": rows, "invoiced": invoiced, "invoice_count": len(rows), "cash": cash, "ar": ar}
        return days

    def kiskadee_budget(self):
        """Phased by day type, so a holiday's lower volume is in the plan."""
        totals = {}
        for d, day in self.kiskadee.items():
            t = totals.setdefault(d.month, {"w": 0.0, "loads": 0, "rev": 0, "carrier": 0, "asset_miles": 0})
            t["w"] += DAY_WEIGHT[day_type(d)]
            loads = [r for r in day["rows"] if not r.get("credit")]
            t["loads"] += len(loads)
            t["rev"] += day["invoiced"]
            t["carrier"] += sum(r["carrier_cost"] or 0 for r in loads)
            t["asset_miles"] += sum(r["miles"] + r["empty_miles"] for r in loads if not r["brokered"])
        rows = []
        for d in SIM:
            t = totals[d.month]
            share = DAY_WEIGHT[day_type(d)] / t["w"]
            rows.append((d.isoformat(), day_type(d), round(t["loads"] * share * 0.98), round(t["rev"] * share * 0.98),
                         round(t["carrier"] * share * 0.98), round(t["asset_miles"] * share * 0.98), STD_COST_PER_MILE,
                         FIXED_COST_DAY_FREIGHT))
        return C.csv_text(["date", "day_type", "loads", "revenue_cents", "carrier_cost_cents", "asset_miles",
                           "std_cost_per_mile_cents", "fixed_cost_cents"], rows)

    # ------------------------------------------------------------------ Possumhaw
    def _possumhaw(self):
        rng = C.stream(self.seed, "hotel")
        days = {}
        for d in SIM:
            ooo = rng.randint(0, 5)
            available = ROOMS - ooo
            wk = d.weekday()
            occ = OCC_BY_MONTH[d.month] + (0.12 if wk in (4, 5) else -0.04 if wk == 6 else -0.05)
            occ = min(0.98, max(0.35, occ + rng.uniform(-0.04, 0.04)))
            sold = round(available * occ)
            adr_raw = 29800 + (4500 if wk in (4, 5) else 0) + ADR_BY_MONTH[d.month] + rng.randint(-1500, 1500)
            room = sold * adr_raw + rng.randint(-sold * 40, sold * 40)
            fb = sold * rng.randint(11500, 14000) + (rng.randint(400000, 1800000) if rng.random() < 0.15 else 0)
            other = sold * rng.randint(3000, 4200)
            total = room + fb + other
            card = C.half_up(total * rng.randint(8600, 9200), 10000)
            days[d] = {"ooo": ooo, "available": available, "sold": sold, "comps": rng.randint(0, 3), "room": room,
                       "adr": C.half_up(room, sold), "fb": fb, "other": other, "total": total, "card": card,
                       "direct": total - card, "fee": None}
        for d, day in days.items():
            day["fee"] = C.half_up(day["card"] * 285, 10000)
        return days

    def possumhaw_budget(self):
        by_month = {}
        for d, day in self.possumhaw.items():
            b = by_month.setdefault(d.month, [0, 0, 0, 0, 0, 0])
            for i, k in enumerate(("available", "sold", "room", "fb", "other")):
                b[i] += day[k]
            b[5] += 1
        rows = []
        for d in SIM:
            avail, sold, room, fb, other, n = by_month[d.month]
            rows.append((d.isoformat(), round(avail / n), round(sold / n), round(room / n), round(fb / n), round(other / n),
                         ROOM_COST_PER_OCCUPIED, FB_COST_BP, OTHER_COST_BP, FIXED_COST_DAY_HOTEL))
        return C.csv_text(["date", "rooms_available", "rooms_sold", "room_revenue_cents", "fb_revenue_cents",
                           "other_revenue_cents", "room_cost_per_occupied_cents", "fb_cost_bp", "other_cost_bp",
                           "fixed_cost_cents"], rows)

    # ------------------------------------------------------------------ files
    def site_csv(self, ops, sid):
        s = self.sideoats[ops]["sites"][sid]
        return C.csv_text(["date", "site_id", "generation_kwh", "availability_pct", "curtailment_kwh",
                           "insolation_kwh_m2", "inverter_faults"],
                          [(ops.isoformat(), sid, s["generation_kwh"], f"{s['availability_pct']:.1f}", s["curtailment_kwh"],
                            f"{s['insolation_kwh_m2']:.2f}", s["inverter_faults"])])

    def battery_csv(self, ops):
        b = self.sideoats[ops]["battery"]
        return C.csv_text(["date", "asset_id", "cycles", "charge_kwh", "discharge_kwh", "arbitrage_revenue_cents"],
                          [(ops.isoformat(), BATTERY[0], b["cycles"], b["charge_kwh"], b["discharge_kwh"],
                            b["arbitrage_revenue"])])

    def settlement_csv(self, ops):
        day = self.sideoats[ops]
        rows = [(ops.isoformat(), sid, s["delivered_kwh"], C.money(s["price"], "plain"), C.money(s["amount"], "plain"), "")
                for sid, s in day["sites"].items()]
        b = day["battery"]
        rows.append((ops.isoformat(), BATTERY[0], b["delivered_kwh"], "", C.money(b["arbitrage_revenue"], "plain"),
                     "battery arbitrage settlement"))
        if "remittance" in day:
            r = day["remittance"]
            rows.append((ops.isoformat(), "REMIT", "", "", C.money(r["amount"], "plain"), f"remittance for {r['month']}"))
        return C.csv_text(["operating_date", "asset_id", "delivered_kwh", "price_usd_per_mwh", "amount_usd", "memo"],
                          rows)

    def price_csv(self, ops):
        return C.csv_text(["date", "hub", "avg_price_usd_per_mwh"],
                          [(ops.isoformat(), HUB, C.money(self.sideoats[ops]["price"], "plain"))])

    def tms_rows(self, ops):
        return self.kiskadee[ops]["rows"]

    def tms_xlsx(self, ops, layout_id="tms_v1", rows=None, totals_label=layouts.KEEP):
        return layouts.render(layout_id, self.tms_rows(ops) if rows is None else rows, ops, totals_label)

    def invoicing_csv(self, ops):
        day = self.kiskadee[ops]
        return C.csv_text(["batch_date", "batch_id", "invoice_count", "invoiced_usd", "cash_applied_usd", "ar_balance_usd"],
                          [(ops.isoformat(), f"INV-{ops.strftime('%Y%m%d')}", day["invoice_count"],
                            C.money(day["invoiced"], "plain"), C.money(day["cash"], "plain"), C.money(day["ar"], "plain"))])

    def night_audit(self, ops, adr=None):
        """The night audit as the property system prints it. adr plants E5, an ADR line that disagrees with
        room revenue over rooms sold."""
        h = self.possumhaw[ops]
        room = h["room"]
        total = room + h["fb"] + h["other"]
        occ = h["sold"] / h["available"] * 100
        revpar = C.half_up(h["room"], h["available"])

        def line(label, value):
            return f"  {label} {'.' * (34 - len(label))} {value:>14}"

        return "\n".join([
            "POSSUMHAW LODGE                                NIGHT AUDIT REPORT",
            f"Business date {ops.strftime('%m/%d/%Y')}                      Printed {C.morning_of(ops).strftime('%m/%d/%Y')} 03:12",
            "-" * 66,
            "ROOMS",
            line("Rooms in inventory", f"{ROOMS}"),
            line("Out of order", f"{h['ooo']}"),
            line("Rooms available", f"{h['available']}"),
            line("Rooms sold", f"{h['sold']}"),
            line("Complimentary rooms", f"{h['comps']}"),
            line("Occupancy", f"{occ:.1f}%"),
            line("ADR", C.money(h["adr"] if adr is None else adr)),
            line("RevPAR", C.money(revpar)),
            "REVENUE",
            line("Room revenue", C.money(room)),
            line("Food and beverage", C.money(h["fb"])),
            line("Spa, golf and other", C.money(h["other"])),
            line("Total revenue", C.money(total)),
            "PAYMENTS",
            line("Card settlements", C.money(h["card"])),
            line("Direct bill and cash", C.money(h["direct"])),
            "-" * 66,
            "End of report",
        ]) + "\n"

    def deposits_csv(self, ops):
        """The card processor's file the morning after ops: yesterday's deposit, which settles the day before."""
        batch = ops - timedelta(days=1)
        h = self.possumhaw[batch]
        return C.csv_text(["deposit_date", "batch_date", "gross_usd", "fees_usd", "net_usd", "reference"],
                          [(ops.isoformat(), batch.isoformat(), C.money(h["card"], "plain"), C.money(h["fee"], "plain"),
                            C.money(h["card"] - h["fee"], "plain"), f"DEP-{ops.strftime('%Y%m%d')}")])

    def daily_files(self, morning):
        """{relative path: bytes} for the files that land on one morning. The demo morning's TMS export is in
        the new layout V00."""
        ops = C.ops_day(morning)
        m = morning.isoformat()
        out = {}
        for sid, *_ in SITES:
            out[f"sideoats/{m}/sideoats_{sid}_{m}.csv"] = self.site_csv(ops, sid).encode()
        out[f"sideoats/{m}/sideoats_battery_{BATTERY[0]}_{m}.csv"] = self.battery_csv(ops).encode()
        out[f"sideoats/{m}/sideoats_settlement_{m}.csv"] = self.settlement_csv(ops).encode()
        out[f"sideoats/{m}/sideoats_market_price_{m}.csv"] = self.price_csv(ops).encode()
        layout = "V00" if morning == C.DEMO else "tms_v1"
        out[f"kiskadee/{m}/kiskadee_tms_{m}.xlsx"] = self.tms_xlsx(ops, layout)
        out[f"kiskadee/{m}/kiskadee_invoicing_{m}.csv"] = self.invoicing_csv(ops).encode()
        out[f"possumhaw/{m}/possumhaw_night_audit_{m}.txt"] = self.night_audit(ops).encode()
        out[f"possumhaw/{m}/possumhaw_deposits_{m}.csv"] = self.deposits_csv(ops).encode()
        return out

    def register_csv(self):
        """Sideoats's asset register, which the fund keeps by hand: capacity and offtake for each asset."""
        rows = [(sid, name, mw * 1000, offtake, C.money(ppa, "plain") if ppa else "") for sid, name, mw, offtake, ppa, _
                in SITES]
        rows.append((BATTERY[0], BATTERY[1], BATTERY[2] * 1000, "arbitrage", ""))
        return C.csv_text(["asset_id", "name", "capacity_kw", "offtake", "ppa_price_usd_per_mwh"], rows)

    def budget_files(self):
        return {"sideoats/register/sideoats_asset_register.csv": self.register_csv().encode(),
                "sideoats/budget/sideoats_budget_2026.csv": self.sideoats_budget().encode(),
                "kiskadee/budget/kiskadee_budget_2026.csv": self.kiskadee_budget().encode(),
                "possumhaw/budget/possumhaw_budget_2026.csv": self.possumhaw_budget().encode()}

    def eval_files(self):
        """The intake agent's eval set: each variant renders one October day's loads, so its control total is
        that day's invoicing batch."""
        out = {}
        for vid in layouts.EVAL_IDS:
            ops = date.fromisoformat(layouts.LAYOUTS[vid]["ops_date"])
            out[f"kiskadee/eval/{vid}_{C.morning_of(ops).isoformat()}.xlsx"] = self.tms_xlsx(ops, vid)
        return out
