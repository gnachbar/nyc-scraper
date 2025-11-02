#!/usr/bin/env python3
"""
Backfill latitude/longitude for existing CleanEvent rows lacking coordinates.

- Deduplicates by (venue, location) pairs
- Uses Google geocoding with local helpers
- Updates all matching rows with the resolved coordinates
- Prints a summary report
"""

import sys
from pathlib import Path

# Ensure src is importable
sys.path.append(str(Path(__file__).parent.parent))

from typing import Dict, Tuple

from src.web.models import SessionLocal, CleanEvent
from src.lib.google_maps import geocode_place, GoogleMapsError
from src.logger import get_logger

logger = get_logger('backfill_geocode')


def main():
    session = SessionLocal()
    try:
        # Find unique (venue, location) combos missing coords
        missing = session.query(CleanEvent.venue, CleanEvent.location).filter(
            (CleanEvent.latitude == None) | (CleanEvent.longitude == None)
        ).distinct().all()

        pairs: Dict[Tuple[str, str], Tuple[float, float]] = {}
        successes = 0
        failures = 0

        logger.info(f"Unique venue/location pairs lacking coords: {len(missing)}")

        for venue, location in missing:
            venue = venue or ''
            location = location or ''
            key = (venue.strip(), location.strip())
            query_parts = [p for p in [venue, location] if p]
            if not query_parts:
                failures += 1
                continue
            query = ' '.join(query_parts)
            try:
                geo = geocode_place(query)
                if geo and geo.get('lat') is not None and geo.get('lng') is not None:
                    lat = float(geo['lat'])
                    lng = float(geo['lng'])
                    pairs[key] = (lat, lng)
                    successes += 1
                else:
                    failures += 1
            except GoogleMapsError as e:
                logger.warning(f"Geocode error for '{query}': {e}")
                failures += 1
            except Exception as e:
                logger.warning(f"Unexpected error for '{query}': {e}")
                failures += 1

        # Update all matching rows for resolved pairs
        updated_rows = 0
        for (venue, location), (lat, lng) in pairs.items():
            q = session.query(CleanEvent).filter(
                (CleanEvent.latitude == None) | (CleanEvent.longitude == None)
            )
            if venue:
                q = q.filter(CleanEvent.venue == venue)
            else:
                q = q.filter((CleanEvent.venue == None) | (CleanEvent.venue == ''))
            if location:
                q = q.filter(CleanEvent.location == location)
            else:
                q = q.filter((CleanEvent.location == None) | (CleanEvent.location == ''))

            rows = q.all()
            for row in rows:
                row.latitude = lat
                row.longitude = lng
                updated_rows += 1

        session.commit()

        print("\n=== Geocode Backfill Summary ===")
        print(f"Unique pairs examined: {len(missing)}")
        print(f"Pairs resolved: {successes}")
        print(f"Pairs unresolved: {failures}")
        print(f"Rows updated: {updated_rows}")

    except Exception as e:
        session.rollback()
        logger.error(f"Backfill failed: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()


