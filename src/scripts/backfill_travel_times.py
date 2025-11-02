#!/usr/bin/env python3
import sys
import argparse
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional, Tuple
from statistics import median
from pathlib import Path

# Ensure src is importable
sys.path.append(str(Path(__file__).parent.parent))

from src.config import Config
from src.web.models import SessionLocal, Venue
from src.lib.google_maps import driving_time_with_departure, subway_time_with_departure

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore


NEW_YORK_TZ = "America/New_York"


def _next_weekday_at(dt_now_local: datetime, target_weekday: int, target_time: time) -> datetime:
    """
    Return the next occurrence (>= now) of the given weekday at target_time in the
    same timezone as dt_now_local.
    """
    days_ahead = (target_weekday - dt_now_local.weekday()) % 7
    candidate = (dt_now_local + timedelta(days=days_ahead)).replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0,
    )
    if candidate < dt_now_local:
        candidate = candidate + timedelta(days=7)
    return candidate


def generate_weekly_sampling_times() -> List[datetime]:
    """
    Generate 21 timestamps (Mon–Sun at 14:00, 17:00, 19:00 America/New_York)
    as timezone-aware datetimes in the future (>= now).
    """
    tz = ZoneInfo(NEW_YORK_TZ)
    now_local = datetime.now(tz)
    hours = [time(14, 0), time(17, 0), time(19, 0)]
    result: List[datetime] = []
    for weekday in range(7):  # 0=Mon .. 6=Sun
        for h in hours:
            result.append(_next_weekday_at(now_local, weekday, h))
    # Sort to be deterministic
    result.sort()
    return result


def _parse_home_coords(coords_str: str) -> Tuple[float, float]:
    lat_str, lng_str = [p.strip() for p in coords_str.split(",", 1)]
    return float(lat_str), float(lng_str)


def _percentile(values: List[int], pct: float) -> Optional[float]:
    if not values:
        return None
    vals = sorted(values)
    k = (len(vals) - 1) * pct
    f = int(k)
    c = min(f + 1, len(vals) - 1)
    if f == c:
        return float(vals[int(k)])
    d0 = vals[f] * (c - k)
    d1 = vals[c] * (k - f)
    return float(d0 + d1)


def compute_travel_profiles_and_update_db(
    times: List[datetime], 
    dry_run: bool = False,
    test_venue_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    For each Venue with coordinates, fetch driving and subway minutes at each sampled time
    from HOME origin, compute medians, and update Venue.driving_time_min and 
    Venue.subway_time_min in database.
    
    Args:
        times: List of datetime objects for sampling
        dry_run: If True, make API calls but don't commit to database
        test_venue_names: If provided, only process venues matching these names
    
    Returns summary: { "venues_updated": count, "venues_failed": count, "venues_processed": [...] }
    """
    if not Config.HOME_COORDS:
        raise RuntimeError("HOME_COORDS is not configured in Config")
    origin = _parse_home_coords(Config.HOME_COORDS)

    # Epoch seconds in UTC for each local NY timestamp
    epoch_seconds: List[int] = [int(dt.timestamp()) for dt in times]

    db = SessionLocal()
    updated = 0
    failed = 0
    processed_details = []
    try:
        query = db.query(Venue).filter(Venue.latitude.isnot(None), Venue.longitude.isnot(None))
        
        # Filter to test venues if specified
        if test_venue_names:
            query = query.filter(Venue.name.in_(test_venue_names))
        
        venues: List[Venue] = query.all()
        
        if dry_run:
            print(f"[DRY RUN] Processing {len(venues)} venue(s): {', '.join([v.name for v in venues])}")
            print("[DRY RUN] Will make real API calls but won't commit to database\n")
        
        for v in venues:
            dest = (float(v.latitude), float(v.longitude))
            driving_values: List[int] = []
            subway_values: List[int] = []
            samples_detail = []
            
            try:
                print(f"Processing venue: {v.name} (ID: {v.id})")
                for i, (dt_obj, ts) in enumerate(zip(times, epoch_seconds), 1):
                    print(f"  Sample {i}/21: {dt_obj.strftime('%a %b %d at %I:%M %p %Z')}...", end=" ", flush=True)
                    
                    # Get driving time
                    driving_mins = driving_time_with_departure(origin, dest, ts, traffic_model="best_guess")
                    
                    # Get subway time
                    subway_mins = subway_time_with_departure(origin, dest, ts)
                    
                    if driving_mins is None and subway_mins is None:
                        print("(no results)")
                        continue
                    
                    result_str = []
                    if driving_mins is not None:
                        driving_values.append(int(driving_mins))
                        result_str.append(f"drive:{driving_mins}min")
                    if subway_mins is not None:
                        subway_values.append(int(subway_mins))
                        result_str.append(f"subway:{subway_mins}min")
                    
                    print(" ".join(result_str))
                    samples_detail.append({
                        "timestamp": dt_obj.isoformat(),
                        "driving_minutes": driving_mins,
                        "subway_minutes": subway_mins
                    })
                
                if not driving_values and not subway_values:
                    failed += 1
                    print(f"  ❌ Failed: No valid samples collected")
                    continue
                
                # Compute medians
                median_driving = int(median(driving_values)) if driving_values else None
                median_subway = int(median(subway_values)) if subway_values else None
                
                old_driving = v.driving_time_min
                old_subway = v.subway_time_min
                
                print(f"  ✅ Collected {len(driving_values)}/21 driving samples, {len(subway_values)}/21 subway samples")
                if median_driving is not None:
                    print(f"  🚗 Driving: {old_driving} min → {median_driving} min (median)")
                if median_subway is not None:
                    print(f"  🚇 Subway: {old_subway} min → {median_subway} min (median)")
                
                if median_driving is not None:
                    v.driving_time_min = median_driving
                if median_subway is not None:
                    v.subway_time_min = median_subway
                
                updated += 1
                
                processed_details.append({
                    "venue_id": v.id,
                    "venue_name": v.name,
                    "old_driving": old_driving,
                    "new_driving_median": median_driving,
                    "old_subway": old_subway,
                    "new_subway_median": median_subway,
                    "driving_samples": len(driving_values),
                    "subway_samples": len(subway_values),
                    "samples": samples_detail
                })
                print()
            except Exception as e:
                failed += 1
                print(f"  ❌ Error: {e}\n")
                continue
        
        if dry_run:
            print("\n[DRY RUN] Rolling back transaction (no changes saved)")
            db.rollback()
        else:
            db.commit()
            print(f"\n✅ Committed {updated} venue update(s) to database")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
    
    return {
        "venues_updated": updated, 
        "venues_failed": failed,
        "venues_processed": processed_details
    }


def _main() -> int:
    """
    Main entry point: Generate 21 weekly sampling times, compute driving and subway profiles
    for all venues, and update Venue.driving_time_min and Venue.subway_time_min in database.
    """
    parser = argparse.ArgumentParser(
        description="Compute weekly driving and subway time profiles for venues using 21 weekly samples"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Make API calls but don't commit to database (for testing)"
    )
    parser.add_argument(
        "--test-venues",
        nargs="+",
        help="Only process specified venue names (for testing). Example: --test-venues 'Kings Theatre' 'Barclays Center'"
    )
    args = parser.parse_args()
    
    print("Generating weekly sampling schedule (Mon-Sun at 2pm, 5pm, 7pm)...")
    times = generate_weekly_sampling_times()
    print(f"Generated {len(times)} sampling times")
    print(f"First sample: {times[0].strftime('%A, %B %d at %I:%M %p %Z')}")
    print(f"Last sample: {times[-1].strftime('%A, %B %d at %I:%M %p %Z')}\n")
    
    if args.test_venues:
        print(f"⚠️  TEST MODE: Only processing venues: {', '.join(args.test_venues)}")
        print("This will query Google Distance Matrix 21 times per test venue (driving + subway).\n")
    else:
        print("Computing travel profiles for ALL venues...")
        print("This will query Google Distance Matrix 21 times per venue (driving + subway).")
        print("Depending on venue count, this may take a while...\n")
    
    try:
        result = compute_travel_profiles_and_update_db(
            times, 
            dry_run=args.dry_run,
            test_venue_names=args.test_venues
        )
        print("\n" + "="*60)
        print("Weekly Travel Time Profile Update Summary")
        print("="*60)
        print(f"Venues updated: {result['venues_updated']}")
        print(f"Venues failed: {result['venues_failed']}")
        if args.dry_run:
            print("\n[DRY RUN] No changes were saved to database")
        else:
            print("\n✅ All venue.driving_time_min and venue.subway_time_min values have been updated with median of 21 weekly samples.")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())

#!/usr/bin/env python3
"""
Backfill travel metrics for CleanEvent rows that have coordinates:
- haversine_distance_miles
- driving_time_min
- walking_time_min
- subway_time_min

Respects HOME_COORDS and GOOGLE_MAPS_API_KEY. Uses caching under the hood.
"""

import sys
from pathlib import Path
from time import sleep

# Ensure src is importable
sys.path.append(str(Path(__file__).parent.parent))

from typing import Optional

from src.web.models import SessionLocal, CleanEvent
from src.transforms.distances import haversine_miles, parse_home_coords
from src.lib.google_maps import distance_times, GoogleMapsError
from src.logger import get_logger

logger = get_logger('backfill_travel_times')


def should_update(e: CleanEvent, only_missing: bool) -> bool:
    if not (e.latitude is not None and e.longitude is not None):
        return False
    if not only_missing:
        return True
    # Update if any are missing
    return (
        e.haversine_distance_miles is None or
        e.driving_time_min is None or
        e.walking_time_min is None or
        e.subway_time_min is None
    )


def main(only_missing: bool = True, batch_size: int = 200, pause_sec: float = 0.2):
    session = SessionLocal()
    updated = 0
    examined = 0
    failures = 0

    try:
        home_lat, home_lng = parse_home_coords()
    except Exception as e:
        logger.error(f"HOME_COORDS not configured: {e}")
        return

    try:
        base = session.query(CleanEvent.id).filter(
            (CleanEvent.latitude != None) & (CleanEvent.longitude != None)
        )
        if only_missing:
            base = base.filter(
                (CleanEvent.haversine_distance_miles == None) |
                (CleanEvent.driving_time_min == None) |
                (CleanEvent.walking_time_min == None) |
                (CleanEvent.subway_time_min == None)
            )
        ids = [row[0] for row in base.all()]

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i+batch_size]
            events = session.query(CleanEvent).filter(CleanEvent.id.in_(batch_ids)).all()
            for e in events:
                if not should_update(e, only_missing):
                    continue
                examined += 1
                try:
                    # Haversine
                    e.haversine_distance_miles = haversine_miles(home_lat, home_lng, e.latitude, e.longitude)
                    # Times
                    times = distance_times((home_lat, home_lng), (e.latitude, e.longitude))
                    e.driving_time_min = times.get('driving_time_min')
                    e.walking_time_min = times.get('walking_time_min')
                    e.subway_time_min = times.get('subway_time_min')
                    updated += 1
                except GoogleMapsError as ge:
                    failures += 1
                    logger.warning(f"Distance API error for event {e.id}: {ge}")
                except Exception as ex:
                    failures += 1
                    logger.warning(f"Unexpected error for event {e.id}: {ex}")

            session.commit()
            sleep(pause_sec)

        print("\n=== Travel Time Backfill Summary ===")
        print(f"Rows examined: {examined}")
        print(f"Rows updated: {updated}")
        print(f"Failures: {failures}")
    except Exception as e:
        session.rollback()
        logger.error(f"Backfill failed: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    # Default: only fill missing
    main(only_missing=True)
