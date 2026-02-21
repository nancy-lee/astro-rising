"""
CLI wrapper for compute_and_save_chart().

Usage:
    python3 compute/run.py --name NAME --birth-date YYYY-MM-DD --birth-time HH:MM \
        --city CITY --country COUNTRY --latitude LAT --longitude LON --gender GENDER \
        [--utc-offset OFFSET] [--house-system SYSTEM]
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from compute.create_chart import compute_and_save_chart


def main():
    parser = argparse.ArgumentParser(description="Compute and save a natal chart.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--birth-date", required=True, dest="birth_date")
    parser.add_argument("--birth-time", required=True, dest="birth_time")
    parser.add_argument("--city", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--latitude", required=True, type=float)
    parser.add_argument("--longitude", required=True, type=float)
    parser.add_argument("--gender", required=True, choices=["male", "female"])
    parser.add_argument("--utc-offset", dest="utc_offset", type=float, default=None)
    parser.add_argument("--house-system", dest="house_system", default="placidus",
                        choices=["placidus", "whole_sign"])

    args = parser.parse_args()

    result = compute_and_save_chart(
        name=args.name,
        birth_date=args.birth_date,
        birth_time=args.birth_time,
        city=args.city,
        country=args.country,
        latitude=args.latitude,
        longitude=args.longitude,
        gender=args.gender,
        utc_offset=args.utc_offset,
        house_system=args.house_system,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
