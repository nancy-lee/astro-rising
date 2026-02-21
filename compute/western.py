"""
Western tropical astrology computation engine.

Handles:
- Planetary positions (tropical longitude, sign, degree, retrograde)
- House cusps (Placidus or Whole Sign)
- Aspect detection between any two sets of positions
- Current transit positions

Uses Swiss Ephemeris with data files (ephe/ directory) for full precision,
including Chiron and other minor bodies.

Design principle: This module COMPUTES and FLAGS. It does not interpret.
Interpretation is the LLM's job, guided by the skill file.
"""

import swisseph as swe
from datetime import datetime
from pathlib import Path
from typing import Optional

# Point Swiss Ephemeris to data files
_ephe_path = str(Path(__file__).parent.parent / "ephe")
swe.set_ephe_path(_ephe_path)


# ============================================================
# CONSTANTS
# ============================================================

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "North Node": swe.TRUE_NODE,
    "Chiron": swe.CHIRON,
}

ASPECTS = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}

DEFAULT_ORBS = {
    "conjunction": 8.0,
    "sextile": 6.0,
    "square": 8.0,
    "trine": 8.0,
    "opposition": 8.0,
}


# ============================================================
# HELPERS
# ============================================================

def _longitude_to_sign(longitude: float) -> dict:
    """Convert ecliptic longitude to sign, degree, minutes."""
    sign_index = int(longitude / 30)
    degree_in_sign = longitude - (sign_index * 30)
    degrees = int(degree_in_sign)
    minutes = int((degree_in_sign - degrees) * 60)
    return {
        "sign": ZODIAC_SIGNS[sign_index % 12],
        "degree": degrees,
        "minutes": minutes,
        "longitude": round(longitude, 4),
    }


def _parse_time(time_utc: str) -> float:
    """Parse time string 'HH:MM' to decimal hours."""
    parts = time_utc.split(":")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    return hours + minutes / 60.0


def _to_julian(date: datetime, time_utc: str = "12:00") -> float:
    """Convert datetime + time string to Julian Day."""
    decimal_hours = _parse_time(time_utc)
    return swe.julday(date.year, date.month, date.day, decimal_hours)


def _normalize_angle(angle: float) -> float:
    """Normalize angle to 0-360 range."""
    return angle % 360.0


def _angle_distance(lon1: float, lon2: float) -> float:
    """Shortest angular distance between two longitudes."""
    diff = abs(lon1 - lon2) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


# ============================================================
# PLANETARY POSITIONS
# ============================================================

def planetary_positions(date: datetime, time_utc: str = "12:00") -> dict:
    """
    Compute tropical planetary positions for a given date/time.

    Args:
        date: datetime object (date portion used)
        time_utc: time in UTC as "HH:MM" string

    Returns:
        Dict keyed by planet name with sign, degree, minutes,
        longitude, speed, and retrograde flag.
    """
    jd = _to_julian(date, time_utc)
    positions = {}

    for name, planet_id in PLANETS.items():
        try:
            result, flag = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH)
        except swe.Error as e:
            positions[name] = {
                "sign": None, "degree": None, "minutes": None,
                "longitude": None, "speed": None, "retrograde": None,
                "error": str(e),
            }
            continue

        longitude = result[0]
        speed = result[3]  # daily speed in longitude

        pos = _longitude_to_sign(longitude)
        pos["speed"] = round(speed, 4)
        pos["retrograde"] = speed < 0

        positions[name] = pos

    return positions


# ============================================================
# HOUSE CUSPS
# ============================================================

HOUSE_SYSTEMS = {
    "placidus": b'P',
    "whole_sign": b'W',
}


def house_cusps(date: datetime, time_utc: str, latitude: float,
                longitude: float, house_system: str = "placidus") -> dict:
    """
    Compute house cusps.

    Args:
        date: datetime object
        time_utc: time in UTC as "HH:MM"
        latitude: geographic latitude (north positive)
        longitude: geographic longitude (east positive)
        house_system: "placidus" (default) or "whole_sign"

    Returns:
        Dict with 12 house cusps, Ascendant, and Midheaven.
    """
    code = HOUSE_SYSTEMS.get(house_system)
    if code is None:
        raise ValueError(f"Unknown house system: {house_system!r}. "
                         f"Options: {list(HOUSE_SYSTEMS.keys())}")
    jd = _to_julian(date, time_utc)
    cusps, ascmc = swe.houses(jd, latitude, longitude, code)

    houses = {}
    for i in range(12):
        houses[str(i + 1)] = _longitude_to_sign(cusps[i])

    return {
        "houses": houses,
        "ascendant": _longitude_to_sign(ascmc[0]),
        "midheaven": _longitude_to_sign(ascmc[1]),
    }


# ============================================================
# ASPECT DETECTION
# ============================================================

def find_aspects(positions_a: dict, positions_b: dict,
                 orbs: Optional[dict] = None,
                 skip_same: bool = False) -> list:
    """
    Find aspects between two sets of planetary positions.

    Works for natal-to-natal (same dict both args) or
    transit-to-natal (different dicts).

    Args:
        positions_a: first set of positions (from planetary_positions)
        positions_b: second set of positions
        orbs: optional custom orb dict (aspect_name → degrees)
        skip_same: if True, skip comparing a planet with itself
                   (useful when positions_a == positions_b)

    Returns:
        List of aspect dicts with planet names, aspect type,
        exact angle, orb, and applying/separating.
    """
    if orbs is None:
        orbs = DEFAULT_ORBS

    aspects_found = []
    seen = set()

    for name_a, pos_a in positions_a.items():
        if pos_a.get("longitude") is None:
            continue
        for name_b, pos_b in positions_b.items():
            if pos_b.get("longitude") is None:
                continue
            if skip_same and name_a == name_b:
                continue

            # Avoid duplicate pairs
            pair_key = tuple(sorted([name_a, name_b]))
            if pair_key in seen:
                continue

            lon_a = pos_a["longitude"]
            lon_b = pos_b["longitude"]
            distance = _angle_distance(lon_a, lon_b)

            for aspect_name, aspect_angle in ASPECTS.items():
                orb_limit = orbs.get(aspect_name, 8.0)
                deviation = abs(distance - aspect_angle)

                if deviation <= orb_limit:
                    # Determine applying vs separating
                    # Use speeds if available
                    speed_a = pos_a.get("speed", 0)
                    speed_b = pos_b.get("speed", 0)

                    # Applying = getting closer to exact
                    # Crude heuristic: if relative speed narrows the gap
                    relative_speed = speed_a - speed_b
                    applying = None
                    if speed_a != 0 or speed_b != 0:
                        # Check if the angle is shrinking toward exact
                        future_lon_a = _normalize_angle(lon_a + speed_a)
                        future_lon_b = _normalize_angle(lon_b + speed_b)
                        future_distance = _angle_distance(future_lon_a, future_lon_b)
                        future_deviation = abs(future_distance - aspect_angle)
                        applying = future_deviation < deviation

                    aspects_found.append({
                        "planet_a": name_a,
                        "planet_b": name_b,
                        "aspect": aspect_name,
                        "exact_angle": round(distance, 2),
                        "orb": round(deviation, 2),
                        "applying": applying,
                    })

                    seen.add(pair_key)
                    break  # Only one aspect per pair

    # Sort by tightness of orb
    aspects_found.sort(key=lambda a: a["orb"])
    return aspects_found


# ============================================================
# CURRENT TRANSITS
# ============================================================

def current_transits(date: datetime) -> dict:
    """
    Shortcut: planetary positions for a given date at noon UTC.
    Used for daily/weekly transit lookups.

    Args:
        date: datetime object

    Returns:
        Same format as planetary_positions()
    """
    return planetary_positions(date, "12:00")


# ============================================================
# TEST / VERIFICATION
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Western Ephemeris Test: February 15, 2026")
    print("=" * 60)

    # Transit positions for today
    date = datetime(2026, 2, 15)
    positions = current_transits(date)

    print("\nPlanetary Positions (noon UTC):")
    for name, pos in positions.items():
        if pos.get("longitude") is None:
            print(f"  {name:12s}: [unavailable — {pos.get('error', 'unknown')}]")
            continue
        retro = " R" if pos["retrograde"] else ""
        print(f"  {name:12s}: {pos['degree']:2d}°{pos['minutes']:02d}' {pos['sign']}{retro}")

    # House cusps for a sample location (New York)
    print("\nHouse Cusps (Placidus, New York, noon UTC):")
    hc = house_cusps(date, "12:00", 40.7128, -74.006)
    print(f"  Ascendant: {hc['ascendant']['degree']}° {hc['ascendant']['sign']}")
    print(f"  Midheaven: {hc['midheaven']['degree']}° {hc['midheaven']['sign']}")
    for num, cusp in hc["houses"].items():
        print(f"  House {num:>2s}: {cusp['degree']:2d}°{cusp['minutes']:02d}' {cusp['sign']}")

    # Self-aspects (natal chart)
    print("\nTransit-to-transit aspects (tightest):")
    aspects = find_aspects(positions, positions, skip_same=True)
    for asp in aspects[:10]:
        app = "applying" if asp["applying"] else "separating"
        print(f"  {asp['planet_a']:12s} {asp['aspect']:11s} {asp['planet_b']:12s} (orb {asp['orb']:.1f}°, {app})")

    print(f"\n{'=' * 60}")
    print("Verification: Sun should be ~26-27° Aquarius on Feb 15, 2026")
    sun = positions["Sun"]
    print(f"Sun computed: {sun['degree']}°{sun['minutes']:02d}' {sun['sign']}")
    if sun["sign"] == "Aquarius" and 25 <= sun["degree"] <= 28:
        print("PASS")
    else:
        print("CHECK - verify against reference ephemeris")
