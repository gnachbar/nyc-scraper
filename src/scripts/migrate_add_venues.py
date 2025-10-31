#!/usr/bin/env python3
"""
Migration: create venues table and add venue_id to clean_events.
Idempotent: skips objects if already present.
"""

from sqlalchemy import inspect, text
from src.web.models import engine
from src.logger import get_logger

logger = get_logger('migrate_add_venues')


def table_exists(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def column_exists(inspector, table: str, column: str) -> bool:
    return any(c.get('name') == column for c in inspector.get_columns(table))


def migrate():
    with engine.begin() as conn:
        inspector = inspect(conn)

        # Create venues table if not exists
        if not table_exists(inspector, 'venues'):
            logger.info('Creating table venues')
            conn.execute(text(
                """
                CREATE TABLE venues (
                  id SERIAL PRIMARY KEY,
                  name VARCHAR(200) NOT NULL,
                  location_text TEXT,
                  latitude FLOAT,
                  longitude FLOAT,
                  haversine_distance_miles FLOAT,
                  driving_time_min INTEGER,
                  walking_time_min INTEGER,
                  subway_time_min INTEGER,
                  created_at TIMESTAMP,
                  updated_at TIMESTAMP
                )
                """
            ))
            # Unique constraint
            conn.execute(text(
                """
                CREATE UNIQUE INDEX uq_venue_name_location
                ON venues (name, location_text)
                """
            ))
        else:
            logger.info('Table venues already exists')

        # Add venue_id to clean_events if missing
        if not column_exists(inspector, 'clean_events', 'venue_id'):
            logger.info('Adding column clean_events.venue_id')
            conn.execute(text("ALTER TABLE clean_events ADD COLUMN venue_id INTEGER"))
            # Add FK if possible
            try:
                conn.execute(text(
                    "ALTER TABLE clean_events ADD CONSTRAINT fk_clean_events_venue_id FOREIGN KEY (venue_id) REFERENCES venues(id)"
                ))
            except Exception as e:
                logger.warning(f"Could not add FK constraint: {e}")
        else:
            logger.info('Column venue_id already exists on clean_events')

        logger.info('Migration complete')


if __name__ == '__main__':
    migrate()


