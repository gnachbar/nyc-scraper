#!/usr/bin/env python3
"""
Migration to add geo and distance/time columns to clean_events if missing.
"""

from sqlalchemy import inspect, text
from src.web.models import engine
from src.logger import get_logger

logger = get_logger('migrate_add_distance_columns')


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c.get('name') == column for c in inspector.get_columns(table))


def add_column_if_missing(conn, table: str, column: str, sql_type: str):
    inspector = inspect(conn)
    if _has_column(inspector, table, column):
        logger.info(f"Column exists: {table}.{column}")
        return
    logger.info(f"Adding column: {table}.{column} {sql_type}")
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


def migrate():
    with engine.begin() as conn:
        table = 'clean_events'
        add_column_if_missing(conn, table, 'latitude', 'FLOAT')
        add_column_if_missing(conn, table, 'longitude', 'FLOAT')
        add_column_if_missing(conn, table, 'haversine_distance_miles', 'FLOAT')
        add_column_if_missing(conn, table, 'driving_time_min', 'INTEGER')
        add_column_if_missing(conn, table, 'walking_time_min', 'INTEGER')
        add_column_if_missing(conn, table, 'subway_time_min', 'INTEGER')
        logger.info('Migration complete')


if __name__ == '__main__':
    migrate()




