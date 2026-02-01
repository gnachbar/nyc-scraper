#!/usr/bin/env python3
"""
Visual Verification Script

Takes a screenshot of a venue page and compares it with scraped data.
Uses Claude's vision capabilities to verify that:
1. The number of events matches
2. Event titles and dates are correctly extracted
3. No events are missing from the scrape
"""

import argparse
import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal


def get_scraped_events(source: str, limit: int = 20):
    """Get the latest scraped events for a source."""
    session = SessionLocal()
    try:
        run = session.query(ScrapeRun).filter(
            ScrapeRun.source == source
        ).order_by(ScrapeRun.id.desc()).first()

        if not run:
            return None, []

        events = session.query(RawEvent).filter(
            RawEvent.scrape_run_id == run.id
        ).order_by(RawEvent.start_time).limit(limit).all()

        return run, events
    finally:
        session.close()


def capture_screenshot(source: str):
    """Capture a screenshot of the venue page."""
    result = subprocess.run(
        ['node', 'src/verify_scraper_visually.js', source],
        capture_output=True,
        text=True,
        timeout=120
    )

    # Extract screenshot path from output
    for line in result.stdout.split('\n'):
        if 'Screenshot saved:' in line:
            path = line.split('Screenshot saved:')[1].strip()
            return path

    return None


def print_comparison_report(source: str, run, events, screenshot_path: str):
    """Print a comparison report for visual verification."""
    print(f"\n{'='*70}")
    print(f"VISUAL VERIFICATION REPORT: {source.upper()}")
    print(f"{'='*70}")

    print(f"\n📸 Screenshot: {screenshot_path}")
    print(f"📊 Database Run: #{run.id} ({run.completed_at})")
    print(f"📅 Events Scraped: {run.events_scraped}")

    if events:
        # Get date range
        dates = [e.start_time for e in events if e.start_time]
        if dates:
            print(f"📆 Date Range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}")

    print(f"\n📋 First {len(events)} Events (for comparison with screenshot):")
    print("-" * 70)

    for i, event in enumerate(events, 1):
        date_str = event.start_time.strftime('%a %b %d, %Y') if event.start_time else 'No date'
        time_str = event.start_time.strftime('%I:%M %p') if event.start_time else 'No time'
        print(f"{i:2}. {event.title[:50]:<50}")
        print(f"    📅 {date_str} at {time_str}")
        if event.url:
            print(f"    🔗 {event.url[:60]}...")
        print()

    print("-" * 70)
    print("\n🔍 VERIFICATION CHECKLIST:")
    print("   □ Count events visible on screenshot")
    print("   □ Verify first few event titles match")
    print("   □ Verify dates are in the future (not past)")
    print("   □ Check if 'Load More' or pagination exists")
    print(f"\n📸 View screenshot at: {screenshot_path}")
    print(f"   Use: open {screenshot_path}")


def main():
    parser = argparse.ArgumentParser(description='Visual verification of scraper results')
    parser.add_argument('source', help='Source/venue name to verify')
    parser.add_argument('--skip-screenshot', action='store_true', help='Skip taking new screenshot')
    parser.add_argument('--limit', type=int, default=20, help='Number of events to show')

    args = parser.parse_args()

    # Get scraped events
    run, events = get_scraped_events(args.source, args.limit)

    if not run:
        print(f"Error: No scrape runs found for {args.source}")
        sys.exit(1)

    # Capture screenshot (unless skipped)
    screenshot_path = None
    if not args.skip_screenshot:
        print(f"Capturing screenshot for {args.source}...")
        screenshot_path = capture_screenshot(args.source)
        if not screenshot_path:
            print("Warning: Failed to capture screenshot")

    # Find latest screenshot if we didn't capture one
    if not screenshot_path:
        screenshots = list(Path('screenshots').glob(f'{args.source}_*.png'))
        if screenshots:
            screenshot_path = str(max(screenshots, key=lambda p: p.stat().st_mtime))

    # Print comparison report
    print_comparison_report(args.source, run, events, screenshot_path or "No screenshot available")

    # Output JSON for programmatic use
    result = {
        "source": args.source,
        "screenshot_path": screenshot_path,
        "scrape_run_id": run.id,
        "events_count": run.events_scraped,
        "sample_events": [
            {
                "title": e.title,
                "date": e.start_time.isoformat() if e.start_time else None,
                "url": e.url
            }
            for e in events
        ]
    }

    # Save JSON for Claude to use
    output_file = f"data/output/verification_{args.source}.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n📄 Verification data saved to: {output_file}")


if __name__ == "__main__":
    main()
