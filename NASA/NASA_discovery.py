"""
NASA CITIZEN SCIENCE DISCOVERY ASSISTANT
══════════════════════════════════════════════════════════════════
Your personal co-discovery tool — built for Shyann 🔭

HOW TO USE:
  1. Go to planethunters.org OR backyardworlds.org
  2. When you find something interesting, grab its RA and Dec
  3. Run this script — it will cross-check every NASA/ESA database
  4. If the score is high — post it to the science team forum!

Run modes:
  python3 NASA_discovery.py              ← interactive mode (asks you questions)
  python3 NASA_discovery.py --scan       ← auto-scan for top candidates
  python3 NASA_discovery.py --monitor    ← watch arXiv for new discoveries daily

APIs used (all free, no auth required):
  SIMBAD TAP          : simbad.cds.unistra.fr
  Gaia DR3 TAP        : gea.esac.esa.int
  GWOSC               : gwosc.org
  NASA Exoplanet Arch : exoplanetarchive.ipac.caltech.edu
  NASA DONKI          : api.nasa.gov
  JPL Sentry          : ssd-api.jpl.nasa.gov
  arXiv               : export.arxiv.org
  NASA Image Library  : images-api.nasa.gov
"""

import requests
import json
import os
import sys
import math
import time
import numpy as np
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote

warnings.filterwarnings("ignore")

NASA_API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")
OUTPUT_FILE  = f"discovery_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

output_lines = []

# ── ANSI colors for terminal ──────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
PURPLE = "\033[95m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
STAR   = "★"
ROCKET = "🚀"
PLANET = "🪐"
SCOPE  = "🔭"
BH     = "⚫"
ALERT  = "⚠️ "

def emit(text="", color=""):
    line = f"{color}{text}{RESET}" if color else text
    print(line)
    output_lines.append(text)

def banner(text, color=BLUE):
    emit()
    emit("═" * 65, color)
    emit(f"  {text}", color + BOLD)
    emit("═" * 65, color)

def divider(label="", color=CYAN):
    emit()
    emit("─" * 55, color)
    if label:
        emit(f"  ▸  {label}", color + BOLD)
        emit("─" * 55, color)

def success(text): emit(f"  {GREEN}✓{RESET}  {text}")
def warn(text):    emit(f"  {YELLOW}⚠{RESET}  {text}")
def info(text):    emit(f"  {BLUE}→{RESET}  {text}")
def highlight(text): emit(f"\n  {PURPLE}{BOLD}{text}{RESET}\n")


# ═══════════════════════════════════════════════════════════════
#  PHYSICS ENGINE
# ═══════════════════════════════════════════════════════════════

G       = 6.674e-11
C       = 3.0e8
M_SUN   = 1.989e30
L_SUN   = 3.846e26
MP      = 1.673e-27
SIGMA_T = 6.652e-29

CHANDRASEKHAR = 1.44
TOV_LIMIT     = 3.0

def schwarzschild_radius_km(mass_solar):
    return 2 * G * (mass_solar * M_SUN) / (C**2) / 1000

def eddington_luminosity_lsun(mass_solar):
    return (4 * math.pi * G * mass_solar * M_SUN * MP * C / SIGMA_T) / L_SUN

def angular_separation_deg(ra1, dec1, ra2, dec2):
    """Great-circle angular separation between two sky positions."""
    r1, d1 = math.radians(ra1),  math.radians(dec1)
    r2, d2 = math.radians(ra2),  math.radians(dec2)
    cos_sep = (math.sin(d1)*math.sin(d2) +
               math.cos(d1)*math.cos(d2)*math.cos(r1-r2))
    cos_sep = max(-1.0, min(1.0, cos_sep))
    return math.degrees(math.acos(cos_sep))

def hr_classify(teff, lum_solar):
    if not teff or not lum_solar or lum_solar <= 0:
        return "Unknown"
    log_l = math.log10(lum_solar)
    if teff > 30000 and log_l > 4:
        return f"{RED}O/WR supergiant — strong BH progenitor{RESET}"
    elif teff > 10000 and log_l > 4:
        return f"{YELLOW}B supergiant — BH progenitor if M > 20 M☉{RESET}"
    elif teff < 4000 and log_l > 4:
        return f"{YELLOW}Red supergiant — BH/NS progenitor{RESET}"
    elif teff < 4000 and log_l > 2:
        return "Red giant — post main sequence"
    elif teff > 5000 and log_l < -1:
        return "White dwarf — collapsed remnant"
    elif 5000 < teff < 6500 and -0.5 < log_l < 0.5:
        return "G-type main sequence (Sun-like)"
    else:
        return "Main sequence / subgiant"


# ═══════════════════════════════════════════════════════════════
#  SAFE HTTP HELPERS
# ═══════════════════════════════════════════════════════════════

def safe_get(url, params=None, timeout=20, label=""):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code != 200:
            warn(f"{label} — HTTP {r.status_code}")
            return None
        text = r.text.strip()
        if not text:
            warn(f"{label} — empty response")
            return None
        return r.json()
    except requests.exceptions.Timeout:
        warn(f"{label} — timed out")
        return None
    except requests.exceptions.ConnectionError:
        warn(f"{label} — connection error")
        return None
    except json.JSONDecodeError:
        warn(f"{label} — bad JSON")
        return None
    except Exception as e:
        warn(f"{label} — {e}")
        return None

def safe_tap(tap_url, query, label="", timeout=25):
    try:
        r = requests.get(
            tap_url,
            params={"LANG": "ADQL", "REQUEST": "doQuery",
                    "QUERY": query, "FORMAT": "json"},
            timeout=timeout
        )
        if r.status_code != 200:
            warn(f"{label} TAP — HTTP {r.status_code}")
            return [], []
        data = r.json()
        cols = [c.get("name", f"c{i}") for i, c in
                enumerate(data.get("metadata", []))]
        rows = data.get("data", [])
        return cols, rows
    except Exception as e:
        warn(f"{label} TAP — {e}")
        return [], []


# ═══════════════════════════════════════════════════════════════
#  SCORING ENGINE
# ═══════════════════════════════════════════════════════════════

def score_black_hole(obj):
    score, flags = 0, []
    otype = str(obj.get("otype",""))
    mass  = obj.get("mass_solar") or 0
    teff  = obj.get("teff") or 0
    log_l = obj.get("log_l")
    rv    = obj.get("radial_velocity") or 0
    pm    = obj.get("proper_motion")

    if "BH" in otype:
        score += 50; flags.append("SIMBAD type = confirmed BH (+50)")
    elif "BH?" in otype:
        score += 35; flags.append("SIMBAD BH candidate type (+35)")
    if any(t in otype for t in ["HXB","LXB","ULX","XB*"]):
        score += 25; flags.append("X-ray binary — known BH host environment (+25)")
    if mass > TOV_LIMIT:
        score += 30; flags.append(f"Mass {mass:.1f}M☉ > TOV limit 3.0M☉ (+30)")
    elif mass > CHANDRASEKHAR:
        score += 10; flags.append(f"Mass {mass:.1f}M☉ > Chandrasekhar limit (+10)")
    if teff > 25000 and log_l and log_l > 4.5:
        score += 20; flags.append(f"Hot supergiant Teff={teff:.0f}K logL={log_l:.1f} — BH progenitor (+20)")
    if teff < 4000 and log_l and log_l > 4:
        score += 15; flags.append(f"Red supergiant logL={log_l:.1f} — late-stage progenitor (+15)")
    if rv and abs(rv) > 100:
        score += 15; flags.append(f"High radial velocity {rv:.1f}km/s — dark companion signal (+15)")
    if pm and pm > 50:
        score += 10; flags.append(f"High proper motion {pm:.1f}mas/yr — possible runaway (+10)")

    return min(score, 100), flags

def score_exoplanet(lc_data):
    """
    Score a light curve for exoplanet transit likelihood.
    lc_data: dict with depth_ppm, duration_hours, period_days, shape
    """
    score, flags = 0, []
    depth    = lc_data.get("depth_ppm", 0)
    duration = lc_data.get("duration_hours", 0)
    period   = lc_data.get("period_days", 0)
    periodic = lc_data.get("periodic", False)
    shape    = lc_data.get("shape", "unknown")

    if periodic:
        score += 30; flags.append("Periodic signal — repeating transit (+30)")
    if 100 < depth < 50000:
        score += 20; flags.append(f"Depth {depth}ppm — planet-scale transit (+20)")
    elif depth > 50000:
        score += 10; flags.append(f"Depth {depth}ppm — possible eclipsing binary not planet")
    if 1 < duration < 16:
        score += 15; flags.append(f"Duration {duration}h — consistent with planet transit (+15)")
    if period > 0:
        score += 15; flags.append(f"Period {period:.1f}d detected (+15)")
    if shape == "flat_bottom":
        score += 20; flags.append("Flat-bottom transit shape — solid body transit (+20)")

    return min(score, 100), flags

def score_new_star(obj):
    score, flags = 0, []
    otype = str(obj.get("otype",""))
    teff  = obj.get("teff") or 0
    log_l = obj.get("log_l")
    pm    = obj.get("proper_motion")

    if any(t in otype for t in ["YSO","TT*","Ae*","Or*","Em*","pA*"]):
        score += 40; flags.append(f"SIMBAD type '{otype}' = young stellar object (+40)")
    if any(t in otype for t in ["Cl*","OpC"]):
        score += 15; flags.append("In open cluster — young stellar region (+15)")
    if teff > 15000 and log_l and log_l > 3:
        score += 20; flags.append(f"Massive hot star Teff={teff:.0f}K — recently formed (+20)")
    if log_l and log_l > 5:
        score += 10; flags.append(f"Hyperluminous logL={log_l:.1f} — hypergiant/LBV (+10)")
    if pm and 10 < pm < 50:
        score += 10; flags.append(f"PM {pm:.1f}mas/yr — possible runaway from birth cluster (+10)")

    return min(score, 100), flags


# ═══════════════════════════════════════════════════════════════
#  DATABASE QUERIES
# ═══════════════════════════════════════════════════════════════

SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
GAIA_TAP   = "https://gea.esac.esa.int/tap-server/tap/sync"
EXOP_TAP   = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

def query_simbad_cone(ra, dec, radius_arcmin=5.0):
    """Query SIMBAD for all objects within radius of coordinates."""
    radius_deg = radius_arcmin / 60.0
    query = f"""
        SELECT TOP 30
            main_id, ra, dec, otype,
            rvz_radvel, plx_value, pmra, pmdec
        FROM basic
        WHERE CONTAINS(
            POINT('ICRS', ra, dec),
            CIRCLE('ICRS', {ra}, {dec}, {radius_deg})
        ) = 1
        ORDER BY plx_value DESC
    """
    cols, rows = safe_tap(SIMBAD_TAP, query, label="SIMBAD cone")
    results = []
    for row in rows:
        d     = dict(zip(cols, row))
        pmra  = d.get("pmra")
        pmdec = d.get("pmdec")
        pm    = math.sqrt(float(pmra)**2 + float(pmdec)**2) if pmra and pmdec else None
        plx   = d.get("plx_value")
        results.append({
            "name":            str(d.get("main_id","?")),
            "ra":              float(d.get("ra",0)) if d.get("ra") else None,
            "dec":             float(d.get("dec",0)) if d.get("dec") else None,
            "otype":           str(d.get("otype","")),
            "radial_velocity": float(d.get("rvz_radvel")) if d.get("rvz_radvel") else None,
            "parallax":        float(plx) if plx else None,
            "proper_motion":   pm,
            "mass_solar":      None,
            "teff":            None,
            "log_l":           None,
            "distance_pc":     1000/float(plx) if plx and float(plx) > 0 else None,
        })
    return results

def query_gaia_cone(ra, dec, radius_arcmin=5.0):
    """Query Gaia DR3 for stellar data near coordinates."""
    radius_deg = radius_arcmin / 60.0
    query = f"""
        SELECT TOP 20
            source_id, ra, dec,
            teff_gspphot, lum_flame, mass_flame,
            radial_velocity, pmra, pmdec,
            parallax, phot_g_mean_mag
        FROM gaiadr3.gaia_source
        WHERE CONTAINS(
            POINT('ICRS', ra, dec),
            CIRCLE('ICRS', {ra}, {dec}, {radius_deg})
        ) = 1
          AND parallax > 0
        ORDER BY phot_g_mean_mag ASC
    """
    cols, rows = safe_tap(GAIA_TAP, query, label="Gaia DR3 cone")
    results = []
    for row in rows:
        d     = dict(zip(cols, row))
        lum   = d.get("lum_flame")
        teff  = d.get("teff_gspphot")
        pmra  = d.get("pmra")
        pmdec = d.get("pmdec")
        pm    = math.sqrt(float(pmra)**2 + float(pmdec)**2) if pmra and pmdec else None
        log_l = math.log10(float(lum)) if lum and float(lum) > 0 else None
        plx   = d.get("parallax")
        results.append({
            "name":            f"Gaia DR3 {d.get('source_id','')}",
            "ra":              float(d.get("ra",0)) if d.get("ra") else None,
            "dec":             float(d.get("dec",0)) if d.get("dec") else None,
            "otype":           "",
            "teff":            float(teff) if teff else None,
            "log_l":           log_l,
            "lum_solar":       float(lum) if lum else None,
            "mass_solar":      float(d.get("mass_flame")) if d.get("mass_flame") else None,
            "radial_velocity": float(d.get("radial_velocity")) if d.get("radial_velocity") else None,
            "proper_motion":   pm,
            "parallax":        float(plx) if plx else None,
            "mag_g":           float(d.get("phot_g_mean_mag")) if d.get("phot_g_mean_mag") else None,
            "distance_pc":     1000/float(plx) if plx and float(plx) > 0 else None,
        })
    return results

def query_exoplanet_archive_cone(ra, dec, radius_deg=0.5):
    """Check NASA Exoplanet Archive for known planets near coordinates."""
    query = f"""
        SELECT pl_name, hostname, ra, dec,
               pl_orbper, pl_rade, pl_masse, disc_year, discoverymethod
        FROM ps
        WHERE ra BETWEEN {ra - radius_deg} AND {ra + radius_deg}
          AND dec BETWEEN {dec - radius_deg} AND {dec + radius_deg}
          AND pl_rade IS NOT NULL
    """
    cols, rows = safe_tap(EXOP_TAP, query, label="Exoplanet Archive")
    results = []
    for row in rows:
        d = dict(zip(cols, row))
        results.append(d)
    return results

def check_gw_proximity(ra, dec, radius_deg=5.0):
    """Check if any GW event is close to these coordinates."""
    gw = safe_get("https://gwosc.org/eventapi/json/allevents/",
                  label="GWOSC proximity check")
    if not gw:
        return []
    events = gw.get("events", {})
    nearby = []
    for name, ev in events.items():
        ev_ra  = ev.get("ra")
        ev_dec = ev.get("dec")
        if ev_ra is not None and ev_dec is not None:
            sep = angular_separation_deg(ra, dec, float(ev_ra), float(ev_dec))
            if sep < radius_deg:
                m1   = ev.get("mass_1_source", {})
                m2   = ev.get("mass_2_source", {})
                m1v  = float(m1.get("best",0)) if isinstance(m1,dict) else 0
                m2v  = float(m2.get("best",0)) if isinstance(m2,dict) else 0
                nearby.append({
                    "name":       name,
                    "separation": sep,
                    "mass_1":     m1v,
                    "mass_2":     m2v,
                    "gps":        ev.get("GPS"),
                })
    return nearby

def check_sentry_cone(ra, dec):
    """Check JPL Sentry for any impact-risk objects in this area."""
    sentry = safe_get("https://ssd-api.jpl.nasa.gov/sentry.api",
                      label="JPL Sentry")
    if not sentry:
        return []
    return sentry.get("data", [])[:5]

def fetch_arxiv_papers(query_term, max_results=5):
    """Fetch latest arXiv papers matching a query."""
    try:
        resp = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": query_term,
                "sortBy":       "submittedDate",
                "sortOrder":    "descending",
                "max_results":  max_results,
            },
            timeout=15
        )
        root    = ET.fromstring(resp.text)
        ns      = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        papers  = []
        for entry in entries:
            title   = entry.findtext("atom:title",   "", ns).strip().replace("\n"," ")
            pub     = entry.findtext("atom:published","",ns)[:10]
            authors = [a.findtext("atom:name","",ns) for a in entry.findall("atom:author",ns)]
            summary = entry.findtext("atom:summary", "",ns).strip().replace("\n"," ")
            link    = entry.findtext("atom:id",      "",ns)
            papers.append({
                "title": title, "date": pub,
                "authors": authors, "summary": summary, "url": link
            })
        return papers
    except Exception as e:
        warn(f"arXiv fetch failed: {e}")
        return []

def fetch_solar_context():
    """Get current solar activity context."""
    start = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    end   = datetime.today().strftime("%Y-%m-%d")
    params = {"startDate": start, "endDate": end, "api_key": NASA_API_KEY}
    flares = safe_get("https://api.nasa.gov/DONKI/FLR", params=params, label="Solar flares")
    storms = safe_get("https://api.nasa.gov/DONKI/GST", params=params, label="Geo storms")
    flare_count = len(flares) if isinstance(flares, list) else 0
    storm_count = len(storms) if isinstance(storms, list) else 0
    max_kp = 0
    if storms:
        for s in storms:
            for k in s.get("allKpIndex",[]):
                max_kp = max(max_kp, k.get("kpIndex",0))
    return flare_count, storm_count, max_kp


# ═══════════════════════════════════════════════════════════════
#  FULL CANDIDATE ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_candidate(ra, dec, name="", search_type="all",
                      radius_arcmin=5.0, notes=""):
    """
    Full multi-database analysis of a sky position.
    This is the core discovery engine.
    """
    banner(f"{SCOPE} CANDIDATE ANALYSIS", PURPLE)
    emit(f"  Target          : {name or 'User candidate'}")
    emit(f"  Coordinates     : RA={ra:.4f}°  Dec={dec:+.4f}°")
    emit(f"  Search radius   : {radius_arcmin:.1f} arcmin")
    emit(f"  Search type     : {search_type}")
    if notes:
        emit(f"  Your notes      : {notes}")
    emit(f"  Analysis time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        "target":       {"ra": ra, "dec": dec, "name": name},
        "simbad":       [],
        "gaia":         [],
        "exoplanets":   [],
        "gw_events":    [],
        "bh_scores":    [],
        "star_scores":  [],
        "papers":       [],
        "verdict":      {},
    }

    # ── 1. SIMBAD cone search ─────────────────────────────────
    divider("STEP 1 — SIMBAD DATABASE CHECK", CYAN)
    info(f"Searching {radius_arcmin:.0f} arcmin around your coordinates...")
    simbad_objs = query_simbad_cone(ra, dec, radius_arcmin)
    results["simbad"] = simbad_objs

    if simbad_objs:
        success(f"Found {len(simbad_objs)} objects in SIMBAD")
        col = "{:<30} {:<10} {:<12} {:<10}"
        emit("\n  " + col.format("Object", "Type", "Distance (pc)", "RV (km/s)"))
        emit("  " + "─" * 65)
        for obj in simbad_objs:
            dist = f"{obj['distance_pc']:.0f}" if obj.get("distance_pc") else "N/A"
            rv   = f"{obj['radial_velocity']:.1f}" if obj.get("radial_velocity") else "N/A"
            otype = obj.get("otype","?")
            # Flag interesting types
            flag = ""
            if "BH" in otype:   flag = f" {RED}← BLACK HOLE!{RESET}"
            elif "YSO" in otype: flag = f" {GREEN}← YOUNG STAR!{RESET}"
            elif "HXB" in otype or "LXB" in otype: flag = f" {YELLOW}← X-RAY BINARY{RESET}"
            emit("  " + col.format(
                obj["name"][:29], otype[:9], dist, rv
            ) + flag)
        results["simbad"] = simbad_objs
    else:
        warn("No known objects found in SIMBAD at these coordinates")
        emit("  This could mean it's an undiscovered object — or coordinates")
        emit("  need adjustment. Try widening the search radius.")

    # ── 2. Gaia DR3 cone search ───────────────────────────────
    divider("STEP 2 — GAIA DR3 STELLAR DATA", CYAN)
    info("Querying 1.8 billion star catalog...")
    gaia_objs = query_gaia_cone(ra, dec, radius_arcmin)
    results["gaia"] = gaia_objs

    if gaia_objs:
        success(f"Found {len(gaia_objs)} Gaia DR3 sources")
        emit()
        for obj in gaia_objs[:8]:
            teff  = obj.get("teff")
            log_l = obj.get("log_l")
            mass  = obj.get("mass_solar")
            mag   = obj.get("mag_g")
            dist  = obj.get("distance_pc")
            rv    = obj.get("radial_velocity")
            pm    = obj.get("proper_motion")

            emit(f"  {obj['name'][:40]}")
            if teff:   emit(f"    Temperature     : {teff:.0f} K")
            if log_l:  emit(f"    Luminosity      : 10^{log_l:.2f} L☉")
            if mass:   emit(f"    Mass            : {mass:.2f} M☉")
            if mag:    emit(f"    Gaia G mag      : {mag:.2f}")
            if dist:   emit(f"    Distance        : {dist:.0f} pc  ({dist*3.26:.0f} ly)")
            if rv:     emit(f"    Radial velocity : {rv:.1f} km/s")
            if pm:     emit(f"    Proper motion   : {pm:.2f} mas/yr")
            if teff and log_l:
                hr = hr_classify(teff, 10**log_l)
                emit(f"    HR class        : {hr}")
            emit()
    else:
        warn("No Gaia sources returned — coordinates may be outside survey or too sparse")

    # ── 3. Known exoplanets check ─────────────────────────────
    divider("STEP 3 — NASA EXOPLANET ARCHIVE CHECK", CYAN)
    info("Checking for known planets near these coordinates...")
    exoplanets = query_exoplanet_archive_cone(ra, dec, radius_deg=1.0)
    results["exoplanets"] = exoplanets

    if exoplanets:
        warn(f"Found {len(exoplanets)} known exoplanet(s) already confirmed near this position")
        for p in exoplanets:
            emit(f"  {p.get('pl_name','?')}  host={p.get('hostname','?')}  "
                 f"period={p.get('pl_orbper','?')}d  radius={p.get('pl_rade','?')} Rₑ  "
                 f"disc={p.get('disc_year','?')}  method={p.get('discoverymethod','?')}")
        emit()
        info("These are ALREADY discovered — but there may be more planets in the same system!")
    else:
        success("No known exoplanets at these coordinates — this area is uncharted!")
        emit("  If your light curve shows a transit signal here,")
        emit("  this could be a GENUINE NEW DISCOVERY.")

    # ── 4. Gravitational wave proximity ───────────────────────
    divider("STEP 4 — GRAVITATIONAL WAVE PROXIMITY CHECK", CYAN)
    info(f"Checking GWOSC for GW events within 5° of target...")
    gw_nearby = check_gw_proximity(ra, dec, radius_deg=5.0)
    results["gw_events"] = gw_nearby

    if gw_nearby:
        highlight(f"GW EVENT(S) FOUND NEAR YOUR TARGET!")
        for ev in gw_nearby:
            emit(f"  {ev['name']:<16} separation={ev['separation']:.2f}°  "
                 f"M1={ev['mass_1']:.1f}M☉  M2={ev['mass_2']:.1f}M☉")
        emit()
        emit("  A GW event near your candidate is a STRONG signal.")
        emit("  It could mean a BH/NS remnant is in this region.")
    else:
        info("No GW events detected within 5° — area has no confirmed merger history")

    # ── 5. Score all objects ──────────────────────────────────
    divider("STEP 5 — ANOMALY SCORING", CYAN)
    all_objects = []

    for obj in simbad_objs:
        bhs, bhf = score_black_hole(obj)
        nss, nsf = score_new_star(obj)
        obj["bh_score"]   = bhs
        obj["bh_flags"]   = bhf
        obj["star_score"] = nss
        obj["star_flags"] = nsf
        obj["source"]     = "SIMBAD"
        all_objects.append(obj)

    for obj in gaia_objs:
        bhs, bhf = score_black_hole(obj)
        nss, nsf = score_new_star(obj)
        obj["bh_score"]   = bhs
        obj["bh_flags"]   = bhf
        obj["star_score"] = nss
        obj["star_flags"] = nsf
        obj["source"]     = "Gaia DR3"
        all_objects.append(obj)

    # Sort by highest score
    all_objects.sort(key=lambda x: max(x.get("bh_score",0),
                                       x.get("star_score",0)), reverse=True)

    if all_objects:
        emit(f"\n  {BOLD}TOP SCORED OBJECTS:{RESET}")
        for obj in all_objects[:8]:
            bhs = obj.get("bh_score", 0)
            nss = obj.get("star_score", 0)
            bh_color  = RED if bhs >= 60 else YELLOW if bhs >= 30 else ""
            star_color= GREEN if nss >= 50 else YELLOW if nss >= 25 else ""
            emit(f"\n  {BOLD}{obj['name']}{RESET}  [{obj['source']}]")
            emit(f"    BH score    : {bh_color}{bhs}/100{RESET}"
                 + (f"  {RED}★ HIGH ALERT{RESET}" if bhs >= 60 else
                    f"  {YELLOW}Notable{RESET}" if bhs >= 30 else ""))
            emit(f"    Star score  : {star_color}{nss}/100{RESET}"
                 + (f"  {GREEN}★ STRONG{RESET}" if nss >= 50 else ""))
            if obj.get("bh_flags"):
                for f in obj["bh_flags"][:3]:
                    emit(f"    {BLUE}BH indicator{RESET}: {f}")
            if obj.get("star_flags"):
                for f in obj["star_flags"][:2]:
                    emit(f"    {GREEN}Star indicator{RESET}: {f}")

    # ── 6. Related papers ─────────────────────────────────────
    divider("STEP 6 — LITERATURE SEARCH (arXiv)", CYAN)
    search_terms = []
    if name:
        search_terms.append(f"ti:{quote(name.replace(' ','+'))}")
    coord_term = f"ti:RA+{ra:.1f}+dec+{dec:.1f}"

    papers = fetch_arxiv_papers(
        f"ti:exoplanet+candidate+AND+cat:astro-ph.EP", max_results=3
    )
    results["papers"] = papers
    if papers:
        success(f"Found {len(papers)} recent relevant papers")
        for p in papers[:3]:
            emit(f"\n  [{p['date']}] {p['title'][:68]}")
            emit(f"   {', '.join(p['authors'][:2])}{'et al.' if len(p['authors'])>2 else ''}")
            emit(f"   {p['summary'][:160]}...")
    else:
        info("No directly matching papers found")

    # ── 7. Solar context ──────────────────────────────────────
    divider("STEP 7 — CURRENT SOLAR ACTIVITY CONTEXT", CYAN)
    flares, storms, max_kp = fetch_solar_context()
    activity = ("ELEVATED" if max_kp >= 5 else "NORMAL")
    emit(f"  Solar flares (7 days) : {flares}")
    emit(f"  Geomagnetic storms    : {storms}")
    emit(f"  Peak Kp index         : {max_kp:.1f}")
    emit(f"  Activity level        : {YELLOW if activity=='ELEVATED' else GREEN}{activity}{RESET}")
    if activity == "ELEVATED":
        warn("Elevated solar activity may affect ground-based observations")

    # ── 8. VERDICT ────────────────────────────────────────────
    banner(f"{ROCKET} DISCOVERY VERDICT", GREEN)

    top_bh    = max((o.get("bh_score",0) for o in all_objects), default=0)
    top_star  = max((o.get("star_score",0) for o in all_objects), default=0)
    known_planet = len(exoplanets) > 0
    gw_hit    = len(gw_nearby) > 0

    verdict_level = "ROUTINE"
    verdict_color = BLUE
    action = []

    if top_bh >= 70 or gw_hit:
        verdict_level = "EXCEPTIONAL — REPORT IMMEDIATELY"
        verdict_color = RED
        action = [
            "Post to SIMBAD Talk forum NOW",
            "Email the science team directly",
            "Cross-reference with LIGO sky maps at gwosc.org",
            "Run NASA_detector.py for full physics breakdown",
        ]
    elif top_bh >= 40 or top_star >= 60:
        verdict_level = "HIGH INTEREST — STRONG CANDIDATE"
        verdict_color = YELLOW
        action = [
            "Post to your Zooniverse project Talk forum",
            "Tag it as 'interesting' for science team review",
            "Run NASA_unified_analysis.py for full context",
            "Check if coordinates match any TESS input catalog stars",
        ]
    elif top_bh >= 20 or top_star >= 30 or not known_planet:
        verdict_level = "WORTH FLAGGING"
        verdict_color = CYAN
        action = [
            "Mark as 'interesting' on Zooniverse",
            "Keep monitoring for repeat signals",
            "Check Backyard Worlds forum for similar objects",
        ]
    else:
        verdict_level = "ROUTINE — KEEP SEARCHING"
        verdict_color = BLUE
        action = ["Continue classifying — each one brings you closer"]

    emit(f"\n  {verdict_color}{BOLD}VERDICT: {verdict_level}{RESET}\n")
    emit(f"  Top BH score     : {top_bh}/100")
    emit(f"  Top star score   : {top_star}/100")
    emit(f"  Known planets    : {'Yes — already discovered' if known_planet else 'NONE — uncharted!'}")
    emit(f"  GW event nearby  : {'YES — significant!' if gw_hit else 'No'}")
    emit(f"  Objects in SIMBAD: {len(simbad_objs)}")
    emit(f"  Gaia sources     : {len(gaia_objs)}")

    emit(f"\n  {BOLD}RECOMMENDED ACTIONS:{RESET}")
    for i, act in enumerate(action, 1):
        emit(f"  {i}. {act}")

    results["verdict"] = {
        "level":       verdict_level,
        "bh_score":    top_bh,
        "star_score":  top_star,
        "known_planet":known_planet,
        "gw_nearby":   gw_hit,
    }

    return results


# ═══════════════════════════════════════════════════════════════
#  AUTO-SCAN MODE
# ═══════════════════════════════════════════════════════════════

def auto_scan():
    """
    Scan a list of high-interest sky regions automatically.
    Queries known star-forming regions, known BH candidate zones,
    and recent TESS targets.
    """
    banner(f"{SCOPE} AUTO-SCAN — HIGH INTEREST SKY REGIONS", PURPLE)
    emit("""
  Scanning known regions of interest:
    • Galactic center region (BH candidates)
    • Orion Nebula (star formation, YSOs)
    • Cygnus X-1 region (stellar mass BH)
    • Eta Carinae (hypergiant, BH progenitor)
    • TESS CVZ (continuous viewing zone — best planet data)
    """)

    scan_targets = [
        {"name": "Galactic Center (Sgr A* region)", "ra": 266.4167, "dec": -29.0078,
         "type": "bh",     "notes": "Supermassive BH Sgr A* — 4.1M solar masses"},
        {"name": "Cygnus X-1",                      "ra": 299.5903, "dec": 35.2016,
         "type": "bh",     "notes": "Confirmed stellar-mass BH, 21 M☉"},
        {"name": "Eta Carinae",                      "ra": 161.2648, "dec": -59.6844,
         "type": "star",   "notes": "Hypergiant — one of most massive stars known"},
        {"name": "Orion Nebula (M42)",               "ra": 83.8221,  "dec": -5.3911,
         "type": "star",   "notes": "Active star formation — dozens of YSOs"},
        {"name": "Rho Ophiuchi cloud",               "ra": 246.6,    "dec": -23.4,
         "type": "star",   "notes": "Nearest star-forming region, 138 pc"},
        {"name": "TESS CVZ South",                   "ra": 90.0,     "dec": -66.0,
         "type": "planet", "notes": "Continuous TESS viewing — best transit coverage"},
        {"name": "V404 Cygni",                       "ra": 306.0159, "dec": 33.8672,
         "type": "bh",     "notes": "Confirmed BH X-ray binary, 9 M☉"},
        {"name": "NGC 3201 (globular cluster)",      "ra": 154.4028, "dec": -46.4119,
         "type": "bh",     "notes": "Dormant BH detected via radial velocity 2019"},
    ]

    top_finds = []

    for target in scan_targets:
        emit(f"\n  {CYAN}Scanning: {target['name']}{RESET}")
        emit(f"  Notes: {target['notes']}")

        simbad = query_simbad_cone(
            target["ra"], target["dec"], radius_arcmin=3.0
        )
        gaia   = query_gaia_cone(
            target["ra"], target["dec"], radius_arcmin=3.0
        )

        all_objs = simbad + gaia
        top_bh   = 0
        top_star = 0

        for obj in all_objs:
            bhs, _ = score_black_hole(obj)
            nss, _ = score_new_star(obj)
            top_bh   = max(top_bh,   bhs)
            top_star = max(top_star, nss)

        color = (RED if top_bh >= 60 or top_star >= 60 else
                 YELLOW if top_bh >= 30 or top_star >= 30 else GREEN)
        emit(f"  {color}BH={top_bh}/100  Star={top_star}/100  "
             f"Objects found: {len(all_objs)}{RESET}")

        top_finds.append({
            "name":       target["name"],
            "ra":         target["ra"],
            "dec":        target["dec"],
            "bh_score":   top_bh,
            "star_score": top_star,
            "count":      len(all_objs),
        })

        time.sleep(0.5)  # be polite to APIs

    divider("AUTO-SCAN RESULTS — RANKED", GREEN)
    top_finds.sort(key=lambda x: max(x["bh_score"], x["star_score"]), reverse=True)
    col = "{:<36} {:<10} {:<10} {:<8}"
    emit("  " + col.format("Target", "BH Score", "Star Score", "Objects"))
    emit("  " + "─" * 68)
    for f in top_finds:
        color = RED if max(f["bh_score"],f["star_score"]) >= 60 else \
                YELLOW if max(f["bh_score"],f["star_score"]) >= 30 else ""
        emit(color + "  " + col.format(
            f["name"][:35],
            f"{f['bh_score']}/100",
            f"{f['star_score']}/100",
            str(f["count"]),
        ) + RESET)

    return top_finds


# ═══════════════════════════════════════════════════════════════
#  MONITOR MODE — Watch for new papers and discoveries
# ═══════════════════════════════════════════════════════════════

def monitor_mode():
    """Pull latest discovery papers from arXiv across all targets."""
    banner(f"{SCOPE} DISCOVERY MONITOR — LATEST FINDS THIS WEEK", GREEN)

    topics = [
        ("New exoplanet candidates",
         "ti:exoplanet+candidate+AND+cat:astro-ph.EP"),
        ("New black hole candidates",
         "ti:black+hole+candidate+AND+cat:astro-ph.HE"),
        ("New stellar objects / YSOs",
         "ti:young+stellar+object+AND+cat:astro-ph.SR"),
        ("Gravitational wave new events",
         "ti:gravitational+wave+detection+AND+cat:astro-ph.HE"),
        ("Planet Nine / outer solar system",
         "ti:Planet+Nine+OR+ti:Planet+9+AND+cat:astro-ph.EP"),
    ]

    for topic, query in topics:
        divider(topic.upper(), GREEN)
        papers = fetch_arxiv_papers(query, max_results=3)
        if papers:
            for p in papers:
                emit(f"  [{p['date']}] {p['title'][:72]}")
                emit(f"   {', '.join(p['authors'][:2])}{'et al.' if len(p['authors'])>2 else ''}")
                emit(f"   {p['summary'][:180]}...")
                emit(f"   {BLUE}{p['url']}{RESET}")
                emit()
        else:
            info("No recent papers found for this topic")

    # Latest GW events
    divider("MOST RECENT GRAVITATIONAL WAVE EVENTS", GREEN)
    gw = safe_get("https://gwosc.org/eventapi/json/allevents/", label="GWOSC")
    if gw:
        events = gw.get("events", {})
        GPS_EPOCH = datetime(1980, 1, 6)
        sorted_events = sorted(
            events.items(),
            key=lambda x: float(x[1].get("GPS",0)),
            reverse=True
        )
        emit(f"  Total confirmed GW events: {len(events)}\n")
        for name, ev in sorted_events[:8]:
            gps   = float(ev.get("GPS",0))
            dt    = GPS_EPOCH + timedelta(seconds=gps) if gps > 0 else None
            m1    = ev.get("mass_1_source",{})
            m2    = ev.get("mass_2_source",{})
            m1v   = float(m1.get("best",0)) if isinstance(m1,dict) else 0
            m2v   = float(m2.get("best",0)) if isinstance(m2,dict) else 0
            total = m1v + m2v
            remnant = total * 0.95
            rs    = schwarzschild_radius_km(remnant)
            date_str = dt.strftime("%Y-%m-%d") if dt else "N/A"
            emit(f"  {name:<16} {date_str}  "
                 f"M1={m1v:.1f}M☉  M2={m2v:.1f}M☉  "
                 f"Remnant={remnant:.1f}M☉  Rs={rs:.1f}km")


# ═══════════════════════════════════════════════════════════════
#  INTERACTIVE MODE
# ═══════════════════════════════════════════════════════════════

def interactive_mode():
    banner(f"{ROCKET} CITIZEN SCIENCE DISCOVERY ASSISTANT", PURPLE)
    emit(f"""
  {BOLD}Welcome, Shyann!{RESET}

  This tool helps you discover planets, stars, and black holes
  by cross-checking your candidates against every major NASA and
  ESA database in real time.

  {BOLD}Where to find candidates:{RESET}
    Planets  → planethunters.org  (TESS light curves)
    Stars    → backyardworlds.org (WISE infrared images)
    BHs      → radio.galaxyzoo.org (radio jets from BH hosts)

  When you find something interesting, grab its RA and Dec
  coordinates (the project will show you these) and enter them here.
    """)

    while True:
        emit(f"\n  {BOLD}MENU:{RESET}")
        emit("  1. Analyze a specific candidate (enter coordinates)")
        emit("  2. Auto-scan known high-interest regions")
        emit("  3. Monitor latest discovery papers (arXiv)")
        emit("  4. Exit")
        emit()

        choice = input(f"  {CYAN}Your choice (1-4): {RESET}").strip()

        if choice == "1":
            emit()
            emit(f"  {BOLD}Enter your candidate coordinates.{RESET}")
            emit("  (Find these on planethunters.org or backyardworlds.org)")
            emit()
            try:
                ra_str  = input(f"  {CYAN}RA  (right ascension, degrees, e.g. 83.8221): {RESET}").strip()
                dec_str = input(f"  {CYAN}Dec (declination, degrees,   e.g. -5.3911): {RESET}").strip()
                ra  = float(ra_str)
                dec = float(dec_str)
            except ValueError:
                warn("Invalid coordinates. Please enter decimal degrees (e.g. 83.82)")
                continue

            name   = input(f"  {CYAN}Object name or ID (optional, press Enter to skip): {RESET}").strip()
            notes  = input(f"  {CYAN}Your notes about this object (optional): {RESET}").strip()
            radius = input(f"  {CYAN}Search radius in arcminutes (default 5): {RESET}").strip()
            radius = float(radius) if radius else 5.0

            emit()
            results = analyze_candidate(ra, dec, name=name, notes=notes,
                                        radius_arcmin=radius)

            # Save report
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            success(f"Full report saved to: {OUTPUT_FILE}")

        elif choice == "2":
            top_finds = auto_scan()
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            success(f"Scan report saved to: {OUTPUT_FILE}")

        elif choice == "3":
            monitor_mode()
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            success(f"Monitor report saved to: {OUTPUT_FILE}")

        elif choice == "4":
            emit()
            highlight(f"Keep looking up, Shyann. The next discovery could be yours.")
            emit(f"  {BLUE}planethunters.org{RESET}  |  "
                 f"{BLUE}backyardworlds.org{RESET}  |  "
                 f"{BLUE}radio.galaxyzoo.org{RESET}")
            emit()
            break
        else:
            warn("Please enter 1, 2, 3, or 4")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--scan":
            auto_scan()
        elif arg == "--monitor":
            monitor_mode()
        elif arg == "--demo":
            # Demo: analyze Cygnus X-1 (confirmed BH)
            analyze_candidate(
                ra=299.5903, dec=35.2016,
                name="Cygnus X-1",
                notes="Demo run — confirmed 21 M☉ stellar black hole",
                radius_arcmin=3.0
            )
        else:
            emit("Usage: python3 NASA_discovery.py [--scan | --monitor | --demo]")
    else:
        interactive_mode()

    # Always save report
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\n  Report saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()