#!/bin/bash
# Astro Rising — Setup

set -e

echo "=== Astro Rising Setup ==="
echo ""

# Check Python version
echo "Checking Python..."
PYTHON_VERSION=$(python3 --version 2>/dev/null || echo "not found")
if [[ "$PYTHON_VERSION" == "not found" ]]; then
    echo "ERROR: Python 3 is required but not found."
    echo "Install Python 3.9+ and try again."
    exit 1
fi
echo "  Found: $PYTHON_VERSION"

MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
if [[ "$MAJOR" -lt 3 ]] || [[ "$MAJOR" -eq 3 && "$MINOR" -lt 9 ]]; then
    echo "ERROR: Python 3.9+ required (found $PYTHON_VERSION)"
    exit 1
fi

# Create virtual environment
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q --disable-pip-version-check -r requirements.txt
echo "  Done."

# Download Swiss Ephemeris data files (for Chiron and minor bodies)
if [ ! -d "ephe" ] || [ ! -f "ephe/seas_18.se1" ]; then
    echo ""
    echo "Downloading Swiss Ephemeris data files..."
    mkdir -p ephe
    curl -sL "https://github.com/aloistr/swisseph/raw/master/ephe/seas_18.se1" -o ephe/seas_18.se1
    curl -sL "https://github.com/aloistr/swisseph/raw/master/ephe/semo_18.se1" -o ephe/semo_18.se1
    curl -sL "https://github.com/aloistr/swisseph/raw/master/ephe/sepl_18.se1" -o ephe/sepl_18.se1
    echo "  Done."
fi

# Verify imports
echo ""
echo "Verifying computation modules..."
python3 -c "import swisseph; print(f'  pyswisseph {swisseph.version} OK')"
python3 -c "from compute.bazi import compute_chart; print('  bazi.py OK')"
python3 -c "from compute.astro_calendar import day_of_week; print('  astro_calendar.py OK')"
python3 -c "from compute.western import planetary_positions; print('  western.py OK')"
python3 -c "from compute.create_chart import compute_and_save_chart; print('  create_chart.py OK')"

# Create chart_data directory
mkdir -p chart_data

echo ""
echo "=== Setup complete ==="
echo ""
echo "Open Claude Code in this directory and it will walk you"
echo "through creating your natal chart on first session."
