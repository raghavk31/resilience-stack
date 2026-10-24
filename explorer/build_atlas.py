"""
build_atlas.py — the sixteen days as one dataset, for the Climate Code explorer.

    py -3.13 explorer/build_atlas.py [--refresh]       (Python 3.12+: the days use 3.12 f-strings)

The explorer on raghavkohli.xyz/work/climate-code/ is a static page: it cannot run the Streamlit
apps, so this script does their country-level work once, ahead of time, and writes what the page
draws from:

    explorer/dist/atlas.json        one record per country, every day's score + the inputs behind it,
                                    and the constant tables the page's own calculators need
    explorer/dist/countries.geojson country outlines (Natural Earth 110m; 50m for the small islands
                                    the coast chapter needs), stripped to iso3 + name

Nothing here is retyped. The constant tables (heat days, coastal exposure, crop envelopes, the audit's
questions, ...) are read out of each dayNN_*.py with `ast`, and the scores repeat each day's formula,
so a change to a day's file changes the explorer the next time this runs. Network responses are cached
in explorer/.cache/; --refresh refetches them. Standard library only.

Then, in the site repo: python scripts/sync-climate-code.py
"""
import ast
import csv
import json
import math
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "explorer" / "dist"
CACHE = ROOT / "explorer" / ".cache"
REFRESH = "--refresh" in sys.argv
UA = {"User-Agent": "ResilienceStack/1.0 (raghav@perspectives.community)"}
WB = "https://api.worldbank.org/v2"


# ── the days' own tables ──────────────────────────────────────────────────────

class _Inf(ast.NodeTransformer):
    """float("inf") → None: JSON has no infinity, so an open-ended tier bound travels as null."""
    def visit_Call(self, node):
        if (isinstance(node.func, ast.Name) and node.func.id == "float" and node.args
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == "inf"):
            return ast.Constant(None)
        return self.generic_visit(node)


def lit(node):
    return ast.literal_eval(_Inf().visit(node))


def consts(day_file: str, *names: str) -> dict:
    """Top-level literal assignments from a day's file, without importing it (each day runs
    Streamlit at import). `A = B = 0.25` binds both names."""
    tree = ast.parse((ROOT / day_file).read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id in names:
                found[t.id] = lit(value)
            elif isinstance(t, ast.Tuple) and isinstance(value, ast.Tuple):     # A, B = 1990, 2021
                for el, v in zip(t.elts, value.elts):
                    if isinstance(el, ast.Name) and el.id in names:
                        found[el.id] = lit(v)
    missing = set(names) - set(found)
    if missing:
        sys.exit(f"{day_file}: no top-level {', '.join(sorted(missing))}")
    return found


# ── network, cached ───────────────────────────────────────────────────────────

def get_json(url: str, key: str, timeout: int = 60, tries: int = 4):
    path = CACHE / f"{key}.json"
    if path.exists() and not REFRESH:
        return json.loads(path.read_text(encoding="utf-8"))
    for i in range(tries):              # NASA POWER drops connections when asked too fast
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(2 ** i * 2)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def wb_meta() -> dict:
    """iso3 → name, region, income id, for real countries (aggregates dropped)."""
    rows = get_json(f"{WB}/country?format=json&per_page=400", "wb_countries")[1]
    out = {}
    for r in rows:
        region = (r.get("region") or {}).get("value", "")
        if region and region != "Aggregates" and len(r["id"]) == 3:
            out[r["id"]] = {"name": r["name"], "region": region.strip(),
                            "income": (r.get("incomeLevel") or {}).get("id", "")}
    return out


def wb_series(code: str, start: int = 1990, end: int = 2025) -> dict:
    """iso3 → {year: value} for one indicator, every country, non-null values only."""
    out, page = {}, 1
    while True:
        url = (f"{WB}/country/all/indicator/{code}?format=json&per_page=20000"
               f"&date={start}:{end}&page={page}")
        payload = get_json(url, f"wb_{code}_{start}_{end}_p{page}", timeout=120)
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            sys.exit(f"World Bank returned nothing for {code}: {str(payload)[:200]}")
        for r in payload[1]:
            iso, v = r.get("countryiso3code"), r.get("value")
            if iso and len(iso) == 3 and v is not None:
                out.setdefault(iso, {})[int(r["date"])] = float(v)
        if page >= payload[0].get("pages", 1):
            return out
        page += 1


def latest(series: dict, iso: str, max_year: int = 9999, positive: bool = False):
    """The most recent value up to max_year, as the days' `mrv=1` / `groupby().first()` take it."""
    ys = series.get(iso, {})
    for y in sorted(ys, reverse=True):
        if y <= max_year and (not positive or ys[y] > 0):
            return ys[y]
    return None


def year_of(series: dict, max_year: int = 9999) -> int:
    """The year most countries' latest value comes from — the label a layer's legend carries."""
    counts = {}
    for ys in series.values():
        y = max((y for y in ys if y <= max_year), default=None)
        if y:
            counts[y] = counts.get(y, 0) + 1
    return max(counts, key=counts.get) if counts else 0


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def pct_rank(vals: dict) -> dict:
    """pandas Series.rank(pct=True) × 100 — average rank for ties, divided by the count."""
    order = sorted(vals, key=lambda k: vals[k])
    out, i, n = {}, 0, len(order)
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in order[i:j + 1]:
            out[k] = r / n * 100
        i = j + 1
    return out


def rnd(v, d=1):
    return None if v is None else round(v, d)


# ── Day 01 · grid stress ──────────────────────────────────────────────────────

def day01(meta: dict) -> tuple[dict, dict]:
    c = consts("day01_grid_stress.py", "YEAR_RANGE")
    last = c["YEAR_RANGE"][1]
    rows = {}
    with open(ROOT / "data" / "owid_energy_slim.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            iso = r["iso_code"]
            if iso and len(iso) == 3 and not iso.startswith("OWID"):
                rows.setdefault(iso, []).append(r)
    access = wb_series("EG.ELC.ACCS.ZS")
    loss = wb_series("EG.ELC.LOSS.ZS")

    def col(rs, name, max_year):
        # groupby("iso_code").first() after a year-descending sort: each column's latest non-null
        for r in sorted(rs, key=lambda r: -int(r["year"])):
            if int(r["year"]) <= max_year and r.get(name) not in ("", None):
                return float(r[name])
        return None

    out = {}
    for iso in meta:
        rs = rows.get(iso, [])
        fossil = col(rs, "fossil_share_elec", last)
        a, l = latest(access, iso), latest(loss, iso)
        fp = None if fossil is None else min(max(fossil, 0), 100)
        gap = None if a is None else 100 - min(max(a, 0), 100)
        gl = None if l is None else min(min(max(l, 0), 100) * 2.5, 100)
        # compute_stress(): weights shift when a component is missing
        if fp is not None and gap is not None and gl is not None:
            s = fp * .45 + gap * .35 + gl * .20
        elif fp is not None and gap is not None:
            s = fp * .56 + gap * .44
        elif fp is not None and gap is None and gl is None:
            s = fp
        elif fp is None and gap is not None:
            s = gap
        else:
            s = None
        # compute_projection(): straight line through renewables share since 2005 → the year it reaches 50%
        hist = sorted((int(r["year"]), float(r["renewables_share_elec"])) for r in rs
                      if r.get("renewables_share_elec") not in ("", None) and int(r["year"]) >= 2005)
        clean50 = None
        if len(hist) >= 5:
            xs, ys = [h[0] for h in hist], [h[1] for h in hist]
            xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
            den = sum((x - xm) ** 2 for x in xs)
            slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / den if den else 0
            if slope > 0:
                clean50 = xs[-1] if ys[-1] >= 50 else int(xs[-1] + (50 - ys[-1]) / slope)
        if s is not None:
            out[iso] = {"s": rnd(s), "fossil": rnd(fp), "gap": rnd(gap), "loss": rnd(l),
                        "renew": rnd(col(rs, "renewables_share_elec", last)), "clean50": clean50}
    src = {"year": min(last, max((int(r["year"]) for rs in rows.values() for r in rs), default=last)),
           "src": "Our World in Data (electricity mix) · World Bank EG.ELC.ACCS.ZS, EG.ELC.LOSS.ZS"}
    return out, src


# ── Day 02 · solar potential (country centroids, NASA POWER climatology) ──────

def day02(meta: dict) -> tuple[dict, dict]:
    pts = consts("day13_crop_advisor.py", "COUNTRY_CENTROIDS")["COUNTRY_CENTROIDS"]

    def one(p):
        url = ("https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=ALLSKY_SFC_SW_DWN"
               f"&community=RE&longitude={p['lon']}&latitude={p['lat']}&format=JSON")
        try:
            d = get_json(url, f"nasa_{p['iso3']}", timeout=60)
            v = d["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
            return p["iso3"], v
        except Exception as e:
            print(f"  nasa {p['iso3']}: {e}")
            return p["iso3"], None

    with ThreadPoolExecutor(2) as ex:
        res = dict(ex.map(one, pts))
    out = {}
    for iso, v in res.items():
        if v and v.get("ANN", -999) > 0:
            months = [v.get(k) for k in ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")]
            out[iso] = {"ghi": rnd(v["ANN"], 2), "m": [rnd(x, 2) for x in months]}
    return out, {"year": "2001–2020 mean",
                 "src": "NASA POWER climatology (ALLSKY_SFC_SW_DWN) at each country's centroid"}


# ── Day 03 · water stress ─────────────────────────────────────────────────────

def day03(meta: dict) -> tuple[dict, dict]:
    ind = consts("day03_water_stress.py", "INDICATORS")["INDICATORS"]
    s = {k: wb_series(code) for k, code in ind.items()}
    out = {}
    for iso in meta:
        w = latest(s["withdrawal_pct"], iso)
        if w is None:
            continue
        out[iso] = {"w": rnd(w), "fw": rnd(latest(s["freshwater_cap"], iso), 0),
                    "safe": rnd(latest(s["safe_access"], iso)), "agri": rnd(latest(s["agri_share"], iso)),
                    "ind": rnd(latest(s["industry_share"], iso)), "dom": rnd(latest(s["domestic_share"], iso))}
    return out, {"year": year_of(s["withdrawal_pct"]),
                 "src": "World Bank / FAO AQUASTAT ER.H2O.FWTL.ZS (freshwater withdrawal, % of resources)"}


# ── Day 04 · food fragility ───────────────────────────────────────────────────

def day04(meta: dict) -> tuple[dict, dict]:
    ind = consts("day04_food_fragility.py", "FOOD_INDICATORS")["FOOD_INDICATORS"]
    s = {k: wb_series(code) for k, code in ind.items()}
    out = {}
    for iso in meta:
        imp, prod, undr = (latest(s[k], iso) for k in ("food_import_pct", "food_prod_index", "undernourishment"))
        if imp is None:            # _compute_fragility(): no import share, no score
            continue
        score, wt = .35 * min(imp / 100, 1), .35
        if prod is not None:
            score += .35 * min(max(0, 1 - prod / 100), 1); wt += .35
        if undr is not None:
            score += .30 * min(undr / 40, 1); wt += .30
        out[iso] = {"s": rnd(score / wt * 100), "imp": rnd(imp), "prod": rnd(prod), "undr": rnd(undr),
                    "agl": rnd(latest(s["agri_land_pct"], iso))}
    return out, {"year": year_of(s["food_import_pct"]),
                 "src": "World Bank TM.VAL.FOOD.ZS.UN, AG.PRD.FOOD.XD, SN.ITK.DEFC.ZS (FAO)"}


# ── Day 05 · extreme heat ─────────────────────────────────────────────────────

def day05(meta: dict) -> tuple[dict, dict]:
    c = consts("day05_extreme_heat.py", "HEAT_DATA", "AGRI_EMPL")
    out = {iso: {"days": d, "agri": c["AGRI_EMPL"].get(iso)} for iso, d in c["HEAT_DATA"].items()}
    return out, {"year": "2018–2022 mean",
                 "src": "Days a year with apparent temperature above 35 °C at the capital · ERA5 via Open-Meteo"}


# ── Day 06 · coastal exposure ─────────────────────────────────────────────────

def day06(meta: dict) -> tuple[dict, dict]:
    c = consts("day06_coastal_risk.py", "COASTAL_DATA")["COASTAL_DATA"]
    out = {iso: {"p1": v[0], "p2": v[1], "p3": v[2], "sub": v[3], "km": v[4], "pop": v[5]} for iso, v in c.items()}
    return out, {"year": "IPCC AR6 projections",
                 "src": "Kulp & Strauss 2019 (Nature Communications) · Climate Central · IPCC AR6 WG1 Ch.9"}


# ── Day 07 · forests ──────────────────────────────────────────────────────────

def day07(meta: dict) -> tuple[dict, dict]:
    c = consts("day07_deforestation.py", "FIRST_YEAR", "LAST_YEAR", "CARBON_DENSITY", "DEFAULT_CARBON",
               "TC_TO_TCO2", "HA_PER_KM2")
    y0, y1 = c["FIRST_YEAR"], c["LAST_YEAR"]
    km2, pct = wb_series("AG.LND.FRST.K2"), wb_series("AG.LND.FRST.ZS")
    out = {}
    for iso in meta:
        a, b = km2.get(iso, {}).get(y0), km2.get(iso, {}).get(y1)
        if not a or b is None:
            continue
        cd = c["CARBON_DENSITY"].get(iso, c["DEFAULT_CARBON"])
        out[iso] = {"d": rnd((b - a) / a * 100), "pct": rnd(pct.get(iso, {}).get(y1)),
                    "km2": round(b), "dkm2": round(b - a),
                    "co2": rnd(b * c["HA_PER_KM2"] * cd * c["TC_TO_TCO2"] / 1e9, 2),
                    "ts": [rnd(pct.get(iso, {}).get(y)) for y in range(y0, y1 + 1, 5)]}
    return out, {"year": f"{y0}–{y1}", "src": "World Bank / FAO FRA AG.LND.FRST.K2, AG.LND.FRST.ZS · "
                                               "carbon density after Pan et al. 2011"}


# ── Day 08 · air ──────────────────────────────────────────────────────────────

def day08(meta: dict) -> tuple[dict, dict]:
    c = consts("day08_air_quality.py", "LAST_MORT_YEAR", "WHO_2021", "VSL_USD", "DEFAULT_VSL")
    pm, mort, pop = wb_series("EN.ATM.PM25.MC.M3"), wb_series("SH.STA.AIRP.P5"), wb_series("SP.POP.TOTL")
    my = c["LAST_MORT_YEAR"]
    out = {}
    for iso, m in meta.items():
        p = latest(pm, iso)
        if p is None:
            continue
        rate, people = mort.get(iso, {}).get(my), pop.get(iso, {}).get(my)
        deaths = round(rate * people / 1e5) if rate is not None and people else None
        vsl = c["VSL_USD"].get(m["income"], c["DEFAULT_VSL"])
        out[iso] = {"pm": rnd(p), "x": rnd(p / c["WHO_2021"]), "mort": rnd(rate), "deaths": deaths,
                    "cost": rnd(deaths * vsl / 1e9, 2) if deaths is not None else None,
                    "ts": [rnd(pm.get(iso, {}).get(y)) for y in range(1990, 2021, 5)]}
    return out, {"year": year_of(pm), "mort_year": my,
                 "src": "World Bank EN.ATM.PM25.MC.M3 · WHO SH.STA.AIRP.P5 · OECD 2020 value of a statistical life"}


# ── Day 09 · migration pressure ───────────────────────────────────────────────

def day09(meta: dict) -> tuple[dict, dict]:
    c = consts("day09_migration.py", "W_WATER", "W_FOOD", "W_HEAT", "W_ECO", "HEAT_SCORE", "DEFAULT_HEAT",
               "REGIONAL_GROWTH", "DEFAULT_GROWTH", "IDMC_NEW_2022", "IDMC_STOCK_2022")
    water, food = wb_series("ER.H2O.FWTL.ZS"), wb_series("SN.ITK.DEFC.ZS")
    gdp, pop = wb_series("NY.GDP.PCAP.CD"), wb_series("SP.POP.TOTL")
    v = {iso: {"w": latest(water, iso), "f": latest(food, iso), "g": latest(gdp, iso), "p": latest(pop, iso)}
         for iso in meta}
    # load_migration_data(): keep countries with any of the four, then fill water/food by their medians
    v = {k: x for k, x in v.items() if any(val is not None for val in x.values())}
    mw, mf = median(x["w"] for x in v.values()), median(x["f"] for x in v.values())

    def eco(g):
        if g is None or g <= 0:
            return 80.0
        return max(0, 100 - math.log10(g) / math.log10(80_000) * 100)

    out = {}
    for iso, x in v.items():
        heat = c["HEAT_SCORE"].get(iso, c["DEFAULT_HEAT"])
        ws = min(max(x["w"] if x["w"] is not None else mw, 0), 150) / 150 * 100
        fs = min(max(x["f"] if x["f"] is not None else mf, 0), 100)
        es = eco(x["g"])
        cmpi = c["W_WATER"] * ws + c["W_FOOD"] * fs + c["W_HEAT"] * heat + c["W_ECO"] * es
        cmpi50 = min(max(c["W_WATER"] * ws + c["W_FOOD"] * fs + c["W_HEAT"] * min(heat * 1.18, 100)
                         + c["W_ECO"] * es, 0), 100)
        growth = c["REGIONAL_GROWTH"].get(meta[iso]["region"], c["DEFAULT_GROWTH"])
        risk = x["p"] * growth * cmpi50 / 100 * .12 / 1e6 if x["p"] else None
        out[iso] = {"s": rnd(cmpi), "s50": rnd(cmpi50), "risk50": rnd(risk, 2),
                    "new": c["IDMC_NEW_2022"].get(iso), "stock": c["IDMC_STOCK_2022"].get(iso),
                    "parts": [rnd(ws), rnd(fs), rnd(heat), rnd(es)]}
    return out, {"year": "2022 · projected to 2050",
                 "src": "World Bank water, undernourishment, GDP · IDMC GRID 2023 · IPCC AR6 WG2 heat hazard"}


# ── Day 10 · polycrisis ───────────────────────────────────────────────────────

def day10(meta: dict) -> tuple[dict, dict]:
    c = consts("day10_polycrisis.py", "DIMS", "HEAT_SCORE", "DEFAULT_HEAT")
    # EG.USE.COMM.FO.ZS is zero-filled after 2015 (and India's 2015 value is broken), so a 0 is read as
    # missing and the last good year is 2014. EN.ATM.CO2E.PC was retired by the World Bank in 2024; its
    # successor is EN.GHG.CO2.PC.CE.AR5 (CO2 per capita, excluding land use).
    raw = {
        "fossil_pct": (wb_series("EG.USE.COMM.FO.ZS"), 2014, True),
        "elec_access": (wb_series("EG.ELC.ACCS.ZS"), 9999, False),
        "water_withdrawal": (wb_series("ER.H2O.FWTL.ZS"), 9999, False),
        "undernourishment": (wb_series("SN.ITK.DEFC.ZS"), 9999, False),
        "pm25": (wb_series("EN.ATM.PM25.MC.M3"), 9999, False),
        "gdp_pc": (wb_series("NY.GDP.PCAP.CD"), 9999, False),
        "co2_pc": (wb_series("EN.GHG.CO2.PC.CE.AR5"), 9999, False),
    }
    isos = list(meta)
    val = {k: {iso: latest(s, iso, my, pos) for iso in isos} for k, (s, my, pos) in raw.items()}
    for k, d in val.items():                           # fillna(median), as load_polycrisis_data() does
        m = median(d.values())
        for iso in isos:
            if d[iso] is None:
                d[iso] = m
    heat = {iso: c["HEAT_SCORE"].get(iso, c["DEFAULT_HEAT"]) for iso in isos}
    dims = {
        "d_energy": pct_rank({i: val["fossil_pct"][i] * .55 + (100 - val["elec_access"][i]) * .45 for i in isos}),
        "d_water": pct_rank(val["water_withdrawal"]),
        "d_food": pct_rank(val["undernourishment"]),
        "d_air": pct_rank(val["pm25"]),
        "d_heat": pct_rank(heat),
        "d_eco": pct_rank({i: -math.log10(max(val["gdp_pc"][i], 1)) for i in isos}),
        "d_co2": pct_rank(val["co2_pc"]),
    }
    out = {}
    for iso in isos:
        vul = sum(dims[col][iso] * w for col, _, w in c["DIMS"].values())
        out[iso] = {"s": rnd(min(max(100 - vul, 0), 100)),
                    "dims": [round(dims[col][iso]) for col, _, _ in c["DIMS"].values()]}
    return out, {"year": "latest of each input",
                 "src": "World Bank (energy, water, food, air, GDP, CO2) · IPCC AR6 WG2 heat hazard · "
                        "percentile rank across all countries"}


# ── the constant tables the page's own calculators use ────────────────────────

def tools() -> dict:
    d02 = consts("day02_solar_atlas.py", "PANEL_W", "PANEL_M2", "EFFICIENCY", "PERF_RATIO", "CO2_G_KWH",
                 "COST_USD_W", "BENCHMARKS", "SOLAR_BANDS")
    d05 = consts("day05_extreme_heat.py", "HEAT_BANDS", "TEMP_DELTAS", "HEAT_THR", "LABOUR_THR")
    d06 = consts("day06_coastal_risk.py", "IPCC_SLR", "SSP_LABELS", "RISK_BANDS")
    slr = {}
    for (ssp, year), v in d06.pop("IPCC_SLR").items():
        slr.setdefault(ssp, {})[str(year)] = v
    d06["IPCC_SLR"] = slr
    return {
        "d01": consts("day01_grid_stress.py", "BANDS"),
        "d02": d02,
        "d03": consts("day03_water_stress.py", "BANDS", "FW_THRESHOLDS", "COLOR_CAP"),
        "d04": consts("day04_food_fragility.py", "FRAG_BANDS"),
        "d05": d05,
        "d06": d06,
        "d07": consts("day07_deforestation.py", "FOREST_HOTSPOTS", "COMPARE_YEARS"),
        "d08": consts("day08_air_quality.py", "WHO_2021", "WHO_2005", "AQI_BREAKS", "CITY_AIR"),
        "d10": consts("day10_polycrisis.py", "DIMS", "RESILIENCE_BANDS", "CARD_DATA"),
        "d11": consts("day11_resilience_audit.py", "SECTIONS", "RESILIENCE_BANDS"),
        "d12": consts("day12_emergency_prep.py", "RISK_OPTIONS", "SPECIAL_OPTIONS"),
        "d13": consts("day13_crop_advisor.py", "CROPS"),
        "d14": consts("day14_offgrid_calc.py", "PANEL_COST_PER_WP", "INVERTER_COST", "BOS_COST",
                      "BATTERY_COST_PER_KWH", "TANK_COST_PER_LITER", "WATER_FILTER_COST", "GARDEN_PER_M2"),
        "d15": consts("day15_water_security.py", "PROFILES", "ROOF_RUNOFF", "GW_SYSTEMS", "FIRST_FLUSH_EFF",
                      "GARDEN_L_PER_M2", "F_TOILET", "F_GREYGEN", "F_POTABLE_INDOOR", "TANK_COST_TIERS",
                      "PRACTICAL_TANK_L", "COST_COLLECTION", "COST_FILTRATION", "COST_PUMP", "COST_GW"),
        "d16": consts("day16_heat_mapper.py", "CATEGORIES", "HEAT_DANGER_C"),
    }


# ── outlines ──────────────────────────────────────────────────────────────────

NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_{}_admin_0_countries.geojson"
ALIAS = {"KOS": "XKX", "SDS": "SSD", "PSX": "PSE", "SAH": "ESH"}


def outlines(wanted: set) -> dict:
    def iso_of(p):
        for k in ("ISO_A3", "ISO_A3_EH", "ADM0_A3"):
            v = p.get(k)
            if v and v != "-99":
                return ALIAS.get(v, v)
        return None

    def shrink(geom, d):
        def ring(r):
            out = []
            for x, y in r:
                pt = [round(x, d), round(y, d)]
                if not out or pt != out[-1]:
                    out.append(pt)
            return out if len(out) >= 4 else None
        if geom["type"] == "Polygon":
            polys = [geom["coordinates"]]
        else:
            polys = geom["coordinates"]
        kept = []
        for poly in polys:
            rings = [r for r in (ring(r) for r in poly) if r]
            if rings:
                kept.append(rings)
        return {"type": "MultiPolygon", "coordinates": kept} if kept else None

    feats, have = [], set()
    for scale, d in (("110m", 2), ("50m", 3)):
        gj = get_json(NE.format(scale), f"ne_{scale}", timeout=180)
        for f in gj["features"]:
            iso = iso_of(f["properties"])
            if not iso or iso in have or (scale == "50m" and iso not in wanted):
                continue
            g = shrink(f["geometry"], d)
            if g:
                have.add(iso)
                feats.append({"type": "Feature", "id": len(feats), "properties": {"iso": iso,
                              "name": f["properties"].get("NAME", iso)}, "geometry": g})
    return {"type": "FeatureCollection", "features": feats}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    meta = wb_meta()
    days = {"grid": day01, "sun": day02, "water": day03, "food": day04, "heat": day05, "coast": day06,
            "forest": day07, "air": day08, "move": day09, "poly": day10}
    countries = {iso: {"n": m["name"], "r": m["region"], "inc": m["income"]} for iso, m in meta.items()}
    sources = {}
    for key, fn in days.items():
        data, src = fn(meta)
        sources[key] = src
        for iso, rec in data.items():
            if iso in countries:
                countries[iso][key] = rec
        print(f"  {key:7} {len(data):4} countries  ({src['year']})")
    atlas = {"built": date.today().isoformat(), "sources": sources, "countries": countries, "tools": tools()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "atlas.json").write_text(json.dumps(atlas, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    geo = outlines(set(countries))
    (OUT / "countries.geojson").write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    missing = sorted(i for i in countries if i not in {f["properties"]["iso"] for f in geo["features"]})
    for f in ("atlas.json", "countries.geojson"):
        print(f"  {f:18} {(OUT / f).stat().st_size / 1e3:7.0f} KB")
    if missing:
        print(f"  no outline for {len(missing)}: {' '.join(missing)}")


if __name__ == "__main__":
    main()
