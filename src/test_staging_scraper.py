#!/usr/bin/env python3
"""
Staging Scraper Validation Script

Validates a staging scraper before promotion to production.
Tests schema, field population, instructions, and database import.
"""

import re
import sys
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal


def read_staging_scraper(source: str) -> str:
    """Read a staging scraper JavaScript file."""
    scraper_path = Path(f"src/scrapers-staging/{source}.js")
    if not scraper_path.exists():
        raise FileNotFoundError(f"Staging scraper file not found: {scraper_path}")
    return scraper_path.read_text()


def test_file_exists(source: str) -> Tuple[bool, str]:
    """Test that the scraper file exists."""
    scraper_path = Path(f"src/scrapers-staging/{source}.js")
    if scraper_path.exists():
        return True, "File exists"
    return False, f"File not found: {scraper_path}"


def test_uses_shared_utilities(content: str) -> Tuple[bool, List[str]]:
    """Test that the scraper uses shared utilities."""
    # Special case: Weekly recurring scrapers using convertWeeklyToDatedEvents
    if 'convertWeeklyToDatedEvents' in content:
        # Only require scraper-utils and scraper-persistence
        required_imports = [
            'scraper-utils.js',
            'scraper-persistence.js'
        ]
    else:
        # Standard scrapers require all three
        required_imports = [
            'scraper-utils.js',
            'scraper-actions.js',
            'scraper-persistence.js'
        ]
    
    missing = []
    for util in required_imports:
        if util not in content:
            missing.append(util)
    
    return len(missing) == 0, missing


def test_schema_definition(content: str) -> Tuple[bool, Dict[str, bool]]:
    """Test that schema contains all required fields."""
    # Special case: Weekly recurring scrapers using convertWeeklyToDatedEvents
    if 'convertWeeklyToDatedEvents' in content:
        # For weekly scrapers, check for custom schema with day field
        required_fields = {
            'eventName': 'eventName' in content and 'z.string()' in content,
            'day': 'day' in content and 'z.string()' in content,
            'eventTime': 'eventTime' in content,
            'eventLocation': 'eventLocation' in content and 'z.string()' in content,
            'eventUrl': 'eventUrl' in content and 'z.string()' in content,
        }
        all_present = all(required_fields.values())
        return all_present, required_fields
    
    # Look for schema definition - check if using shared utility
    schema_match = re.search(
        r'createStandardSchema\(\{[^}]*\}\)',
        content,
        re.DOTALL
    )
    
    if not schema_match:
        return False, {}
    
    # If using createStandardSchema, assume it has all required fields (defined in utility)
    # Just verify that it's being used correctly
    is_using_shared_schema = 'createStandardSchema' in content
    
    if is_using_shared_schema:
        # Check that extractEventsFromPage is being used with the schema
        has_extract_call = 'extractEventsFromPage' in content
        return has_extract_call, {
            'eventName': True,
            'eventDate': True,
            'eventTime': True,
            'eventLocation': True,
            'eventUrl': True,
        }
    
    # Fallback: Check for required fields in schema (for custom schemas)
    required_fields = {
        'eventName': 'eventName' in content and 'z.string()' in content,
        'eventDate': 'eventDate' in content and 'z.string()' in content,
        'eventTime': 'eventTime' in content,
        'eventLocation': 'eventLocation' in content and 'z.string()' in content,
        'eventUrl': 'eventUrl' in content and 'z.string().url()' in content,
    }
    
    all_present = all(required_fields.values())
    return all_present, required_fields


def test_extraction_instruction(content: str) -> Tuple[bool, str]:
    """Test that extraction instruction mentions all required fields."""
    # Special case: Weekly recurring scrapers using convertWeeklyToDatedEvents
    if 'convertWeeklyToDatedEvents' in content:
        # For weekly scrapers, check for page.extract() calls
        if 'page.extract' in content:
            # Check if instructions mention event data
            if 'eventName' in content.lower() or 'event name' in content.lower():
                return True, "Extraction instructions present for weekly recurring events"
        return False, "No extraction calls found"
    
    # Extract instruction from extractEventsFromPage call
    # Handle both single-line and multi-line instructions
    instruction_match = re.search(
        r'extractEventsFromPage\s*\(\s*[^,]+\s*,\s*"([^"]*(?:\\.[^"]*)*)"',
        content,
        re.DOTALL
    )
    
    if not instruction_match:
        return False, "No extraction instruction found"
    
    instruction = instruction_match.group(1).lower()
    
    # Check for mentions of required fields
    required_mentions = {
        'eventName': any(term in instruction for term in ['eventname', 'event name', 'name']),
        'eventDate': any(term in instruction for term in ['eventdate', 'event date', 'date']),
        'eventTime': any(term in instruction for term in ['eventtime', 'event time', 'time']),
        'eventLocation': any(term in instruction for term in ['eventlocation', 'event location', 'location', 'venue']),
        'eventUrl': any(term in instruction for term in ['eventurl', 'event url', 'url', 'link'])
    }
    
    missing = [field for field, present in required_mentions.items() if not present]
    
    if missing:
        return False, f"Missing field mentions: {', '.join(missing)}"
    
    return True, "All fields mentioned"


def test_location_handling(content: str, source: str) -> Tuple[bool, str]:
    """Test that location is properly handled (hardcoded or extracted)."""
    # Special case: Weekly recurring scrapers using convertWeeklyToDatedEvents
    if 'convertWeeklyToDatedEvents' in content:
        # Check for hardcoded location in the content
        if 'eventLocation' in content and ('Le Pistol' in content or 'eventLocationDefault' in content):
            return True, "Weekly recurring: location hardcoded"
        return False, "Weekly recurring: location not found"
    
    # Extract instruction from extractEventsFromPage call (same pattern as extraction test)
    instruction_match = re.search(
        r'extractEventsFromPage\s*\(\s*[^,]+\s*,\s*"([^"]*(?:\\.[^"]*)*)"',
        content,
        re.DOTALL
    )
    
    if not instruction_match:
        return False, "No instruction found"
    
    instruction = instruction_match.group(1).lower()
    
    # Check if it's a single-venue or multi-venue scraper
    # Look for eventLocationDefault in createStandardSchema
    has_default = 'eventLocationDefault' in content
    
    if has_default:
        # Single-venue scraper: should hardcode location
        # Look for hardcoding language in instruction
        hardcode_keywords = ['set', 'hardcode', 'all events', 'for all']
        has_hardcode_language = any(keyword in instruction for keyword in hardcode_keywords)
        
        if has_hardcode_language:
            return True, "Single-venue: hardcoded correctly"
        else:
            return False, "Single-venue: missing hardcode language in instruction"
    else:
        # Multi-venue scraper: should extract location
        has_extract_language = any(term in instruction for term in ['extract', 'get', 'find'])
        
        if has_extract_language:
            return True, "Multi-venue: extraction mentioned"
        else:
            return False, "Multi-venue: missing extraction language"


def test_error_handling(content: str) -> Tuple[bool, str]:
    """Test that scraper has proper error handling."""
    has_try = 'try {' in content
    has_catch = 'catch' in content
    has_finally = 'finally {' in content
    has_error_handler = 'handleScraperError' in content
    
    if has_try and has_catch and has_finally and has_error_handler:
        return True, "Error handling present"
    
    missing = []
    if not has_try:
        missing.append('try')
    if not has_catch:
        missing.append('catch')
    if not has_finally:
        missing.append('finally')
    if not has_error_handler:
        missing.append('handleScraperError')
    
    return False, f"Missing: {', '.join(missing)}"


def test_database_save(content: str) -> Tuple[bool, str]:
    """Test that scraper saves to database."""
    has_save = 'saveEventsToDatabase' in content
    
    if has_save:
        return True, "Database save present"
    return False, "Missing saveEventsToDatabase call"


def test_export_structure(content: str) -> Tuple[bool, str]:
    """Test that scraper has proper export structure."""
    has_export = 'export async function' in content or 'export default' in content
    has_main_check = 'import.meta.url' in content or '__name__' in content
    
    if has_export and has_main_check:
        return True, "Export structure correct"
    
    missing = []
    if not has_export:
        missing.append('export function')
    if not has_main_check:
        missing.append('main check')
    
    return False, f"Missing: {', '.join(missing)}"


def test_browserbase_session(content: str) -> Tuple[bool, str]:
    """Test that scraper opens Browserbase session."""
    has_open = 'openBrowserbaseSession' in content
    
    if has_open:
        return True, "Browserbase session handling present"
    return False, "Missing openBrowserbaseSession call"


def test_time_regression(source: str) -> Tuple[bool, str]:
    """
    Test that events don't all have the same time (detects time extraction bugs).
    
    This checks if all events from the latest scrape run have identical start_time values,
    which would indicate a time extraction regression (e.g., all times defaulting to midnight).
    """
    try:
        session = SessionLocal()
        
        # Get the latest scrape run for this source
        latest_run = session.query(ScrapeRun).filter(
            ScrapeRun.source == source
        ).order_by(ScrapeRun.id.desc()).first()
        
        if not latest_run:
            return True, "No scrape runs found - run scraper first"
        
        # Get all events from this run
        events = session.query(RawEvent).filter(
            RawEvent.scrape_run_id == latest_run.id
        ).all()
        
        if not events:
            return True, "No events found in latest run"
        
        if len(events) < 2:
            return True, "Only one event - cannot check for time regression"
        
        # Check if all events have the same start_time
        start_times = [event.start_time for event in events if event.start_time]
        
        if not start_times:
            return False, "No events have start_time populated"
        
        # Count unique start_times
        unique_times = set(start_times)
        
        if len(unique_times) == 1:
            # All events have the same time - this is a regression!
            time_str = start_times[0].strftime('%Y-%m-%d %H:%M:%S') if start_times[0] else 'null'
            return False, f"All {len(events)} events have identical start_time: {time_str}"
        
        # Check if more than 50% of events have the same time (also suspicious)
        time_counts = Counter(start_times)
        most_common_time, most_common_count = time_counts.most_common(1)[0]
        
        if most_common_count > len(events) * 0.5:
            time_str = most_common_time.strftime('%Y-%m-%d %H:%M:%S') if most_common_time else 'null'
            return False, f"{most_common_count}/{len(events)} events have same start_time: {time_str}"
        
        session.close()
        return True, f"Times are diverse ({len(unique_times)} unique times)"
        
    except Exception as e:
        return False, f"Error checking time regression: {e}"


def run_staging_scraper(source: str) -> Tuple[bool, str, Optional[str]]:
    """
    Run the staging scraper and capture output.
    Returns (success, stdout, stderr)
    """
    scraper_path = Path(f"src/scrapers-staging/{source}.js")
    
    if not scraper_path.exists():
        return False, "", f"Scraper file not found: {scraper_path}"
    
    try:
        result = subprocess.run(
            ['node', str(scraper_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        success = result.returncode == 0
        return success, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "", "Scraper timed out after 10 minutes"
    except Exception as e:
        return False, "", str(e)


def parse_events_scraped(output: str) -> int:
    """Parse number of events scraped from output."""
    for line in output.split('\n'):
        if 'Total events found:' in line or 'Events Imported:' in line:
            try:
                parts = line.split(':')
                if len(parts) >= 2:
                    number_str = parts[1].strip().split()[0]
                    return int(number_str)
            except (ValueError, IndexError):
                pass
    return 0


def run_all_validations(source: str) -> Dict[str, bool]:
    """Run all validation tests for a staging scraper."""
    print(f"\n{'='*80}")
    print(f"VALIDATING STAGING SCRAPER: {source}")
    print(f"{'='*80}\n")
    
    try:
        content = read_staging_scraper(source)
    except FileNotFoundError as e:
        print(f"✗ ERROR: {e}")
        return {'file_exists': False}
    
    results = {}
    
    # Test 1: File exists
    print("1. File Exists")
    passed, msg = test_file_exists(source)
    results['file_exists'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 2: Uses shared utilities
    print("2. Uses Shared Utilities")
    passed, missing = test_uses_shared_utilities(content)
    results['uses_shared_utilities'] = passed
    if passed:
        print("   ✓ All required utilities imported")
    else:
        print(f"   ✗ Missing utilities: {', '.join(missing)}")
    print()
    
    # Test 3: Schema definition
    print("3. Schema Definition")
    passed, fields = test_schema_definition(content)
    results['schema_definition'] = passed
    if passed:
        print("   ✓ All required fields present")
    else:
        missing_fields = [f for f, p in fields.items() if not p]
        print(f"   ✗ Missing fields: {', '.join(missing_fields)}")
    print()
    
    # Test 4: Extraction instruction
    print("4. Extraction Instruction")
    passed, msg = test_extraction_instruction(content)
    results['extraction_instruction'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 5: Location handling
    print("5. Location Handling")
    passed, msg = test_location_handling(content, source)
    results['location_handling'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 6: Error handling
    print("6. Error Handling")
    passed, msg = test_error_handling(content)
    results['error_handling'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 7: Database save
    print("7. Database Save")
    passed, msg = test_database_save(content)
    results['database_save'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 8: Export structure
    print("8. Export Structure")
    passed, msg = test_export_structure(content)
    results['export_structure'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 9: Browserbase session
    print("9. Browserbase Session")
    passed, msg = test_browserbase_session(content)
    results['browserbase_session'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 10: Time regression check
    print("10. Time Regression Check")
    passed, msg = test_time_regression(source)
    results['time_regression'] = passed
    print(f"   {'✓' if passed else '✗'} {msg}\n")
    
    # Test 11: Run scraper (optional - commented out by default as it's expensive)
    print("11. Run Scraper (Manual Test)")
    print("   ℹ Run manually: node src/scrapers-staging/{source}.js")
    print("   ℹ Check that events are populated in database\n")
    
    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Validate a staging scraper')
    parser.add_argument('source', help='Source name (e.g., brooklyn_museum)')
    parser.add_argument('--run', action='store_true', help='Also run the scraper to test')
    
    args = parser.parse_args()
    
    # Run validations
    results = run_all_validations(args.source)
    
    # Optionally run the scraper
    if args.run:
        print("="*80)
        print("RUNNING SCRAPER")
        print("="*80)
        success, stdout, stderr = run_staging_scraper(args.source)
        
        if success:
            events_count = parse_events_scraped(stdout)
            print(f"\n✓ Scraper ran successfully")
            print(f"  Events scraped: {events_count}")
        else:
            print(f"\n✗ Scraper failed")
            if stderr:
                print(f"  Error: {stderr[:500]}")
        print()
    
    # Summary
    print("="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"{status} {test_name}")
    
    print()
    if all_passed:
        print("✓ ALL VALIDATIONS PASSED")
        print("  Scraper is ready for promotion")
        return 0
    else:
        print("✗ SOME VALIDATIONS FAILED")
        print("  Fix issues before promoting")
        return 1


if __name__ == "__main__":
    sys.exit(main())

