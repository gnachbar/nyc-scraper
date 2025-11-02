#!/usr/bin/env python3
"""
Tests for recurring events functionality:
- DB grouping correctness
- UI filter integration
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import CleanEvent, Venue, SessionLocal
from src.clean_events import mark_recurring_events
from src.lib.recurrence_utils import normalize_recurrence_key
from src.logger import get_logger

logger = get_logger('test_recurring_events')


def test_recurrence_key_normalization():
    """Test that recurrence_key normalization works correctly"""
    logger.info("Testing recurrence_key normalization...")
    
    test_cases = [
        ("Trivia Night", "trivia night"),
        ("Trivia  Night!!!", "trivia night"),
        ("Comedy Show: Open Mic", "comedy show open mic"),
        ("Jazz Night @ Le Pistol", "jazz night  le pistol"),
        ("", ""),
        (None, ""),
    ]
    
    for title, expected in test_cases:
        result = normalize_recurrence_key(title)
        assert result == expected, f"Expected '{expected}' but got '{result}' for '{title}'"
    
    logger.info("✓ Recurrence key normalization tests passed")
    return True


def test_mark_recurring_events():
    """Test that mark_recurring_events correctly identifies and marks recurring events"""
    logger.info("Testing mark_recurring_events...")
    
    db = SessionLocal()
    
    try:
        # Clean up any existing test data
        db.query(CleanEvent).filter(CleanEvent.source == 'test_recurring').delete()
        db.query(Venue).filter(Venue.name == 'Test Venue').delete()
        db.commit()
        
        # Create a test venue
        test_venue = Venue(name='Test Venue', location_text='123 Test St')
        db.add(test_venue)
        db.flush()
        
        # Create test events:
        # - "Trivia Night" on 3 different dates (should be recurring)
        # - "One-Time Concert" on 1 date (should NOT be recurring)
        # - "Jazz Night" on 2 different dates (should be recurring)
        
        base_date = datetime(2025, 11, 1, 19, 0, 0)
        
        # Trivia Night - recurring (3 dates)
        trivia_events = [
            CleanEvent(
                title="Trivia Night",
                description="Weekly trivia",
                start_time=base_date + timedelta(days=i*7),
                venue="Test Venue",
                display_venue="Test Venue",
                source="test_recurring",
                recurrence_key=normalize_recurrence_key("Trivia Night"),
                is_recurring=False  # Initially false
            )
            for i in range(3)
        ]
        
        # One-Time Concert - not recurring (1 date)
        one_time_event = CleanEvent(
            title="One-Time Concert",
            description="Special event",
            start_time=base_date + timedelta(days=30),
            venue="Test Venue",
            display_venue="Test Venue",
            source="test_recurring",
            recurrence_key=normalize_recurrence_key("One-Time Concert"),
            is_recurring=False
        )
        
        # Jazz Night - recurring (2 dates)
        jazz_events = [
            CleanEvent(
                title="Jazz Night",
                description="Weekly jazz",
                start_time=base_date + timedelta(days=10 + i*7),
                venue="Test Venue",
                display_venue="Test Venue",
                source="test_recurring",
                recurrence_key=normalize_recurrence_key("Jazz Night"),
                is_recurring=False  # Initially false
            )
            for i in range(2)
        ]
        
        # Add all events
        for event in trivia_events + [one_time_event] + jazz_events:
            event.venue_id = test_venue.id
            db.add(event)
        
        db.commit()
        
        # Run mark_recurring_events
        mark_recurring_events()
        
        # Verify results
        db.refresh(trivia_events[0])
        db.refresh(one_time_event)
        db.refresh(jazz_events[0])
        
        # Trivia Night (3 dates) should be marked as recurring
        trivia_recurring = db.query(CleanEvent).filter(
            CleanEvent.display_venue == "Test Venue",
            CleanEvent.recurrence_key == normalize_recurrence_key("Trivia Night")
        ).all()
        
        assert len(trivia_recurring) == 3, f"Expected 3 Trivia Night events, got {len(trivia_recurring)}"
        assert all(e.is_recurring == True for e in trivia_recurring), "All Trivia Night events should be marked recurring"
        
        # One-Time Concert (1 date) should NOT be marked as recurring
        assert one_time_event.is_recurring == False, "One-Time Concert should NOT be marked recurring"
        
        # Jazz Night (2 dates) should be marked as recurring
        jazz_recurring = db.query(CleanEvent).filter(
            CleanEvent.display_venue == "Test Venue",
            CleanEvent.recurrence_key == normalize_recurrence_key("Jazz Night")
        ).all()
        
        assert len(jazz_recurring) == 2, f"Expected 2 Jazz Night events, got {len(jazz_recurring)}"
        assert all(e.is_recurring == True for e in jazz_recurring), "All Jazz Night events should be marked recurring"
        
        # Clean up
        db.query(CleanEvent).filter(CleanEvent.source == 'test_recurring').delete()
        db.query(Venue).filter(Venue.name == 'Test Venue').delete()
        db.commit()
        
        logger.info("✓ mark_recurring_events tests passed")
        return True
        
    except Exception as e:
        logger.error(f"mark_recurring_events test failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def test_backend_filter_recurring():
    """Test that backend filter correctly filters by recurring status"""
    logger.info("Testing backend recurring filter...")
    
    from src.web.app import app
    
    with app.test_client() as client:
        # Test 1: Filter for recurring events
        response = client.get('/?recurring=recurring')
        assert response.status_code == 200
        
        # Test 2: Filter for non-recurring events
        response = client.get('/?recurring=non-recurring')
        assert response.status_code == 200
        
        # Test 3: Show all events
        response = client.get('/?recurring=all')
        assert response.status_code == 200
        
        # Test 4: Default (no filter)
        response = client.get('/')
        assert response.status_code == 200
        
        # Test 5: API endpoint with recurring filter
        response = client.get('/api/events?recurring=recurring')
        assert response.status_code == 200
        data = response.get_json()
        assert 'filters' in data
        assert data['filters']['recurring'] == 'recurring'
        
        # Test 6: API endpoint with non-recurring filter
        response = client.get('/api/events?recurring=non-recurring')
        assert response.status_code == 200
        data = response.get_json()
        assert data['filters']['recurring'] == 'non-recurring'
    
    logger.info("✓ Backend filter tests passed")
    return True


def test_cross_venue_recurring():
    """Test that recurring events are venue-specific (same title at different venues should NOT be recurring)"""
    logger.info("Testing cross-venue recurring behavior...")
    
    db = SessionLocal()
    
    try:
        # Clean up any existing test data
        db.query(CleanEvent).filter(CleanEvent.source == 'test_recurring').delete()
        db.query(Venue).filter(Venue.name.in_(['Test Venue A', 'Test Venue B'])).delete()
        db.commit()
        
        # Create two test venues
        venue_a = Venue(name='Test Venue A', location_text='123 Test St')
        venue_b = Venue(name='Test Venue B', location_text='456 Test St')
        db.add(venue_a)
        db.add(venue_b)
        db.flush()
        
        base_date = datetime(2025, 11, 1, 19, 0, 0)
        
        # Same title "Jazz Night" at two different venues (should NOT be recurring together)
        event_a = CleanEvent(
            title="Jazz Night",
            description="Jazz at venue A",
            start_time=base_date,
            venue="Test Venue A",
            display_venue="Test Venue A",
            source="test_recurring",
            recurrence_key=normalize_recurrence_key("Jazz Night"),
            venue_id=venue_a.id,
            is_recurring=False
        )
        
        event_b = CleanEvent(
            title="Jazz Night",
            description="Jazz at venue B",
            start_time=base_date + timedelta(days=7),
            venue="Test Venue B",
            display_venue="Test Venue B",
            source="test_recurring",
            recurrence_key=normalize_recurrence_key("Jazz Night"),
            venue_id=venue_b.id,
            is_recurring=False
        )
        
        db.add(event_a)
        db.add(event_b)
        db.commit()
        
        # Run mark_recurring_events
        mark_recurring_events()
        
        # Refresh events
        db.refresh(event_a)
        db.refresh(event_b)
        
        # Both should remain False because they're at different venues
        assert event_a.is_recurring == False, "Event at Venue A should NOT be recurring (different venue)"
        assert event_b.is_recurring == False, "Event at Venue B should NOT be recurring (different venue)"
        
        # Clean up
        db.query(CleanEvent).filter(CleanEvent.source == 'test_recurring').delete()
        db.query(Venue).filter(Venue.name.in_(['Test Venue A', 'Test Venue B'])).delete()
        db.commit()
        
        logger.info("✓ Cross-venue recurring test passed")
        return True
        
    except Exception as e:
        logger.error(f"Cross-venue recurring test failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def run_all_tests():
    """Run all recurring events tests"""
    logger.info("Starting recurring events tests...")
    
    tests = [
        ("Recurrence Key Normalization", test_recurrence_key_normalization),
        ("Mark Recurring Events", test_mark_recurring_events),
        ("Cross-Venue Recurring", test_cross_venue_recurring),
        ("Backend Filter", test_backend_filter_recurring),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running: {test_name}")
            logger.info(f"{'='*60}")
            
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                failed += 1
                logger.error(f"❌ {test_name} FAILED")
                
        except Exception as e:
            failed += 1
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Test Summary: {passed} passed, {failed} failed")
    logger.info(f"{'='*60}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    if success:
        print("\n✅ All recurring events tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some recurring events tests failed!")
        sys.exit(1)

