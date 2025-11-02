#!/usr/bin/env python3
"""
Migration: add 'category', 'category_confidence', 'is_recurring', and 'recurrence_key' columns to clean_events table.
Idempotent: skips columns if already present.
"""

from sqlalchemy import inspect, text
from src.web.models import engine
from src.logger import get_logger

logger = get_logger('migrate_add_category_recurring')


def column_exists(inspector, table: str, column: str) -> bool:
    return any(c.get('name') == column for c in inspector.get_columns(table))


def migrate():
    with engine.begin() as conn:
        inspector = inspect(conn)

        # Add 'category' column if missing
        if not column_exists(inspector, 'clean_events', 'category'):
            logger.info('Adding column clean_events.category')
            conn.execute(text("ALTER TABLE clean_events ADD COLUMN category TEXT"))
            try:
                conn.execute(text("CREATE INDEX idx_clean_events_category ON clean_events(category)"))
            except Exception as e:
                logger.warning(f"Could not create index on category: {e}")
        else:
            logger.info('Column category already exists on clean_events')

        # Add 'category_confidence' column if missing
        if not column_exists(inspector, 'clean_events', 'category_confidence'):
            logger.info('Adding column clean_events.category_confidence')
            conn.execute(text("ALTER TABLE clean_events ADD COLUMN category_confidence FLOAT"))
        else:
            logger.info('Column category_confidence already exists on clean_events')

        # Add 'is_recurring' column if missing
        if not column_exists(inspector, 'clean_events', 'is_recurring'):
            logger.info('Adding column clean_events.is_recurring')
            conn.execute(text("ALTER TABLE clean_events ADD COLUMN is_recurring BOOLEAN DEFAULT FALSE"))
            try:
                conn.execute(text("CREATE INDEX idx_clean_events_is_recurring ON clean_events(is_recurring)"))
            except Exception as e:
                logger.warning(f"Could not create index on is_recurring: {e}")
        else:
            logger.info('Column is_recurring already exists on clean_events')

        # Add 'recurrence_key' column if missing
        if not column_exists(inspector, 'clean_events', 'recurrence_key'):
            logger.info('Adding column clean_events.recurrence_key')
            conn.execute(text("ALTER TABLE clean_events ADD COLUMN recurrence_key TEXT"))
            try:
                conn.execute(text("CREATE INDEX idx_clean_events_recurrence_key ON clean_events(recurrence_key)"))
            except Exception as e:
                logger.warning(f"Could not create index on recurrence_key: {e}")
        else:
            logger.info('Column recurrence_key already exists on clean_events')

        logger.info('Migration complete')


if __name__ == '__main__':
    migrate()

