"""
Generate reading context for a user on a given date.

This is the main entry point that orchestrates all computation 
and produces a single JSON payload for the LLM interpretation layer.

Usage:
    python compute/generate_context.py --user sample --date 2026-02-15
    python compute/generate_context.py --user sample --date 2026-02-15 --type weekly
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from compute.astro_calendar import day_of_week, week_layout, lmt_correction
from compute.bazi import (
    compute_chart, annual_pillar, annual_interactions,
    STEM_BY_PINYIN, BRANCH_BY_PINYIN, ten_god
)
from compute.western import planetary_positions, current_transits, find_aspects


def load_user_chart(user_name: str) -> dict:
    """Load a user's natal chart data from JSON file."""
    chart_path = Path(__file__).parent.parent / "chart_data" / f"{user_name}.json"
    if not chart_path.exists():
        raise FileNotFoundError(f"No chart data found for user '{user_name}' at {chart_path}")
    
    with open(chart_path) as f:
        return json.load(f)


def compute_bazi_context(user_chart: dict, target_date: datetime) -> dict:
    """Compute BaZi context for a specific date against a natal chart."""
    
    bazi = user_chart["bazi"]
    year = target_date.year
    
    # Annual pillar and interactions
    ap = annual_pillar(year)
    
    # We use the pre-stored natal data rather than recomputing
    # (since the chart file is the source of truth, especially for 
    # hour pillar which may have been manually verified)
    
    # Get Day Master
    dm_pinyin = bazi["day_master"]["stem"]
    dm = STEM_BY_PINYIN[dm_pinyin]
    
    # Annual stem's Ten God
    annual_god = ten_god(dm, ap.stem)
    
    # Branch interactions between natal and annual
    from compute.bazi import find_branch_interactions, EARTHLY_BRANCHES
    
    natal_branches = []
    natal_labels = []
    for pos in ["year", "month", "day", "hour"]:
        branch_pinyin = bazi["pillars"][pos]["branch"]
        natal_branches.append(BRANCH_BY_PINYIN[branch_pinyin])
        natal_labels.append(pos)
    
    # Add annual branch
    natal_branches.append(ap.branch)
    natal_labels.append("annual")
    
    all_interactions = find_branch_interactions(natal_branches, natal_labels)
    annual_specific = [i for i in all_interactions 
                      if any("annual:" in b for b in i["branches"])]
    
    return {
        "annual_pillar": {
            "stem": ap.stem.pinyin,
            "branch": ap.branch.pinyin,
            "animal": ap.branch.animal,
            "stem_element": ap.stem.element.value,
            "description": f"{ap.stem.pinyin} {ap.branch.pinyin} ({ap.stem.polarity.value} {ap.stem.element.value} {ap.branch.animal})",
        },
        "annual_ten_god": annual_god,
        "annual_interactions": annual_specific,
        "all_active_interactions": all_interactions,
        "current_luck_pillar": bazi.get("current_luck_pillar", {}),
    }


def generate_reading_context(user_name: str, target_date: str, 
                              reading_type: str = "weekly") -> dict:
    """
    Generate the complete context payload for a reading.
    
    This is what gets passed to the LLM alongside the SKILL.md instructions.
    """
    date = datetime.fromisoformat(target_date)
    
    # Load user chart
    user_chart = load_user_chart(user_name)
    
    # Calendar context
    today = day_of_week(date)
    
    calendar_context = {
        "today": today,
        "reading_type": reading_type,
    }
    
    if reading_type == "weekly":
        # Generate week from the given date
        calendar_context["week"] = week_layout(date)
        # Also compute end of week
        end_date = date + timedelta(days=6)
        calendar_context["week_end"] = day_of_week(end_date)
    
    # BaZi context
    bazi_context = compute_bazi_context(user_chart, date)
    
    # Western transit context — compute actual positions via ephemeris
    transit_positions = current_transits(date)

    # Build natal positions dict from chart data for aspect comparison
    natal_positions = {}
    for planet_name, planet_data in user_chart["western"]["planets"].items():
        if planet_data.get("degree") is None:
            continue
        # Convert chart format (sign + degree) to ecliptic longitude
        sign = planet_data["sign"]
        degree = planet_data["degree"]
        sign_index = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ].index(sign)
        longitude = sign_index * 30 + degree
        # Normalize planet name to match transit keys
        display_name = planet_name.replace("_", " ").title()
        natal_positions[f"natal {display_name}"] = {
            "longitude": longitude,
            "sign": sign,
            "degree": int(degree),
            "minutes": int((degree - int(degree)) * 60),
            "speed": 0,  # natal positions don't move
        }

    # Transit-to-natal aspects
    transit_to_natal = find_aspects(transit_positions, natal_positions)

    # Transit-to-transit aspects (what's happening in the sky)
    transit_to_transit = find_aspects(transit_positions, transit_positions, skip_same=True)

    western_context = {
        "transit_positions": transit_positions,
        "transit_to_natal_aspects": transit_to_natal,
        "transit_to_transit_aspects": transit_to_transit[:15],  # top 15 by orb tightness
    }

    # For weekly readings, also compute transits for each day
    if reading_type == "weekly":
        daily_transits = {}
        for i in range(7):
            day_date = date + timedelta(days=i)
            day_key = day_date.strftime("%Y-%m-%d")
            day_positions = current_transits(day_date)
            day_aspects = find_aspects(day_positions, natal_positions)
            daily_transits[day_key] = {
                "positions": {name: {"sign": p["sign"], "degree": p["degree"],
                              "minutes": p.get("minutes"), "retrograde": p.get("retrograde")}
                              for name, p in day_positions.items() if p.get("sign")},
                "aspects_to_natal": day_aspects[:20],
            }
        western_context["daily_transits"] = daily_transits

    # Assemble full context
    context = {
        "generated_at": datetime.now().isoformat(),
        "target_date": target_date,
        "reading_type": reading_type,
        "user": {
            "name": user_chart["user"]["name"],
            "birth_date": user_chart["user"]["birth_date"],
        },
        "calendar": calendar_context,
        "western": {
            "natal": user_chart["western"],
            "transits": western_context,
        },
        "bazi": {
            "natal": user_chart["bazi"],
            "current_year": bazi_context,
        },
    }

    return context


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate astrology reading context")
    parser.add_argument("--user", required=True, help="User name (matches chart_data filename)")
    parser.add_argument("--date", required=True, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--type", default="weekly", choices=["weekly", "monthly", "transit", "question"],
                       help="Reading type")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    
    args = parser.parse_args()
    
    context = generate_reading_context(args.user, args.date, args.type)
    
    output = json.dumps(context, indent=2, ensure_ascii=False)

    # Default output path: chart_data/<user>_context.json
    out_path = args.output or str(
        Path(__file__).parent.parent / "chart_data" / f"{args.user}_context.json"
    )
    with open(out_path, "w") as f:
        f.write(output)
    print(out_path)
