#!/usr/bin/env python3
"""
Migration: add description column to raw_events and clean_events tables.
Idempotent: skips columns if already present.
"""

from sqlalchemy import inspect, text
from src.web.models import engine
from src.logger import get_logger

logger = get_logger('migrate_add_description')


def column_exists(inspector, table: str, column: str) -> bool:
    return any(c.get('name') == column for c in inspector.get_columns(table))


def migrate():
    with engine.begin() as conn:
        inspector = inspect(conn)

        # Add description to raw_events if missing
        if not column_exists(inspector, 'raw_events', 'description'):
            logger.info('Adding column raw_events.description')
            conn.execute(text("ALTER TABLE raw_events ADD COLUMN description TEXT"))
        else:
            logger.info('Column description already exists on raw_events')

        # Add description to clean_events if missing
        if not column_exists(inspector, 'clean_events', 'description'):
            logger.info('Adding column clean_events.description')
            conn.execute(text("ALTER TABLE clean_events ADD COLUMN description TEXT"))
        else:
            logger.info('Column description already exists on clean_events')

        logger.info('Migration complete')


if __name__ == '__main__':
    migrate()

