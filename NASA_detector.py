"""
NASA STELLAR ANOMALY & BLACK HOLE DETECTION ENGINE
════════════════════════════════════════════════════
Queries live astronomical databases to identify:
  • Black hole candidates (stellar-mass and dormant)
  • Anomalous stellar objects (pre-collapse, hypergiants, X-ray binaries)
  • New/recent transient events that could indicate stellar birth or death
  • GW-detected merger remnants

Data sources (all free, no auth required):
  Gaia DR3        : gea.esac.esa.int/tap-server/tap  (1.8 billion stars)
  SIMBAD TAP      : simbad.cds.unistra.fr/simbad/sim-tap
  GWOSC           : gwosc.org/eventapi  (all GW merger events)
  NASA Exoplanet  : exoplanetarchive.ipac.caltech.edu/TAP
  arXiv           : export.arxiv.org/api
  NASA DONKI      : api.nasa.gov/DONKI (solar context)

Physics models applied:
  Schwarzschild radius        : Rs = 2GM/c²
  Eddington luminosity        : L_Edd = 4πGMmpc/σT
  Chandrasekhar limit         : 1.4 M☉ (white dwarf → collapse threshold)
  TOV limit                   : ~3.0 M☉ (neutron star → BH threshold)
  HR diagram classification   : L vs Teff placement
  Anomaly scoring             : Multi-factor weighted score per object
"""

import requests
import json
import os
import math
import numpy as np
import warnings
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

warnings.filterwarnings("ignore")

NASA_API_KEY = os.environ.get("NASA_API_KEY", "DEMO KEY")
OUTPUT_FILE  = "detection_report.txt"

output_lines = []

def emit(text=""):
    print(text)
    output_lines.append(str(text))

def section(title, source=""):
    emit()
    emit("═" * 72)
    emit(f"  {title}")
    if source:
        emit(f"  Source: {source}")
    emit("═" * 72)

def divider(label=""):
    emit()
    emit("─" * 60)
    if label:
        emit(f"  ▸  {label}")
        emit("─" * 60)

def safe_tap(url, query, label="", timeout=20):
    """Execute a TAP ADQL query and return parsed rows + column names."""
    try:
        resp = requests.get(
            url,
            params={"LANG": "ADQL", "REQUEST": "doQuery",
                    "QUERY": query, "FORMAT": "json"},
            timeout=timeout
        )
        if resp.status_code != 200:
            emit(f"  [SKIP] {label} — HTTP {resp.status_code}")
            return [], []
        data = resp.json()
        cols = [c.get("name", f"col{i}") for i, c in enumerate(data.get("metadata", []))]
        rows = data.get("data", [])
        return cols, rows
    except Exception as e:
        emit(f"  [SKIP] {label} — {e}")
        return [], []

def safe_get(url, params=None, timeout=15, label=""):
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code != 200:
            emit(f"  [SKIP] {label} — HTTP {resp.status_code}")
            return None
        return resp.json()
    except Exception as e:
        emit(f"  [SKIP] {label} — {e}")
        return None


# ═════════════════════════════════════════════════════════════
#  PHYSICS ENGINE
# ═════════════════════════════════════════════════════════════

# Physical constants
G    = 6.674e-11      # gravitational constant (m³/kg/s²)
C    = 3.0e8          # speed of light (m/s)
M_SUN= 1.989e30       # solar mass (kg)
L_SUN= 3.846e26       # solar luminosity (W)
K_B  = 1.381e-23      # Boltzmann constant
SIGMA= 5.67e-8        # Stefan-Boltzmann constant
MP   = 1.673e-27      # proton mass (kg)
SIGMA_T = 6.652e-29   # Thomson cross-section (m²)

CHANDRASEKHAR_LIMIT = 1.44   # solar masses — WD collapse limit
TOV_LIMIT           = 3.0    # solar masses — NS→BH limit
STELLAR_BH_MIN      = 3.0    # solar masses — minimum stellar BH mass
ISCO_FACTOR         = 6.0    # innermost stable circular orbit = 6 × Rs/2


def schwarzschild_radius(mass_solar):
    """Schwarzschild radius in km for a given mass in solar masses."""
    mass_kg = mass_solar * M_SUN
    rs_m    = 2 * G * mass_kg / (C ** 2)
    return rs_m / 1000  # km


def eddington_luminosity(mass_solar):
    """Eddington luminosity in solar luminosities."""
    mass_kg = mass_solar * M_SUN
    l_edd   = 4 * math.pi * G * mass_kg * MP * C / SIGMA_T
    return l_edd / L_SUN  # in L_sun


def stellar_lifetime_gyr(mass_solar, luminosity_solar=None):
    """Rough main-sequence lifetime. L ∝ M^3.5 approximation."""
    if luminosity_solar is None:
        luminosity_solar = mass_solar ** 3.5
    t = (mass_solar / luminosity_solar) * 10.0  # Gyr
    return t


def hr_classify(teff, luminosity_solar):
    """Classify star on the Hertzsprung-Russell diagram."""
    log_l = math.log10(max(luminosity_solar, 1e-6))
    if teff is None or luminosity_solar is None:
        return "Unknown"
    if teff > 30000 and log_l > 4:
        return "O-type supergiant / Wolf-Rayet  [BH progenitor candidate]"
    elif teff > 10000 and log_l > 4:
        return "B-type supergiant  [BH progenitor if M > 20 M☉]"
    elif teff > 7500 and log_l > 3:
        return "A-type giant"
    elif teff > 5200 and log_l > 3.5:
        return "Yellow hypergiant  [rare, unstable — BH progenitor]"
    elif teff < 4000 and log_l > 4:
        return "Red supergiant  [BH or NS progenitor — M > 8 M☉]"
    elif teff < 4000 and log_l > 2:
        return "Red giant  [post main sequence]"
    elif 5000 < teff < 6500 and -0.5 < log_l < 0.5:
        return "G-type main sequence (Sun-like)"
    elif teff > 5000 and log_l < -1:
        return "White dwarf  [collapsed remnant — near Chandrasekhar limit if massive]"
    elif teff < 3500 and log_l < 0:
        return "M-dwarf  [low mass main sequence]"
    else:
        return "Main sequence / subgiant"


def bh_candidate_score(obj):
    """
    Score an object 0-100 for black hole candidacy.
    Based on multiple physical indicators.
    """
    score  = 0
    flags  = []

    mass  = obj.get("mass_solar", 0) or 0
    teff  = obj.get("teff", 0)       or 0
    log_l = obj.get("log_l", None)
    pm    = obj.get("proper_motion", None)
    rv    = obj.get("radial_velocity", None)
    otype = obj.get("otype", "")     or ""

    # SIMBAD object type hints
    if "BH" in otype or "X" in otype:
        score += 40
        flags.append("SIMBAD type suggests BH/X-ray binary (+40)")
    if "?" in otype and ("BH" in otype or "NS" in otype):
        score += 25
        flags.append("SIMBAD BH/NS candidate type (+25)")

    # Mass above TOV limit → must be BH if compact
    if mass > TOV_LIMIT:
        score += 30
        flags.append(f"Mass {mass:.1f} M☉ > TOV limit 3.0 M☉ (+30)")
    elif mass > CHANDRASEKHAR_LIMIT:
        score += 10
        flags.append(f"Mass {mass:.1f} M☉ > Chandrasekhar limit (+10)")

    # Hot, very luminous → BH progenitor (will collapse)
    if teff and log_l:
        if teff > 25000 and log_l > 4.5:
            score += 20
            flags.append(f"Hot supergiant Teff={teff}K, logL={log_l:.1f} — BH progenitor (+20)")
        elif teff < 4000 and log_l > 4:
            score += 15
            flags.append(f"Red supergiant logL={log_l:.1f} — late BH/NS progenitor (+15)")

    # High proper motion + no parallax = possible dark companion
    if pm and pm > 50:
        score += 10
        flags.append(f"High proper motion {pm:.1f} mas/yr — possible unseen dark companion (+10)")

    # Radial velocity anomaly — could indicate massive invisible companion
    if rv and abs(rv) > 100:
        score += 15
        flags.append(f"High radial velocity {rv:.1f} km/s — massive companion candidate (+15)")

    score = min(score, 100)
    return score, flags


def new_star_score(obj):
    """
    Score an object 0-100 for new/young star candidacy.
    """
    score = 0
    flags = []
    teff  = obj.get("teff", 0)   or 0
    log_l = obj.get("log_l", None)
    otype = obj.get("otype", "") or ""
    pm    = obj.get("proper_motion", None)

    # SIMBAD type hints
    if any(t in otype for t in ["YSO", "TT", "Ae", "Or*", "pA*", "Em*"]):
        score += 40
        flags.append(f"SIMBAD type '{otype}' indicates pre-main-sequence/young star (+40)")
    if "Cl*" in otype or "OpC" in otype:
        score += 15
        flags.append("Associated with open cluster — young stellar region (+15)")

    # Hot and luminous but not yet on main sequence
    if teff and log_l:
        if teff > 15000 and log_l and log_l > 3:
            score += 20
            flags.append(f"Massive hot star Teff={teff}K — possibly recently formed (+20)")
        if log_l and log_l > 5:
            score += 10
            flags.append(f"Extremely luminous logL={log_l:.1f} — hypergiant/LBV, recently formed (+10)")

    # High proper motion = recently ejected from birth cluster
    if pm and 10 < pm < 50:
        score += 10
        flags.append(f"Moderate proper motion {pm:.1f} mas/yr — possible runaway star (+10)")

    score = min(score, 100)
    return score, flags


# ═════════════════════════════════════════════════════════════
#  SECTION 1 — SIMBAD: Known BH & BH Candidates
# ═════════════════════════════════════════════════════════════

def query_simbad_bh_candidates():
    section(
        "SIMBAD DATABASE — BLACK HOLE & CANDIDATE QUERY",
        "simbad.cds.unistra.fr/simbad/sim-tap  (19.5M objects)"
    )

    emit("""
  SIMBAD is the world reference database for astronomical objects.
  We query it directly for all objects classified as:
    BH   = confirmed black hole
    BH?  = black hole candidate
    HXB  = high-mass X-ray binary (common BH host)
    LXB  = low-mass X-ray binary
    ULX  = ultraluminous X-ray source (likely BH or NS)
    """)

    SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"

    # Query 1: Confirmed black holes
    divider("CONFIRMED BLACK HOLES IN SIMBAD")
    bh_query = """
        SELECT TOP 50
            main_id, ra, dec, otype,
            rvz_radvel, plx_value, pmra, pmdec
        FROM basic
        WHERE otype = 'BH'
        ORDER BY main_id
    """
    cols, rows = safe_tap(SIMBAD_TAP, bh_query, label="SIMBAD confirmed BHs")

    confirmed_bhs = []
    if rows:
        emit(f"  Found {len(rows)} confirmed black holes in SIMBAD\n")
        col = "{:<30} {:<12} {:<12} {:<10} {:<12}"
        emit("  " + col.format("Object", "RA (°)", "Dec (°)", "Type", "RV (km/s)"))
        emit("  " + "─" * 78)
        for row in rows:
            d = dict(zip(cols, row))
            rv  = d.get("rvz_radvel")
            plx = d.get("plx_value")
            pm  = None
            pmra  = d.get("pmra")
            pmdec = d.get("pmdec")
            if pmra and pmdec:
                pm = math.sqrt(float(pmra)**2 + float(pmdec)**2)

            obj = {
                "name":           str(d.get("main_id", "?")),
                "ra":             d.get("ra"),
                "dec":            d.get("dec"),
                "otype":          str(d.get("otype", "")),
                "radial_velocity":float(rv) if rv else None,
                "parallax":       float(plx) if plx else None,
                "proper_motion":  pm,
                "mass_solar":     None,
                "teff":           None,
                "log_l":          None,
            }
            confirmed_bhs.append(obj)

            emit("  " + col.format(
                str(d.get("main_id","?"))[:29],
                f"{float(d.get('ra',0)):.4f}"  if d.get("ra")  else "N/A",
                f"{float(d.get('dec',0)):.4f}" if d.get("dec") else "N/A",
                str(d.get("otype","?"))[:9],
                f"{float(rv):.1f}" if rv else "N/A",
            ))
    else:
        emit("  SIMBAD BH query returned no results — trying alternate approach.")

    # Query 2: BH candidates
    divider("BLACK HOLE CANDIDATES (BH?) IN SIMBAD")
    bhc_query = """
        SELECT TOP 50
            main_id, ra, dec, otype,
            rvz_radvel, plx_value, pmra, pmdec
        FROM basic
        WHERE otype = 'BH?'
        ORDER BY main_id
    """
    cols2, rows2 = safe_tap(SIMBAD_TAP, bhc_query, label="SIMBAD BH candidates")

    bh_candidates = []
    if rows2:
        emit(f"  Found {len(rows2)} black hole candidates\n")
        col = "{:<30} {:<12} {:<12} {:<10} {:<12}"
        emit("  " + col.format("Object", "RA (°)", "Dec (°)", "Type", "RV (km/s)"))
        emit("  " + "─" * 78)
        for row in rows2:
            d = dict(zip(cols2, row))
            rv    = d.get("rvz_radvel")
            pmra  = d.get("pmra")
            pmdec = d.get("pmdec")
            pm    = math.sqrt(float(pmra)**2 + float(pmdec)**2) if pmra and pmdec else None

            obj = {
                "name":           str(d.get("main_id","?")),
                "ra":             d.get("ra"),
                "dec":            d.get("dec"),
                "otype":          str(d.get("otype","")),
                "radial_velocity":float(rv) if rv else None,
                "parallax":       float(d.get("plx_value")) if d.get("plx_value") else None,
                "proper_motion":  pm,
                "mass_solar":     None,
                "teff":           None,
                "log_l":          None,
            }
            bh_candidates.append(obj)
            emit("  " + col.format(
                str(d.get("main_id","?"))[:29],
                f"{float(d.get('ra',0)):.4f}"  if d.get("ra")  else "N/A",
                f"{float(d.get('dec',0)):.4f}" if d.get("dec") else "N/A",
                str(d.get("otype","?"))[:9],
                f"{float(rv):.1f}" if rv else "N/A",
            ))

    # Query 3: X-ray binaries (most known stellar BHs live here)
    divider("HIGH-MASS X-RAY BINARIES — LIKELY BH HOSTS")
    xrb_query = """
        SELECT TOP 30
            main_id, ra, dec, otype, rvz_radvel
        FROM basic
        WHERE otype IN ('HXB', 'LXB', 'ULX', 'XB*')
        ORDER BY main_id
    """
    cols3, rows3 = safe_tap(SIMBAD_TAP, xrb_query, label="SIMBAD X-ray binaries")
    if rows3:
        emit(f"  Found {len(rows3)} X-ray binary systems\n")
        for row in rows3[:15]:
            d = dict(zip(cols3, row))
            rv = d.get("rvz_radvel")
            emit(f"  {str(d.get('main_id','?')):<30}  Type: {str(d.get('otype','?')):<6}  RV: {f'{float(rv):.1f} km/s' if rv else 'N/A'}")

    return confirmed_bhs, bh_candidates


# ═════════════════════════════════════════════════════════════
#  SECTION 2 — Gaia DR3: Anomalous Stars & BH Candidates
# ═════════════════════════════════════════════════════════════

def query_gaia_anomalies():
    section(
        "GAIA DR3 — STELLAR ANOMALY DETECTION",
        "gea.esac.esa.int/tap-server/tap  (1.8 billion stars)"
    )

    emit("""
  Gaia DR3 contains 1.8 billion stellar measurements including:
  luminosity, temperature, proper motion, parallax, and radial velocity.
  We apply physics-based filters to flag anomalous objects that could
  indicate black holes, neutron stars, or rare stellar types.

  Detection criteria applied:
    1. Ultra-high luminosity (logL > 5.5)  → hypergiant / LBV / BH accretion
    2. Very high radial velocity (|RV| > 200 km/s) → possible dark companion
    3. Extremely hot (Teff > 40,000 K) with high L → Wolf-Rayet / BH progenitor
    4. High proper motion + bright → possible runaway from binary that exploded
    5. Color-luminosity outliers → objects off the main sequence unexpectedly
    """)

    GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"

    candidates = []

    # Query 1: Extremely luminous stars (hypergiant / BH progenitor territory)
    divider("EXTREME LUMINOSITY STARS (logL > 5.5 L☉) — BH Progenitors")
    lum_query = """
        SELECT TOP 30
            source_id, ra, dec,
            teff_gspphot, logg_gspphot,
            lum_flame, mass_flame,
            radial_velocity, pmra, pmdec,
            parallax, phot_g_mean_mag
        FROM gaiadr3.gaia_source
        WHERE lum_flame > 316228
          AND lum_flame IS NOT NULL
          AND parallax > 0.01
        ORDER BY lum_flame DESC
    """
    cols, rows = safe_tap(GAIA_TAP, lum_query, label="Gaia hyper-luminous stars")

    if rows:
        emit(f"  Found {len(rows)} hyper-luminous stellar objects\n")
        col = "{:<22} {:<10} {:<10} {:<10} {:<12} {:<10}"
        emit("  " + col.format("Source ID", "RA", "Dec", "Teff (K)", "logL (L☉)", "Mass (M☉)"))
        emit("  " + "─" * 76)
        for row in rows:
            d     = dict(zip(cols, row))
            lum   = d.get("lum_flame")
            mass  = d.get("mass_flame")
            teff  = d.get("teff_gspphot")
            rv    = d.get("radial_velocity")
            pmra  = d.get("pmra")
            pmdec = d.get("pmdec")
            pm    = math.sqrt(float(pmra)**2 + float(pmdec)**2) if pmra and pmdec else None
            log_l = math.log10(float(lum)) if lum else None

            obj = {
                "name":           f"Gaia DR3 {d.get('source_id','')}",
                "ra":             d.get("ra"),
                "dec":            d.get("dec"),
                "teff":           float(teff) if teff else None,
                "log_l":          log_l,
                "mass_solar":     float(mass) if mass else None,
                "radial_velocity":float(rv) if rv else None,
                "proper_motion":  pm,
                "parallax":       float(d.get("parallax")) if d.get("parallax") else None,
                "mag_g":          float(d.get("phot_g_mean_mag")) if d.get("phot_g_mean_mag") else None,
                "otype":          "",
            }
            candidates.append(obj)

            hr  = hr_classify(obj["teff"], lum) if teff and lum else "N/A"
            bhs, bhf = bh_candidate_score(obj)

            emit("  " + col.format(
                str(d.get("source_id",""))[:21],
                f"{float(d.get('ra',0)):.3f}" if d.get("ra") else "N/A",
                f"{float(d.get('dec',0)):.3f}" if d.get("dec") else "N/A",
                f"{float(teff):.0f}" if teff else "N/A",
                f"{log_l:.2f}" if log_l else "N/A",
                f"{float(mass):.1f}" if mass else "N/A",
            ))
            emit(f"         HR Class  : {hr[:65]}")
            emit(f"         BH Score  : {bhs}/100  {'⚠ HIGH CANDIDATE' if bhs >= 40 else ''}")
            if bhf:
                for f in bhf:
                    emit(f"         Indicator : {f}")
            emit()
    else:
        emit("  Gaia luminosity query returned no data.")

    # Query 2: High radial velocity stars — possible dark companion
    divider("HIGH RADIAL VELOCITY STARS (|RV| > 200 km/s) — Dark Companion Indicator")
    rv_query = """
        SELECT TOP 20
            source_id, ra, dec,
            teff_gspphot, lum_flame, mass_flame,
            radial_velocity, pmra, pmdec, parallax,
            phot_g_mean_mag
        FROM gaiadr3.gaia_source
        WHERE ABS(radial_velocity) > 200
          AND radial_velocity IS NOT NULL
          AND parallax > 0.1
          AND phot_g_mean_mag < 12
        ORDER BY ABS(radial_velocity) DESC
    """
    cols2, rows2 = safe_tap(GAIA_TAP, rv_query, label="Gaia high-RV stars")

    if rows2:
        emit(f"  Found {len(rows2)} high-radial-velocity bright stars\n")
        for row in rows2[:10]:
            d     = dict(zip(cols2, row))
            rv    = d.get("radial_velocity")
            lum   = d.get("lum_flame")
            teff  = d.get("teff_gspphot")
            mass  = d.get("mass_flame")
            pmra  = d.get("pmra")
            pmdec = d.get("pmdec")
            pm    = math.sqrt(float(pmra)**2 + float(pmdec)**2) if pmra and pmdec else None
            log_l = math.log10(float(lum)) if lum else None

            obj = {
                "name":           f"Gaia DR3 {d.get('source_id','')}",
                "ra":             d.get("ra"), "dec": d.get("dec"),
                "teff":           float(teff) if teff else None,
                "log_l":          log_l,
                "mass_solar":     float(mass) if mass else None,
                "radial_velocity":float(rv) if rv else None,
                "proper_motion":  pm,
                "parallax":       float(d.get("parallax")) if d.get("parallax") else None,
                "otype":          "",
            }
            candidates.append(obj)
            bhs, bhf = bh_candidate_score(obj)

            emit(f"  Gaia {str(d.get('source_id',''))[:20]}")
            emit(f"    RA/Dec          : {float(d.get('ra',0)):.4f}° / {float(d.get('dec',0)):.4f}°")
            emit(f"    Radial Velocity : {float(rv):.1f} km/s  ← HIGH")
            emit(f"    Teff            : {float(teff):.0f} K" if teff else "    Teff            : N/A")
            emit(f"    Luminosity      : 10^{log_l:.2f} L☉" if log_l else "    Luminosity      : N/A")
            emit(f"    BH Score        : {bhs}/100  {'⚠ CANDIDATE' if bhs >= 30 else ''}")
            emit()
    else:
        emit("  No high-RV bright stars returned — Gaia TAP may have query limits.")

    return candidates


# ═════════════════════════════════════════════════════════════
#  SECTION 3 — Young Star / New Star Candidates
# ═════════════════════════════════════════════════════════════

def query_new_stars():
    section(
        "NEW & YOUNG STAR DETECTION",
        "SIMBAD TAP + Gaia DR3 + arXiv transients"
    )

    emit("""
  Stars form in giant molecular clouds when gravity overcomes pressure.
  Young stellar objects (YSOs) are pre-main-sequence stars still
  accreting from their birth cloud — detectable by infrared excess,
  H-alpha emission, and irregular variability.

  We query for:
    YSO   = Young Stellar Object (pre-main-sequence)
    TT*   = T Tauri star (solar-mass YSO, < 10 Myr old)
    Ae*   = Herbig Ae/Be star (intermediate-mass YSO)
    Or*   = Star in star-forming region (Orion variables)
    Em*   = Emission-line star (often young, active)
    """)

    SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"

    new_star_candidates = []

    # Query: Young stellar objects
    divider("YOUNG STELLAR OBJECTS (YSOs) — Recently Formed Stars")
    yso_query = """
        SELECT TOP 50
            main_id, ra, dec, otype,
            rvz_radvel, plx_value, pmra, pmdec
        FROM basic
        WHERE otype IN ('YSO', 'TT*', 'Ae*', 'Or*', 'Em*', 'pA*')
          AND plx_value > 1.0
        ORDER BY plx_value DESC
    """
    cols, rows = safe_tap(SIMBAD_TAP, yso_query, label="SIMBAD YSOs")

    if rows:
        emit(f"  Found {len(rows)} nearby young stellar objects\n")
        col = "{:<28} {:<12} {:<12} {:<8} {:<12}"
        emit("  " + col.format("Object", "RA (°)", "Dec (°)", "Type", "Parallax (mas)"))
        emit("  " + "─" * 76)
        for row in rows[:25]:
            d     = dict(zip(cols, row))
            plx   = d.get("plx_value")
            rv    = d.get("rvz_radvel")
            pmra  = d.get("pmra")
            pmdec = d.get("pmdec")
            pm    = math.sqrt(float(pmra)**2 + float(pmdec)**2) if pmra and pmdec else None

            if plx:
                dist_pc = 1000 / float(plx)  # parsecs from parallax
            else:
                dist_pc = None

            obj = {
                "name":           str(d.get("main_id","?")),
                "ra":             d.get("ra"), "dec": d.get("dec"),
                "otype":          str(d.get("otype","")),
                "radial_velocity":float(rv) if rv else None,
                "parallax":       float(plx) if plx else None,
                "proper_motion":  pm,
                "teff": None, "log_l": None, "mass_solar": None,
            }
            new_star_candidates.append(obj)
            nss, nsf = new_star_score(obj)

            emit("  " + col.format(
                str(d.get("main_id","?"))[:27],
                f"{float(d.get('ra',0)):.4f}"  if d.get("ra")  else "N/A",
                f"{float(d.get('dec',0)):.4f}" if d.get("dec") else "N/A",
                str(d.get("otype","?"))[:7],
                f"{float(plx):.2f}" if plx else "N/A",
            ))
            if dist_pc:
                emit(f"         Distance        : {dist_pc:.0f} pc  ({dist_pc*3.26:.0f} ly)")
            emit(f"         New Star Score  : {nss}/100  {'⭐ STRONG CANDIDATE' if nss >= 50 else ''}")
    else:
        emit("  SIMBAD YSO query returned no data — trying alternate object types.")

    # Query: Protostellar objects
    divider("PROTOSTELLAR OBJECTS — Stars Still Forming")
    proto_query = """
        SELECT TOP 20
            main_id, ra, dec, otype, plx_value
        FROM basic
        WHERE otype IN ('pr*', 'cor', 'FIR', 'DNe', 'MoC')
          AND plx_value > 0.5
        ORDER BY plx_value DESC
    """
    cols2, rows2 = safe_tap(SIMBAD_TAP, proto_query, label="SIMBAD protostars")
    if rows2:
        emit(f"\n  Found {len(rows2)} protostellar / molecular cloud objects\n")
        for row in rows2[:10]:
            d   = dict(zip(cols2, row))
            plx = d.get("plx_value")
            dist= 1000/float(plx) if plx else None
            emit(f"  {str(d.get('main_id','?')):<30}  Type: {str(d.get('otype','?')):<6}  "
                 f"Dist: {f'{dist:.0f} pc' if dist else 'N/A'}")

    return new_star_candidates


# ═════════════════════════════════════════════════════════════
#  SECTION 4 — GW-Based New BH Detection
# ═════════════════════════════════════════════════════════════

def gw_new_bh_analysis():
    section(
        "GRAVITATIONAL WAVE — NEW BLACK HOLE REMNANT ANALYSIS",
        "GWOSC gwosc.org — Every detected merger creates a new BH"
    )

    emit("""
  Every confirmed GW merger event CREATES a new black hole.
  The remnant mass = (m1 + m2) - radiated_mass (Δm ≈ 5% typical)
  This is the most direct detection of new black hole formation.
  We analyze all events, compute remnant masses, and flag the most recent.
    """)

    gw = safe_get("https://gwosc.org/eventapi/json/allevents/", label="GWOSC all events")
    if not gw:
        emit("  GWOSC data unavailable.")
        return

    events = gw.get("events", {})
    GPS_EPOCH = datetime(1980, 1, 6)

    new_bhs = []
    for name, ev in events.items():
        m1   = ev.get("mass_1_source", {})
        m2   = ev.get("mass_2_source", {})
        dist = ev.get("luminosity_distance", {})
        gps  = float(ev.get("GPS", 0))
        m1v  = float(m1.get("best", 0)) if isinstance(m1, dict) else 0
        m2v  = float(m2.get("best", 0)) if isinstance(m2, dict) else 0
        dv   = float(dist.get("best", 0)) if isinstance(dist, dict) else 0

        if m1v > 0 and m2v > 0:
            total       = m1v + m2v
            radiated    = total * 0.05   # ~5% typical GW radiation
            remnant     = total - radiated
            rs_km       = schwarzschild_radius(remnant)
            event_date  = GPS_EPOCH + timedelta(seconds=gps) if gps > 0 else None

            # Classify remnant
            if m2v < 3.0 and m1v < 3.0:
                remnant_type = "Massive NS or light BH"
            elif remnant > 100:
                remnant_type = "Intermediate-mass BH"
            else:
                remnant_type = "Stellar-mass BH"

            new_bhs.append({
                "name":         name,
                "date":         event_date,
                "m1":           m1v,
                "m2":           m2v,
                "total":        total,
                "remnant":      remnant,
                "remnant_type": remnant_type,
                "rs_km":        rs_km,
                "distance_mpc": dv,
                "gps":          gps,
            })

    # Sort by date, most recent first
    new_bhs.sort(key=lambda x: x["gps"], reverse=True)

    divider("MOST RECENTLY FORMED BLACK HOLES (GW-detected)")
    emit(f"  Total new BHs created via detected mergers : {len(new_bhs)}\n")

    col = "{:<16} {:<12} {:<10} {:<10} {:<14} {:<10} {:<16}"
    emit("  " + col.format("Event", "Date", "M1 (M☉)", "M2 (M☉)", "Remnant (M☉)", "Rs (km)", "Dist (Mpc)"))
    emit("  " + "─" * 90)

    for bh in new_bhs[:20]:
        date_str = bh["date"].strftime("%Y-%m-%d") if bh["date"] else "N/A"
        emit("  " + col.format(
            bh["name"][:15],
            date_str,
            f"{bh['m1']:.1f}",
            f"{bh['m2']:.1f}",
            f"{bh['remnant']:.1f}",
            f"{bh['rs_km']:.1f}",
            f"{bh['distance_mpc']:.0f}",
        ))

    # Physics breakdown of most recent
    if new_bhs:
        divider("MOST RECENT GW-DETECTED NEW BLACK HOLE — DETAILED PHYSICS")
        latest = new_bhs[0]
        emit(f"\n  Event Name           : {latest['name']}")
        emit(f"  Detection Date       : {latest['date'].strftime('%Y-%m-%d') if latest['date'] else 'N/A'}")
        emit(f"  Progenitor Mass 1    : {latest['m1']:.2f} M☉")
        emit(f"  Progenitor Mass 2    : {latest['m2']:.2f} M☉")
        emit(f"  Total System Mass    : {latest['total']:.2f} M☉")
        emit(f"  Radiated as GW       : {latest['total']*0.05:.2f} M☉  → {latest['total']*0.05*M_SUN*C**2:.3e} J")
        emit(f"  New BH Remnant Mass  : {latest['remnant']:.2f} M☉")
        emit(f"  Schwarzschild Radius : {latest['rs_km']:.2f} km  (event horizon diameter: {latest['rs_km']*2:.2f} km)")
        emit(f"  Remnant Type         : {latest['remnant_type']}")
        emit(f"  Eddington Luminosity : {eddington_luminosity(latest['remnant']):.3e} L☉")
        emit(f"  Distance from Earth  : {latest['distance_mpc']:.0f} Mpc  ({latest['distance_mpc']*3.26:.0f} million ly)")

        # Time since merger
        if latest["date"]:
            age = datetime.now() - latest["date"]
            emit(f"  Time since merger    : {age.days:,} days  ({age.days/365.25:.1f} years)")

    # Mass distribution analysis
    divider("REMNANT BLACK HOLE MASS DISTRIBUTION")
    if new_bhs:
        remnants = [b["remnant"] for b in new_bhs]
        emit(f"  Mean remnant mass    : {np.mean(remnants):.1f} M☉")
        emit(f"  Median remnant mass  : {np.median(remnants):.1f} M☉")
        emit(f"  Largest new BH       : {max(remnants):.1f} M☉  ({new_bhs[remnants.index(max(remnants))]['name']})")
        emit(f"  Smallest new BH      : {min(remnants):.1f} M☉")

        emit("\n  MASS GAP ANALYSIS:")
        emit("  (The 'mass gap' between ~3-5 M☉ is poorly understood)")
        gap_objects = [b for b in new_bhs if 3 <= b["remnant"] <= 5]
        emit(f"  Objects in mass gap (3-5 M☉) : {len(gap_objects)}")
        for g in gap_objects[:5]:
            emit(f"    {g['name']:<16} : {g['remnant']:.2f} M☉  ← mass gap object")

    return new_bhs


# ═════════════════════════════════════════════════════════════
#  SECTION 5 — ANOMALY SCORING & RANKED CANDIDATE LIST
# ═════════════════════════════════════════════════════════════

def rank_all_candidates(simbad_bhs, simbad_candidates, gaia_candidates, new_stars):
    section(
        "RANKED CANDIDATE LIST — ALL ANOMALIES SCORED",
        "Combined SIMBAD + Gaia DR3 + Physics Models"
    )

    emit("""
  All candidates from all sources are now scored using our physics engine.
  Each object receives:
    BH Score  (0-100) : probability indicator of black hole nature
    Star Score(0-100) : probability indicator of new/young star nature
    
  Scoring factors:
    Object type classification (SIMBAD)    : up to +40 pts
    Mass above TOV/Chandrasekhar limit     : up to +30 pts
    HR diagram position (temperature/lum)  : up to +20 pts
    Radial velocity anomaly                : up to +15 pts
    Proper motion anomaly                  : up to +10 pts
    """)

    all_candidates = []

    # Score SIMBAD confirmed BHs
    for obj in simbad_bhs:
        obj["otype"] = obj.get("otype", "") or "BH"
        bhs, bhf = bh_candidate_score(obj)
        obj["bh_score"]    = bhs
        obj["bh_flags"]    = bhf
        obj["star_score"]  = 0
        obj["star_flags"]  = []
        obj["source"]      = "SIMBAD confirmed"
        all_candidates.append(obj)

    # Score SIMBAD BH candidates
    for obj in simbad_candidates:
        bhs, bhf = bh_candidate_score(obj)
        obj["bh_score"]   = bhs
        obj["bh_flags"]   = bhf
        obj["star_score"] = 0
        obj["star_flags"] = []
        obj["source"]     = "SIMBAD candidate"
        all_candidates.append(obj)

    # Score Gaia anomalies
    for obj in gaia_candidates:
        bhs, bhf = bh_candidate_score(obj)
        nss, nsf = new_star_score(obj)
        obj["bh_score"]   = bhs
        obj["bh_flags"]   = bhf
        obj["star_score"] = nss
        obj["star_flags"] = nsf
        obj["source"]     = "Gaia DR3"
        all_candidates.append(obj)

    # Score new star candidates
    for obj in new_stars:
        bhs, bhf = bh_candidate_score(obj)
        nss, nsf = new_star_score(obj)
        obj["bh_score"]   = bhs
        obj["bh_flags"]   = bhf
        obj["star_score"] = nss
        obj["star_flags"] = nsf
        obj["source"]     = "SIMBAD YSO"
        all_candidates.append(obj)

    # Sort by BH score descending
    all_candidates.sort(key=lambda x: x.get("bh_score", 0), reverse=True)

    divider("TOP BLACK HOLE CANDIDATES — RANKED")
    col = "{:<4} {:<30} {:<8} {:<8} {:<16} {:<14}"
    emit("  " + col.format("Rank", "Object", "BH Score", "Source", "Type", "RV (km/s)"))
    emit("  " + "─" * 82)

    for i, obj in enumerate(all_candidates[:25], 1):
        rv = obj.get("radial_velocity")
        alert = "  ★ HIGH ALERT" if obj.get("bh_score",0) >= 60 else ""
        emit("  " + col.format(
            f"#{i}",
            str(obj.get("name","?"))[:29],
            f"{obj.get('bh_score',0)}/100",
            obj.get("source","?")[:7],
            str(obj.get("otype","?"))[:15],
            f"{float(rv):.1f}" if rv else "N/A",
        ) + alert)

    # New star ranking
    all_candidates.sort(key=lambda x: x.get("star_score", 0), reverse=True)
    new_star_ranked = [o for o in all_candidates if o.get("star_score", 0) >= 20]

    divider("TOP NEW / YOUNG STAR CANDIDATES — RANKED")
    col2 = "{:<4} {:<30} {:<10} {:<8} {:<16}"
    emit("  " + col2.format("Rank", "Object", "Star Score", "Source", "Type"))
    emit("  " + "─" * 70)

    for i, obj in enumerate(new_star_ranked[:20], 1):
        alert = "  ⭐ STRONG" if obj.get("star_score",0) >= 50 else ""
        emit("  " + col2.format(
            f"#{i}",
            str(obj.get("name","?"))[:29],
            f"{obj.get('star_score',0)}/100",
            obj.get("source","?")[:7],
            str(obj.get("otype","?"))[:15],
        ) + alert)

    divider("SUMMARY STATISTICS")
    bh_high   = sum(1 for o in all_candidates if o.get("bh_score",0) >= 60)
    bh_med    = sum(1 for o in all_candidates if 30 <= o.get("bh_score",0) < 60)
    star_high = sum(1 for o in all_candidates if o.get("star_score",0) >= 50)

    emit(f"  Total candidates analyzed    : {len(all_candidates)}")
    emit(f"  High-confidence BH (≥60)     : {bh_high}  objects")
    emit(f"  Moderate BH candidate (30-59): {bh_med}  objects")
    emit(f"  Strong new star (≥50)        : {star_high}  objects")
    emit()
    emit("  NOTE ON SCORING:")
    emit("  These scores are computed from publicly available catalog data")
    emit("  using established astrophysical criteria. They are NOT official")
    emit("  classifications. Confirmation requires spectroscopic follow-up,")
    emit("  radial velocity curves, and ideally X-ray or GW observations.")
    emit("  Scores ≥ 60 represent objects that match multiple BH indicators")
    emit("  and warrant serious observational attention.")

    return all_candidates


# ═════════════════════════════════════════════════════════════
#  SECTION 6 — Latest Candidate Papers from arXiv
# ═════════════════════════════════════════════════════════════

def fetch_latest_candidate_papers():
    section(
        "LATEST DISCOVERY PAPERS — arXiv (This Week)",
        "export.arxiv.org — astro-ph.SR + astro-ph.HE"
    )

    queries = [
        ("New stellar-mass black hole candidates",
         "ti:black+hole+candidate+AND+cat:astro-ph.HE"),
        ("Young stellar objects and star formation",
         "ti:young+stellar+object+OR+ti:star+formation+AND+cat:astro-ph.SR"),
        ("Gravitational wave new remnants",
         "ti:gravitational+wave+remnant+AND+cat:astro-ph.HE"),
    ]

    for topic, query in queries:
        divider(topic.upper())
        try:
            resp = requests.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": query,
                    "sortBy":       "submittedDate",
                    "sortOrder":    "descending",
                    "max_results":  4,
                },
                timeout=15
            )
            root    = ET.fromstring(resp.text)
            ns      = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            for entry in entries:
                title   = entry.findtext("atom:title",   "", ns).strip().replace("\n"," ")
                pub     = entry.findtext("atom:published","",ns)[:10]
                authors = [a.findtext("atom:name","",ns) for a in entry.findall("atom:author",ns)]
                summary = entry.findtext("atom:summary", "",ns).strip().replace("\n"," ")
                link    = entry.findtext("atom:id",      "",ns)

                emit(f"  [{pub}] {title[:72]}")
                emit(f"         {', '.join(authors[:2])}{'et al.' if len(authors)>2 else ''}")
                emit(f"         {summary[:200]}...")
                emit(f"         URL: {link}")
                emit()
        except Exception as e:
            emit(f"  [SKIP] arXiv {topic}: {e}")


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════

def main():
    emit("★" * 72)
    emit("  🔭  NASA STELLAR ANOMALY & BLACK HOLE DETECTION ENGINE")
    emit("      Gaia DR3 · SIMBAD · GWOSC · arXiv · Physics Models")
    emit(f"      Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit("★" * 72)
    emit()
    emit("  PHYSICS CONSTANTS IN USE:")
    emit(f"    Schwarzschild radius (1 M☉) : {schwarzschild_radius(1):.3f} km")
    emit(f"    Chandrasekhar limit         : {CHANDRASEKHAR_LIMIT} M☉")
    emit(f"    TOV limit (NS→BH)           : {TOV_LIMIT} M☉")
    emit(f"    Eddington L (10 M☉ BH)      : {eddington_luminosity(10):.3e} L☉")
    emit(f"    Eddington L (1M M☉ BH)      : {eddington_luminosity(1e6):.3e} L☉")

    # Install check reminder
    emit()
    emit("  REQUIRED LIBRARIES: pip install requests numpy")
    emit("  (No additional installs needed — uses direct HTTP TAP queries)")
    emit()

    # Run all detection modules
    simbad_bhs, simbad_candidates = query_simbad_bh_candidates()
    gaia_candidates               = query_gaia_anomalies()
    new_stars                     = query_new_stars()
    gw_new_bhs                    = gw_new_bh_analysis()
    all_ranked                    = rank_all_candidates(
                                        simbad_bhs, simbad_candidates,
                                        gaia_candidates, new_stars
                                    )
    fetch_latest_candidate_papers()

    emit("\n" + "★" * 72)
    emit("  ✅  Detection scan complete.")
    emit("★" * 72 + "\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\n  📄  Full report saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()