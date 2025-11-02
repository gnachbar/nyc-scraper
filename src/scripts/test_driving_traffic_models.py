import sys
from typing import Tuple, Optional, Dict, Any

import requests

from src.config import Config  # loads .env on import
from src.lib.google_maps import geocode_place


def _query_distance_matrix(
    origin: Tuple[float, float],
    dest: Tuple[float, float],
    traffic_model: str,
) -> Optional[int]:
    """
    Call Google Distance Matrix for driving with departure_time=now and a specific traffic_model.
    Returns duration_in_traffic in whole minutes, or None.
    """
    if not Config.GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set")

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params: Dict[str, Any] = {
        "origins": f"{origin[0]},{origin[1]}",
        "destinations": f"{dest[0]},{dest[1]}",
        "mode": "driving",
        "key": Config.GOOGLE_MAPS_API_KEY,
        "language": Config.GMAPS_LANGUAGE,
        "region": Config.GMAPS_REGION,
        "departure_time": "now",
        "traffic_model": traffic_model,
    }

    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        return None
    rows = data.get("rows") or []
    if not rows or not rows[0].get("elements"):
        return None
    elem = rows[0]["elements"][0]
    if elem.get("status") != "OK":
        return None
    dur = elem.get("duration_in_traffic") or elem.get("duration")
    if not dur:
        return None
    seconds = dur.get("value")
    if not isinstance(seconds, (int, float)):
        return None
    return int(round(seconds / 60))


def _parse_coords(env_value: str) -> Tuple[float, float]:
    lat_str, lng_str = [p.strip() for p in env_value.split(",", 1)]
    return float(lat_str), float(lng_str)


def main() -> int:
    home_coords = Config.HOME_COORDS
    if not home_coords:
        print("ERROR: HOME_COORDS env var is required (format: 'lat,lng')", file=sys.stderr)
        return 1
    try:
        origin = _parse_coords(home_coords)
    except Exception:
        print("ERROR: HOME_COORDS must be in 'lat,lng' format", file=sys.stderr)
        return 1

    # Brooklyn Museum
    destination_query = "Brooklyn Museum, 200 Eastern Pkwy, Brooklyn, NY"
    dest_geo = geocode_place(destination_query)
    if not dest_geo:
        print("ERROR: Could not geocode destination.", file=sys.stderr)
        return 1
    dest = (dest_geo["lat"], dest_geo["lng"])

    results: Dict[str, Optional[int]] = {}
    for model in ("best_guess", "optimistic", "pessimistic"):
        minutes = _query_distance_matrix(origin, dest, model)
        results[model] = minutes

    print("Driving time (minutes) from HOME_COORDS to Brooklyn Museum:")
    for model in ("best_guess", "optimistic", "pessimistic"):
        val = results[model]
        print(f"  {model:12s}: {val if val is not None else 'N/A'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


