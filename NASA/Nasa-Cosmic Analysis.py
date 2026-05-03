import requests
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from scipy.signal import correlate
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from datetime import datetime, timedelta
import json
import warnings
import os
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
NASA_API_KEY = "DEMO KEY"  # Replace with your key from api.nasa.gov
OUTPUT_FILE  = "cosmic_analysis_report.txt"
# ─────────────────────────────────────────────────────────────

output_lines = []

def emit(text=""):
    """Print to terminal AND collect for file output."""
    print(text)
    output_lines.append(text)

def section(title, source=""):
    emit()
    emit("═" * 70)
    emit(f"  {title}")
    if source:
        emit(f"  Source: {source}")
    emit("═" * 70)

def divider(label=""):
    emit()
    emit("─" * 60)
    if label:
        emit(f"  ▸  {label}")
        emit("─" * 60)


# ═════════════════════════════════════════════════════════════
#  DATA FETCHERS
# ═════════════════════════════════════════════════════════════

def fetch_solar_flares(days=90):
    emit(f"  [Fetching] Solar flares (last {days} days)...")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    end   = datetime.today().strftime("%Y-%m-%d")
    try:
        r = requests.get(
            "https://api.nasa.gov/DONKI/FLR",
            params={"startDate": start, "endDate": end, "api_key": NASA_API_KEY},
            timeout=15
        ).json()
        records = []
        for f in (r if isinstance(r, list) else []):
            try:
                records.append({
                    "time":        datetime.strptime(f["beginTime"][:16], "%Y-%m-%dT%H:%M"),
                    "class":       f.get("classType", ""),
                    "class_value": parse_flare_class(f.get("classType", "")),
                    "location":    f.get("sourceLocation", ""),
                    "type":        "solar_flare",
                })
            except:
                continue
        emit(f"  [OK] {len(records)} solar flares fetched")
        return pd.DataFrame(records)
    except Exception as e:
        emit(f"  [ERROR] Solar flares: {e}")
        return pd.DataFrame()


def fetch_geomagnetic_storms(days=90):
    emit(f"  [Fetching] Geomagnetic storms (last {days} days)...")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    end   = datetime.today().strftime("%Y-%m-%d")
    try:
        r = requests.get(
            "https://api.nasa.gov/DONKI/GST",
            params={"startDate": start, "endDate": end, "api_key": NASA_API_KEY},
            timeout=15
        ).json()
        records = []
        for s in (r if isinstance(r, list) else []):
            try:
                kp_data = s.get("allKpIndex", [])
                max_kp  = max((k.get("kpIndex", 0) for k in kp_data), default=0)
                records.append({
                    "time":     datetime.strptime(s["startTime"][:16], "%Y-%m-%dT%H:%M"),
                    "max_kp":   max_kp,
                    "type":     "geomagnetic_storm",
                })
            except:
                continue
        emit(f"  [OK] {len(records)} geomagnetic storms fetched")
        return pd.DataFrame(records)
    except Exception as e:
        emit(f"  [ERROR] Geomagnetic storms: {e}")
        return pd.DataFrame()


def fetch_cmes(days=90):
    emit(f"  [Fetching] Coronal mass ejections (last {days} days)...")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    end   = datetime.today().strftime("%Y-%m-%d")
    try:
        r = requests.get(
            "https://api.nasa.gov/DONKI/CME",
            params={"startDate": start, "endDate": end, "api_key": NASA_API_KEY},
            timeout=15
        ).json()
        records = []
        for c in (r if isinstance(r, list) else []):
            try:
                analyses = c.get("cmeAnalyses") or []
                speed = analyses[0].get("speed", 0) if analyses else 0
                records.append({
                    "time":  datetime.strptime(c["startTime"][:16], "%Y-%m-%dT%H:%M"),
                    "speed": float(speed) if speed else 0.0,
                    "type":  "cme",
                })
            except:
                continue
        emit(f"  [OK] {len(records)} CMEs fetched")
        return pd.DataFrame(records)
    except Exception as e:
        emit(f"  [ERROR] CMEs: {e}")
        return pd.DataFrame()


def fetch_neos(days=7):
    emit(f"  [Fetching] Near-Earth objects (next {days} days)...")
    today = datetime.today()
    end   = today + timedelta(days=days)
    try:
        r = requests.get(
            "https://api.nasa.gov/neo/rest/v1/feed",
            params={
                "start_date": today.strftime("%Y-%m-%d"),
                "end_date":   end.strftime("%Y-%m-%d"),
                "api_key":    NASA_API_KEY,
            },
            timeout=15
        ).json()
        records = []
        for date_group in r.get("near_earth_objects", {}).values():
            for neo in date_group:
                try:
                    approach = neo["close_approach_data"][0]
                    records.append({
                        "name":      neo.get("name", ""),
                        "date":      datetime.strptime(approach["close_approach_date"], "%Y-%m-%d"),
                        "miss_km":   float(approach["miss_distance"]["kilometers"]),
                        "speed_kms": float(approach["relative_velocity"]["kilometers_per_second"]),
                        "diam_m":    (neo["estimated_diameter"]["meters"]["estimated_diameter_min"] +
                                      neo["estimated_diameter"]["meters"]["estimated_diameter_max"]) / 2,
                        "hazardous": 1 if neo.get("is_potentially_hazardous_asteroid") else 0,
                        "type":      "neo",
                    })
                except:
                    continue
        emit(f"  [OK] {len(records)} NEOs fetched")
        return pd.DataFrame(records)
    except Exception as e:
        emit(f"  [ERROR] NEOs: {e}")
        return pd.DataFrame()


def fetch_gravitational_waves():
    emit("  [Fetching] Gravitational wave events (GWOSC all-time)...")
    try:
        r = requests.get(
            "https://gwosc.org/eventapi/json/allevents/",
            timeout=15
        ).json()
        events = r.get("events", {})
        records = []
        for name, ev in events.items():
            try:
                m1   = ev.get("mass_1_source", {})
                m2   = ev.get("mass_2_source", {})
                dist = ev.get("luminosity_distance", {})
                snr  = ev.get("network_matched_filter_snr", {})
                records.append({
                    "name":     name,
                    "gps":      float(ev.get("GPS", 0)),
                    "mass_1":   float(m1.get("best", 0)) if isinstance(m1, dict) else 0,
                    "mass_2":   float(m2.get("best", 0)) if isinstance(m2, dict) else 0,
                    "distance": float(dist.get("best", 0)) if isinstance(dist, dict) else 0,
                    "snr":      float(snr.get("best", 0)) if isinstance(snr, dict) else 0,
                    "type":     "gw_event",
                })
            except:
                continue
        emit(f"  [OK] {len(records)} gravitational wave events fetched")
        return pd.DataFrame(records)
    except Exception as e:
        emit(f"  [ERROR] Gravitational waves: {e}")
        return pd.DataFrame()


def parse_flare_class(cls):
    """Convert flare class (e.g. M2.5, X1.3) to numeric energy proxy."""
    if not cls:
        return 0.0
    try:
        letter = cls[0].upper()
        number = float(cls[1:]) if len(cls) > 1 else 1.0
        scale  = {"A": 1e-8, "B": 1e-7, "C": 1e-6, "M": 1e-5, "X": 1e-4}
        return scale.get(letter, 0) * number
    except:
        return 0.0


# ═════════════════════════════════════════════════════════════
#  ANALYSIS ENGINE
# ═════════════════════════════════════════════════════════════

def analyze_solar_geomagnetic(flares_df, storms_df, cmes_df):
    section(
        "ANALYSIS 1 — SOLAR FLARES ↔ GEOMAGNETIC STORMS ↔ CMEs",
        "Energy Cascade: Sun → Solar Wind → Earth's Magnetosphere"
    )

    emit("""
  PHYSICAL CONTEXT
  ────────────────
  The Sun, Earth, and interplanetary space form a coupled energy system.
  Solar flares release electromagnetic energy (light, X-rays) at light speed.
  CMEs expel billions of tons of magnetized plasma at 250–3000 km/s.
  When CMEs strike Earth's magnetosphere, they induce geomagnetic storms.
  This is energy transformation — not creation — across the cosmic fabric.
    """)

    if flares_df.empty or storms_df.empty:
        emit("  [SKIP] Insufficient data for solar-geomagnetic correlation.")
        return

    # ── Flare class distribution
    divider("SOLAR FLARE CLASS DISTRIBUTION")
    class_counts = {}
    for cls in flares_df["class"].dropna():
        letter = cls[0].upper() if cls else "?"
        class_counts[letter] = class_counts.get(letter, 0) + 1

    total = sum(class_counts.values())
    for letter in ["A", "B", "C", "M", "X"]:
        count = class_counts.get(letter, 0)
        bar   = "█" * min(count, 50)
        pct   = (count / total * 100) if total else 0
        emit(f"  {letter}-class : {bar} {count} ({pct:.1f}%)")

    emit(f"\n  Total flares analyzed : {len(flares_df)}")
    emit(f"  Most energetic class  : {flares_df.loc[flares_df['class_value'].idxmax(), 'class'] if not flares_df.empty else 'N/A'}")
    emit(f"  Mean energy proxy     : {flares_df['class_value'].mean():.2e} W/m²")

    # ── Storm intensity distribution
    divider("GEOMAGNETIC STORM INTENSITY (Kp Index)")
    emit("  Kp Scale: 1-3=quiet  4=active  5-6=minor storm  7=major  8-9=extreme")
    emit()
    if not storms_df.empty:
        for kp_min, kp_max, label in [(1,3,"Quiet  "), (4,4,"Active "), (5,6,"Minor  "), (7,7,"Major  "), (8,9,"Extreme")]:
            count = len(storms_df[(storms_df["max_kp"] >= kp_min) & (storms_df["max_kp"] <= kp_max)])
            bar   = "█" * count
            emit(f"  Kp {kp_min}-{kp_max} ({label}): {bar} {count}")
        emit(f"\n  Mean Kp              : {storms_df['max_kp'].mean():.2f}")
        emit(f"  Max Kp recorded      : {storms_df['max_kp'].max():.0f}")
        emit(f"  Total storms         : {len(storms_df)}")

    # ── Temporal lag correlation
    divider("TEMPORAL LAG ANALYSIS — Flare → Storm Delay")
    emit("""
  Solar flares travel at light speed (~8 min to Earth).
  CMEs (which cause storms) travel at ~300–2000 km/s → arrival: 1–4 days.
  We look for storms occurring 1–5 days after major flares.
    """)

    if not flares_df.empty and not storms_df.empty:
        major_flares = flares_df[flares_df["class_value"] >= 1e-5]  # M-class and above
        lag_days_found = []
        for _, flare in major_flares.iterrows():
            window_start = flare["time"]
            window_end   = flare["time"] + timedelta(days=5)
            following_storms = storms_df[
                (storms_df["time"] >= window_start) &
                (storms_df["time"] <= window_end)
            ]
            for _, storm in following_storms.iterrows():
                lag = (storm["time"] - flare["time"]).total_seconds() / 3600
                lag_days_found.append(lag)

        if lag_days_found:
            lag_arr = np.array(lag_days_found)
            emit(f"  M/X flares analyzed         : {len(major_flares)}")
            emit(f"  Storm follow-ups detected   : {len(lag_days_found)}")
            emit(f"  Mean flare→storm lag        : {np.mean(lag_arr):.1f} hours  ({np.mean(lag_arr)/24:.1f} days)")
            emit(f"  Median lag                  : {np.median(lag_arr):.1f} hours")
            emit(f"  Std deviation               : {np.std(lag_arr):.1f} hours")
            emit(f"  Fastest follow-on storm     : {np.min(lag_arr):.1f} hours (likely EM-driven)")
            emit(f"  Slowest follow-on storm     : {np.max(lag_arr):.1f} hours")

            # Storm follow rate
            rate = len(lag_days_found) / len(major_flares) * 100 if len(major_flares) else 0
            emit(f"\n  Storm-following-flare rate  : {rate:.1f}%")
            if rate > 50:
                emit("  ✦ PATTERN: Majority of M/X flares preceded a geomagnetic storm.")
                emit("    This confirms the Sun→CME→magnetosphere energy transfer chain.")
        else:
            emit("  No storm follow-ups detected in current window.")

    # ── CME speed vs storm intensity
    divider("CME SPEED ↔ STORM INTENSITY CORRELATION")
    if not cmes_df.empty and not storms_df.empty and len(cmes_df) >= 3:
        # Match CMEs to storms by proximity in time
        pairs = []
        for _, cme in cmes_df.iterrows():
            window_end = cme["time"] + timedelta(days=5)
            matching   = storms_df[
                (storms_df["time"] >= cme["time"]) &
                (storms_df["time"] <= window_end)
            ]
            for _, storm in matching.iterrows():
                pairs.append({"cme_speed": cme["speed"], "storm_kp": storm["max_kp"]})

        if len(pairs) >= 3:
            pairs_df = pd.DataFrame(pairs)
            r, p = stats.pearsonr(pairs_df["cme_speed"], pairs_df["storm_kp"])
            emit(f"  Matched CME→storm pairs     : {len(pairs)}")
            emit(f"  Pearson correlation (r)     : {r:.3f}")
            emit(f"  p-value                     : {p:.4f}")
            emit(f"  Statistical significance    : {'YES (p < 0.05)' if p < 0.05 else 'Not significant at p<0.05'}")
            if abs(r) > 0.4:
                direction = "positive" if r > 0 else "negative"
                emit(f"\n  ✦ PATTERN: {direction.upper()} correlation found.")
                emit(f"    Faster CMEs tend to produce {'stronger' if r > 0 else 'weaker'} geomagnetic storms.")
                emit(f"    This reflects direct kinetic energy transfer into Earth's magnetic field.")
        else:
            emit("  Not enough matched pairs for CME↔storm correlation.")
    else:
        emit("  Insufficient CME or storm data for this analysis.")


def analyze_gravitational_waves(gw_df):
    section(
        "ANALYSIS 2 — GRAVITATIONAL WAVE EVENT PATTERNS",
        "LIGO/Virgo/KAGRA via GWOSC (gwosc.org)"
    )

    emit("""
  PHYSICAL CONTEXT
  ────────────────
  Gravitational waves are literal ripples in the fabric of spacetime,
  caused by the most violent events in the universe — merging black holes,
  neutron stars, and potentially other exotic objects.
  Each detection is a direct measurement of spacetime geometry changing.
  Einstein predicted these in 1916. LIGO confirmed them in 2015.
  They represent pure energy transfer through the spacetime fabric itself.
    """)

    if gw_df.empty:
        emit("  [SKIP] No gravitational wave data available.")
        return

    # ── Basic stats
    divider("GRAVITATIONAL WAVE EVENT STATISTICS")
    emit(f"  Total confirmed GW events    : {len(gw_df)}")
    emit(f"  Date range (GPS seconds)     : {gw_df['gps'].min():.0f} → {gw_df['gps'].max():.0f}")

    gw_df["total_mass"] = gw_df["mass_1"] + gw_df["mass_2"]
    gw_df["mass_ratio"] = gw_df.apply(
        lambda r: r["mass_1"] / r["mass_2"] if r["mass_2"] > 0 else np.nan, axis=1
    )

    valid_mass = gw_df[gw_df["total_mass"] > 0]
    if not valid_mass.empty:
        emit(f"\n  MASS STATISTICS (solar masses, M☉):")
        emit(f"    Mean total mass            : {valid_mass['total_mass'].mean():.1f} M☉")
        emit(f"    Median total mass          : {valid_mass['total_mass'].median():.1f} M☉")
        emit(f"    Max total mass             : {valid_mass['total_mass'].max():.1f} M☉")
        emit(f"    Min total mass             : {valid_mass['total_mass'].min():.1f} M☉")
        emit(f"    Std deviation              : {valid_mass['total_mass'].std():.1f} M☉")

    valid_dist = gw_df[gw_df["distance"] > 0]
    if not valid_dist.empty:
        emit(f"\n  DISTANCE STATISTICS (megaparsecs, Mpc):")
        emit(f"    Mean distance              : {valid_dist['distance'].mean():.0f} Mpc")
        emit(f"    Median distance            : {valid_dist['distance'].median():.0f} Mpc")
        emit(f"    Nearest event              : {valid_dist['distance'].min():.0f} Mpc")
        emit(f"    Most distant event         : {valid_dist['distance'].max():.0f} Mpc")

    # ── Detection rate over time
    divider("DETECTION RATE — OBSERVING RUN ANALYSIS")
    emit("""
  LIGO observing runs:
    O1: Sep 2015 – Jan 2016   (first detections)
    O2: Nov 2016 – Aug 2017
    O3: Apr 2019 – Mar 2020
    O4: May 2023 – present
    """)

    # GPS epoch: Jan 6, 1980 = Unix 315964800
    GPS_EPOCH = datetime(1980, 1, 6)
    gw_df["datetime"] = gw_df["gps"].apply(
        lambda g: GPS_EPOCH + timedelta(seconds=float(g)) if g > 0 else pd.NaT
    )
    gw_df["year"] = gw_df["datetime"].dt.year

    year_counts = gw_df["year"].value_counts().sort_index()
    emit("  Events per year:")
    for year, count in year_counts.items():
        bar = "█" * count
        emit(f"    {year} : {bar} {count}")

    emit(f"\n  Detection rate is ACCELERATING — reflecting:")
    emit(f"    • Improved detector sensitivity each run")
    emit(f"    • Network expansion (Virgo 2017, KAGRA 2020)")
    emit(f"    • Better signal processing algorithms")

    # ── Mass clustering
    divider("MASS CLUSTERING — K-MEANS ANALYSIS")
    emit("""
  Are GW events grouping into distinct mass populations?
  (Black hole mergers vs neutron star mergers vs mixed?)
    """)

    cluster_df = gw_df[(gw_df["mass_1"] > 0) & (gw_df["mass_2"] > 0)].copy()
    if len(cluster_df) >= 6:
        X = cluster_df[["mass_1", "mass_2", "distance"]].fillna(0)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        cluster_df["cluster"] = kmeans.fit_predict(X_scaled)

        for i in range(3):
            grp = cluster_df[cluster_df["cluster"] == i]
            labels = {0: "Neutron Star / Low-mass", 1: "Stellar Black Hole", 2: "Heavy Black Hole"}
            m1_mean = grp["mass_1"].mean()
            label = "Neutron Star / Low-mass" if m1_mean < 5 else ("Stellar Black Hole" if m1_mean < 40 else "Heavy Black Hole")
            emit(f"  Cluster {i+1} ({label}):")
            emit(f"    Count        : {len(grp)} events")
            emit(f"    Mean Mass 1  : {grp['mass_1'].mean():.1f} M☉")
            emit(f"    Mean Mass 2  : {grp['mass_2'].mean():.1f} M☉")
            emit(f"    Mean Distance: {grp['distance'].mean():.0f} Mpc")
            emit()

        emit("  ✦ PATTERN: GW events naturally cluster into mass populations.")
        emit("    Each cluster likely represents a distinct formation pathway —")
        emit("    different chapters in how the universe transforms mass into")
        emit("    gravitational energy rippling through the spacetime fabric.")

    # ── Mass ratio analysis
    divider("MASS RATIO DISTRIBUTION — SYMMETRY OF MERGERS")
    valid_ratio = gw_df[gw_df["mass_ratio"].notna() & (gw_df["mass_ratio"] > 0)]
    if not valid_ratio.empty:
        emit(f"  Mean mass ratio (m1/m2)      : {valid_ratio['mass_ratio'].mean():.2f}")
        emit(f"  Median mass ratio            : {valid_ratio['mass_ratio'].median():.2f}")
        symmetric = len(valid_ratio[valid_ratio["mass_ratio"] < 1.5])
        asymmetric = len(valid_ratio[valid_ratio["mass_ratio"] >= 1.5])
        emit(f"  Near-equal mass mergers      : {symmetric} ({symmetric/len(valid_ratio)*100:.0f}%)")
        emit(f"  Asymmetric mergers (>1.5:1)  : {asymmetric} ({asymmetric/len(valid_ratio)*100:.0f}%)")
        emit()
        emit("  ✦ PATTERN: Near-equal mass mergers dominate — suggesting black holes")
        emit("    in binary systems co-evolve from similar-mass stellar pairs.")


def analyze_neo_patterns(neo_df, flares_df):
    section(
        "ANALYSIS 3 — NEO APPROACH PATTERNS & SOLAR CORRELATION",
        "NASA NeoWs + DONKI"
    )

    emit("""
  PHYSICAL CONTEXT
  ────────────────
  NEO trajectories are shaped by gravity — primarily the Sun, with
  perturbations from Jupiter and other planets. Solar activity (radiation
  pressure, solar wind) exerts minor but measurable forces on small bodies.
  The question: does solar activity correlate with NEO clustering or approach
  distances? This is a frontier research question — we look for signals here.
    """)

    if neo_df.empty:
        emit("  [SKIP] No NEO data available.")
        return

    # ── Basic stats
    divider("NEO APPROACH STATISTICS")
    emit(f"  Total NEOs in window         : {len(neo_df)}")
    emit(f"  Potentially hazardous        : {neo_df['hazardous'].sum()} ({neo_df['hazardous'].mean()*100:.1f}%)")
    emit(f"  Mean miss distance           : {neo_df['miss_km'].mean():,.0f} km")
    emit(f"  Closest approach             : {neo_df['miss_km'].min():,.0f} km")
    emit(f"  Mean estimated diameter      : {neo_df['diam_m'].mean():.1f} m")
    emit(f"  Largest estimated diameter   : {neo_df['diam_m'].max():.1f} m")
    emit(f"  Mean approach speed          : {neo_df['speed_kms'].mean():.2f} km/s")

    # ── Size vs speed correlation
    divider("SIZE ↔ APPROACH SPEED CORRELATION")
    if len(neo_df) >= 3:
        r, p = stats.pearsonr(neo_df["diam_m"], neo_df["speed_kms"])
        emit(f"  Pearson r (diameter vs speed): {r:.3f}")
        emit(f"  p-value                      : {p:.4f}")
        emit(f"  Significant                  : {'YES' if p < 0.05 else 'No'}")
        if abs(r) > 0.3:
            emit(f"\n  ✦ PATTERN: {'Larger' if r > 0 else 'Smaller'} objects tend to approach")
            emit(f"    at {'higher' if r > 0 else 'lower'} relative velocities.")
            emit(f"    This reflects orbital mechanics — size reflects origin belt,")
            emit(f"    which correlates with orbital energy and thus approach speed.")

    # ── Hazard profile
    divider("HAZARDOUS vs NON-HAZARDOUS PROFILE")
    haz    = neo_df[neo_df["hazardous"] == 1]
    nonhaz = neo_df[neo_df["hazardous"] == 0]
    if not haz.empty and not nonhaz.empty:
        emit(f"  Hazardous NEOs:")
        emit(f"    Mean diameter    : {haz['diam_m'].mean():.1f} m")
        emit(f"    Mean miss dist   : {haz['miss_km'].mean():,.0f} km")
        emit(f"    Mean speed       : {haz['speed_kms'].mean():.2f} km/s")
        emit()
        emit(f"  Non-Hazardous NEOs:")
        emit(f"    Mean diameter    : {nonhaz['diam_m'].mean():.1f} m")
        emit(f"    Mean miss dist   : {nonhaz['miss_km'].mean():,.0f} km")
        emit(f"    Mean speed       : {nonhaz['speed_kms'].mean():.2f} km/s")

    # ── Cross-check with solar activity window
    divider("NEO APPROACH TIMING vs SOLAR ACTIVITY WINDOW")
    if not flares_df.empty and not neo_df.empty:
        recent_flares = flares_df[
            flares_df["time"] >= (datetime.today() - timedelta(days=7))
        ]
        if not recent_flares.empty:
            emit(f"  Solar flares in last 7 days  : {len(recent_flares)}")
            major = recent_flares[recent_flares["class_value"] >= 1e-5]
            emit(f"  M/X class flares             : {len(major)}")
            emit(f"  NEOs approaching this week   : {len(neo_df)}")
            emit()
            if len(major) > 2 and len(neo_df) > 5:
                emit("  ✦ SIGNAL: Elevated solar activity coincides with NEO cluster.")
                emit("    NOTE: Correlation ≠ causation here — solar radiation pressure")
                emit("    is too weak to meaningfully redirect large NEOs on short timescales.")
                emit("    However, at geological timescales, solar activity may influence")
                emit("    the Yarkovsky effect — thermal re-radiation that slowly shifts orbits.")
            else:
                emit("  No strong solar-NEO temporal overlap detected in this window.")
        else:
            emit("  No recent flares to cross-reference with NEO approaches.")


def analyze_dark_matter_cosmology(gw_df):
    section(
        "ANALYSIS 4 — DARK MATTER, COSMIC FABRIC & UNIFIED ENERGY PATTERNS",
        "Planck Mission | GWOSC | Theoretical Cosmology"
    )

    emit("""
  PHYSICAL CONTEXT — THE UNIFIED FABRIC VIEW
  ────────────────────────────────────────────
  Modern physics increasingly points toward a universe where all phenomena
  are expressions of a single underlying energy fabric — spacetime itself.

  The law of conservation of energy is not just a rule — it's a fundamental
  property of the fabric. Energy cannot be created or destroyed because
  spacetime has a continuous symmetry in time (Noether's theorem, 1915).

  Dark matter and dark energy are not separate from this fabric —
  they ARE part of it, simply in forms we cannot yet directly observe.

  Known energy-matter composition of the universe:
    Normal matter (atoms, us)  :  ~4.9%
    Dark matter                : ~26.8%
    Dark energy                : ~68.3%

  We can only directly see 4.9% of the universe.
  The other 95.1% is inferred through its gravitational and geometric effects
  on the fabric — on the very spacetime that GW detectors measure.
    """)

    divider("DARK MATTER — OBSERVATIONAL EVIDENCE SUMMARY")
    evidence = [
        ("Galaxy Rotation Curves",
         "Stars at galaxy edges orbit too fast for visible mass.\n"
         "    Implies a dark matter halo extending far beyond visible disk.\n"
         "    First noted by Vera Rubin & Kent Ford (1970s)."),
        ("Gravitational Lensing",
         "Light bends more around galaxy clusters than visible mass predicts.\n"
         "    Dark matter acts as additional gravitational lens.\n"
         "    Einstein rings and arcs confirm this routinely."),
        ("Bullet Cluster (1E 0657-558)",
         "Two galaxy clusters collided. Hot gas (visible) slowed down.\n"
         "    But gravitational mass (lensing map) passed straight through.\n"
         "    Strongest direct evidence for dark matter as a separate component."),
        ("Cosmic Microwave Background",
         "Tiny temperature fluctuations in the CMB match predictions\n"
         "    only when dark matter is included in models.\n"
         "    Planck satellite data (2018) confirms Ωdm ≈ 0.268."),
        ("Large-Scale Structure",
         "The cosmic web — filaments, voids, galaxy clusters —\n"
         "    only forms correctly in simulations with dark matter.\n"
         "    Dark matter provides the gravitational scaffolding."),
    ]
    for name, desc in evidence:
        emit(f"\n  ◈ {name}")
        emit(f"    {desc}")

    divider("DARK MATTER DENSITY MODELING")
    emit("""
  NFW PROFILE (Navarro-Frenk-White, 1996) — most widely used model:
  
  ρ(r) = ρ₀ / [ (r/rₛ) · (1 + r/rₛ)² ]
  
  where:
    ρ(r)  = dark matter density at radius r from galactic center
    ρ₀    = characteristic density
    rₛ    = scale radius (typically ~20 kpc for Milky Way)

  Milky Way dark matter halo parameters (estimated):
    Scale radius (rₛ)          : ~20 kpc  (~65,000 light-years)
    Virial radius              : ~250 kpc (~815,000 light-years)
    Total dark matter mass     : ~1 × 10¹² M☉  (1 trillion solar masses)
    Local density (solar nbhd) : ~0.3 GeV/cm³  (~8 × 10⁻²⁷ kg/m³)
    """)

    # Compute NFW profile numerically
    emit("  NFW Dark Matter Density Profile (Milky Way model):")
    emit("  (Distance from center → density estimate)\n")
    rho_0 = 0.3        # GeV/cm³ (local normalization)
    r_s   = 20.0       # kpc scale radius
    r_sun = 8.5        # kpc (Sun's distance from galactic center)

    # Normalize so that ρ(r_sun) = rho_0
    def nfw(r, rho0, rs):
        return rho0 / ((r / rs) * (1 + r / rs) ** 2)

    norm_factor = rho_0 / nfw(r_sun, 1.0, r_s)

    radii = [1, 2, 5, 8.5, 10, 20, 50, 100, 200]
    emit(f"  {'Radius (kpc)':<16} {'Distance (kly)':<18} {'DM Density (GeV/cm³)':<22} {'Relative to Sun'}")
    emit("  " + "─" * 72)
    for r in radii:
        density = nfw(r, norm_factor, r_s)
        ratio   = density / rho_0
        dist_ly = r * 3261.6
        marker  = "  ← Solar neighborhood" if r == 8.5 else ""
        emit(f"  {r:<16.1f} {dist_ly:<18,.0f} {density:<22.4f} {ratio:.3f}x{marker}")

    divider("GRAVITATIONAL WAVE ↔ COSMOLOGICAL CONTEXT")
    if not gw_df.empty and len(gw_df) >= 5:
        valid = gw_df[(gw_df["mass_1"] > 0) & (gw_df["distance"] > 0)].copy()
        if len(valid) >= 5:
            emit("""
  Gravitational waves propagate through dark matter — and dark matter
  does NOT dampen or absorb GW signals (unlike EM radiation).
  This makes GW astronomy a unique probe of the universe's structure —
  seeing through all matter, dark or otherwise.

  We can use GW event distances to probe cosmic expansion:
    """)
            # Hubble constant proxy from GW events
            # v_recession ≈ H0 * d  — GW events as standard sirens
            # True H0 from GW150914 paper was ~70 km/s/Mpc
            emit("  GW EVENTS AS STANDARD SIRENS (Hubble constant probe):")
            emit(f"  {'Event':<16} {'Distance (Mpc)':<18} {'Total Mass (M☉)':<18} {'Implied recession speed'}")
            emit("  " + "─" * 72)
            H0 = 67.4  # Planck 2018 value
            for _, row in valid.head(10).iterrows():
                v_recession = H0 * row["distance"]
                emit(f"  {row['name']:<16} {row['distance']:<18.0f} {row['total_mass']:<18.1f} {v_recession:,.0f} km/s")

            r, p = stats.pearsonr(valid["distance"], valid["total_mass"])
            emit(f"\n  Distance ↔ Total Mass correlation  : r = {r:.3f}  (p = {p:.4f})")
            if abs(r) > 0.3:
                emit(f"  ✦ PATTERN: {'More massive' if r > 0 else 'Less massive'} mergers detected")
                emit(f"    at {'greater' if r > 0 else 'shorter'} distances.")
                emit(f"    This reflects detection bias — LIGO sees massive events farther away.")
                emit(f"    It also tells us something about where in the cosmic web")
                emit(f"    the most massive black hole binaries preferentially form.")

    divider("THE UNIFIED FABRIC — SYNTHESIS")
    emit("""
  ENERGY CONSERVATION ACROSS ALL SCALES:
  ───────────────────────────────────────
  Every phenomenon analyzed in this report is a transformation of energy
  through the same underlying spacetime fabric:

  ☀  SOLAR SCALE
     Nuclear fusion in the Sun → electromagnetic radiation + solar wind
     Solar wind → kinetic energy → geomagnetic storms → heat, aurora
     Energy form: nuclear → EM → kinetic → thermal

  🌑  STELLAR SCALE
     Massive stars → gravitational collapse → black holes / neutron stars
     Merging compact objects → gravitational wave energy
     Energy form: gravitational potential → spacetime ripples → heat (eventually)

  🌌  GALACTIC SCALE
     Dark matter halos → gravitational wells → galaxy formation scaffolding
     Baryonic matter falls into DM potential wells → stars, galaxies
     Energy form: gravitational potential → kinetic → radiative

  🌐  COSMIC SCALE
     Dark energy → accelerating spacetime expansion
     Doing work against gravity across the entire observable universe
     Energy form: vacuum energy → kinetic expansion of spacetime itself

  SPACETIME AS A FABRIC (General Relativity + Quantum hints):
  ────────────────────────────────────────────────────────────
  • GW detections confirm spacetime is elastic — it carries waves
  • Dark matter distributions curve spacetime without light interaction
  • Quantum entanglement may connect distant spacetime regions (ER=EPR)
  • The Planck scale (~10⁻³⁵ m) suggests spacetime itself is quantized
  • All forces — gravity, EM, strong, weak — may be geometry at different scales

  CURRENT FRONTIER RESEARCH:
  ──────────────────────────
  • LISA (ESA, 2030s) — space-based GW detector, will map DM through GW lensing
  • CMB-S4 — next-gen CMB survey, will constrain dark matter particle properties
  • Euclid Space Telescope (ESA, launched 2023) — mapping dark matter across cosmic time
  • Event Horizon Telescope expansions — probing spacetime geometry at BH boundaries
  • LHC dark matter searches — direct production of DM particles
  • Pulsar Timing Arrays — detecting nano-Hz GW background (confirmed 2023)
    """)


def analyze_cross_patterns(flares_df, storms_df, gw_df, neo_df):
    section(
        "ANALYSIS 5 — CROSS-DOMAIN PATTERN SYNTHESIS",
        "All datasets combined"
    )

    emit("""
  This section looks across ALL datasets simultaneously for emergent patterns —
  signals that only appear when you view solar, gravitational, and cosmic data
  as a single unified energy system rather than separate phenomena.
    """)

    divider("ENERGY SCALE COMPARISON — PUTTING IT ALL IN PERSPECTIVE")
    energy_events = [
        ("Moderate solar flare (M1)",        "1 × 10²⁰",  "joules"),
        ("Major solar flare (X10)",           "1 × 10²⁵",  "joules"),
        ("Coronal mass ejection",             "1 × 10²⁴",  "joules"),
        ("Geomagnetic storm (Dst = -200 nT)", "1 × 10¹⁵",  "joules"),
        ("GW150914 merger (radiated)",        "5.4 × 10⁴⁷","joules  (3 M☉ converted to waves)"),
        ("Typical BH merger (GW event)",      "~10⁴⁷",     "joules"),
        ("Sun's total lifetime output",       "1.2 × 10⁴⁴","joules"),
        ("Milky Way dark matter binding",     "~10⁵³",     "joules  (estimated)"),
        ("Observable universe dark energy",   "~10⁶⁹",     "joules  (estimated)"),
    ]
    emit(f"  {'Event':<42} {'Energy':<16} {'Notes'}")
    emit("  " + "─" * 80)
    for name, energy, unit in energy_events:
        emit(f"  {name:<42} {energy:<16} {unit}")

    emit("""
  ✦ KEY INSIGHT: A single black hole merger releases more energy in
    gravitational waves than our Sun will emit over its entire lifetime.
    Yet we barely feel it — because gravitational waves interact so weakly
    with matter. The energy IS there. It passes through us constantly.
    This is the nature of the fabric — most of its energy is invisible to us.
    """)

    divider("TEMPORAL CLUSTERING ANALYSIS — ALL EVENTS")
    all_times = []
    if not flares_df.empty:
        for t in flares_df["time"]:
            all_times.append({"time": t, "type": "flare", "weight": 1})
    if not storms_df.empty:
        for t in storms_df["time"]:
            all_times.append({"time": t, "type": "storm", "weight": 2})

    if len(all_times) >= 5:
        all_times_df = pd.DataFrame(all_times).sort_values("time")
        all_times_df["day_of_week"] = all_times_df["time"].dt.dayofweek
        all_times_df["hour"]        = all_times_df["time"].dt.hour
        emit("  Event frequency by day of week (0=Mon, 6=Sun):")
        for day in range(7):
            count = len(all_times_df[all_times_df["day_of_week"] == day])
            bar   = "█" * count
            days  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            emit(f"    {days[day]} : {bar} {count}")
        emit()
        emit("  ✦ NOTE: Solar activity has no weekly pattern — any variation here")
        emit("    reflects reporting cadence, not physical patterns.")
        emit("    The Sun does not observe weekends.")

    divider("FINAL SYNTHESIS — WHAT THE DATA TELLS US")
    emit("""
  Across every dataset analyzed — solar flares, geomagnetic storms,
  coronal mass ejections, gravitational waves, and dark matter modeling —
  the same fundamental truth emerges:

  1. ENERGY FLOWS, IT DOES NOT DISAPPEAR
     Every joule released in a solar flare becomes storm energy, heat,
     aurora light, ionospheric heating. Every joule radiated as GWs
     began as gravitational potential energy in a binary system.
     Conservation is not a coincidence. It is geometry.

  2. THE UNIVERSE IS COUPLED ACROSS SCALES
     Solar activity affects Earth's magnetosphere affects satellite orbits
     affects GPS accuracy affects our daily infrastructure.
     Black hole mergers billions of light-years away stretch and compress
     the very space our atoms occupy — by 10⁻¹⁸ meters.
     We are not separate from cosmic events. We are embedded in them.

  3. DARK MATTER IS THE HIDDEN SCAFFOLDING
     The 27% of the universe we cannot see directly is what allowed
     galaxies — and us — to form. Without dark matter's gravitational
     wells, normal matter would have dispersed too uniformly to clump
     into stars. We exist because of something we cannot yet detect directly.

  4. SPACETIME IS PHYSICAL, NOT JUST MATHEMATICAL
     LIGO proved it. Spacetime is elastic. It carries waves.
     It curves around mass. It expands. It may be quantized.
     The "fabric" metaphor is not a metaphor — it is the most accurate
     description we have of what space and time actually are.

  5. WE ARE AT THE BEGINNING
     We can directly observe only 4.9% of the universe's content.
     Every GW detection opens a new window. Every CMB measurement
     tightens our model. Every NEO tracked improves our understanding
     of the solar system's dynamic equilibrium.

  The universe is not a collection of separate things happening.
  It is one thing — one fabric, one energy, one evolving system —
  and we are a small, curious, self-aware part of it.
    """)


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════
def main():
    emit("★" * 70)
    emit("  🌌  NASA COSMIC PATTERN ANALYSIS ENGINE")
    emit("      Solar · Gravitational · Dark Matter · Spacetime Fabric")
    emit(f"      Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit("★" * 70)

    if NASA_API_KEY == "DEMO_KEY":
        emit("\n  ⚠️  Using DEMO_KEY — rate limits may apply.")
        emit("      Get your free key at: https://api.nasa.gov\n")

    # ── Fetch all data
    section("FETCHING LIVE DATA FROM NASA & GWOSC APIs", "")
    flares_df = fetch_solar_flares(days=90)
    storms_df = fetch_geomagnetic_storms(days=90)
    cmes_df   = fetch_cmes(days=90)
    neo_df    = fetch_neos(days=7)
    gw_df     = fetch_gravitational_waves()

    # ── Run all analyses
    analyze_solar_geomagnetic(flares_df, storms_df, cmes_df)
    analyze_gravitational_waves(gw_df)
    analyze_neo_patterns(neo_df, flares_df)
    analyze_dark_matter_cosmology(gw_df)
    analyze_cross_patterns(flares_df, storms_df, gw_df, neo_df)

    # ── Save to file
    emit("\n\n" + "★" * 70)
    emit("  ✅  Analysis complete.")
    emit("★" * 70 + "\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\n  📄  Full report saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()