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


def backfill_venues_for_source(source: Optional[str] = None):
    """
    Backfill venues for a specific source (or all sources if None).
    
    Args:
        source: Optional source name to filter by. If None, processes all sources.
    
    Returns:
        dict with keys: venues_created, venues_geocoded, distances_calculated, 
        travel_times_calculated, venues_linked
    """
    session = SessionLocal()
    resolved = 0
    created = 0
    linked_rows = 0
    geocoded = 0
    distances = 0
    travel_times = 0

    try:
        # Distinct venue/location pairs from clean_events
        query = session.query(CleanEvent.display_venue, CleanEvent.location).distinct()
        if source:
            query = query.filter(CleanEvent.source == source)
        pairs = query.all()
        
        if source:
            logger.info(f"Found {len(pairs)} distinct (display_venue, location) pairs for source '{source}'")
        else:
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

            # Skip if venue already has everything (coordinates, distance, and travel times)
            needs_geocode = venue.latitude is None or venue.longitude is None
            needs_distance = venue.haversine_distance_miles is None
            needs_travel_times = any(getattr(venue, f) is None for f in ['driving_time_min','walking_time_min','subway_time_min'])
            
            if not needs_geocode and not needs_distance and not needs_travel_times:
                continue  # Skip venues that already have all data

            # If coords missing, geocode
            if needs_geocode:
                q = ' '.join([p for p in [name, loc_text] if p])
                try:
                    geo = geocode_place(q)
                    if geo and geo.get('lat') is not None and geo.get('lng') is not None:
                        venue.latitude = float(geo['lat'])
                        venue.longitude = float(geo['lng'])
                        geocoded += 1
                except GoogleMapsError as e:
                    logger.warning(f"Geocode error for '{q}': {e}")
                except Exception as e:
                    logger.warning(f"Unexpected geocode error for '{q}': {e}")

            # If we have coords, compute distances/times if missing
            if venue.latitude is not None and venue.longitude is not None:
                try:
                    if needs_distance:
                        venue.haversine_distance_miles = haversine_miles(home_lat, home_lng, venue.latitude, venue.longitude)
                        distances += 1
                    if needs_travel_times:
                        times = distance_times((home_lat, home_lng), (venue.latitude, venue.longitude))
                        venue.driving_time_min = times.get('driving_time_min')
                        venue.walking_time_min = times.get('walking_time_min')
                        venue.subway_time_min = times.get('subway_time_min')
                        travel_times += 1
                        resolved += 1
                except Exception as e:
                    logger.warning(f"Distance calc error for '{name}': {e}")

        session.commit()

        # Link clean_events to venues via (display_venue, location)
        query = session.query(CleanEvent)
        if source:
            query = query.filter(CleanEvent.source == source)
        
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
            rows = query.filter(
                CleanEvent.display_venue == name,
                (CleanEvent.location == loc_text) if loc_text else ( (CleanEvent.location == None) | (CleanEvent.location == '') )
            ).all()
            for r in rows:
                if r.venue_id != venue.id:
                    r.venue_id = venue.id
                    linked_rows += 1
        session.commit()

        result = {
            'venues_created': created,
            'venues_geocoded': geocoded,
            'distances_calculated': distances,
            'travel_times_calculated': travel_times,
            'venues_linked': linked_rows
        }
        
        if source:
            print(f"\n=== Venue Backfill Summary for '{source}' ===")
        else:
            print("\n=== Venue Backfill Summary ===")
        print(f"Distinct pairs: {len(pairs)}")
        print(f"Venues created: {created}")
        print(f"Venues geocoded: {geocoded}")
        print(f"Distances calculated: {distances}")
        print(f"Travel times calculated: {travel_times}")
        print(f"CleanEvent rows linked: {linked_rows}")
        
        return result

    except Exception as e:
        session.rollback()
        logger.error(f"Backfill venues failed: {e}")
        raise
    finally:
        session.close()


def main():
    """Main entry point - backfill all venues."""
    backfill_venues_for_source(None)


if __name__ == '__main__':
    main()


