"""
Database connection test script
"""
from models import SessionLocal, RawEvent, CleanEvent
from database import test_connection
from logger import get_logger
from datetime import datetime

logger = get_logger('database_test')


def test_database_operations():
    """Test database operations with sample data"""
    try:
        logger.info("Testing database operations...")
        
        # Test session creation
        db = SessionLocal()
        logger.info("Database session created successfully")
        
        # Test inserting a sample raw event
        sample_raw_event = RawEvent(
            source="test_scraper",
            source_id="test_001",
            title="Test Event",
            description="This is a test event for database testing",
            start_time=datetime(2025, 11, 1, 19, 0, 0),
            end_time=datetime(2025, 11, 1, 21, 0, 0),
            location="Test Venue, NYC",
            venue="Test Venue",
            price_info="Free",
            category="Test",
            url="https://example.com/test-event",
            raw_data={"test": "data"}
        )
        
        db.add(sample_raw_event)
        db.commit()
        logger.info("Sample raw event inserted successfully")
        
        # Test querying the raw event
        retrieved_event = db.query(RawEvent).filter_by(source="test_scraper").first()
        if retrieved_event:
            logger.info(f"Retrieved event: {retrieved_event.title}")
        else:
            logger.error("Failed to retrieve the inserted event")
            return False
        
        # Test inserting a sample clean event
        sample_clean_event = CleanEvent(
            title="Test Clean Event",
            description="This is a test clean event",
            start_time=datetime(2025, 11, 2, 20, 0, 0),
            end_time=datetime(2025, 11, 2, 22, 0, 0),
            location="Clean Test Venue, NYC",
            venue="Clean Test Venue",
            price_range="Free",
            category="Test",
            url="https://example.com/clean-test-event",
            source="test_scraper",
            source_urls=["https://example.com/clean-test-event"]
        )
        
        db.add(sample_clean_event)
        db.commit()
        logger.info("Sample clean event inserted successfully")
        
        # Test querying the clean event
        retrieved_clean_event = db.query(CleanEvent).filter_by(source="test_scraper").first()
        if retrieved_clean_event:
            logger.info(f"Retrieved clean event: {retrieved_clean_event.title}")
        else:
            logger.error("Failed to retrieve the inserted clean event")
            return False
        
        # Clean up test data
        db.query(RawEvent).filter_by(source="test_scraper").delete()
        db.query(CleanEvent).filter_by(source="test_scraper").delete()
        db.commit()
        logger.info("Test data cleaned up")
        
        db.close()
        logger.info("Database operations test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database operations test failed: {e}")
        return False


def run_all_tests():
    """Run all database tests"""
    logger.info("Starting comprehensive database tests...")
    
    # Test 1: Basic connection
    logger.info("Test 1: Basic database connection")
    if not test_connection():
        logger.error("Basic connection test failed")
        return False
    
    # Test 2: Database operations
    logger.info("Test 2: Database operations")
    if not test_database_operations():
        logger.error("Database operations test failed")
        return False
    
    logger.info("All database tests passed successfully!")
    return True


if __name__ == "__main__":
    success = run_all_tests()
    if success:
        print("✅ All database tests passed!")
    else:
        print("❌ Some database tests failed!")
        exit(1)
