"""
Calendar utilities for astrology calculations.
Handles day-of-week computation, solar term lookups, 
LMT correction, and date range generation.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from pathlib import Path
import math
import swisseph as swe

# Point Swiss Ephemeris to data files
_ephe_path = str(Path(__file__).parent.parent / "ephe")
swe.set_ephe_path(_ephe_path)


def day_of_week(date: Union[datetime, str]) -> dict:
    """
    Returns day of week info for a given date.
    Solves the LLM calendar problem - never guess what day it is.
    
    Args:
        date: datetime object or ISO format string (YYYY-MM-DD)
    
    Returns:
        dict with 'date', 'day_name', 'day_number' (0=Monday, 6=Sunday)
    """
    if isinstance(date, str):
        date = datetime.fromisoformat(date)
    
    return {
        "date": date.strftime("%Y-%m-%d"),
        "day_name": date.strftime("%A"),
        "day_number": date.weekday(),  # 0=Monday, 6=Sunday
        "iso_format": date.isoformat(),
    }


def week_layout(start_date: Union[datetime, str]) -> list[dict]:
    """
    Returns a full week starting from the given date.
    Useful for weekly readings - get every day mapped correctly.
    
    Args:
        start_date: datetime or ISO string for the start of the week
    
    Returns:
        List of 7 day_of_week dicts
    """
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date)
    
    return [day_of_week(start_date + timedelta(days=i)) for i in range(7)]


def lmt_correction(longitude: float, standard_meridian: float = 120.0) -> float:
    """
    Calculate Local Mean Time correction in minutes.
    
    China uses a single timezone based on 120°E. For locations 
    significantly west of this (like Nanning at 108.37°E), the clock 
    time differs from solar time.
    
    Args:
        longitude: birth location longitude in degrees (east positive)
        standard_meridian: timezone standard meridian (120.0 for China/CST)
    
    Returns:
        Correction in minutes (negative = subtract from clock time)
    
    Example:
        Nanning (108.37°E): correction = (108.37 - 120.0) * 4 = -46.52 min
        So 2:05 PM clock time → ~1:18 PM LMT
    """
    return (longitude - standard_meridian) * 4.0


def apply_lmt(clock_time: datetime, longitude: float, 
              standard_meridian: float = 120.0) -> datetime:
    """
    Convert clock time to Local Mean Time.
    
    Args:
        clock_time: datetime in clock/standard time
        longitude: birth location longitude
        standard_meridian: timezone standard meridian
    
    Returns:
        datetime adjusted to LMT
    """
    correction_minutes = lmt_correction(longitude, standard_meridian)
    return clock_time + timedelta(minutes=correction_minutes)


# ============================================================
# SOLAR TERM COMPUTATION
# ============================================================
#
# The 12 Jie (节) solar terms mark BaZi month boundaries.
# Each Jie is defined by the Sun reaching a specific ecliptic longitude.
# Swiss Ephemeris swe.solcross_ut() finds the exact crossing moment.
#
# Li Chun (315°) → Tiger month (month 1)
# Jing Zhe (345°) → Rabbit month (month 2)
# Qing Ming (15°) → Dragon month (month 3)
# Li Xia (45°) → Snake month (month 4)
# Mang Zhong (75°) → Horse month (month 5)
# Xiao Shu (105°) → Goat month (month 6)
# Li Qiu (135°) → Monkey month (month 7)
# Bai Lu (165°) → Rooster month (month 8)
# Han Lu (195°) → Dog month (month 9)
# Li Dong (225°) → Pig month (month 10)
# Da Xue (255°) → Rat month (month 11)
# Xiao Han (285°) → Ox month (month 12)

# (longitude, term_name, branch_pinyin, branch_index)
JIE_DEFINITIONS = [
    (285, "Xiao Han", "Chou", 1),
    (315, "Li Chun", "Yin", 2),
    (345, "Jing Zhe", "Mao", 3),
    (15,  "Qing Ming", "Chen", 4),
    (45,  "Li Xia", "Si", 5),
    (75,  "Mang Zhong", "Wu", 6),
    (105, "Xiao Shu", "Wei", 7),
    (135, "Li Qiu", "Shen", 8),
    (165, "Bai Lu", "You", 9),
    (195, "Han Lu", "Xu", 10),
    (225, "Li Dong", "Hai", 11),
    (255, "Da Xue", "Zi", 0),
]


def find_jie_dates(year: int) -> list[dict]:
    """
    Compute all 12 Jie solar term dates for a given Gregorian year.

    Uses Swiss Ephemeris to find the exact moment the Sun crosses
    each Jie longitude. Returns dates in chronological order.

    Args:
        year: Gregorian year

    Returns:
        List of dicts with keys: month, day, hour_utc, term_name,
        branch, branch_index, jd (Julian Day of crossing)
    """
    results = []
    jd_year_start = swe.julday(year, 1, 1, 0)

    for lon, name, branch, branch_idx in JIE_DEFINITIONS:
        jd_cross = swe.solcross_ut(float(lon), jd_year_start, 0)
        y, m, d, h = swe.revjul(jd_cross)
        # Only include crossings that fall within this Gregorian year
        if y == year:
            results.append({
                "month": m,
                "day": d,
                "hour_utc": round(h, 2),
                "term_name": name,
                "branch": branch,
                "branch_index": branch_idx,
                "jd": jd_cross,
            })

    results.sort(key=lambda x: x["jd"])
    return results


def find_nearest_jie(birth_jd: float, year: int, forward: bool) -> float:
    """
    Find the nearest Jie solar term JD in the given direction from birth.

    Args:
        birth_jd: Julian Day of birth
        year: birth year (Gregorian)
        forward: True = find next Jie after birth, False = find previous

    Returns:
        Julian Day of the nearest Jie solar term
    """
    # Get Jie dates for birth year and adjacent years
    all_jie = []
    for y in [year - 1, year, year + 1]:
        all_jie.extend(find_jie_dates(y))
    all_jie.sort(key=lambda x: x["jd"])

    if forward:
        for jie in all_jie:
            if jie["jd"] > birth_jd:
                return jie["jd"]
    else:
        for jie in reversed(all_jie):
            if jie["jd"] < birth_jd:
                return jie["jd"]

    raise ValueError(f"Could not find {'next' if forward else 'previous'} Jie from JD {birth_jd}")


def date_range(start: Union[datetime, str], end: Union[datetime, str]) -> list[dict]:
    """
    Generate a list of dates between start and end (inclusive).
    Each entry includes day_of_week info.
    
    Useful for generating reading context for a period.
    """
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.fromisoformat(end)
    
    dates = []
    current = start
    while current <= end:
        dates.append(day_of_week(current))
        current += timedelta(days=1)
    return dates


# Quick verification
if __name__ == "__main__":
    # Test: What day is February 15, 2026?
    result = day_of_week("2026-02-15")
    print(f"February 15, 2026 is a {result['day_name']}")

    # Test: Week layout from Feb 15
    week = week_layout("2026-02-15")
    for day in week:
        print(f"  {day['day_name']} {day['date']}")

    # Test: LMT correction for San Francisco (-122.4194°W, PST = UTC-8, meridian -120°)
    correction = lmt_correction(-122.4194, -120.0)
    print(f"\nSan Francisco LMT correction: {correction:.1f} minutes")

    clock_time = datetime(1990, 3, 15, 10, 30)  # 10:30 AM PST
    lmt = apply_lmt(clock_time, -122.4194, -120.0)
    print(f"Clock time: {clock_time.strftime('%I:%M %p')}")
    print(f"LMT: {lmt.strftime('%I:%M %p')}")

    # Test: Solar terms for 2026
    print("\n2026 Jie Solar Terms:")
    for jie in find_jie_dates(2026):
        print(f"  {jie['term_name']:12s} → {jie['branch']:4s}: {jie['month']:02d}-{jie['day']:02d}")
