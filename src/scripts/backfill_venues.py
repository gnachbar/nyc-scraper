#!/usr/bin/env python3
"""
Backfill venues table from distinct (display_venue, location) pairs in clean_events.
Steps:
- Extract distinct pairs
- Upsert into venues
- Geocode coordinates when missing
- Compute haversine + driving/walking/subway once per venue
- Link clean_events.venue_id
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from typing import Dict, Tuple, Optional

from sqlalchemy import and_

from src.web.models import SessionLocal, CleanEvent, Venue
from src.lib.google_maps import geocode_place, distance_times, GoogleMapsError
from src.transforms.distances import haversine_miles, parse_home_coords
from src.logger import get_logger

logger = get_logger('backfill_venues')


def get_or_create_venue(session, name: str, location_text: Optional[str]):
    venue = session.query(Venue).filter(
        Venue.name == name,
        Venue.location_text == (location_text or None)
    ).first()
    if venue:
        return venue, False
    venue = Venue(name=name, location_text=location_text or None)
    session.add(venue)
    session.flush()
    return venue, True


def main():
    session = SessionLocal()
    resolved = 0
    created = 0
    linked_rows = 0

    try:
        # Distinct venue/location pairs from clean_events
        pairs = session.query(CleanEvent.display_venue, CleanEvent.location).distinct().all()
        logger.info(f"Found {len(pairs)} distinct (display_venue, location) pairs")

        # Home coords
        try:
            home_lat, home_lng = parse_home_coords()
        except Exception as e:
            logger.error(f"HOME_COORDS not configured: {e}")
            return

        for name, loc in pairs:
            name = (name or '').strip()
            loc_text = (loc or '').strip() or None
            if not name:
                continue

            venue, was_created = get_or_create_venue(session, name, loc_text)
            if was_created:
                created += 1

            # If coords missing, geocode
            if venue.latitude is None or venue.longitude is None:
                q = ' '.join([p for p in [name, loc_text] if p])
                try:
                    geo = geocode_place(q)
                    if geo and geo.get('lat') is not None and geo.get('lng') is not None:
                        venue.latitude = float(geo['lat'])
                        venue.longitude = float(geo['lng'])
                except GoogleMapsError as e:
                    logger.warning(f"Geocode error for '{q}': {e}")
                except Exception as e:
                    logger.warning(f"Unexpected geocode error for '{q}': {e}")

            # If we have coords, compute distances/times if missing
            if venue.latitude is not None and venue.longitude is not None:
                try:
                    if venue.haversine_distance_miles is None:
                        venue.haversine_distance_miles = haversine_miles(home_lat, home_lng, venue.latitude, venue.longitude)
                    if any(getattr(venue, f) is None for f in ['driving_time_min','walking_time_min','subway_time_min']):
                        times = distance_times((home_lat, home_lng), (venue.latitude, venue.longitude))
                        venue.driving_time_min = times.get('driving_time_min')
                        venue.walking_time_min = times.get('walking_time_min')
                        venue.subway_time_min = times.get('subway_time_min')
                        resolved += 1
                except Exception as e:
                    logger.warning(f"Distance calc error for '{name}': {e}")

        session.commit()

        # Link clean_events to venues via (display_venue, location)
        for name, loc in pairs:
            name = (name or '').strip()
            loc_text = (loc or '').strip() or None
            if not name:
                continue
            venue = session.query(Venue).filter(
                Venue.name == name,
                Venue.location_text == (loc_text or None)
            ).first()
            if not venue:
                continue
            rows = session.query(CleanEvent).filter(
                CleanEvent.display_venue == name,
                (CleanEvent.location == loc_text) if loc_text else ( (CleanEvent.location == None) | (CleanEvent.location == '') )
            ).all()
            for r in rows:
                if r.venue_id != venue.id:
                    r.venue_id = venue.id
                    linked_rows += 1
        session.commit()

        print("\n=== Venue Backfill Summary ===")
        print(f"Distinct pairs: {len(pairs)}")
        print(f"Venues created: {created}")
        print(f"Venues distance/times resolved: {resolved}")
        print(f"CleanEvent rows linked: {linked_rows}")

    except Exception as e:
        session.rollback()
        logger.error(f"Backfill venues failed: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()


