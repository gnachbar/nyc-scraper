#!/usr/bin/env python3
"""
Run Staging Scraper with Comprehensive Feedback

Executes a staging scraper and returns comprehensive JSON output including:
- Execution status and timing
- Screenshot path for visual verification
- Database query results (events scraped, sample events)
- Structural validation test results

This enables automated scraper iteration loops with visual verification.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal


def find_latest_screenshot(source: str, screenshots_dir: str = "screenshots") -> Optional[str]:
    """Find the most recent screenshot for a source."""
    pattern = os.path.join(screenshots_dir, f"{source}_*.png")
    screenshots = glob(pattern)

    if not screenshots:
        return None

    # Sort by modification time, most recent first
    screenshots.sort(key=os.path.getmtime, reverse=True)
    return screenshots[0]


def get_browserbase_url_from_output(output: str) -> Optional[str]:
    """Extract Browserbase session URL from scraper output."""
    match = re.search(r'https://browserbase\.com/sessions/([a-zA-Z0-9-]+)', output)
    if match:
        return match.group(0)
    return None


def get_latest_scrape_run(source: str) -> Optional[Dict[str, Any]]:
    """Get the latest scrape run info from database."""
    try:
        session = SessionLocal()
        latest_run = session.query(ScrapeRun).filter(
            ScrapeRun.source == source
        ).order_by(ScrapeRun.id.desc()).first()

        if not latest_run:
            session.close()
            return None

        result = {
            "scrape_run_id": latest_run.id,
            "status": latest_run.status,
            "events_scraped": latest_run.events_scraped,
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
            "error_message": latest_run.error_message
        }

        session.close()
        return result
    except Exception as e:
        return {"error": str(e)}


def get_sample_events(source: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get sample events from the latest scrape run."""
    try:
        session = SessionLocal()

        # Get the latest scrape run
        latest_run = session.query(ScrapeRun).filter(
            ScrapeRun.source == source
        ).order_by(ScrapeRun.id.desc()).first()

        if not latest_run:
            session.close()
            return []

        # Get events from this run
        events = session.query(RawEvent).filter(
            RawEvent.scrape_run_id == latest_run.id
        ).limit(limit).all()

        sample = []
        for event in events:
            sample.append({
                "title": event.title,
                "date": event.start_time.strftime("%Y-%m-%d") if event.start_time else None,
                "time": event.start_time.strftime("%H:%M") if event.start_time else None,
                "venue": event.venue or event.location,
                "url": event.url
            })

        session.close()
        return sample
    except Exception as e:
        return [{"error": str(e)}]


def check_time_regression(source: str) -> Dict[str, Any]:
    """Check if all events have the same time (regression indicator)."""
    try:
        session = SessionLocal()

        latest_run = session.query(ScrapeRun).filter(
            ScrapeRun.source == source
        ).order_by(ScrapeRun.id.desc()).first()

        if not latest_run:
            session.close()
            return {"checked": False, "reason": "No scrape runs found"}

        events = session.query(RawEvent).filter(
            RawEvent.scrape_run_id == latest_run.id
        ).all()

        if len(events) < 2:
            session.close()
            return {"checked": False, "reason": "Not enough events to check"}

        start_times = [e.start_time for e in events if e.start_time]

        if not start_times:
            session.close()
            return {"all_same_time": False, "events_with_times": 0, "total_events": len(events)}

        unique_times = set(start_times)
        all_same = len(unique_times) == 1

        session.close()
        return {
            "all_same_time": all_same,
            "events_with_times": len(start_times),
            "total_events": len(events),
            "unique_time_count": len(unique_times)
        }
    except Exception as e:
        return {"error": str(e)}


def run_structural_validation(source: str) -> Dict[str, Any]:
    """Run structural validation tests and return results."""
    try:
        result = subprocess.run(
            ['python3', 'src/test_staging_scraper.py', source, '--json'],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Try to parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            # Fallback: run without --json and parse manually
            result = subprocess.run(
                ['python3', 'src/test_staging_scraper.py', source],
                capture_output=True,
                text=True,
                timeout=60
            )

            # Parse the output for pass/fail indicators
            output = result.stdout
            results = {}

            # Look for checkmarks and X marks
            for line in output.split('\n'):
                if line.strip().startswith('✓') or line.strip().startswith('✗'):
                    # Extract test name from summary section
                    parts = line.strip().split(' ', 1)
                    if len(parts) == 2:
                        passed = parts[0] == '✓'
                        test_name = parts[1].strip()
                        results[test_name] = passed

            all_passed = all(results.values()) if results else False
            return {"all_passed": all_passed, "results": results}

    except subprocess.TimeoutExpired:
        return {"error": "Validation timed out"}
    except Exception as e:
        return {"error": str(e)}


def run_staging_scraper(source: str, timeout: int = 600) -> Dict[str, Any]:
    """
    Run a staging scraper and return comprehensive feedback as JSON.

    Args:
        source: Name of the scraper (e.g., 'kings_theatre')
        timeout: Maximum execution time in seconds (default: 10 minutes)

    Returns:
        Dict with execution info, screenshot path, database results, and validation
    """
    scraper_path = Path(f"src/scrapers-staging/{source}.js")

    if not scraper_path.exists():
        return {
            "execution": {
                "success": False,
                "error": f"Scraper file not found: {scraper_path}"
            }
        }

    # Record start time
    start_time = time.time()

    # Run the scraper
    try:
        result = subprocess.run(
            ['node', str(scraper_path)],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        duration = time.time() - start_time
        success = result.returncode == 0

        execution_info = {
            "success": success,
            "exit_code": result.returncode,
            "duration_seconds": round(duration, 2),
            "browserbase_url": get_browserbase_url_from_output(result.stdout + result.stderr)
        }

        if not success:
            execution_info["stdout"] = result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
            execution_info["stderr"] = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr

    except subprocess.TimeoutExpired:
        return {
            "execution": {
                "success": False,
                "error": f"Scraper timed out after {timeout} seconds"
            }
        }
    except Exception as e:
        return {
            "execution": {
                "success": False,
                "error": str(e)
            }
        }

    # Find screenshot
    screenshot_path = find_latest_screenshot(source)
    screenshot_info = {
        "path": screenshot_path,
        "exists": screenshot_path is not None and os.path.exists(screenshot_path) if screenshot_path else False
    }

    # Get database info
    scrape_run = get_latest_scrape_run(source)
    sample_events = get_sample_events(source, limit=5)
    time_check = check_time_regression(source)

    database_info = {
        "scrape_run_id": scrape_run.get("scrape_run_id") if scrape_run else None,
        "events_scraped": scrape_run.get("events_scraped", 0) if scrape_run else 0,
        "events_with_times": time_check.get("events_with_times", 0),
        "all_same_time": time_check.get("all_same_time", False),
        "sample_events": sample_events
    }

    # Run structural validation
    validation = run_structural_validation(source)

    return {
        "execution": execution_info,
        "screenshot": screenshot_info,
        "database": database_info,
        "structural_validation": validation
    }


def main():
    parser = argparse.ArgumentParser(
        description='Run a staging scraper and return comprehensive JSON feedback'
    )
    parser.add_argument('source', help='Source name (e.g., brooklyn_bowl)')
    parser.add_argument(
        '--json',
        action='store_true',
        default=True,
        help='Output results as JSON (default: true)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Timeout in seconds (default: 600 = 10 minutes)'
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty print JSON output'
    )

    args = parser.parse_args()

    # Run the scraper
    result = run_staging_scraper(args.source, timeout=args.timeout)

    # Output as JSON
    if args.pretty:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps(result, default=str))

    # Exit with appropriate code
    if result.get("execution", {}).get("success"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
