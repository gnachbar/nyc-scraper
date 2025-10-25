#!/usr/bin/env python3
"""
Test scraper consistency across Kings Theatre, MSG Calendar, and Prospect Park.

Tests that all scrapers follow consistent patterns for:
- Schema structure
- eventLocation handling
- Extraction instructions
"""

import re
import sys
from pathlib import Path


def read_scraper_file(source: str) -> str:
    """Read a scraper JavaScript file."""
    scraper_path = Path(f"src/scrapers/{source}.js")
    if not scraper_path.exists():
        raise FileNotFoundError(f"Scraper file not found: {scraper_path}")
    return scraper_path.read_text()


def extract_schema(content: str) -> dict:
    """Extract the Zod schema definition."""
    schema_match = re.search(
        r'const StandardEventSchema = z\.object\(\{([^}]+)\}\)',
        content,
        re.DOTALL
    )
    if not schema_match:
        return {}
    
    schema_text = schema_match.group(1)
    
    return {
        'eventName': 'eventName' in schema_text and 'z.string()' in schema_text,
        'eventDate': 'eventDate' in schema_text and 'z.string()' in schema_text,
        'eventTime': 'eventTime' in schema_text,
        'eventLocation': 'eventLocation' in schema_text and 'z.string()' in schema_text,
        'eventUrl': 'eventUrl' in schema_text and 'z.string().url()' in schema_text,
    }


def extract_instruction(content: str) -> str:
    """Extract the extraction instruction."""
    # Look for the instruction within page.extract()
    match = re.search(
        r'instruction:\s*"([^"]+)"',
        content,
        re.DOTALL
    )
    return match.group(1) if match else ""


def test_schema_consistency(source: str) -> tuple[bool, list[str]]:
    """Test that the schema contains all required fields."""
    content = read_scraper_file(source)
    schema = extract_schema(content)
    
    required_fields = ['eventName', 'eventDate', 'eventTime', 'eventLocation', 'eventUrl']
    missing = [field for field in required_fields if not schema.get(field)]
    
    return len(missing) == 0, missing


def test_event_location_instruction(source: str) -> tuple[bool, str]:
    """Test that eventLocation is mentioned in the extraction instruction."""
    content = read_scraper_file(source)
    instruction = extract_instruction(content)
    
    # Check if instruction mentions eventLocation or venue name
    has_event_location = 'eventLocation' in instruction.lower()
    
    if source == 'msg_calendar':
        has_venue_name = 'madison square garden' in instruction.lower()
    elif source == 'kings_theatre':
        has_venue_name = 'kings theatre' in instruction.lower()
    elif source == 'prospect_park':
        # Prospect Park extracts actual subvenues, so we look for location-related terms
        has_venue_name = any(term in instruction.lower() for term in ['location', 'subvenue', 'venue'])
    else:
        has_venue_name = False
    
    return has_event_location or has_venue_name, instruction


def test_url_extraction(source: str) -> tuple[bool, str]:
    """Test that URL extraction is mentioned in the instruction."""
    content = read_scraper_file(source)
    instruction = extract_instruction(content)
    
    # Check for URL-related terms
    has_url = any(term in instruction.lower() for term in ['url', 'link', 'click'])
    
    return has_url, instruction


def run_all_tests():
    """Run all consistency tests for all scrapers."""
    sources = ['kings_theatre', 'msg_calendar', 'prospect_park']
    
    print("=" * 80)
    print("SCRAPER CONSISTENCY TESTS")
    print("=" * 80)
    print()
    
    all_passed = True
    
    for source in sources:
        print(f"Testing: {source}")
        print("-" * 80)
        
        # Test 1: Schema consistency
        schema_ok, missing_fields = test_schema_consistency(source)
        if schema_ok:
            print("  ✓ Schema contains all required fields")
        else:
            print(f"  ✗ Schema missing fields: {', '.join(missing_fields)}")
            all_passed = False
        
        # Test 2: eventLocation instruction
        location_ok, instruction = test_event_location_instruction(source)
        if location_ok:
            print("  ✓ eventLocation handling mentioned in instruction")
        else:
            print("  ✗ eventLocation handling NOT mentioned in instruction")
            all_passed = False
        
        # Test 3: URL extraction
        url_ok, _ = test_url_extraction(source)
        if url_ok:
            print("  ✓ URL extraction mentioned in instruction")
        else:
            print("  ✗ URL extraction NOT mentioned in instruction")
            all_passed = False
        
        # Show instruction snippet
        instruction_preview = instruction[:150] + "..." if len(instruction) > 150 else instruction
        print(f"  Instruction: {instruction_preview}")
        print()
    
    print("=" * 80)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

