#!/usr/bin/env python3
"""
Backfill script: populate recurrence_key for existing events and mark recurring events.

This script:
1. Sets recurrence_key for all events where it's None
2. Runs mark_recurring_events() to flag recurring events
"""

import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import CleanEvent, SessionLocal
from src.lib.recurrence_utils import normalize_recurrence_key
from src.clean_events import mark_recurring_events
from src.logger import get_logger

logger = get_logger('backfill_recurrence_key')


def backfill_recurrence_keys():
    """
    Backfill recurrence_key for all events that don't have it set.
    """
    logger.info("Starting recurrence_key backfill...")
    session = SessionLocal()
    
    try:
        # Find all events with None or empty recurrence_key
        events_without_key = session.query(CleanEvent).filter(
            (CleanEvent.recurrence_key.is_(None)) | (CleanEvent.recurrence_key == '')
        ).all()
        
        logger.info(f"Found {len(events_without_key)} events without recurrence_key")
        
        if not events_without_key:
            logger.info("No events need backfilling")
            return 0
        
        # Update each event with its normalized recurrence_key
        updated_count = 0
        for event in events_without_key:
            if event.title:
                recurrence_key = normalize_recurrence_key(event.title)
                event.recurrence_key = recurrence_key
                updated_count += 1
        
        session.commit()
        logger.info(f"Updated {updated_count} events with recurrence_key")
        
        return updated_count
        
    except Exception as e:
        logger.error(f"Error backfilling recurrence_key: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    """Main function to run backfill and mark recurring events."""
    try:
        # Step 1: Backfill recurrence_key for existing events
        updated = backfill_recurrence_keys()
        
        if updated > 0:
            logger.info(f"Backfilled {updated} events with recurrence_key")
        else:
            logger.info("No events needed backfilling")
        
        # Step 2: Mark recurring events
        logger.info("Marking recurring events...")
        mark_recurring_events()
        
        logger.info("Backfill complete!")
        
        # Verify results
        session = SessionLocal()
        try:
            total_events = session.query(CleanEvent).count()
            events_with_key = session.query(CleanEvent).filter(
                CleanEvent.recurrence_key.isnot(None),
                CleanEvent.recurrence_key != ''
            ).count()
            recurring_events = session.query(CleanEvent).filter(
                CleanEvent.is_recurring == True
            ).count()
            
            logger.info(f"\nSummary:")
            logger.info(f"  Total events: {total_events}")
            logger.info(f"  Events with recurrence_key: {events_with_key}")
            logger.info(f"  Recurring events: {recurring_events}")
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

