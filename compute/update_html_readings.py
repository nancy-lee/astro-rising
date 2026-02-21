"""
Patch readings log into an existing chart HTML file.

Reads chart_data/<name>_readings.json and replaces (or inserts) a
<section id="readings-log"> block in chart_data/<name>_chart.html.
Entries are shown newest-first: summary visible, full text collapsible.

Usage:
    python3 compute/update_html_readings.py --user <name>
"""

import argparse
import json
import re
from pathlib import Path


# ============================================================
# CSS injected once if missing from the document
# ============================================================

READINGS_CSS = """
/* Readings Log */
.readings-log {
    max-width: 860px;
    margin: 48px auto 0;
    border-top: 1px solid #2e2a24;
    padding-top: 32px;
    padding-bottom: 48px;
}
.readings-log-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 15px;
    color: #5c564e;
    text-transform: uppercase;
    letter-spacing: 3px;
    text-align: center;
    margin-bottom: 28px;
}
.reading-entry {
    margin-bottom: 24px;
    border: 1px solid #2e2a24;
    border-radius: 10px;
    background: #1c1915;
    overflow: hidden;
}
.reading-entry-header {
    display: flex;
    align-items: baseline;
    gap: 16px;
    padding: 14px 20px 12px;
    border-bottom: 1px solid #2e2a24;
}
.reading-entry-date {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 17px;
    color: #c9a84c;
    font-weight: 600;
}
.reading-entry-type {
    font-size: 11px;
    color: #5c564e;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
.reading-entry-themes {
    font-size: 11px;
    color: #5c564e;
    margin-left: auto;
    font-style: italic;
}
.reading-entry-summary {
    padding: 12px 20px;
    font-size: 14px;
    color: #a89e92;
    line-height: 1.6;
    border-bottom: 1px solid #2e2a24;
}
.reading-entry details {
    padding: 0;
}
.reading-entry details summary {
    padding: 10px 20px;
    font-size: 12px;
    color: #5c564e;
    cursor: pointer;
    user-select: none;
    letter-spacing: 0.3px;
    list-style: none;
}
.reading-entry details summary::-webkit-details-marker { display: none; }
.reading-entry details summary::before {
    content: '▸ ';
    color: #c9a84c;
    font-size: 10px;
}
.reading-entry details[open] summary::before {
    content: '▾ ';
}
.reading-entry details summary:hover { color: #8a8178; }
.reading-full-text {
    padding: 16px 20px 20px;
    font-size: 14px;
    color: #e5ddd0;
    line-height: 1.75;
    white-space: pre-wrap;
    border-top: 1px solid #2e2a24;
}
"""


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def build_readings_section(entries: list) -> str:
    """Build the full <section id="readings-log"> HTML block."""
    if not entries:
        return ""

    # Newest first
    sorted_entries = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)

    parts = ['<section id="readings-log">']
    parts.append('<div class="readings-log">')
    parts.append('<div class="readings-log-title">Reading History</div>')

    for entry in sorted_entries:
        date = escape_html(entry.get("date", ""))
        rtype = escape_html(entry.get("type", "").capitalize())
        summary = escape_html(entry.get("summary", ""))
        full_text = escape_html(entry.get("full_text", ""))
        themes = entry.get("themes", [])
        themes_str = escape_html("  ·  ".join(themes[:5])) if themes else ""
        entry_id = escape_html(entry.get("id", ""))

        parts.append(f'<div class="reading-entry" id="{entry_id}">')
        parts.append('<div class="reading-entry-header">')
        parts.append(f'<span class="reading-entry-date">{date}</span>')
        parts.append(f'<span class="reading-entry-type">{rtype}</span>')
        if themes_str:
            parts.append(f'<span class="reading-entry-themes">{themes_str}</span>')
        parts.append('</div>')

        if summary:
            parts.append(f'<div class="reading-entry-summary">{summary}</div>')

        if full_text:
            parts.append('<details>')
            parts.append('<summary>Read full reading →</summary>')
            parts.append(f'<div class="reading-full-text">{full_text}</div>')
            parts.append('</details>')

        parts.append('</div>')

    parts.append('</div>')
    parts.append('</section>')

    return "\n".join(parts)


def inject_css_if_missing(html: str) -> str:
    """Add readings CSS to <style> block if not already present."""
    if "readings-log" in html:
        # Already has readings CSS
        return html
    # Insert before closing </style>
    return html.replace("</style>", READINGS_CSS + "\n</style>", 1)


def patch_html(html: str, readings_section: str) -> str:
    """Replace existing readings section or insert before </body>."""
    pattern = re.compile(
        r'<section id="readings-log">.*?</section>',
        re.DOTALL,
    )
    if pattern.search(html):
        html = pattern.sub(readings_section, html)
    else:
        html = html.replace("</body>", readings_section + "\n</body>", 1)
    return html


def main():
    parser = argparse.ArgumentParser(description="Update readings log in chart HTML")
    parser.add_argument("--user", required=True, help="User name (matches chart_data/<name>_*.json)")
    args = parser.parse_args()

    name = args.user
    chart_dir = Path("chart_data")

    readings_path = chart_dir / f"{name}_readings.json"
    html_path = chart_dir / f"{name}_chart.html"

    if not readings_path.exists():
        print(f"No readings file found at {readings_path} — nothing to do.")
        return

    if not html_path.exists():
        print(f"No chart HTML found at {html_path} — cannot patch.")
        return

    with open(readings_path) as f:
        entries = json.load(f)

    with open(html_path) as f:
        html = f.read()

    readings_section = build_readings_section(entries)
    if not readings_section:
        print("No reading entries to display.")
        return

    html = inject_css_if_missing(html)
    html = patch_html(html, readings_section)

    with open(html_path, "w") as f:
        f.write(html)

    print(f"Readings log updated in {html_path} ({len(entries)} entries).")


if __name__ == "__main__":
    main()
