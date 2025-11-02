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
from typing import List


def get_production_scrapers() -> List[str]:
    """Get list of all production scrapers dynamically."""
    scrapers_dir = Path("src/scrapers")
    if not scrapers_dir.exists():
        return []
    
    scrapers = []
    for file in scrapers_dir.glob("*.js"):
        scrapers.append(file.stem)
    
    return sorted(scrapers)


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
    
    required_fields = ['eventName', 'eventDate', 'eventTime', 'eventDescription', 'eventLocation', 'eventUrl']
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


def test_instruction_structure(source: str) -> tuple[bool, list[str]]:
    """Test that instruction mentions all required fields."""
    content = read_scraper_file(source)
    instruction = extract_instruction(content).lower()
    
    # Check if instruction mentions all required fields
    required_mentions = {
        'eventName': any(term in instruction for term in ['eventname', 'event name', 'name']),
        'eventDate': any(term in instruction for term in ['eventdate', 'event date', 'date']),
        'eventTime': any(term in instruction for term in ['eventtime', 'event time', 'time']),
        'eventLocation': any(term in instruction for term in ['eventlocation', 'event location', 'location', 'venue']),
        'eventUrl': any(term in instruction for term in ['eventurl', 'event url', 'url'])
    }
    
    missing = [field for field, present in required_mentions.items() if not present]
    
    return len(missing) == 0, missing


def test_cross_scraper_consistency():
    """Test that all scrapers' instructions follow similar patterns."""
    sources = get_production_scrapers()
    
    # Extract all instructions
    instructions = {}
    for source in sources:
        try:
            content = read_scraper_file(source)
            instructions[source] = extract_instruction(content).lower()
        except FileNotFoundError:
            continue
    
    # Check for common patterns
    common_patterns = [
        'event name',
        'date',
        'time',
        'url',
        'click'
    ]
    
    results = {}
    for source, instruction in instructions.items():
        patterns_found = [pattern for pattern in common_patterns if pattern in instruction]
        results[source] = {
            'patterns': patterns_found,
            'missing': [p for p in common_patterns if p not in instruction]
        }
    
    return results


def test_hardcoded_location(source: str) -> tuple[bool, str]:
    """Test that single-venue scrapers hardcode location in instruction and schema."""
    content = read_scraper_file(source)
    instruction = extract_instruction(content).lower()
    
    # Single-venue scrapers should hardcode location
    single_venue_scrapers = {
        'kings_theatre': {
            'venue_name': 'kings theatre',
            'should_hardcode': True
        },
        'msg_calendar': {
            'venue_name': 'madison square garden',
            'should_hardcode': True
        },
        'prospect_park': {
            'venue_name': None,
            'should_hardcode': False  # This one extracts actual subvenues
        }
    }
    
    if source not in single_venue_scrapers:
        return True, "Unknown scraper"
    
    config = single_venue_scrapers[source]
    
    if config['should_hardcode']:
        # Check if instruction tells Stagehand to hardcode the venue name
        venue_name = config['venue_name']
        hardcode_keywords = ['set', 'hardcode', 'all events', 'for all']
        
        has_venue_name = venue_name in instruction
        has_hardcode_language = any(keyword in instruction for keyword in hardcode_keywords)
        
        # Also check for eventLocation mentioned with venue name nearby
        # This catches patterns like "set eventLocation to 'Madison Square Garden'"
        has_explicit_hardcode = False
        if 'eventlocation' in instruction:
            # Check if venue name appears near eventLocation mention
            instruction_words = instruction.split()
            for i, word in enumerate(instruction_words):
                if 'eventlocation' in word:
                    # Check surrounding words for venue name
                    context = ' '.join(instruction_words[max(0, i-3):i+4])
                    if venue_name in context:
                        has_explicit_hardcode = True
                        break
        
        is_hardcoded = has_venue_name and (has_hardcode_language or has_explicit_hardcode)
        
        details = f"venue_name={has_venue_name}, hardcode_language={has_hardcode_language}, explicit={has_explicit_hardcode}"
        return is_hardcoded, details
    else:
        # Multi-venue scraper should NOT hardcode
        should_not_hardcode = 'extract' in instruction or 'location' in instruction
        return should_not_hardcode, "Multi-venue scraper should extract locations"


def run_all_tests():
    """Run all consistency tests for all scrapers."""
    sources = get_production_scrapers()
    
    if not sources:
        print("✗ No production scrapers found")
        return 1
    
    print("=" * 80)
    print("SCRAPER CONSISTENCY TESTS")
    print("=" * 80)
    print(f"Found {len(sources)} production scrapers: {', '.join(sources)}")
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
        
        # Test 4: Instruction structure consistency
        structure_ok, missing_fields = test_instruction_structure(source)
        if structure_ok:
            print("  ✓ Instruction mentions all required fields")
        else:
            print(f"  ✗ Instruction missing fields: {', '.join(missing_fields)}")
            all_passed = False
        
        # Test 5: Hardcoded location
        hardcode_ok, details = test_hardcoded_location(source)
        if hardcode_ok:
            print("  ✓ Location hardcoding/ex extraction handled correctly")
        else:
            print(f"  ✗ Location hardcoding incorrect: {details}")
            all_passed = False
        
        # Show instruction snippet
        instruction_preview = instruction[:150] + "..." if len(instruction) > 150 else instruction
        print(f"  Instruction: {instruction_preview}")
        print()
    
    print("=" * 80)
    print("CROSS-SCRAPER CONSISTENCY TEST")
    print("=" * 80)
    
    # Cross-scraper consistency check
    cross_results = test_cross_scraper_consistency()
    common_patterns = ['event name', 'date', 'time', 'url', 'click']
    
    print("\nInstruction Pattern Comparison:")
    for source, result in cross_results.items():
        missing = result['missing']
        if missing:
            print(f"  ✗ {source}: Missing patterns: {', '.join(missing)}")
            all_passed = False
        else:
            print(f"  ✓ {source}: All common patterns present")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

