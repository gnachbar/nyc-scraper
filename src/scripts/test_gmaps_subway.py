#!/usr/bin/env python3
"""
Quick tester for Google Distance Matrix (transit=subway) between HOME_COORDS and a destination.

Usage examples:
  GOOGLE_MAPS_API_KEY=... HOME_COORDS="40.68,-73.97" \
    python src/scripts/test_gmaps_subway.py --dest "Kings Theatre Brooklyn"

Optional args:
  --dest-lat 40.650 --dest-lng -73.956   # skip geocoding and use explicit coords
  --departure-time now                    # or unix timestamp seconds
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

# Ensure project root is importable so `import src.*` works
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from dotenv import load_dotenv
load_dotenv(dotenv_path=str(PROJECT_ROOT / ".env"), override=False)

from src.config import Config
from src.transforms.distances import parse_home_coords
from src.lib.google_maps import geocode_place, distance_times, GoogleMapsError, _distance_matrix  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Google DM subway travel time")
    parser.add_argument("--dest", type=str, default="Kings Theatre Brooklyn",
                        help="Destination place text to geocode (default: Kings Theatre Brooklyn)")
    parser.add_argument("--dest-lat", type=float, default=None,
                        help="Destination latitude (skip geocoding if provided)")
    parser.add_argument("--dest-lng", type=float, default=None,
                        help="Destination longitude (skip geocoding if provided)")
    parser.add_argument("--departure-time", type=str, default="now",
                        help="Departure time for driving/transit (e.g. 'now' or unix seconds)")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        home_lat, home_lng = parse_home_coords(Config.HOME_COORDS)
    except Exception as e:
        print(f"HOME_COORDS not configured or invalid: {e}")
        sys.exit(1)

    dest_lat: Optional[float] = args.dest_lat
    dest_lng: Optional[float] = args.dest_lng
    dest_label = args.dest

    if dest_lat is None or dest_lng is None:
        try:
            geo = geocode_place(dest_label)
            if not geo:
                print(f"Geocoding failed for '{dest_label}'")
                sys.exit(2)
            dest_lat = float(geo["lat"])  # type: ignore[index]
            dest_lng = float(geo["lng"])  # type: ignore[index]
            print(f"Geocoded '{dest_label}' -> ({dest_lat:.6f}, {dest_lng:.6f})")
        except GoogleMapsError as ge:
            print(f"Geocode error: {ge}")
            sys.exit(2)

    origin: Tuple[float, float] = (home_lat, home_lng)
    dest: Tuple[float, float] = (dest_lat, dest_lng)  # type: ignore[arg-type]

    print(f"Origin (HOME_COORDS): ({origin[0]:.6f}, {origin[1]:.6f})")
    print(f"Destination: ({dest[0]:.6f}, {dest[1]:.6f})")
    print(f"Departure time: {args.departure_time}")

    try:
        # Specific subway time using transit_mode=subway
        subway_min = _distance_matrix(origin, dest, mode="transit", transit_mode="subway", departure_time=args.departure_time)
        # Also compute other modes for comparison
        times = distance_times(origin, dest)
    except GoogleMapsError as ge:
        print(f"Distance Matrix error: {ge}")
        sys.exit(3)

    print("\n== Results ==")
    print(f"Subway minutes (transit_mode=subway): {subway_min}")
    print(f"Driving minutes: {times.get('driving_time_min')}")
    print(f"Walking minutes: {times.get('walking_time_min')}")
    print(f"Subway minutes (via distance_times): {times.get('subway_time_min')}")


if __name__ == "__main__":
    main()


