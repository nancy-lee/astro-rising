"""
Chart creation library.
Computes Western + BaZi natal chart from birth data, writes chart_data JSON.

Called by Claude during first-session onboarding — not run directly by users.
Timezone is auto-detected from birth coordinates and date (handles historical DST).

Usage from Python:
    from compute.create_chart import compute_and_save_chart
    compute_and_save_chart(
        name="Alex", birth_date="1990-03-15", birth_time="10:30",
        city="San Francisco", country="USA",
        latitude=37.7749, longitude=-122.4194, gender="male",
        utc_offset=None  # optional: override auto-detected UTC offset
    )
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from compute.western import planetary_positions, house_cusps, find_aspects
from compute.bazi import compute_chart, BRANCH_BY_PINYIN
from compute.astro_calendar import lmt_correction
from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()


def utc_offset_for(latitude, longitude, birth_date, birth_time):
    """
    Determine UTC offset from coordinates and date.
    Detects historical DST (e.g., China 1986-1991).

    Returns:
        (clock_offset, standard_offset, timezone_name, dst_detected)

        clock_offset:    what the clock was actually set to (includes DST if active)
        standard_offset: the zone's standard (non-DST) offset
        dst_detected:    True if DST was active at birth time

    Western astrology uses clock_offset (actual astronomical moment).
    BaZi uses standard_offset (strips DST for LMT calculation).
    When DST is not active, both offsets are the same.
    """
    tz_name = _tf.timezone_at(lat=latitude, lng=longitude)
    if tz_name is None:
        raise ValueError(f"Could not determine timezone for ({latitude}, {longitude})")

    hour, minute = map(int, birth_time.split(":"))
    local_dt = datetime(birth_date.year, birth_date.month, birth_date.day,
                        hour, minute, tzinfo=ZoneInfo(tz_name))
    offset_seconds = local_dt.utcoffset().total_seconds()
    clock_offset = offset_seconds / 3600

    # Check if DST is active
    dst_seconds = local_dt.dst()
    dst_detected = dst_seconds is not None and dst_seconds.total_seconds() > 0

    # Standard offset = clock offset minus DST adjustment
    if dst_detected:
        standard_offset = clock_offset - (dst_seconds.total_seconds() / 3600)
    else:
        standard_offset = clock_offset

    return clock_offset, standard_offset, tz_name, dst_detected


# ============================================================
# COMPUTATION HELPERS
# ============================================================

def sun_longitude_to_month_branch_index(sun_lon):
    """
    Map Sun's ecliptic longitude to BaZi month branch index.

    Solar term Jie boundaries mark BaZi month transitions:
      315° (Li Chun)    → Yin (Tiger, index 2)
      345° (Jing Zhe)   → Mao (Rabbit, index 3)
       15° (Qing Ming)  → Chen (Dragon, index 4)
       45° (Li Xia)     → Si (Snake, index 5)
       75° (Mang Zhong) → Wu (Horse, index 6)
      105° (Xiao Shu)   → Wei (Goat, index 7)
      135° (Li Qiu)     → Shen (Monkey, index 8)
      165° (Bai Lu)     → You (Rooster, index 9)
      195° (Han Lu)     → Xu (Dog, index 10)
      225° (Li Dong)    → Hai (Pig, index 11)
      255° (Da Xue)     → Zi (Rat, index 0)
      285° (Xiao Han)   → Chou (Ox, index 1)
    """
    adjusted = (sun_lon - 315) % 360
    month_num = int(adjusted / 30)
    branch_indices = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1]
    return branch_indices[month_num]


def assign_house(planet_lon, cusp_longitudes):
    """Determine which house a planet falls in based on cusp longitudes."""
    for i in range(12):
        cusp_start = cusp_longitudes[i]
        cusp_end = cusp_longitudes[(i + 1) % 12]

        if cusp_start < cusp_end:
            if cusp_start <= planet_lon < cusp_end:
                return i + 1
        else:  # wraps around 0°/360°
            if planet_lon >= cusp_start or planet_lon < cusp_end:
                return i + 1
    return 1  # fallback


# ============================================================
# CHART COMPUTATION
# ============================================================

def compute_western_chart(birth_date, birth_time, utc_offset, latitude, longitude,
                          house_system="placidus"):
    """
    Compute Western tropical natal chart.

    Args:
        birth_date: datetime object
        birth_time: "HH:MM" string (local clock time)
        utc_offset: float (e.g., -8 for PST, +8 for China)
        latitude: float (north positive)
        longitude: float (east positive)
        house_system: "placidus" (default) or "whole_sign"

    Returns:
        (western_dict, raw_positions) — the formatted chart and raw ephemeris data
    """
    birth_hour, birth_minute = map(int, birth_time.split(":"))

    # Convert local birth time to UTC
    local_dt = datetime(birth_date.year, birth_date.month, birth_date.day,
                        birth_hour, birth_minute)
    utc_dt = local_dt - timedelta(hours=utc_offset)
    utc_time_str = f"{utc_dt.hour:02d}:{utc_dt.minute:02d}"

    # Planetary positions at birth (UTC)
    positions = planetary_positions(utc_dt, utc_time_str)

    # House cusps
    hc = house_cusps(utc_dt, utc_time_str, latitude, longitude, house_system)

    # House cusp longitudes for planet-to-house assignment
    cusp_lons = [hc["houses"][str(i + 1)]["longitude"] for i in range(12)]

    # Build planets dict
    planets = {}
    for planet_name, pos in positions.items():
        key = planet_name.lower().replace(" ", "_")
        if pos.get("longitude") is None:
            planets[key] = {"sign": None, "degree": None, "house": None}
            continue
        house_num = assign_house(pos["longitude"], cusp_lons)
        planets[key] = {
            "sign": pos["sign"],
            "degree": round(pos["longitude"] % 30, 1),
            "house": house_num,
        }

    # Natal aspects (top 20 tightest)
    natal_aspects_raw = find_aspects(positions, positions, skip_same=True)
    natal_aspects = []
    for asp in natal_aspects_raw[:20]:
        natal_aspects.append({
            "planet1": asp["planet_a"].lower().replace(" ", "_"),
            "planet2": asp["planet_b"].lower().replace(" ", "_"),
            "aspect": asp["aspect"],
            "orb": asp["orb"],
        })

    # Format houses
    houses = {}
    for num, cusp in hc["houses"].items():
        houses[num] = {
            "sign": cusp["sign"],
            "degree": round(cusp["longitude"] % 30, 1),
        }

    western = {
        "house_system": house_system.replace("_", " ").title(),
        "zodiac": "tropical",
        "lmt_corrected": False,
        "ascendant": {
            "sign": hc["ascendant"]["sign"],
            "degree": round(hc["ascendant"]["longitude"] % 30, 1),
        },
        "midheaven": {
            "sign": hc["midheaven"]["sign"],
            "degree": round(hc["midheaven"]["longitude"] % 30, 1),
        },
        "planets": planets,
        "houses": houses,
        "natal_aspects": natal_aspects,
        "key_themes": [],
    }

    return western, positions


def compute_bazi_chart(birth_date, birth_time, utc_offset, longitude, gender, sun_longitude):
    """
    Compute BaZi Four Pillars natal chart.

    Args:
        birth_date: datetime object
        birth_time: "HH:MM" string (local clock time)
        utc_offset: float
        longitude: float (east positive) — for LMT correction
        gender: "male" or "female" — determines luck pillar direction
        sun_longitude: float — Sun's ecliptic longitude at birth (from Western computation)

    Returns:
        (bazi_dict, lmt_correction_minutes, lmt_time_str)
    """
    birth_hour, birth_minute = map(int, birth_time.split(":"))
    local_dt = datetime(birth_date.year, birth_date.month, birth_date.day,
                        birth_hour, birth_minute)

    # LMT correction for BaZi hour pillar
    standard_meridian = utc_offset * 15
    lmt_correction_min = lmt_correction(longitude, standard_meridian)
    lmt_dt = local_dt + timedelta(minutes=lmt_correction_min)
    lmt_hour = lmt_dt.hour
    lmt_time_str = f"{lmt_dt.hour:02d}:{lmt_dt.minute:02d}"

    # Determine BaZi month from Sun's ecliptic longitude
    month_branch_index = sun_longitude_to_month_branch_index(sun_longitude)

    # Compute full chart
    chart = compute_chart(
        birth_date=birth_date,
        birth_hour_lmt=lmt_hour,
        gender=gender,
        month_branch_index=month_branch_index,
    )

    # Format pillars
    pillars = {}
    for pos_name in ["year", "month", "day", "hour"]:
        p = chart["pillars"][pos_name]
        pillars[pos_name] = {
            "stem": p["stem"]["pinyin"],
            "branch": p["branch"]["pinyin"],
            "description": p["description"],
        }

    # Determine current luck pillar based on age (month-aware)
    today = datetime.now().date()
    age = today.year - birth_date.year - (
        1 if (today.month, today.day) < (birth_date.month, birth_date.day) else 0
    )
    current_lp = None
    for lp in chart["luck_pillars"]:
        if lp["age_start"] <= age <= lp["age_end"]:
            current_lp = lp
            break

    # Format luck pillars
    luck_pillars = []
    for lp in chart["luck_pillars"][:8]:
        luck_pillars.append({
            "number": lp["number"],
            "stem": lp["stem"],
            "branch": lp["branch"],
            "animal": lp["branch_animal"],
            "ages": f"{lp['age_start']}-{lp['age_end']}",
            "element_theme": f"{lp['stem_element'].capitalize()}/{lp['branch_element'].capitalize()}",
        })

    # Year animal label
    year_branch = BRANCH_BY_PINYIN[pillars["year"]["branch"]]
    zodiac_animal = f"{pillars['year']['stem']} {year_branch.animal}"

    bazi = {
        "pillars": pillars,
        "day_master": chart["day_master"],
        "zodiac_animal": zodiac_animal,
        "notable_features": [],
        "luck_pillars": luck_pillars,
        "current_luck_pillar": {
            "number": current_lp["number"],
            "description": current_lp["description"],
            "themes": "",
        } if current_lp else {},
        "key_themes": [],
    }

    return bazi, lmt_correction_min, lmt_time_str


def compute_and_save_chart(name, birth_date, birth_time,
                           city, country, latitude, longitude, gender,
                           utc_offset=None, house_system="placidus"):
    """
    Compute full natal chart and save to chart_data/<name>.json.

    This is the main entry point — called by Claude during onboarding.
    Timezone is auto-detected from coordinates and birth date.

    Args:
        name: str — user's name (used as filename)
        birth_date: str "YYYY-MM-DD" or datetime
        birth_time: str "HH:MM" (24h, local clock time)
        city: str
        country: str
        latitude: float (north positive)
        longitude: float (east positive)
        gender: "male" or "female"
        utc_offset: float or None — if provided, overrides auto-detected offset
        house_system: "placidus" (default) or "whole_sign"

    Returns:
        dict with keys: path, timezone, western_summary, bazi_summary
    """
    if isinstance(birth_date, str):
        birth_date = datetime.strptime(birth_date, "%Y-%m-%d")

    # Auto-detect timezone from coordinates and date
    clock_offset, standard_offset, tz_name, dst_detected = utc_offset_for(
        latitude, longitude, birth_date, birth_time
    )

    # Determine offsets for each system
    if utc_offset is not None:
        # Manual override: use for both systems
        western_offset = utc_offset
        bazi_offset = utc_offset
        timezone_source = "manual"
    else:
        # Western uses clock offset (actual astronomical moment)
        # BaZi uses standard offset (strips DST for LMT/solar time)
        western_offset = clock_offset
        bazi_offset = standard_offset if dst_detected else clock_offset
        timezone_source = "auto_split" if dst_detected else "auto"

    # Compute Western chart (uses clock offset for correct UTC moment)
    western, positions = compute_western_chart(
        birth_date, birth_time, western_offset, latitude, longitude, house_system
    )

    # Compute BaZi chart (uses standard offset for LMT correction)
    # When DST is active, convert clock time to standard time first
    bazi_birth_time = birth_time
    if dst_detected and utc_offset is None:
        dst_adj = clock_offset - standard_offset  # typically 1 hour
        h, m = map(int, birth_time.split(":"))
        std_dt = datetime(birth_date.year, birth_date.month, birth_date.day,
                          h, m) - timedelta(hours=dst_adj)
        bazi_birth_time = f"{std_dt.hour:02d}:{std_dt.minute:02d}"

    sun_lon = positions["Sun"]["longitude"]
    bazi, lmt_correction_min, lmt_time_str = compute_bazi_chart(
        birth_date, bazi_birth_time, bazi_offset, longitude, gender, sun_lon
    )

    # Timezone label (show clock offset — what the user experienced)
    tz_sign = "+" if clock_offset >= 0 else ""
    tz_int = int(clock_offset) if clock_offset == int(clock_offset) else clock_offset

    # Assemble
    chart_data = {
        "user": {
            "name": name,
            "birth_date": birth_date.strftime("%Y-%m-%d"),
            "birth_time_clock": birth_time,
            "birth_time_lmt": lmt_time_str,
            "timezone": f"{tz_name} (UTC{tz_sign}{tz_int})",
            "western_utc_offset": western_offset,
            "bazi_utc_offset": bazi_offset,
            "dst_detected": dst_detected,
            "timezone_source": timezone_source,
            "location": {
                "city": city,
                "country": country,
                "latitude": latitude,
                "longitude": longitude,
            },
            "lmt_correction_minutes": round(lmt_correction_min),
            "gender": gender,
        },
        "western": western,
        "bazi": bazi,
    }

    # Write
    chart_dir = Path(__file__).parent.parent / "chart_data"
    chart_dir.mkdir(exist_ok=True)
    filename = name.lower().replace(" ", "_")
    chart_path = chart_dir / f"{filename}.json"

    with open(chart_path, "w") as f:
        json.dump(chart_data, f, indent=2, ensure_ascii=False)

    # Generate visual chart
    from compute.visualize_chart import create_chart_visualization
    html_path = create_chart_visualization(chart_path)

    # Return summary for Claude to confirm with the user
    sun = western["planets"]["sun"]
    moon = western["planets"]["moon"]
    asc = western["ascendant"]
    dm = bazi["day_master"]

    return {
        "path": str(chart_path),
        "html_path": html_path,
        "timezone": f"{tz_name} (UTC{tz_sign}{tz_int})",
        "dst_detected": dst_detected,
        "timezone_source": timezone_source,
        "western_utc_offset": western_offset,
        "bazi_utc_offset": bazi_offset,
        "western_summary": {
            "sun": f"{sun['degree']}° {sun['sign']} (house {sun['house']})",
            "moon": f"{moon['degree']}° {moon['sign']} (house {moon['house']})",
            "ascendant": f"{asc['degree']}° {asc['sign']}",
            "natal_aspects": len(western["natal_aspects"]),
        },
        "bazi_summary": {
            "day_master": dm["description"],
            "pillars": {pos: bazi["pillars"][pos]["description"]
                        for pos in ["year", "month", "day", "hour"]},
            "zodiac_animal": bazi["zodiac_animal"],
            "luck_pillars": len(bazi["luck_pillars"]),
        },
    }
