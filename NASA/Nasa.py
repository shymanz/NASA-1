import requests
import json
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
#  PASTE YOUR FREE NASA API KEY HERE
#  Get one in 30 seconds at: https://api.nasa.gov
# ─────────────────────────────────────────────────────────────
NASA_API_KEY = "DEMO KEY"  # Replace with your key


# ═════════════════════════════════════════════════════════════
#  SECTION 1 — OUR SOLAR SYSTEM (NASA Fact Sheets)
# ═════════════════════════════════════════════════════════════
PLANET_DATA = {
    "Mercury": {
        "mass_kg": "3.285 × 10²³ kg", "diameter_km": 4879,
        "gravity_ms2": 3.7, "escape_velocity_kms": 4.3,
        "rotation_period_hours": 1407.6, "orbital_period_days": 88.0,
        "distance_from_sun_km": "57,909,227 km", "avg_temp_c": 167,
        "moons": 0, "surface_pressure": "~0 (trace)", "type": "Terrestrial",
        "rings": "No", "discovered_by": "Known since antiquity",
    },
    "Venus": {
        "mass_kg": "4.867 × 10²⁴ kg", "diameter_km": 12104,
        "gravity_ms2": 8.87, "escape_velocity_kms": 10.36,
        "rotation_period_hours": -5832.5, "orbital_period_days": 224.7,
        "distance_from_sun_km": "108,209,475 km", "avg_temp_c": 464,
        "moons": 0, "surface_pressure": "92 atm", "type": "Terrestrial",
        "rings": "No", "discovered_by": "Known since antiquity",
    },
    "Earth": {
        "mass_kg": "5.972 × 10²⁴ kg", "diameter_km": 12756,
        "gravity_ms2": 9.8, "escape_velocity_kms": 11.19,
        "rotation_period_hours": 23.9, "orbital_period_days": 365.2,
        "distance_from_sun_km": "149,598,262 km", "avg_temp_c": 15,
        "moons": 1, "surface_pressure": "1 atm", "type": "Terrestrial",
        "rings": "No", "discovered_by": "N/A (our home)",
    },
    "Mars": {
        "mass_kg": "6.39 × 10²³ kg", "diameter_km": 6792,
        "gravity_ms2": 3.72, "escape_velocity_kms": 5.03,
        "rotation_period_hours": 24.6, "orbital_period_days": 687.0,
        "distance_from_sun_km": "227,943,824 km", "avg_temp_c": -65,
        "moons": 2, "surface_pressure": "0.01 atm", "type": "Terrestrial",
        "rings": "No", "discovered_by": "Known since antiquity",
    },
    "Jupiter": {
        "mass_kg": "1.898 × 10²⁷ kg", "diameter_km": 142984,
        "gravity_ms2": 24.79, "escape_velocity_kms": 59.5,
        "rotation_period_hours": 9.9, "orbital_period_days": 4331,
        "distance_from_sun_km": "778,340,821 km", "avg_temp_c": -110,
        "moons": 95, "surface_pressure": "Unknown (no solid surface)",
        "type": "Gas Giant", "rings": "Yes (faint)",
        "discovered_by": "Known since antiquity",
    },
    "Saturn": {
        "mass_kg": "5.683 × 10²⁶ kg", "diameter_km": 120536,
        "gravity_ms2": 10.44, "escape_velocity_kms": 35.5,
        "rotation_period_hours": 10.7, "orbital_period_days": 10747,
        "distance_from_sun_km": "1,426,666,422 km", "avg_temp_c": -140,
        "moons": 146, "surface_pressure": "Unknown (no solid surface)",
        "type": "Gas Giant", "rings": "Yes (prominent)",
        "discovered_by": "Known since antiquity",
    },
    "Uranus": {
        "mass_kg": "8.681 × 10²⁵ kg", "diameter_km": 51118,
        "gravity_ms2": 8.87, "escape_velocity_kms": 21.3,
        "rotation_period_hours": -17.2, "orbital_period_days": 30589,
        "distance_from_sun_km": "2,870,658,186 km", "avg_temp_c": -195,
        "moons": 28, "surface_pressure": "Unknown (no solid surface)",
        "type": "Ice Giant", "rings": "Yes (faint)",
        "discovered_by": "William Herschel (1781)",
    },
    "Neptune": {
        "mass_kg": "1.024 × 10²⁶ kg", "diameter_km": 49528,
        "gravity_ms2": 11.15, "escape_velocity_kms": 23.5,
        "rotation_period_hours": 16.1, "orbital_period_days": 59800,
        "distance_from_sun_km": "4,498,396,441 km", "avg_temp_c": -200,
        "moons": 16, "surface_pressure": "Unknown (no solid surface)",
        "type": "Ice Giant", "rings": "Yes (faint)",
        "discovered_by": "Le Verrier & Galle (1846)",
    },
}


def section_header(title, source=""):
    print("\n\n" + "═" * 65)
    print(f"  {title}")
    if source:
        print(f"  Source: {source}")
    print("═" * 65)


def divider(label=""):
    print(f"\n{'─' * 50}")
    if label:
        print(f"  ✦  {label}")
        print(f"{'─' * 50}")


# ═════════════════════════════════════════════════════════════
#  SECTION 1 — SOLAR SYSTEM PLANETS
# ═════════════════════════════════════════════════════════════
def print_solar_system():
    section_header(
        "OUR SOLAR SYSTEM — NASA PLANETARY FACT SHEETS",
        "nssdc.gsfc.nasa.gov/planetary/factsheet"
    )
    for name, d in PLANET_DATA.items():
        divider(name.upper())
        print(f"  Type                : {d['type']}")
        print(f"  Mass                : {d['mass_kg']}")
        print(f"  Diameter            : {d['diameter_km']:,} km")
        print(f"  Surface Gravity     : {d['gravity_ms2']} m/s²")
        print(f"  Escape Velocity     : {d['escape_velocity_kms']} km/s")
        rot = d['rotation_period_hours']
        retro = " (retrograde)" if rot < 0 else ""
        print(f"  Rotation Period     : {abs(rot)} hours{retro}")
        print(f"  Orbital Period      : {d['orbital_period_days']:,} days")
        print(f"  Distance from Sun   : {d['distance_from_sun_km']}")
        print(f"  Avg Temperature     : {d['avg_temp_c']}°C")
        print(f"  Known Moons         : {d['moons']}")
        print(f"  Ring System         : {d['rings']}")
        print(f"  Surface Pressure    : {d['surface_pressure']}")
        print(f"  Discovered By       : {d['discovered_by']}")


# ═════════════════════════════════════════════════════════════
#  SECTION 2 — EXOPLANETS
# ═════════════════════════════════════════════════════════════
def print_exoplanets():
    section_header(
        "NASA EXOPLANET ARCHIVE — CONFIRMED EXOPLANETS (25)",
        "exoplanetarchive.ipac.caltech.edu"
    )
    url = (
        "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
        "?query=select+pl_name,hostname,pl_orbper,pl_rade,pl_masse,"
        "disc_year,discoverymethod,pl_eqt"
        "+from+ps+where+pl_rade+is+not+null+and+rownum+<=+25"
        "&format=json"
    )
    try:
        data = requests.get(url, timeout=15).json()
    except Exception as e:
        print(f"  [ERROR] {e}")
        return

    col = "{:<22} {:<18} {:<13} {:<11} {:<11} {:<8} {:<18} {:<10}"
    print("\n  " + col.format(
        "Planet", "Host Star", "Orb. Period",
        "Radius(Rₑ)", "Mass(Mₑ)", "Year", "Detection Method", "Eq. Temp(K)"
    ))
    print("  " + "─" * 105)
    for p in data:
        print("  " + col.format(
            str(p.get("pl_name") or "N/A"),
            str(p.get("hostname") or "N/A"),
            f"{p['pl_orbper']:.2f} d" if p.get("pl_orbper") else "N/A",
            f"{p['pl_rade']:.2f}"     if p.get("pl_rade")   else "N/A",
            f"{p['pl_masse']:.2f}"    if p.get("pl_masse")  else "N/A",
            str(p.get("disc_year") or "N/A"),
            str(p.get("discoverymethod") or "N/A"),
            f"{p['pl_eqt']:.0f} K"   if p.get("pl_eqt")    else "N/A",
        ))


# ═════════════════════════════════════════════════════════════
#  SECTION 3 — ASTRONOMY PICTURE OF THE DAY
# ═════════════════════════════════════════════════════════════
def print_apod():
    section_header(
        "ASTRONOMY PICTURE OF THE DAY (APOD)",
        "api.nasa.gov/planetary/apod"
    )
    try:
        r = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params={"api_key": NASA_API_KEY, "count": 5},
            timeout=10
        ).json()
        for item in r:
            divider(item.get("title", "Untitled"))
            print(f"  Date        : {item.get('date', 'N/A')}")
            print(f"  Media Type  : {item.get('media_type', 'N/A')}")
            print(f"  URL         : {item.get('url', 'N/A')}")
            desc = item.get("explanation", "")
            print(f"  Description : {desc[:300]}{'...' if len(desc) > 300 else ''}")
    except Exception as e:
        print(f"  [ERROR] {e}")


# ═════════════════════════════════════════════════════════════
#  SECTION 4 — MARS ROVER MISSIONS
# ═════════════════════════════════════════════════════════════
def print_mars_rovers():
    section_header(
        "MARS ROVER MISSIONS — LATEST PHOTOS",
        "api.nasa.gov/mars-photos"
    )
    rovers = ["curiosity", "perseverance", "opportunity", "spirit"]
    for rover in rovers:
        divider(f"ROVER: {rover.upper()}")
        try:
            # Get manifest first
            manifest_url = f"https://api.nasa.gov/mars-photos/api/v1/manifests/{rover}"
            manifest = requests.get(
                manifest_url,
                params={"api_key": NASA_API_KEY},
                timeout=10
            ).json().get("photo_manifest", {})

            print(f"  Status          : {manifest.get('status', 'N/A').upper()}")
            print(f"  Launch Date     : {manifest.get('launch_date', 'N/A')}")
            print(f"  Landing Date    : {manifest.get('landing_date', 'N/A')}")
            print(f"  Max Sol (Day)   : {manifest.get('max_sol', 'N/A')}")
            print(f"  Max Earth Date  : {manifest.get('max_date', 'N/A')}")
            print(f"  Total Photos    : {manifest.get('total_photos', 'N/A'):,}" if manifest.get('total_photos') else "  Total Photos    : N/A")

            # Latest photos
            max_sol = manifest.get("max_sol")
            if max_sol:
                photos_url = f"https://api.nasa.gov/mars-photos/api/v1/rovers/{rover}/photos"
                photos = requests.get(
                    photos_url,
                    params={"sol": max_sol, "api_key": NASA_API_KEY, "page": 1},
                    timeout=10
                ).json().get("photos", [])

                if photos:
                    print(f"\n  Latest {min(3, len(photos))} photo(s) from Sol {max_sol}:")
                    for photo in photos[:3]:
                        print(f"    📷 Camera    : {photo.get('camera', {}).get('full_name', 'N/A')}")
                        print(f"       Earth Date: {photo.get('earth_date', 'N/A')}")
                        print(f"       Image URL : {photo.get('img_src', 'N/A')}")
                        print()
                else:
                    print(f"  No photos found for Sol {max_sol}.")
        except Exception as e:
            print(f"  [ERROR] {e}")


# ═════════════════════════════════════════════════════════════
#  SECTION 5 — NEAR EARTH OBJECTS (ASTEROIDS)
# ═════════════════════════════════════════════════════════════
def print_neo():
    section_header(
        "NEAR-EARTH OBJECTS — ASTEROID TRACKING (NEXT 3 DAYS)",
        "api.nasa.gov/neo/rest/v1/feed"
    )
    today = datetime.today()
    end   = today + timedelta(days=3)
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

        all_neos = []
        for date_group in r.get("near_earth_objects", {}).values():
            all_neos.extend(date_group)

        print(f"\n  Total NEOs detected in window : {r.get('element_count', 'N/A')}")
        print(f"  Showing top 15 by close approach:\n")

        col = "{:<30} {:<12} {:<18} {:<20} {:<10}"
        print("  " + col.format("Name", "Date", "Miss Distance(km)", "Diameter(m est.)", "Hazardous?"))
        print("  " + "─" * 92)

        for neo in sorted(
            all_neos,
            key=lambda x: float(x["close_approach_data"][0]["miss_distance"]["kilometers"])
        )[:15]:
            name     = neo.get("name", "N/A")
            approach = neo["close_approach_data"][0]
            date     = approach.get("close_approach_date", "N/A")
            miss_km  = float(approach["miss_distance"]["kilometers"])
            diam_min = neo["estimated_diameter"]["meters"]["estimated_diameter_min"]
            diam_max = neo["estimated_diameter"]["meters"]["estimated_diameter_max"]
            hazard   = "⚠️  YES" if neo.get("is_potentially_hazardous_asteroid") else "No"
            print("  " + col.format(
                name[:29], date,
                f"{miss_km:,.0f}",
                f"{diam_min:.1f} – {diam_max:.1f}",
                hazard
            ))
    except Exception as e:
        print(f"  [ERROR] {e}")


# ═════════════════════════════════════════════════════════════
#  SECTION 6 — SPACE WEATHER & SOLAR FLARES
# ═════════════════════════════════════════════════════════════
def print_space_weather():
    section_header(
        "SPACE WEATHER — SOLAR FLARES & GEOMAGNETIC STORMS",
        "api.nasa.gov/DONKI"
    )
    start = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    end   = datetime.today().strftime("%Y-%m-%d")

    # Solar Flares
    divider("SOLAR FLARES (Last 30 Days)")
    try:
        flares = requests.get(
            "https://api.nasa.gov/DONKI/FLR",
            params={"startDate": start, "endDate": end, "api_key": NASA_API_KEY},
            timeout=10
        ).json()
        if not flares:
            print("  No solar flares recorded in this period.")
        else:
            print(f"  {len(flares)} flare(s) detected\n")
            for f in flares[:10]:
                print(f"  🌟 Class        : {f.get('classType', 'N/A')}")
                print(f"     Begin Time   : {f.get('beginTime', 'N/A')}")
                print(f"     Peak Time    : {f.get('peakTime', 'N/A')}")
                print(f"     End Time     : {f.get('endTime', 'N/A')}")
                print(f"     Source Loc.  : {f.get('sourceLocation', 'N/A')}")
                print()
    except Exception as e:
        print(f"  [ERROR] {e}")

    # Geomagnetic Storms
    divider("GEOMAGNETIC STORMS (Last 30 Days)")
    try:
        storms = requests.get(
            "https://api.nasa.gov/DONKI/GST",
            params={"startDate": start, "endDate": end, "api_key": NASA_API_KEY},
            timeout=10
        ).json()
        if not storms:
            print("  No geomagnetic storms recorded in this period.")
        else:
            print(f"  {len(storms)} storm(s) detected\n")
            for s in storms[:5]:
                print(f"  🌐 Storm Start  : {s.get('startTime', 'N/A')}")
                kp_data = s.get("allKpIndex", [])
                if kp_data:
                    max_kp = max(k.get("kpIndex", 0) for k in kp_data)
                    print(f"     Max Kp Index : {max_kp} (9 = extreme storm)")
                print()
    except Exception as e:
        print(f"  [ERROR] {e}")

    # Coronal Mass Ejections
    divider("CORONAL MASS EJECTIONS (Last 30 Days)")
    try:
        cmes = requests.get(
            "https://api.nasa.gov/DONKI/CME",
            params={"startDate": start, "endDate": end, "api_key": NASA_API_KEY},
            timeout=10
        ).json()
        if not cmes:
            print("  No CMEs recorded in this period.")
        else:
            print(f"  {len(cmes)} CME(s) detected\n")
            for c in cmes[:5]:
                print(f"  ☀️  Start Time   : {c.get('startTime', 'N/A')}")
                analyses = c.get("cmeAnalyses") or []
                if analyses:
                    a = analyses[0]
                    print(f"     Speed        : {a.get('speed', 'N/A')} km/s")
                    print(f"     Type         : {a.get('type', 'N/A')}")
                    print(f"     Half Angle   : {a.get('halfAngle', 'N/A')}°")
                print()
    except Exception as e:
        print(f"  [ERROR] {e}")


# ═════════════════════════════════════════════════════════════
#  SECTION 7 — HUBBLE / JAMES WEBB IMAGERY METADATA
# ═════════════════════════════════════════════════════════════
def print_hubble_webb():
    section_header(
        "HUBBLE SPACE TELESCOPE — IMAGE METADATA",
        "hubblesite.org/api/v3"
    )
    try:
        r = requests.get(
            "https://hubblesite.org/api/v3/images?page=1&per_page=10",
            timeout=10
        ).json()
        images = r if isinstance(r, list) else r.get("images", [])
        for img in images[:8]:
            divider(img.get("name", "Untitled"))
            print(f"  ID          : {img.get('id', 'N/A')}")
            print(f"  Collection  : {img.get('collection', 'N/A')}")
            print(f"  Mission     : {img.get('mission', 'Hubble')}")
            desc = img.get("description", "")
            if desc:
                print(f"  Description : {str(desc)[:250]}{'...' if len(str(desc)) > 250 else ''}")
    except Exception as e:
        print(f"  [ERROR fetching Hubble data] {e}")

    # James Webb via NASA image library
    section_header(
        "JAMES WEBB SPACE TELESCOPE — NASA IMAGE LIBRARY",
        "images-api.nasa.gov"
    )
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": "james webb space telescope", "media_type": "image", "page_size": 8},
            timeout=10
        ).json()
        items = r.get("collection", {}).get("items", [])
        for item in items[:8]:
            data  = item.get("data", [{}])[0]
            links = item.get("links", [{}])
            divider(data.get("title", "Untitled"))
            print(f"  Date Created : {data.get('date_created', 'N/A')[:10]}")
            print(f"  Center       : {data.get('center', 'N/A')}")
            desc = data.get("description", "")
            print(f"  Description  : {str(desc)[:250]}{'...' if len(str(desc)) > 250 else ''}")
            if links:
                print(f"  Preview URL  : {links[0].get('href', 'N/A')}")
    except Exception as e:
        print(f"  [ERROR fetching Webb data] {e}")


# ═════════════════════════════════════════════════════════════
#  SECTION 8 — ISS TRACKING
# ═════════════════════════════════════════════════════════════
def print_iss():
    section_header(
        "INTERNATIONAL SPACE STATION — LIVE TRACKING",
        "api.wheretheiss.at & open-notify.org"
    )
    divider("CURRENT ISS POSITION")
    try:
        pos = requests.get(
            "https://api.wheretheiss.at/v1/satellites/25544",
            timeout=10
        ).json()
        print(f"  Latitude        : {pos.get('latitude', 'N/A'):.4f}°")
        print(f"  Longitude       : {pos.get('longitude', 'N/A'):.4f}°")
        print(f"  Altitude        : {pos.get('altitude', 'N/A'):.2f} km")
        print(f"  Velocity        : {pos.get('velocity', 'N/A'):.2f} km/h")
        print(f"  Visibility      : {pos.get('visibility', 'N/A')}")
        ts = pos.get("timestamp")
        if ts:
            print(f"  Timestamp (UTC) : {datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"  [ERROR] {e}")

    divider("CURRENT ISS CREW")
    try:
        crew = requests.get("http://api.open-notify.org/astros.json", timeout=10).json()
        iss_crew = [p for p in crew.get("people", []) if p.get("craft") == "ISS"]
        print(f"  People aboard ISS: {len(iss_crew)}\n")
        for person in iss_crew:
            print(f"  👨‍🚀 {person.get('name', 'N/A')}")
    except Exception as e:
        print(f"  [ERROR] {e}")


# ═════════════════════════════════════════════════════════════
#  SECTION 9 — FABRIC OF THE UNIVERSE
#  Dark matter, CMB, gravitational waves, black holes, wormholes
# ═════════════════════════════════════════════════════════════
def print_fabric_of_universe():
    section_header(
        "FABRIC OF THE UNIVERSE — COSMOLOGY & FUNDAMENTAL PHYSICS",
        "NASA / ESA / LIGO / Event Horizon Telescope / Planck Mission"
    )

    divider("THE OBSERVABLE UNIVERSE — KEY MEASUREMENTS")
    facts = [
        ("Age of Universe",              "13.787 ± 0.020 billion years  (Planck Mission 2018)"),
        ("Diameter (observable)",         "~93 billion light-years across"),
        ("Expansion Rate (Hubble const)", "67.4 km/s/Mpc  (Planck 2018)"),
        ("Shape",                         "Flat (to within 0.4% margin — Planck data)"),
        ("Total Energy Composition",      "~68% Dark Energy | ~27% Dark Matter | ~5% Normal Matter"),
        ("Cosmic Microwave Background",   "2.725 K  (relic radiation from 380,000 yrs after Big Bang)"),
        ("Speed of Light (vacuum)",       "299,792,458 m/s  (exact, by definition)"),
        ("Planck Length (smallest scale)","1.616 × 10⁻³⁵ meters"),
        ("Planck Time",                   "5.391 × 10⁻⁴⁴ seconds"),
    ]
    for label, value in facts:
        print(f"  {label:<35}: {value}")

    divider("DARK MATTER & DARK ENERGY")
    print("""
  DARK MATTER
  ───────────
  Dark matter does not emit, absorb, or reflect light — it is detected
  only through its gravitational effects on visible matter.

  Evidence:
    • Galaxy rotation curves (stars orbit too fast at outer edges)
    • Gravitational lensing (light bends more than visible mass predicts)
    • Large-scale cosmic structure formation
    • Bullet Cluster collision (mass map separates from hot gas)

  Leading Candidates:
    • WIMPs (Weakly Interacting Massive Particles)
    • Axions
    • Sterile neutrinos
    • Primordial black holes (partial candidate)

  Estimated density in Milky Way: ~0.3 GeV/cm³ near the solar neighborhood

  DARK ENERGY
  ───────────
  A mysterious force driving the accelerating expansion of the universe.
  First inferred in 1998 from Type Ia supernova distance measurements.
  
  Properties:
    • Acts as negative pressure on spacetime
    • Cosmological constant (Λ) is the leading model
    • Equation of state parameter w ≈ -1.03 (near perfect cosmological constant)
    • Energy density: ~6 × 10⁻¹⁰ J/m³  (incredibly diffuse but dominates at large scales)
    """)

    divider("LIGHT & PHOTON PHYSICS")
    print("""
  PHOTON PROPERTIES
  ─────────────────
  • Mass           : 0 (massless — confirmed to < 10⁻¹⁸ eV)
  • Speed (vacuum) : 299,792,458 m/s  (c — universal speed limit)
  • Wave-particle duality: behaves as both wave and particle
  • Spin           : 1 (boson — force carrier of electromagnetism)
  • Energy         : E = hf  (h = Planck's constant 6.626 × 10⁻³⁴ J·s)

  ELECTROMAGNETIC SPECTRUM (low → high energy):
    Radio waves    → Microwaves → Infrared → Visible Light
    → Ultraviolet → X-rays → Gamma rays

  VISIBLE LIGHT (wavelengths):
    Red    : ~700 nm      Orange : ~620 nm      Yellow : ~580 nm
    Green  : ~530 nm      Blue   : ~470 nm      Violet : ~400 nm

  COSMIC LIGHT FACTS:
    • Light from the Sun takes ~8 min 20 sec to reach Earth
    • Light from Proxima Centauri (nearest star): ~4.24 years
    • Light from Andromeda Galaxy: ~2.537 million years
    • Most distant light ever detected: CMB — 13.8 billion light-years
    • Gravitational lensing bends light around massive objects (Einstein 1915)
    """)

    divider("BLACK HOLES")
    print("""
  WHAT IS A BLACK HOLE?
  ─────────────────────
  A region of spacetime where gravity is so extreme that nothing —
  not even light — can escape beyond the event horizon.

  TYPES:
    Stellar Black Holes     : 3 – 100 solar masses (formed from dying stars)
    Intermediate Black Holes: 100 – 100,000 solar masses (rare, still studied)
    Supermassive Black Holes: Millions to billions of solar masses
                              (found at centers of most galaxies)
    Primordial Black Holes  : Hypothetical — may have formed in early universe

  KEY CONCEPTS:
    Event Horizon  : The point of no return. Radius = Schwarzschild radius
                     Rs = 2GM/c²
                     (For Earth-mass black hole: ~9mm diameter)
    Singularity    : The theoretical center — infinite density, 
                     where known physics breaks down
    Hawking Rad.   : Black holes slowly emit thermal radiation and evaporate
                     (Stephen Hawking, 1974) — never yet directly observed
    Spaghettification: Tidal forces near a black hole stretch matter vertically
                       and compress it horizontally
    Time Dilation  : Clocks run slower near a black hole (general relativity)

  NOTABLE BLACK HOLES:
    Sagittarius A*      : Supermassive BH at Milky Way center
                          Mass ~4.1 million solar masses
                          Imaged by Event Horizon Telescope (2022)
    M87*                : First ever black hole imaged (EHT, 2019)
                          Mass ~6.5 billion solar masses
                          Located 55 million light-years away
    TON 618             : One of the most massive known
                          Mass ~66 billion solar masses
    GW150914            : First gravitational wave detection (LIGO 2015)
                          Two black holes merged ~1.3 billion ly away
                          Masses: ~29 + ~36 solar masses → 62 solar masses
                          Energy radiated: ~3 solar masses as gravitational waves

  GRAVITATIONAL WAVES:
    Ripples in spacetime caused by accelerating massive objects.
    Predicted by Einstein (1916), detected by LIGO (2015).
    Travel at the speed of light.
    Strain detected: h ~ 10⁻²¹  (incredibly tiny distortions)
    """)

    divider("WORMHOLES & SPACETIME")
    print("""
  WHAT IS A WORMHOLE?
  ───────────────────
  A hypothetical tunnel connecting two separate points in spacetime,
  formally known as an Einstein-Rosen Bridge (Einstein & Rosen, 1935).

  TYPES:
    Schwarzschild Wormhole : Original solution — not traversable,
                             collapses before anything could pass through
    Traversable Wormhole   : Theoretical — would require exotic matter
                             with negative energy density to stay open
    Inter-universal        : Hypothetical connection between different universes

  REQUIREMENTS FOR TRAVERSABLE WORMHOLE:
    • Exotic matter (negative energy density — violates known energy conditions)
    • Casimir effect produces small amounts of negative energy (quantum level)
    • No confirmed large-scale exotic matter source known
    • Quantum entanglement may be related (ER = EPR conjecture, Maldacena 2013)

  ER = EPR CONJECTURE:
    A theoretical connection between Einstein-Rosen bridges (wormholes)
    and quantum entanglement (Einstein-Podolsky-Rosen paradox).
    Suggests entangled particles may be connected by microscopic wormholes.
    Still highly speculative — active research frontier.

  SPACETIME FABRIC:
    • Spacetime is a 4D continuum (3 spatial + 1 time dimension)
    • Mass and energy curve spacetime (General Relativity, Einstein 1915)
    • Curvature IS gravity — objects follow geodesics (curved paths)
    • At quantum scales: spacetime may be quantized ("quantum foam")
    • String theory proposes up to 10 or 11 dimensions
    • The Planck scale (~10⁻³⁵ m) is where quantum gravity dominates
    """)

    # Live gravitational wave event data from GWOSC
    divider("GRAVITATIONAL WAVE EVENTS — GWOSC (LIVE)")
    try:
        r = requests.get(
            "https://gwosc.org/eventapi/json/allevents/",
            timeout=10
        ).json()
        events = r.get("events", {})
        print(f"  Total confirmed GW events detected: {len(events)}\n")
        col = "{:<14} {:<12} {:<14} {:<14} {:<12}"
        print("  " + col.format("Event", "GPS Time", "Mass 1 (M☉)", "Mass 2 (M☉)", "Distance"))
        print("  " + "─" * 68)
        for i, (name, ev) in enumerate(list(events.items())[:12]):
            m1   = ev.get("mass_1_source", {})
            m2   = ev.get("mass_2_source", {})
            dist = ev.get("luminosity_distance", {})
            m1v  = f"{m1.get('best', 'N/A'):.1f}" if isinstance(m1, dict) and m1.get("best") else "N/A"
            m2v  = f"{m2.get('best', 'N/A'):.1f}" if isinstance(m2, dict) and m2.get("best") else "N/A"
            dv   = f"{dist.get('best', 'N/A'):.0f} Mpc" if isinstance(dist, dict) and dist.get("best") else "N/A"
            gps  = str(ev.get("GPS", "N/A"))[:10]
            print("  " + col.format(name[:13], gps, m1v, m2v, dv))
    except Exception as e:
        print(f"  [ERROR fetching GW data] {e}")


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════
def main():
    print("\n" + "★" * 65)
    print("  🚀  NASA FULL COSMIC DATA FETCHER")
    print("      Solar System · Exoplanets · Mars · APOD · Asteroids")
    print("      Space Weather · Hubble/Webb · ISS · Fabric of Universe")
    print("★" * 65)

    if NASA_API_KEY == "DEMO_KEY":
        print("\n  ⚠️  Using DEMO_KEY — some endpoints may be rate-limited.")
        print("      Get your free key at: https://api.nasa.gov\n")

    print_solar_system()
    print_exoplanets()
    print_apod()
    print_mars_rovers()
    print_neo()
    print_space_weather()
    print_hubble_webb()
    print_iss()
    print_fabric_of_universe()

    print("\n\n" + "★" * 65)
    print("  ✅  All data fetched. End of report.")
    print("★" * 65 + "\n")


if __name__ == "__main__":
    main()