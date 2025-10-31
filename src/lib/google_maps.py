"""
Google Maps helper functions for geocoding venues.

This module avoids relying on src.config.Config to keep it decoupled from
any reverted/optional configuration; it reads env vars directly.

Functions:
- geocode_place(query) -> Optional[dict]
  Returns dict with {lat, lng, formatted_address, place_id, provider: 'google'} or None
"""

import os
import time
from typing import Optional, Dict, Any, Tuple, Union

import requests
from hashlib import sha1
from src.lib.cache import cache_get, cache_set
from src.config import Config


GOOGLE_MAPS_API_KEY = Config.GOOGLE_MAPS_API_KEY
GMAPS_REGION = Config.GMAPS_REGION
GMAPS_LANGUAGE = Config.GMAPS_LANGUAGE
HOME_COORDS = Config.HOME_COORDS


class GoogleMapsError(RuntimeError):
    pass


def _request_json(url: str, params: Dict[str, Any], retries: int = 3, backoff_sec: float = 0.8) -> Dict[str, Any]:
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            # Retry on common transient codes
            if resp.status_code in (408, 429, 500, 502, 503, 504):
                time.sleep(backoff_sec * (2 ** attempt))
                continue
            # Non-retryable
            raise GoogleMapsError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # network error
            last_exc = exc
            time.sleep(backoff_sec * (2 ** attempt))
    if last_exc:
        raise GoogleMapsError(str(last_exc))
    raise GoogleMapsError("Unknown Google Maps request failure")


def geocode_place(query: str, region: str = GMAPS_REGION, language: str = GMAPS_LANGUAGE) -> Optional[Dict[str, Any]]:
    """
    Geocode a venue name/address to coordinates using Google Geocoding API.

    Falls back to Places Text Search if Geocoding returns ZERO_RESULTS.

    Returns dict with keys: lat, lng, formatted_address, place_id, provider.
    Returns None if not found.
    """
    api_key = GOOGLE_MAPS_API_KEY
    if not api_key:
        raise GoogleMapsError("GOOGLE_MAPS_API_KEY not set")

    # Prefer Places Text Search with location bias near home to avoid wrong cities
    places_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    places_params = {
        "query": query,
        "key": api_key,
        "region": region,
        "language": language,
    }
    # Apply location bias if HOME_COORDS present
    try:
        if HOME_COORDS:
            lat_str, lng_str = [p.strip() for p in HOME_COORDS.split(',')]
            places_params["locationbias"] = f"circle:50000@{lat_str},{lng_str}"  # 50km bias around home
    except Exception:
        pass
    pdata = _request_json(places_url, places_params)
    pstatus = pdata.get("status")
    if pstatus == "OK" and pdata.get("results"):
        r0 = pdata["results"][0]
        loc = r0["geometry"]["location"]
        return {
            "lat": float(loc["lat"]),
            "lng": float(loc["lng"]),
            "formatted_address": r0.get("formatted_address"),
            "place_id": r0.get("place_id"),
            "provider": "google",
        }
    if pstatus in ("OVER_QUERY_LIMIT", "REQUEST_DENIED", "INVALID_REQUEST"):
        raise GoogleMapsError(f"Places error: {pstatus}")

    # Fallback: Geocoding API
    geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geo_params = {
        "address": query,
        "key": api_key,
        "region": region,
        "language": language,
    }
    data = _request_json(geo_url, geo_params)
    status = data.get("status")
    if status == "OK" and data.get("results"):
        r0 = data["results"][0]
        loc = r0["geometry"]["location"]
        return {
            "lat": float(loc["lat"]),
            "lng": float(loc["lng"]),
            "formatted_address": r0.get("formatted_address"),
            "place_id": r0.get("place_id"),
            "provider": "google",
        }
    if status in ("OVER_QUERY_LIMIT", "REQUEST_DENIED", "INVALID_REQUEST"):  # fail fast
        raise GoogleMapsError(f"Geocoding error: {status}")

    return None


def _distance_matrix(
    origin: Tuple[float, float],
    dest: Tuple[float, float],
    mode: str,
    transit_mode: Optional[str] = None,
    departure_time: Union[str, int] = "now",
    traffic_model: Optional[str] = None,
) -> Optional[int]:
    """
    Call Google Distance Matrix for a single mode; return duration in minutes or None.
    """
    api_key = GOOGLE_MAPS_API_KEY
    if not api_key:
        raise GoogleMapsError("GOOGLE_MAPS_API_KEY not set")

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params: Dict[str, Any] = {
        "origins": f"{origin[0]},{origin[1]}",
        "destinations": f"{dest[0]},{dest[1]}",
        "mode": mode,
        "key": api_key,
        "language": GMAPS_LANGUAGE,
        "region": GMAPS_REGION,
    }
    if mode in ("driving", "transit"):
        params["departure_time"] = departure_time
    if mode == "transit" and transit_mode:
        params["transit_mode"] = transit_mode
    if mode == "driving" and traffic_model:
        params["traffic_model"] = traffic_model

    # Cache key: rounded coords (4dp ~ 10-11m), mode, transit_mode, departure bucket (only when not 'now')
    departure_bucket = "now" if departure_time == "now" else str(departure_time)
    key_raw = (
        f"dm|{round(origin[0],4)},{round(origin[1],4)}|"
        f"{round(dest[0],4)},{round(dest[1],4)}|{mode}|{transit_mode or ''}|{departure_bucket}|{traffic_model or ''}"
    )
    key = sha1(key_raw.encode("utf-8")).hexdigest()
    cached = cache_get(key)
    if isinstance(cached, int):
        return cached

    data = _request_json(url, params)
    status = data.get("status")
    if status != "OK":
        if status == "ZERO_RESULTS":
            return None
        raise GoogleMapsError(f"Distance Matrix error: {status}")

    rows = data.get("rows") or []
    if not rows or not rows[0].get("elements"):
        return None
    elem = rows[0]["elements"][0]
    if elem.get("status") != "OK":
        return None
    dur = elem.get("duration_in_traffic") if mode == "driving" and "duration_in_traffic" in elem else elem.get("duration")
    if not dur:
        return None
    seconds = dur.get("value")
    if not isinstance(seconds, (int, float)):
        return None
    minutes = int(round(seconds / 60))
    cache_set(key, minutes)
    return minutes


def distance_times(
    origin: Tuple[float, float],
    dest: Tuple[float, float],
) -> Dict[str, Optional[int]]:
    """
    Compute travel times via Google Distance Matrix for driving, walking, and subway transit.
    Returns a dict with keys: driving_time_min, walking_time_min, subway_time_min.
    """
    driving_min = _distance_matrix(origin, dest, mode="driving")
    walking_min = _distance_matrix(origin, dest, mode="walking")
    # Prefer subway-only transit; if None, we could later fall back to generic transit
    subway_min = _distance_matrix(origin, dest, mode="transit", transit_mode="subway")
    return {
        "driving_time_min": driving_min,
        "walking_time_min": walking_min,
        "subway_time_min": subway_min,
    }


def driving_time_with_departure(
    origin: Tuple[float, float],
    dest: Tuple[float, float],
    departure_time_epoch: int,
    traffic_model: str = "best_guess",
) -> Optional[int]:
    """
    Return driving time in minutes for a specific future departure time.

    Uses Google Distance Matrix with duration_in_traffic and the provided
    traffic_model (default 'best_guess').
    """
    return _distance_matrix(
        origin,
        dest,
        mode="driving",
        transit_mode=None,
        departure_time=departure_time_epoch,
        traffic_model=traffic_model,
    )


def subway_time_with_departure(
    origin: Tuple[float, float],
    dest: Tuple[float, float],
    departure_time_epoch: int,
) -> Optional[int]:
    """
    Return subway transit time in minutes for a specific future departure time.

    Uses Google Distance Matrix with transit mode set to subway only.
    """
    return _distance_matrix(
        origin,
        dest,
        mode="transit",
        transit_mode="subway",
        departure_time=departure_time_epoch,
        traffic_model=None,
    )


