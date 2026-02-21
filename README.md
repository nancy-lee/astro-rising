# Astro Rising

A dual-system astrology reading tool combining Western tropical astrology and Chinese BaZi (Four Pillars of Destiny). Clone it, install one dependency, open Claude Code, and it becomes your astrologer.

## Setup

```bash
git clone https://github.com/nancy-lee/astro-rising.git
cd astro-rising
./setup.sh
claude
```

That's it. On first session, Claude asks about your familiarity with astrology, then asks for your birth details (name, date, time, place — all at once). It computes your full natal chart in the background and introduces you to your chart at whatever depth matches your experience level. Then ask for a reading whenever you're ready.

### Requirements

- Python 3.9+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

`setup.sh` creates a virtual environment, installs dependencies ([pyswisseph](https://pypi.org/project/pyswisseph/) + [timezonefinder](https://pypi.org/project/timezonefinder/)), and downloads Swiss Ephemeris data files.

## Two Systems, One Chart

Western astrology and Chinese BaZi both start from the same birth moment, but they read it through different lenses. Western astrology maps the sky — where the planets were, what signs they occupied, how they angled against each other. BaZi maps the calendar — what combination of elemental energies defined the year, month, day, and hour of your birth.

They're not competing systems. A Western chart tells you about psychological patterns, relationship dynamics, and life themes through planetary symbolism. A BaZi chart tells you about your elemental constitution, the timing of life phases, and how your energy interacts with the world around you. Used together, they catch things the other misses.

## Western Astrology

The Western chart computes tropical planetary positions (Sun through Pluto, plus Chiron and the North Node), house cusps, and aspects between planets.

**Signs and degrees** describe *what* energy a planet carries. Your Sun at 20° Leo is 20° Leo regardless of house system — this never changes.

**Houses** describe *where* that energy shows up in your life. This is where the two available house systems diverge:

- **Placidus** (default) — Divides the sky into unequal houses based on your birth latitude and exact birth time. The most widely used system in modern consultative astrology. House sizes vary — some are large, some compressed — which creates emphasis patterns unique to your chart.

- **Whole Sign** — Each house is exactly one zodiac sign, starting from your Ascendant's sign. The oldest house system (Hellenistic era), and what Co-Star, Chani, and most modern Hellenistic practitioners use. Simpler and more symmetrical — every house is 30°.

Both systems produce the same Ascendant, the same planetary signs and degrees, and the same aspects. They disagree on which *house* a planet falls in, which changes interpretation of where that planet's energy is most active. Neither is wrong — they're different framing choices.

**Aspects** are angular relationships between planets (conjunction, sextile, square, trine, opposition). These are the same in both house systems.

## Chinese BaZi (Four Pillars)

BaZi reads the birth moment as four pillars — year, month, day, and hour — each composed of a Heavenly Stem and an Earthly Branch. Together, the eight characters (ba zi, 八字) describe your elemental makeup.

**Day Master** — The stem of your day pillar. This is the "self" of the chart: your elemental core. A Ji (yin earth) Day Master has a different relationship to the world than a Ren (yang water) Day Master, even if they share the same Western Sun sign.

**Four Pillars** — Year (social generation, ancestors), month (career, parents), day (self, spouse), hour (children, later life). Each pillar carries an element and an animal, and the interactions between them — clashes, combinations, harms — shape the chart's dynamics.

**Luck Pillars** — Ten-year phases that shift the elemental environment around you. Knowing which Luck Pillar you're in tells you what kind of energy is available (or challenging) right now, independent of transits.

**Solar time, not clock time.** BaZi uses Local Mean Time (LMT) — the sun-based time at your exact longitude — not whatever the clock said. If you were born in western China, your LMT might differ from Beijing Standard Time by over an hour. The system computes this correction automatically.

**Solar terms, not calendar months.** BaZi months don't start on the 1st. They're defined by the Sun's ecliptic longitude — specifically the Jie (节) solar term boundaries. Li Chun (Spring Begins, 315° longitude) starts the Tiger month, and so on through the year. The computation derives these from the Swiss Ephemeris.

## Architecture

```
compute/
  bazi.py              BaZi Four Pillars computation engine
  calendar.py          Date utilities, solar terms, LMT correction
  western.py           Swiss Ephemeris wrapper (positions, houses, aspects)
  create_chart.py      Chart creation library (called by onboard agent)
  generate_context.py  Reading context orchestrator (called by reading agent)

chart_data/
  sample.json          Example chart (fictional, for testing)
  <yourname>.json      Your natal chart (private, gitignored)

.claude/
  agents/onboard.md    First-session chart creation + introduction
  agents/reading.md    Reading generation from transits + natal chart
  settings.json        Permissions for computation commands
```
