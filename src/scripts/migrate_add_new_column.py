#!/usr/bin/env python3
"""
Migration: add 'new' column to clean_events table.
Idempotent: skips column if already present.
"""

from sqlalchemy import inspect, text
from src.web.models import engine
from src.logger import get_logger

logger = get_logger('migrate_add_new_column')


def column_exists(inspector, table: str, column: str) -> bool:
    return any(c.get('name') == column for c in inspector.get_columns(table))


def migrate():
    with engine.begin() as conn:
        inspector = inspect(conn)

        # Add 'new' column to clean_events if missing
        if not column_exists(inspector, 'clean_events', 'new'):
            logger.info('Adding column clean_events.new')
            conn.execute(text("ALTER TABLE clean_events ADD COLUMN new BOOLEAN DEFAULT FALSE"))
            # Create index for faster queries filtering by new status
            try:
                conn.execute(text("CREATE INDEX idx_clean_events_new ON clean_events(new)"))
            except Exception as e:
                logger.warning(f"Could not create index: {e}")
        else:
            logger.info('Column new already exists on clean_events')

        logger.info('Migration complete')


if __name__ == '__main__':
    migrate()

