"""
Database setup and connection utilities
"""
from sqlalchemy import text
from models import create_tables, drop_tables, engine, SessionLocal
from config import Config
from logger import get_logger

logger = get_logger('database')


def setup_database():
    """Set up the database by creating all tables"""
    try:
        logger.info("Setting up database...")
        logger.info(f"Database URL: {Config.DATABASE_URL}")
        
        # Create all tables
        create_tables()
        logger.info("Database tables created successfully")
        
        return True
    except Exception as e:
        logger.error(f"Failed to setup database: {e}")
        return False


def test_connection():
    """Test database connection"""
    try:
        logger.info("Testing database connection...")
        
        # Test engine connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
            
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def reset_database():
    """Reset database by dropping and recreating all tables"""
    try:
        logger.warning("Resetting database - all data will be lost!")
        drop_tables()
        create_tables()
        logger.info("Database reset successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        return False


if __name__ == "__main__":
    # Run database setup when script is executed directly
    logger.info("Starting database setup...")
    
    if test_connection():
        if setup_database():
            logger.info("Database setup completed successfully!")
        else:
            logger.error("Database setup failed!")
    else:
        logger.error("Cannot setup database - connection failed!")
