#!/usr/bin/env python3
"""
Unified Scraper Runner

Simple CLI to run scrapers with self-healing capabilities.

Usage:
    python src/run_scrapers.py                    # Run all scrapers
    python src/run_scrapers.py --source venue     # Run specific scraper
    python src/run_scrapers.py --failed-only      # Re-run only failed scrapers
    python src/run_scrapers.py --validate         # Run validation only
    python src/run_scrapers.py --status           # Show current status
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from src.self_healing_runner import SelfHealingRunner, get_all_sources
from src.validate_scraper_results import run_all_validations, load_venue_baselines


def show_status():
    """Show current scraper status from last run."""
    # Find most recent run file
    output_dir = Path("data/output")
    run_files = list(output_dir.glob("self_healing_run_*.json"))

    if not run_files:
        print("No previous runs found. Run scrapers first.")
        return

    latest = max(run_files, key=lambda p: p.stat().st_mtime)
    with open(latest) as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print(f"LAST RUN: {latest.name}")
    print(f"{'='*60}")
    print(f"Started:  {data.get('started_at', 'N/A')}")
    print(f"Completed: {data.get('completed_at', 'N/A')}")

    s = data.get("summary", {})
    print(f"\n✅ Success: {s.get('success', 0)}/{s.get('total', 0)}")
    print(f"❌ Failed:  {s.get('failed', 0)}/{s.get('total', 0)}")
    print(f"⏭️  Skipped: {s.get('skipped', 0)}/{s.get('total', 0)}")
    print(f"📊 Total Events: {s.get('total_events', 0)}")

    # Show failed scrapers
    failed = [k for k, v in data.get("sources", {}).items() if not v.get("success")]
    if failed:
        print(f"\n❌ Failed Scrapers:")
        for src in failed:
            info = data["sources"][src]
            print(f"   - {src}: {info.get('error_message', 'Unknown error')}")

    # Show healing actions
    healing_log = data.get("healing_log", [])
    if healing_log:
        print(f"\n🔧 Healing Actions Applied: {len(healing_log)}")
        for h in healing_log[-5:]:  # Show last 5
            print(f"   - {h['source']}: {h['action']} ({h['issue']})")


def get_failed_sources() -> list:
    """Get list of failed sources from last run."""
    output_dir = Path("data/output")
    run_files = list(output_dir.glob("self_healing_run_*.json"))

    if not run_files:
        return []

    latest = max(run_files, key=lambda p: p.stat().st_mtime)
    with open(latest) as f:
        data = json.load(f)

    return [k for k, v in data.get("sources", {}).items() if not v.get("success")]


def run_validation():
    """Run validation on all scrapers."""
    sources = get_all_sources()
    print(f"\n🔍 Running validation for {len(sources)} scrapers...\n")
    run_all_validations(sources, verbose=False)


def main():
    parser = argparse.ArgumentParser(
        description='Run scrapers with self-healing capabilities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/run_scrapers.py                    # Run all scrapers
  python src/run_scrapers.py --source bam       # Run BAM scraper only
  python src/run_scrapers.py --failed-only      # Re-run failed scrapers
  python src/run_scrapers.py --validate         # Run validation only
  python src/run_scrapers.py --status           # Show last run status
        """
    )

    parser.add_argument('--source', '-s', help='Run specific source only')
    parser.add_argument('--sources', nargs='+', help='Run multiple specific sources')
    parser.add_argument('--failed-only', action='store_true', help='Re-run only failed scrapers from last run')
    parser.add_argument('--validate', '-v', action='store_true', help='Run validation only (no scraping)')
    parser.add_argument('--status', action='store_true', help='Show status from last run')
    parser.add_argument('--list', '-l', action='store_true', help='List all available scrapers')

    args = parser.parse_args()

    # Handle special commands
    if args.status:
        show_status()
        return

    if args.list:
        sources = get_all_sources()
        print(f"\nAvailable scrapers ({len(sources)}):")
        for s in sources:
            print(f"  - {s}")
        return

    if args.validate:
        run_validation()
        return

    # Determine sources to run
    if args.source:
        sources = [args.source]
    elif args.sources:
        sources = args.sources
    elif args.failed_only:
        sources = get_failed_sources()
        if not sources:
            print("No failed scrapers to re-run!")
            return
        print(f"Re-running {len(sources)} failed scrapers: {', '.join(sources)}")
    else:
        sources = get_all_sources()

    # Run scrapers with self-healing
    print(f"\n🏁 Starting self-healing scraper run")
    print(f"   Sources: {len(sources)}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    runner = SelfHealingRunner(verbose=True)
    results = runner.run_all(sources)

    # Run validation after scraping
    print("\n🔍 Running post-scrape validation...")
    run_validation()

    # Return appropriate exit code
    if results["summary"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
