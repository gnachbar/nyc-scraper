"""
Distance utilities, including Haversine miles and home coord parsing.
"""

import math
import os
from typing import Tuple, Optional


EARTH_RADIUS_MI = 3958.7613


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute great-circle distance between two lat/lon points in miles.
    Uses Haversine formula with earth radius EARTH_RADIUS_MI.
    """
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_MI * c


def parse_home_coords(env_value: Optional[str] = None) -> Tuple[float, float]:
    """
    Parse HOME_COORDS env var formatted as "lat,lon" into floats.
    Falls back to environment if env_value is None.
    """
    value = env_value if env_value is not None else os.getenv("HOME_COORDS")
    if not value:
        raise ValueError("HOME_COORDS not set. Expected format: 'lat,lon'")
    parts = [p.strip() for p in value.split(',')]
    if len(parts) != 2:
        raise ValueError("Invalid HOME_COORDS format. Expected 'lat,lon'")
    return float(parts[0]), float(parts[1])


