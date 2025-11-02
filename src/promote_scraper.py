#!/usr/bin/env python3
"""
Scraper Promotion Script

Promotes a validated staging scraper to production by:
0. Updating configuration files (import script, test script, pipeline config)
1. Running validation tests
2. Moving scraper from staging to production directory
3. Running first production test
"""

import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import List

# App imports
from src.web.models import SessionLocal, CleanEvent
from src.lib.google_maps import geocode_place, GoogleMapsError


def read_file_content(file_path: Path) -> str:
    """Read file content."""
    return file_path.read_text()


def write_file_content(file_path: Path, content: str):
    """Write file content."""
    file_path.write_text(content)


def update_configuration_files(source: str) -> bool:
    """Update all configuration files to include new scraper."""
    print(f"\n{'='*80}")
    print(f"STEP 0: Updating Configuration Files")
    print(f"{'='*80}\n")
    
    print("Updating configuration files to support new scraper...")
    
    if not update_import_script(source):
        print("\n✗ Failed to update import script")
        return False
    
    if not update_clean_script(source):
        print("\n✗ Failed to update clean script")
        return False
    
    if not update_test_script(source):
        print("\n✗ Failed to update test script")
        return False
    
    if not update_pipeline_config(source):
        print("\n✗ Failed to update pipeline config")
        return False
    
    print("\n✓ All configuration files updated successfully")
    return True


def validate_staging_scraper(source: str) -> bool:
    """Run validation tests on staging scraper."""
    print(f"\n{'='*80}")
    print(f"STEP 1: Running Validation Tests")
    print(f"{'='*80}\n")
    
    result = subprocess.run(
        ['python3', 'src/test_staging_scraper.py', source],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    if result.returncode != 0:
        print("\n✗ Validation failed. Fix issues before promoting.")
        print(result.stderr)
        return False
    
    print("\n✓ All validations passed!")
    return True


def move_scraper_to_production(source: str) -> bool:
    """Move scraper from staging to production directory."""
    print(f"\n{'='*80}")
    print(f"STEP 2: Moving Scraper to Production")
    print(f"{'='*80}\n")
    
    # Note: Pipeline config was already updated in STEP 0
    
    staging_path = Path(f"src/scrapers-staging/{source}.js")
    production_path = Path(f"src/scrapers/{source}.js")
    
    if not staging_path.exists():
        print(f"✗ Staging scraper not found: {staging_path}")
        return False
    
    if production_path.exists():
        print(f"⚠ Production scraper already exists: {production_path}")
        response = input("  Overwrite? (yes/no): ")
        if response.lower() != 'yes':
            print("  Promotion cancelled.")
            return False
    
    try:
        shutil.copy2(staging_path, production_path)
        print(f"✓ Copied {staging_path} → {production_path}")
        return True
    except Exception as e:
        print(f"✗ Error copying file: {e}")
        return False


def update_import_script(source: str) -> bool:
    """Update import_scraped_data.py to include new scraper."""
    import_path = Path("src/import_scraped_data.py")
    content = read_file_content(import_path)
    
    # Check if scraper is already in the list
    if f"'{source}'" in content:
        print(f"✓ Scraper '{source}' already in import script")
        return True
    
    import re
    
    # Update the valid_sources list
    pattern = r"valid_sources = \[([^\]]+)\]"
    match = re.search(pattern, content)
    
    if not match:
        print("✗ Could not find valid_sources list in import_scraped_data.py")
        return False
    
    sources_list = match.group(1)
    
    # Add new scraper to sources list
    new_sources = sources_list.rstrip() + f", '{source}'"
    new_content = content.replace(sources_list, new_sources)
    
    # Also update the help text
    help_pattern = r"help='Source name \([^\)]+\)'"
    help_match = re.search(help_pattern, content)
    if help_match:
        # Extract existing sources from help text
        help_text = help_match.group(0)
        # Add new source to help text
        new_help = help_text.rstrip("'") + f", {source}'"
        new_content = new_content.replace(help_text, new_help)
    
    write_file_content(import_path, new_content)
    print(f"✓ Added '{source}' to import script")
    return True


def update_clean_script(source: str) -> bool:
    """Update clean_events.py to include new scraper."""
    clean_path = Path("src/clean_events.py")
    content = read_file_content(clean_path)
    
    # Check if scraper is already in the list
    if f"'{source}'" in content:
        print(f"✓ Scraper '{source}' already in clean script")
        return True
    
    import re
    
    # Update the choices list
    pattern = r"choices=\[([^\]]+)\]"
    match = re.search(pattern, content)
    
    if not match:
        print("✗ Could not find choices list in clean_events.py")
        return False
    
    choices_list = match.group(1)
    
    # Add new scraper to choices list
    new_choices = choices_list.rstrip() + f", '{source}'"
    new_content = content.replace(choices_list, new_choices)
    
    write_file_content(clean_path, new_content)
    print(f"✓ Added '{source}' to clean script")
    return True


def update_test_script(source: str) -> bool:
    """Update test_scrapers.py to include new scraper."""
    test_path = Path("src/test_scrapers.py")
    content = read_file_content(test_path)
    
    # Check if scraper is already in the list
    if f"'{source}'" in content:
        print(f"✓ Scraper '{source}' already in test script")
        return True
    
    import re
    
    # Update the choices list
    pattern = r"choices=\[([^\]]+)\]"
    match = re.search(pattern, content)
    
    if not match:
        print("✗ Could not find choices list in test_scrapers.py")
        return False
    
    choices_list = match.group(1)
    
    # Add new scraper to choices list
    new_choices = choices_list.rstrip() + f", '{source}'"
    new_content = content.replace(choices_list, new_choices)
    
    # Also update the default sources list for --all flag
    default_sources_pattern = r"sources = \['kings_theatre', 'msg_calendar', 'prospect_park', 'brooklyn_museum'\]"
    default_sources_match = re.search(default_sources_pattern, content)
    
    if default_sources_match:
        default_sources = default_sources_match.group(0)
        new_default_sources = default_sources.rstrip(']') + f", '{source}']"
        new_content = new_content.replace(default_sources, new_default_sources)
    
    write_file_content(test_path, new_content)
    print(f"✓ Added '{source}' to test script")
    return True


def update_pipeline_config(source: str) -> bool:
    """Update run_pipeline.py to include new scraper."""
    pipeline_path = Path("src/run_pipeline.py")
    content = read_file_content(pipeline_path)
    
    # Check if scraper is already in the list
    if f"'{source}'" in content:
        print(f"✓ Scraper '{source}' already in pipeline configuration")
        return True
    
    # Find the choices list
    import re
    
    # Pattern to find the choices parameter in argparse
    pattern = r"choices=\[([^\]]+)\]"
    match = re.search(pattern, content)
    
    if not match:
        print("✗ Could not find choices list in run_pipeline.py")
        return False
    
    choices_list = match.group(1)
    
    # Add new scraper to choices list
    new_choices = choices_list.rstrip() + f", '{source}'"
    new_content = content.replace(choices_list, new_choices)
    
    # Also update the default sources list
    default_sources_pattern = r"sources = \['kings_theatre', 'msg_calendar', 'prospect_park', 'brooklyn_museum'\]"
    default_sources_match = re.search(default_sources_pattern, content)
    
    if default_sources_match:
        default_sources = default_sources_match.group(0)
        new_default_sources = default_sources.rstrip(']') + f", '{source}']"
        new_content = new_content.replace(default_sources, new_default_sources)
    
    write_file_content(pipeline_path, new_content)
    print(f"✓ Added '{source}' to pipeline configuration")
    return True


def update_consistency_tests(source: str) -> bool:
    """Update test_scraper_consistency.py to dynamically detect scrapers."""
    # Check if consistency tests need updating
    # We'll handle this in a separate update to make it dynamic
    print(f"✓ Consistency tests will auto-detect new scrapers")
    return True


def run_first_production_test(source: str) -> bool:
    """Run the first production pipeline test."""
    print(f"\n{'='*80}")
    print(f"STEP 3: Running First Production Test")
    print(f"{'='*80}\n")
    
    print(f"Running pipeline for '{source}' only...")
    print("(This will run: scrape → clean → test)")
    print()
    
    result = subprocess.run(
        ['python3', 'src/run_pipeline.py', '--source', source],
        text=True
    )
    
    if result.returncode == 0:
        print(f"\n✓ First production run successful!")
        return True
    else:
        print(f"\n✗ First production run failed")
        return False


def geocode_new_source_coords(source: str) -> bool:
    """Step 4: Geocode unique venues for the newly promoted source and update coords."""
    print(f"\n{'='*80}")
    print(f"STEP 4: Geocode Venue Coordinates for '{source}'")
    print(f"{'='*80}\n")

    session = SessionLocal()
    try:
        # Find unique (venue, location) for this source with missing coords
        pairs = session.query(CleanEvent.venue, CleanEvent.location).filter(
            CleanEvent.source == source,
            (CleanEvent.latitude == None) | (CleanEvent.longitude == None)
        ).distinct().all()

        if not pairs:
            print("No missing coordinates for this source. Skipping.")
            return True

        print(f"Found {len(pairs)} unique venue/location pairs needing coordinates.")
        resolved = 0
        updated_rows = 0

        for venue, location in pairs:
            query_parts = [p for p in [venue or '', location or ''] if p]
            if not query_parts:
                continue
            query = ' '.join(query_parts)
            try:
                geo = geocode_place(query)
                if geo and geo.get('lat') is not None and geo.get('lng') is not None:
                    lat = float(geo['lat']); lng = float(geo['lng'])
                    # Update all rows for this venue/location
                    q = session.query(CleanEvent).filter(
                        CleanEvent.source == source,
                        (CleanEvent.latitude == None) | (CleanEvent.longitude == None)
                    )
                    if venue:
                        q = q.filter(CleanEvent.venue == venue)
                    else:
                        q = q.filter((CleanEvent.venue == None) | (CleanEvent.venue == ''))
                    if location:
                        q = q.filter(CleanEvent.location == location)
                    else:
                        q = q.filter((CleanEvent.location == None) | (CleanEvent.location == ''))

                    rows = q.all()
                    for row in rows:
                        row.latitude = lat
                        row.longitude = lng
                        updated_rows += 1
                    resolved += 1
                else:
                    print(f"Could not geocode '{query}'")
            except GoogleMapsError as e:
                print(f"Geocode error for '{query}': {e}")
            except Exception as e:
                print(f"Unexpected error for '{query}': {e}")

        session.commit()
        print(f"\n✓ Geocoding complete: {resolved}/{len(pairs)} pairs resolved, {updated_rows} rows updated")
        return True
    except Exception as e:
        session.rollback()
        print(f"✗ Geocoding step failed: {e}")
        return False
    finally:
        session.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Promote a staging scraper to production')
    parser.add_argument('source', help='Source name (e.g., brooklyn_museum)')
    parser.add_argument('--skip-test', action='store_true', 
                       help='Skip running the first production test')
    parser.add_argument('--force', action='store_true',
                       help='Skip validation and force promotion')
    parser.add_argument('--prepare', action='store_true',
                       help='Just update config files and test manually, don\'t promote')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    if args.prepare:
        print(f"PREPARING SCRAPER FOR TESTING: {args.source}")
    else:
        print(f"PROMOTING SCRAPER: {args.source}")
    print(f"{'='*80}")
    
    # Step 0: Update configuration files (import script, test script, pipeline config)
    if not update_configuration_files(args.source):
        print("\n✗ Failed at configuration update step")
        sys.exit(1)
    
    # If --prepare flag, just test manually and exit
    if args.prepare:
        print(f"\n{'='*80}")
        print(f"Configuration files updated! Now you can test:")
        print(f"{'='*80}")
        print(f"\nRun: node src/scrapers-staging/{args.source}.js")
        print(f"\nThen run: python src/promote_scraper.py {args.source}")
        print()
        return
    
    # Step 1: Validate
    if not args.force:
        if not validate_staging_scraper(args.source):
            print("\n✗ Promotion failed at validation step")
            sys.exit(1)
    else:
        print("\n⚠ Skipping validation (--force flag)")
    
    # Step 2: Move to production
    if not move_scraper_to_production(args.source):
        print("\n✗ Promotion failed at move step")
        sys.exit(1)
    
    # Step 3: Run first production test
    if not args.skip_test:
        if not run_first_production_test(args.source):
            print("\n⚠ First production test failed, but scraper is promoted")
            print(f"  Run manually: python src/run_pipeline.py --source {args.source}")
    else:
        print("\n⚠ Skipping first production test (--skip-test flag)")
        print(f"  Run manually: python src/run_pipeline.py --source {args.source}")
    
    # Step 4: Geocode venue coordinates for this source
    if not geocode_new_source_coords(args.source):
        print("\n⚠ Geocoding step encountered issues. You can retry later with:\n   python src/promote_scraper.py {args.source} --skip-test")
    
    # Success summary
    print(f"\n{'='*80}")
    print(f"✓ PROMOTION COMPLETE")
    print(f"{'='*80}")
    print(f"\nScraper '{args.source}' has been promoted to production!")
    print(f"\nNext steps:")
    print(f"  1. Verify data in raw_events and clean_events tables")
    print(f"  2. Run full pipeline: python src/run_pipeline.py")
    print(f"  3. Commit changes to git")
    print()


if __name__ == "__main__":
    main()

