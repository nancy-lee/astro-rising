"""
Natal chart visualization — generates self-contained HTML with inline SVG/CSS.
No dependencies beyond stdlib. Opens in any browser.

Usage:
    python3 compute/visualize_chart.py --chart chart_data/sample.json
"""

import json
import math
import os
import sys
import webbrowser
from pathlib import Path


# ============================================================
# CONSTANTS
# ============================================================

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGN_GLYPHS = {
    "Aries": "\u2648", "Taurus": "\u2649", "Gemini": "\u264A",
    "Cancer": "\u264B", "Leo": "\u264C", "Virgo": "\u264D",
    "Libra": "\u264E", "Scorpio": "\u264F", "Sagittarius": "\u2650",
    "Capricorn": "\u2651", "Aquarius": "\u2652", "Pisces": "\u2653",
}

SIGN_ELEMENTS = {
    "Aries": "fire", "Taurus": "earth", "Gemini": "air", "Cancer": "water",
    "Leo": "fire", "Virgo": "earth", "Libra": "air", "Scorpio": "water",
    "Sagittarius": "fire", "Capricorn": "earth", "Aquarius": "air", "Pisces": "water",
}

# Warmer element colors for Western signs
ELEMENT_COLORS = {
    "fire": "#d4694a",
    "earth": "#8a9a5b",
    "air": "#c9a84c",
    "water": "#5b8fa8",
}

WESTERN_ELEMENT_EMOJIS = {
    "fire": "\U0001F525",
    "earth": "\u26F0\uFE0F",
    "air": "\U0001F4A8",
    "water": "\U0001F4A7",
}

PLANET_GLYPHS = {
    "sun": "\u2609", "moon": "\u263D", "mercury": "\u263F",
    "venus": "\u2640", "mars": "\u2642", "jupiter": "\u2643",
    "saturn": "\u2644", "uranus": "\u2645", "neptune": "\u2646",
    "pluto": "\u2647", "north_node": "\u260A", "chiron": "\u26B7",
}

PLANET_LABELS = {
    "sun": "Sun", "moon": "Moon", "mercury": "Mercury",
    "venus": "Venus", "mars": "Mars", "jupiter": "Jupiter",
    "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune",
    "pluto": "Pluto", "north_node": "N.Node", "chiron": "Chiron",
}

ASPECT_STYLES = {
    "conjunction": {"color": "#c9a84c", "dash": "", "symbol": "\u260C", "type": "neutral"},
    "sextile":     {"color": "#5b8fa8", "dash": "6,3", "symbol": "\u26B9", "type": "soft"},
    "square":      {"color": "#d4694a", "dash": "", "symbol": "\u25A1", "type": "hard"},
    "trine":       {"color": "#5b8fa8", "dash": "", "symbol": "\u25B3", "type": "soft"},
    "opposition":  {"color": "#d4694a", "dash": "8,4", "symbol": "\u260D", "type": "hard"},
}

# BaZi element colors (warmer)
BAZI_ELEMENT_COLORS = {
    "wood":  "#5a9e6f",
    "fire":  "#d4694a",
    "earth": "#b8963e",
    "metal": "#9a9590",
    "water": "#5b8fa8",
}

BAZI_ELEMENT_EMOJIS = {
    "wood": "\U0001F333",
    "fire": "\U0001F525",
    "earth": "\u26F0\uFE0F",
    "metal": "\U0001FA99",
    "water": "\U0001F4A7",
}

BRANCH_EMOJIS = {
    "Zi": "\U0001F400", "Chou": "\U0001F402", "Yin": "\U0001F405",
    "Mao": "\U0001F407", "Chen": "\U0001F409", "Si": "\U0001F40D",
    "Wu": "\U0001F434", "Wei": "\U0001F410", "Shen": "\U0001F412",
    "You": "\U0001F413", "Xu": "\U0001F415", "Hai": "\U0001F416",
}

STEM_ELEMENTS = {
    "Jia": "wood", "Yi": "wood",
    "Bing": "fire", "Ding": "fire",
    "Wu": "earth", "Ji": "earth",
    "Geng": "metal", "Xin": "metal",
    "Ren": "water", "Gui": "water",
}

BRANCH_ELEMENTS = {
    "Zi": "water", "Chou": "earth", "Yin": "wood", "Mao": "wood",
    "Chen": "earth", "Si": "fire", "Wu": "fire", "Wei": "earth",
    "Shen": "metal", "You": "metal", "Xu": "earth", "Hai": "water",
}

BRANCH_ANIMALS = {
    "Zi": "Rat", "Chou": "Ox", "Yin": "Tiger", "Mao": "Rabbit",
    "Chen": "Dragon", "Si": "Snake", "Wu": "Horse", "Wei": "Goat",
    "Shen": "Monkey", "You": "Rooster", "Xu": "Dog", "Hai": "Pig",
}

STEM_CHINESE = {
    "Jia": "\u7532", "Yi": "\u4E59", "Bing": "\u4E19", "Ding": "\u4E01",
    "Wu": "\u620A", "Ji": "\u5DF1", "Geng": "\u5E9A", "Xin": "\u8F9B",
    "Ren": "\u58EC", "Gui": "\u7678",
}


# ============================================================
# HELPERS
# ============================================================

def sign_degree_to_longitude(sign, degree):
    """Convert sign name + degree-within-sign to absolute ecliptic longitude."""
    idx = SIGNS.index(sign)
    return idx * 30 + degree


def longitude_to_svg_angle(lon, asc_longitude):
    """
    Convert ecliptic longitude to SVG angle (clockwise from top).
    The Ascendant sits at the 9 o'clock position (180° in SVG).
    Ecliptic goes counter-clockwise, SVG goes clockwise, so we negate.
    """
    return -(lon - asc_longitude)


def polar_to_xy(cx, cy, radius, angle_deg):
    """Convert polar coordinates to SVG x,y. Angle 0 = right (3 o'clock)."""
    rad = math.radians(angle_deg)
    return cx + radius * math.cos(rad), cy - radius * math.sin(rad)


def escape_html(text):
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ============================================================
# WESTERN CHART WHEEL SVG
# ============================================================

def generate_western_wheel_svg(western_data):
    """Generate an SVG string for the Western natal chart wheel."""
    size = 680
    cx, cy = size / 2, size / 2
    r_outer = 310
    r_inner = 260
    r_house = 250
    r_planet = 210
    r_aspect = 155
    r_label = 286

    asc_sign = western_data["ascendant"]["sign"]
    asc_degree = western_data["ascendant"]["degree"]
    asc_lon = sign_degree_to_longitude(asc_sign, asc_degree)

    parts = []
    parts.append(f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg"'
                 f' style="max-width:680px;width:100%;height:auto;">')

    # Background
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_outer + 12}" fill="#1c1915"/>')

    # --- Zodiac ring segments ---
    for i, sign in enumerate(SIGNS):
        seg_start_lon = i * 30
        seg_end_lon = (i + 1) * 30

        a1 = longitude_to_svg_angle(seg_start_lon, asc_lon)
        a2 = longitude_to_svg_angle(seg_end_lon, asc_lon)

        x1o, y1o = polar_to_xy(cx, cy, r_outer, a1)
        x2o, y2o = polar_to_xy(cx, cy, r_outer, a2)
        x1i, y1i = polar_to_xy(cx, cy, r_inner, a1)
        x2i, y2i = polar_to_xy(cx, cy, r_inner, a2)

        element = SIGN_ELEMENTS[sign]
        color = ELEMENT_COLORS[element]

        parts.append(
            f'<path d="M {x1o:.1f} {y1o:.1f} '
            f'A {r_outer} {r_outer} 0 0 0 {x2o:.1f} {y2o:.1f} '
            f'L {x2i:.1f} {y2i:.1f} '
            f'A {r_inner} {r_inner} 0 0 1 {x1i:.1f} {y1i:.1f} Z" '
            f'fill="{color}" fill-opacity="0.18" stroke="#2e2a24" stroke-width="0.5"/>'
        )

        # Sign glyph + name label, rotated tangent to the ring
        glyph = SIGN_GLYPHS[sign]
        sign_upper = sign.upper()

        mid_lon = seg_start_lon + 15
        mid_angle = longitude_to_svg_angle(mid_lon, asc_lon)
        gx, gy = polar_to_xy(cx, cy, r_label, mid_angle)

        # Tangent rotation: text reads along the arc (perpendicular to radius).
        # In our coord system (0=right, CCW+), tangent CCW = mid_angle + 90.
        # SVG rotate is CW, so negate: rotation = -(mid_angle + 90).
        rot = -(mid_angle + 90)
        # Normalize to [-180, 180]
        rot = ((rot + 180) % 360) - 180
        # If text would be upside-down (rotation beyond ±90), flip 180°
        if rot > 90:
            rot -= 180
        elif rot < -90:
            rot += 180

        parts.append(
            f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="DM Sans, sans-serif" '
            f'transform="rotate({rot:.1f} {gx:.1f} {gy:.1f})">'
            f'<tspan fill="{color}" font-size="14">{glyph}</tspan>'
            f'<tspan dx="2" fill="#8a8178" font-size="8" letter-spacing="1">{sign_upper}</tspan>'
            f'</text>'
        )

    # --- Inner circle ---
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="none" stroke="#2e2a24" stroke-width="0.5"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="#2e2a24" stroke-width="1"/>')

    # --- House cusp lines ---
    houses = western_data["houses"]
    for num_str, cusp in houses.items():
        cusp_lon = sign_degree_to_longitude(cusp["sign"], cusp["degree"])
        angle = longitude_to_svg_angle(cusp_lon, asc_lon)

        is_angular = num_str in ("1", "4", "7", "10")
        r_end = r_outer if is_angular else r_house
        width = "1.5" if is_angular else "0.5"
        color = "#c9a84c" if is_angular else "#2e2a24"

        x2, y2 = polar_to_xy(cx, cy, r_end, angle)
        parts.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}"/>'
        )

        # House number label
        next_num = int(num_str) % 12 + 1
        next_cusp = houses[str(next_num)]
        next_lon = sign_degree_to_longitude(next_cusp["sign"], next_cusp["degree"])
        diff = (next_lon - cusp_lon) % 360
        mid_lon = (cusp_lon + diff / 2) % 360
        mid_angle = longitude_to_svg_angle(mid_lon, asc_lon)
        hx, hy = polar_to_xy(cx, cy, r_inner - 20, mid_angle)
        parts.append(
            f'<text x="{hx:.1f}" y="{hy:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" fill="#5c564e" font-size="10" '
            f'font-family="DM Sans, sans-serif">{num_str}</text>'
        )

    # --- Planets ---
    planets = western_data["planets"]
    planet_positions = {}

    valid_planets = []
    for name, data in planets.items():
        if data.get("degree") is None or data.get("sign") is None:
            continue
        lon = sign_degree_to_longitude(data["sign"], data["degree"])
        valid_planets.append((name, lon))

    valid_planets.sort(key=lambda x: x[1])
    placed_angles = []
    MIN_SPREAD = 8

    for name, lon in valid_planets:
        angle = longitude_to_svg_angle(lon, asc_lon)

        adjusted = angle
        for placed in placed_angles:
            if abs((adjusted - placed + 180) % 360 - 180) < MIN_SPREAD:
                adjusted = placed - MIN_SPREAD

        placed_angles.append(adjusted)
        planet_positions[name] = (angle, lon)
        pdata = planets[name]

        px, py = polar_to_xy(cx, cy, r_planet, adjusted)
        glyph = PLANET_GLYPHS.get(name, "?")
        label = PLANET_LABELS.get(name, name)

        parts.append(
            f'<text x="{px:.1f}" y="{py:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" fill="#e5ddd0" font-size="15" '
            f'style="cursor:default">'
            f'<title>{label} {pdata["degree"]:.1f}\u00B0 {pdata["sign"]} (H{pdata["house"]})</title>'
            f'{glyph}</text>'
        )

        # Tick mark
        tx1, ty1 = polar_to_xy(cx, cy, r_inner, angle)
        tx2, ty2 = polar_to_xy(cx, cy, r_planet + 14, angle)
        parts.append(
            f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" '
            f'stroke="#2e2a24" stroke-width="0.5"/>'
        )

    # --- Aspect lines (top 8 tightest) ---
    aspects = western_data.get("natal_aspects", [])
    sorted_aspects = sorted(aspects, key=lambda a: a["orb"])[:8]

    for asp in sorted_aspects:
        p1 = asp["planet1"]
        p2 = asp["planet2"]
        if p1 not in planet_positions or p2 not in planet_positions:
            continue

        angle1, _ = planet_positions[p1]
        angle2, _ = planet_positions[p2]

        x1, y1 = polar_to_xy(cx, cy, r_aspect, angle1)
        x2, y2 = polar_to_xy(cx, cy, r_aspect, angle2)

        style = ASPECT_STYLES.get(asp["aspect"], {"color": "#5c564e", "dash": ""})
        opacity = max(0.25, 0.8 - asp["orb"] / 10.0)
        dash = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ""

        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{style["color"]}" stroke-width="1" opacity="{opacity:.2f}"{dash}>'
            f'<title>{PLANET_LABELS.get(p1, p1)} {asp["aspect"]} '
            f'{PLANET_LABELS.get(p2, p2)} ({asp["orb"]}\u00B0)</title></line>'
        )

    # --- ASC / MC labels ---
    asc_angle = longitude_to_svg_angle(asc_lon, asc_lon)
    ax, ay = polar_to_xy(cx, cy, r_outer + 10, asc_angle)
    parts.append(
        f'<text x="{ax:.1f}" y="{ay:.1f}" text-anchor="end" '
        f'fill="#c9a84c" font-size="12" font-weight="bold" '
        f'font-family="DM Sans, sans-serif">ASC</text>'
    )

    mc_lon = sign_degree_to_longitude(western_data["midheaven"]["sign"],
                                       western_data["midheaven"]["degree"])
    mc_angle = longitude_to_svg_angle(mc_lon, asc_lon)
    mx, my = polar_to_xy(cx, cy, r_outer + 10, mc_angle)
    parts.append(
        f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
        f'fill="#c9a84c" font-size="12" font-weight="bold" '
        f'font-family="DM Sans, sans-serif">MC</text>'
    )

    parts.append('</svg>')
    return "\n".join(parts)


# ============================================================
# PLANET TABLE
# ============================================================

def generate_planet_table_html(western_data):
    """Generate a clean planet placement table."""
    planets = western_data["planets"]
    # Display order
    order = ["sun", "moon", "mercury", "venus", "mars", "jupiter",
             "saturn", "uranus", "neptune", "pluto", "north_node", "chiron"]

    rows = []
    for name in order:
        data = planets.get(name)
        if not data or data.get("degree") is None:
            continue

        glyph = PLANET_GLYPHS.get(name, "")
        label = PLANET_LABELS.get(name, name)
        sign = data["sign"]
        degree = data["degree"]
        house = data["house"]
        element = SIGN_ELEMENTS.get(sign, "fire")
        elem_color = ELEMENT_COLORS[element]
        elem_emoji = WESTERN_ELEMENT_EMOJIS.get(element, "")

        rows.append(
            f'<tr>'
            f'<td class="pt-glyph">{glyph}</td>'
            f'<td class="pt-name">{label}</td>'
            f'<td class="pt-pos"><span style="color:{elem_color}">'
            f'{degree:.1f}\u00B0 {sign}</span> {elem_emoji}</td>'
            f'<td class="pt-house">House {house}</td>'
            f'</tr>'
        )

    return (
        '<table class="planet-table">'
        '<tbody>' + "\n".join(rows) + '</tbody>'
        '</table>'
    )


# ============================================================
# ASPECTS TABLE
# ============================================================

def generate_aspects_html(western_data):
    """Generate a clean aspects grid."""
    aspects = western_data.get("natal_aspects", [])
    sorted_aspects = sorted(aspects, key=lambda a: a["orb"])

    items = []
    for asp in sorted_aspects:
        p1 = asp["planet1"]
        p2 = asp["planet2"]
        aspect_name = asp["aspect"]
        orb = asp["orb"]

        g1 = PLANET_GLYPHS.get(p1, "?")
        g2 = PLANET_GLYPHS.get(p2, "?")
        l1 = PLANET_LABELS.get(p1, p1)
        l2 = PLANET_LABELS.get(p2, p2)

        style = ASPECT_STYLES.get(aspect_name, {"symbol": "?", "type": "neutral", "color": "#5c564e"})
        symbol = style["symbol"]
        asp_type = style["type"]
        color = style["color"]

        items.append(
            f'<div class="aspect-item">'
            f'<span class="aspect-glyphs">{g1} '
            f'<span style="color:{color}">{symbol}</span> {g2}</span>'
            f'<span class="aspect-desc">{l1} {aspect_name} {l2}</span>'
            f'<span class="aspect-orb">{orb:.1f}\u00B0</span>'
            f'</div>'
        )

    return '<div class="aspects-grid">' + "\n".join(items) + '</div>'


# ============================================================
# BAZI PILLARS HTML
# ============================================================

def generate_bazi_pillars_html(bazi_data):
    """Generate HTML for BaZi four pillars and luck pillar timeline."""
    pillars = bazi_data["pillars"]
    day_master = bazi_data["day_master"]
    luck_pillars = bazi_data.get("luck_pillars", [])
    current_lp = bazi_data.get("current_luck_pillar", {})
    current_lp_num = current_lp.get("number")

    parts = []
    parts.append('<div class="bazi-section">')

    # Four Pillars
    parts.append('<div class="pillars-grid">')
    for pillar_name in ["Year", "Month", "Day", "Hour"]:
        key = pillar_name.lower()
        p = pillars[key]
        stem = p["stem"]
        branch = p["branch"]
        animal = BRANCH_ANIMALS.get(branch, "")
        animal_emoji = BRANCH_EMOJIS.get(branch, "")

        stem_elem = STEM_ELEMENTS.get(stem, "earth")
        branch_elem = BRANCH_ELEMENTS.get(branch, "earth")
        stem_color = BAZI_ELEMENT_COLORS[stem_elem]
        branch_color = BAZI_ELEMENT_COLORS[branch_elem]
        stem_emoji = BAZI_ELEMENT_EMOJIS.get(stem_elem, "")
        stem_chinese = STEM_CHINESE.get(stem, "")

        is_day = key == "day"
        highlight = ' pillar-highlight' if is_day else ''

        parts.append(
            f'<div class="pillar{highlight}">'
            f'<div class="pillar-label">{pillar_name}</div>'
            f'<div class="pillar-stem" style="color:{stem_color}">'
            f'{stem} {stem_chinese} {stem_emoji}</div>'
            f'<div class="pillar-divider"></div>'
            f'<div class="pillar-branch" style="color:{branch_color}">'
            f'{branch} {animal_emoji}</div>'
            f'<div class="pillar-animal">{animal}</div>'
            f'</div>'
        )
    parts.append('</div>')

    # Luck Pillars timeline
    if luck_pillars:
        parts.append('<div class="luck-section">')
        parts.append('<div class="luck-title">Luck Pillars</div>')
        parts.append('<div class="luck-grid">')
        for lp in luck_pillars:
            is_current = lp.get("number") == current_lp_num
            highlight = ' lp-current' if is_current else ''
            stem_elem = STEM_ELEMENTS.get(lp["stem"], "earth")
            stem_color = BAZI_ELEMENT_COLORS[stem_elem]
            branch = lp["branch"]
            animal_emoji = BRANCH_EMOJIS.get(branch, "")

            parts.append(
                f'<div class="luck-pillar{highlight}">'
                f'<div class="lp-animal-emoji">{animal_emoji}</div>'
                f'<div class="lp-stem" style="color:{stem_color}">'
                f'{lp["stem"]} {lp["branch"]}</div>'
                f'<div class="lp-animal">{lp["animal"]}</div>'
                f'<div class="lp-ages">{lp["ages"]}</div>'
                f'</div>'
            )
        parts.append('</div>')

        # Current luck pillar description
        if current_lp.get("themes"):
            parts.append(
                f'<div class="lp-themes">'
                f'<strong>Current: {current_lp.get("description", "")}</strong><br>'
                f'{current_lp["themes"]}</div>'
            )

        parts.append('</div>')

    parts.append('</div>')
    return "\n".join(parts)


# ============================================================
# KEY SIGNATURES BANNER
# ============================================================

def generate_signatures_html(western_data, bazi_data):
    """Generate the key signatures summary banner."""
    planets = western_data["planets"]
    asc = western_data["ascendant"]
    day_master = bazi_data["day_master"]
    zodiac_animal = bazi_data.get("zodiac_animal", "")

    sun = planets.get("sun", {})
    moon = planets.get("moon", {})

    sun_glyph = PLANET_GLYPHS["sun"]
    moon_glyph = PLANET_GLYPHS["moon"]

    dm_elem = day_master["element"]
    dm_color = BAZI_ELEMENT_COLORS.get(dm_elem, "#b8963e")
    dm_emoji = BAZI_ELEMENT_EMOJIS.get(dm_elem, "")
    dm_chinese = day_master.get("chinese", "")

    # Get zodiac animal emoji from year branch
    year_branch = bazi_data["pillars"]["year"]["branch"]
    year_emoji = BRANCH_EMOJIS.get(year_branch, "")

    items = []

    if sun.get("sign"):
        items.append(f'{sun_glyph} {sun["degree"]:.0f}\u00B0 {sun["sign"]}')
    if moon.get("sign"):
        items.append(f'{moon_glyph} {moon["degree"]:.0f}\u00B0 {moon["sign"]}')
    items.append(f'ASC {asc["degree"]:.0f}\u00B0 {asc["sign"]}')

    western_line = '  \u00B7  '.join(items)

    dm_polarity = day_master.get("polarity", "")
    bazi_line = (
        f'<span style="color:{dm_color}">Day Master: {day_master["stem"]} '
        f'{dm_chinese} ({dm_polarity} {dm_elem}) {dm_emoji}</span>'
        f'  \u00B7  {year_emoji} {zodiac_animal}'
    )

    return (
        f'<div class="signatures">'
        f'<div class="sig-western">{western_line}</div>'
        f'<div class="sig-bazi">{bazi_line}</div>'
        f'</div>'
    )


# ============================================================
# CSS
# ============================================================

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@400;500;600&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    background: #13110e;
    color: #e5ddd0;
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    padding: 40px 24px;
    min-height: 100vh;
    background-image: radial-gradient(ellipse at 50% 0%, #1f1b16 0%, #13110e 60%);
}

body > * {
    animation: fadeIn 0.6s ease-out both;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

.header {
    text-align: center;
    margin-bottom: 12px;
}
.header h1 {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 32px;
    font-weight: 600;
    color: #c9a84c;
    margin-bottom: 6px;
    letter-spacing: 1px;
}
.header .meta {
    font-size: 13px;
    color: #8a8178;
    letter-spacing: 0.3px;
}

/* Signatures Banner */
.signatures {
    text-align: center;
    padding: 16px 24px;
    margin: 20px auto 32px;
    max-width: 800px;
    border-top: 1px solid #2e2a24;
    border-bottom: 1px solid #2e2a24;
}
.sig-western {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 18px;
    color: #e5ddd0;
    margin-bottom: 6px;
    letter-spacing: 0.5px;
}
.sig-bazi {
    font-size: 13px;
    color: #8a8178;
}

/* Main Grid */
.charts {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 48px;
    max-width: 1280px;
    margin: 0 auto;
    align-items: start;
}
.chart-panel {
    min-width: 0;
}
.panel-title {
    text-align: center;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 15px;
    color: #5c564e;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 3px;
}
.panel-subtitle {
    text-align: center;
    font-size: 12px;
    color: #5c564e;
    max-width: 420px;
    margin: 0 auto 20px;
    line-height: 1.5;
}

/* Planet Table */
.planet-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 24px;
}
.planet-table td {
    padding: 7px 8px;
    border-bottom: 1px solid #1c1915;
    font-size: 13px;
    vertical-align: middle;
}
.planet-table tr:hover {
    background: #1c1915;
}
.pt-glyph {
    font-size: 16px;
    width: 28px;
    text-align: center;
    color: #e5ddd0;
}
.pt-name {
    color: #8a8178;
    width: 70px;
}
.pt-pos {
    color: #e5ddd0;
}
.pt-house {
    color: #5c564e;
    text-align: right;
    font-size: 12px;
}

/* BaZi Section */
.bazi-section { padding: 8px 0; }
.pillars-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 28px;
}
.pillar {
    text-align: center;
    padding: 20px 8px 16px;
    border: 1px solid #2e2a24;
    border-radius: 10px;
    background: #1c1915;
}
.pillar-highlight {
    border-color: #c9a84c;
    background: #201c15;
    box-shadow: 0 0 12px rgba(201, 168, 76, 0.08);
}
.pillar-label {
    font-size: 10px;
    color: #5c564e;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 12px;
}
.pillar-stem {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
}
.pillar-divider {
    width: 24px;
    height: 1px;
    background: #2e2a24;
    margin: 0 auto 8px;
}
.pillar-branch {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 4px;
}
.pillar-animal {
    font-size: 11px;
    color: #8a8178;
    margin-top: 4px;
}

/* Luck Pillars */
.luck-section { margin-top: 8px; }
.luck-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 13px;
    color: #5c564e;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 14px;
    text-align: center;
}
.luck-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
    gap: 8px;
    margin-bottom: 16px;
}
.luck-pillar {
    text-align: center;
    padding: 12px 4px 10px;
    border: 1px solid #2e2a24;
    border-radius: 8px;
    background: #1c1915;
}
.lp-current {
    border-color: #c9a84c;
    background: #201c15;
}
.lp-animal-emoji { font-size: 18px; margin-bottom: 4px; }
.lp-stem { font-size: 12px; font-weight: 600; margin: 4px 0 2px; }
.lp-animal { font-size: 10px; color: #8a8178; }
.lp-ages { font-size: 10px; color: #5c564e; margin-top: 2px; }
.lp-themes {
    font-size: 13px;
    color: #8a8178;
    padding: 12px;
    border-left: 2px solid #c9a84c;
    margin-top: 12px;
    line-height: 1.6;
}

/* Aspects Section */
.aspects-section {
    max-width: 1280px;
    margin: 40px auto 0;
    border-top: 1px solid #2e2a24;
    padding-top: 28px;
}
.aspects-section-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 15px;
    color: #5c564e;
    text-transform: uppercase;
    letter-spacing: 3px;
    text-align: center;
    margin-bottom: 20px;
}
.aspects-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 32px;
    max-width: 800px;
    margin: 0 auto;
}
.aspect-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 13px;
}
.aspect-item:hover {
    background: #1c1915;
}
.aspect-glyphs {
    font-size: 14px;
    min-width: 56px;
    color: #e5ddd0;
}
.aspect-desc {
    color: #8a8178;
    flex: 1;
    font-size: 12px;
}
.aspect-orb {
    color: #5c564e;
    font-size: 11px;
    min-width: 36px;
    text-align: right;
}

@media (max-width: 860px) {
    .charts { grid-template-columns: 1fr; }
    .aspects-grid { grid-template-columns: 1fr; }
    body { padding: 20px 12px; }
    .header h1 { font-size: 26px; }
}
"""


# ============================================================
# HTML ASSEMBLY
# ============================================================

def create_chart_visualization(chart_json_path):
    """
    Read chart JSON and generate a self-contained HTML visualization.

    Args:
        chart_json_path: path to chart_data/<name>.json

    Returns:
        Path to the generated HTML file.
    """
    chart_json_path = Path(chart_json_path)
    with open(chart_json_path) as f:
        data = json.load(f)

    user = data["user"]
    western = data["western"]
    bazi = data["bazi"]

    # Generate components
    wheel_svg = generate_western_wheel_svg(western)
    planet_table = generate_planet_table_html(western)
    bazi_html = generate_bazi_pillars_html(bazi)
    signatures = generate_signatures_html(western, bazi)
    aspects_html = generate_aspects_html(western)

    # Header info
    name = user["name"]
    birth_date = user["birth_date"]
    birth_time = user["birth_time_clock"]
    location = user["location"]
    tz = user.get("timezone", "")

    # House system label
    house_system = western.get("house_system", "Placidus")
    western_label = f"Western Tropical \u00B7 {house_system}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Natal Chart \u2014 {escape_html(name)}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="header">
<h1>{escape_html(name)}</h1>
<div class="meta">{escape_html(birth_date)} at {escape_html(birth_time)} \u2014 {escape_html(location["city"])}, {escape_html(location["country"])} \u2014 {escape_html(tz)}</div>
</div>

{signatures}

<div class="charts">
<div class="chart-panel">
<div class="panel-title">{escape_html(western_label)}</div>
<div class="panel-subtitle">Sun, Moon, and planets mapped to the zodiac at the moment of birth. {escape_html(house_system)} houses divide the sky by time and latitude.</div>
{wheel_svg}
{planet_table}
</div>
<div class="chart-panel">
<div class="panel-title">BaZi Four Pillars</div>
<div class="panel-subtitle">Each pillar pairs a heavenly stem (element + yin/yang) with an earthly branch (one of 12 animals). The stem on top of the Day Pillar is your Day Master \u2014 your core elemental identity, distinct from your zodiac animal year.</div>
{bazi_html}
</div>
</div>

<div class="aspects-section">
<div class="aspects-section-title">Natal Aspects</div>
{aspects_html}
</div>

</body>
</html>"""

    # Save alongside the JSON
    output_dir = chart_json_path.parent
    filename = chart_json_path.stem + "_chart.html"
    output_path = output_dir / filename
    with open(output_path, "w") as f:
        f.write(html)

    return str(output_path)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate natal chart visualization")
    parser.add_argument("--chart", required=True, help="Path to chart JSON file")
    parser.add_argument("--open", action="store_true", help="Open in browser after generating")
    args = parser.parse_args()

    html_path = create_chart_visualization(args.chart)
    print(f"Chart saved to: {html_path}")

    if args.open:
        webbrowser.open(f"file://{os.path.abspath(html_path)}")
