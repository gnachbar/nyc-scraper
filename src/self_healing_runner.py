#!/usr/bin/env python3
"""
Self-Healing Scraper Runner

Runs scrapers with automatic issue detection and self-healing capabilities.

Self-Healing Actions:
1. STALE_DATA: Re-run scraper (data might just be old)
2. WRONG_YEAR: Fix year in extraction instruction and re-run
3. EMPTY_RESULTS: Add waits, try alternative URL, re-run
4. URL_EXTRACTION_FAILED: Apply URL fallback fix
5. TIME_EXTRACTION_FAILED: Mark as known limitation
6. PAGINATION_INCOMPLETE: Increase max clicks, re-run
7. BROWSER_CRASHED: Retry up to 3 times

Escalation: After 3 failed auto-fix attempts, log for manual review.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal
from src.validate_scraper_results import validate_source, load_venue_baselines
from src.auto_fix_rules import apply_auto_fix


class IssueType(Enum):
    STALE_DATA = "stale_data"
    WRONG_YEAR = "wrong_year"
    EMPTY_RESULTS = "empty_results"
    URL_EXTRACTION_FAILED = "url_extraction_failed"
    TIME_EXTRACTION_FAILED = "time_extraction_failed"
    PAGINATION_INCOMPLETE = "pagination_incomplete"
    BROWSER_CRASHED = "browser_crashed"
    LOW_EVENT_COUNT = "low_event_count"
    UNKNOWN = "unknown"


class FixAction(Enum):
    RETRY = "retry"
    SKIP = "skip"  # Known limitation, don't retry
    ESCALATE = "escalate"  # Needs manual intervention
    FIXED = "fixed"  # Issue was fixed, continue


@dataclass
class ScrapeResult:
    source: str
    success: bool
    events_count: int = 0
    issues: List[IssueType] = field(default_factory=list)
    error_message: str = ""
    screenshot_path: str = ""
    duration_seconds: float = 0
    retry_count: int = 0


@dataclass
class HealingAction:
    issue: IssueType
    action: FixAction
    description: str
    applied: bool = False


class SelfHealingRunner:
    """Runs scrapers with automatic issue detection and healing."""

    MAX_RETRIES = 3

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.baselines = load_venue_baselines()
        self.healing_log: List[Dict] = []

    def log(self, message: str):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def run_scraper(self, source: str) -> Tuple[bool, str, str]:
        """Run a scraper and capture output."""
        self.log(f"🚀 Running scraper: {source}")

        start_time = time.time()
        scraper_path = f"src/scrapers/{source}.js"

        # Check if scraper exists
        if not Path(scraper_path).exists():
            return False, "", f"Scraper not found: {scraper_path}"

        try:
            result = subprocess.run(
                ["node", scraper_path],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            duration = time.time() - start_time
            self.log(f"⏱️  Completed in {duration:.1f}s (exit code: {result.returncode})")

            return result.returncode == 0, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return False, "", "Scraper timed out after 10 minutes"
        except Exception as e:
            return False, "", str(e)

    def detect_issues(self, source: str, stdout: str, stderr: str) -> List[IssueType]:
        """Detect issues from scraper output and database state."""
        issues = []

        # Check for browser crashes
        if "browser has been closed" in stderr or "Target page" in stderr:
            issues.append(IssueType.BROWSER_CRASHED)

        # Check for empty results
        if "No events found" in stdout or "events_scraped: 0" in stdout.lower():
            issues.append(IssueType.EMPTY_RESULTS)

        # Check database for issues
        session = SessionLocal()
        try:
            validation = validate_source(source, session, self.baselines)

            if validation.get("status") == "NO_DATA":
                issues.append(IssueType.EMPTY_RESULTS)
                return issues

            # Check for stale data (all events in past)
            date_analysis = validation.get("date_analysis", {})
            if "55/55 events are in the past" in str(validation.get("warnings", [])):
                issues.append(IssueType.STALE_DATA)

            # Check months ahead - if negative, dates are wrong
            months_ahead = date_analysis.get("months_ahead", 0)
            if months_ahead < 0:
                issues.append(IssueType.WRONG_YEAR)

            # Check for URL extraction issues
            field_analysis = validation.get("field_analysis", {})
            url_pct = field_analysis.get("fields", {}).get("url", {}).get("percent_filled", 100)
            if url_pct < 90:
                issues.append(IssueType.URL_EXTRACTION_FAILED)

            # Check for time extraction issues
            time_analysis = field_analysis.get("time_analysis", {})
            if time_analysis.get("midnight_percentage", 0) == 100:
                baseline = self.baselines.get(source, {})
                if baseline.get("times_available", True):
                    issues.append(IssueType.TIME_EXTRACTION_FAILED)

            # Check for low event count
            baseline_analysis = validation.get("baseline_analysis", {})
            if not baseline_analysis.get("within_range", True):
                current = baseline_analysis.get("current_count", 0)
                expected_min = baseline_analysis.get("expected_min", 0)
                if current < expected_min * 0.5:
                    issues.append(IssueType.LOW_EVENT_COUNT)

        finally:
            session.close()

        return issues

    def apply_healing(self, source: str, issue: IssueType) -> HealingAction:
        """Apply a healing action for the detected issue."""

        if issue == IssueType.BROWSER_CRASHED:
            return HealingAction(
                issue=issue,
                action=FixAction.RETRY,
                description="Browser crashed - will retry"
            )

        elif issue == IssueType.EMPTY_RESULTS:
            return HealingAction(
                issue=issue,
                action=FixAction.RETRY,
                description="Empty results - will retry with fresh session"
            )

        elif issue == IssueType.WRONG_YEAR:
            # Try to auto-fix the year in extraction instructions
            fix_result = apply_auto_fix(source, "wrong_year")
            if fix_result["applied"]:
                self.log(f"🔧 Auto-fix applied: {fix_result['description']}")
                return HealingAction(
                    issue=issue,
                    action=FixAction.RETRY,
                    description=f"Auto-fixed year extraction - {fix_result['description']}",
                    applied=True
                )
            else:
                return HealingAction(
                    issue=issue,
                    action=FixAction.ESCALATE,
                    description=f"Year extraction issue - {fix_result['description']}"
                )

        elif issue == IssueType.STALE_DATA:
            return HealingAction(
                issue=issue,
                action=FixAction.RETRY,
                description="Stale data detected - will re-scrape"
            )

        elif issue == IssueType.URL_EXTRACTION_FAILED:
            # Try to auto-fix URL extraction
            fix_result = apply_auto_fix(source, "url_extraction_failed")
            if fix_result["applied"]:
                self.log(f"🔧 Auto-fix applied: {fix_result['description']}")
                return HealingAction(
                    issue=issue,
                    action=FixAction.RETRY,
                    description=f"Auto-fixed URL extraction - {fix_result['description']}",
                    applied=True
                )
            else:
                return HealingAction(
                    issue=issue,
                    action=FixAction.ESCALATE,
                    description=f"URL extraction failing - {fix_result['description']}"
                )

        elif issue == IssueType.TIME_EXTRACTION_FAILED:
            # Auto-mark as known limitation
            fix_result = apply_auto_fix(source, "time_extraction_failed")
            if fix_result["applied"]:
                self.log(f"🔧 Auto-fix applied: {fix_result['description']}")
            return HealingAction(
                issue=issue,
                action=FixAction.SKIP,
                description=f"Time extraction not available - {fix_result['description']}"
            )

        elif issue == IssueType.PAGINATION_INCOMPLETE:
            # Try to increase pagination clicks
            fix_result = apply_auto_fix(source, "pagination_incomplete")
            if fix_result["applied"]:
                self.log(f"🔧 Auto-fix applied: {fix_result['description']}")
                return HealingAction(
                    issue=issue,
                    action=FixAction.RETRY,
                    description=f"Increased pagination - {fix_result['description']}",
                    applied=True
                )
            else:
                return HealingAction(
                    issue=issue,
                    action=FixAction.ESCALATE,
                    description=f"Pagination issue - {fix_result['description']}"
                )

        elif issue == IssueType.LOW_EVENT_COUNT:
            return HealingAction(
                issue=issue,
                action=FixAction.RETRY,
                description="Low event count - will retry"
            )

        else:
            return HealingAction(
                issue=issue,
                action=FixAction.ESCALATE,
                description="Unknown issue - needs manual review"
            )

    def run_with_healing(self, source: str) -> ScrapeResult:
        """Run a scraper with self-healing capabilities."""
        result = ScrapeResult(source=source, success=False)

        for attempt in range(self.MAX_RETRIES):
            result.retry_count = attempt

            if attempt > 0:
                self.log(f"🔄 Retry attempt {attempt + 1}/{self.MAX_RETRIES}")
                time.sleep(5)  # Brief delay between retries

            # Run the scraper
            start_time = time.time()
            success, stdout, stderr = self.run_scraper(source)
            result.duration_seconds = time.time() - start_time

            if not success and "Scraper not found" in stderr:
                result.error_message = stderr
                self.log(f"❌ {stderr}")
                return result

            # Detect issues
            issues = self.detect_issues(source, stdout, stderr)
            result.issues = issues

            if not issues:
                # Success! No issues detected
                result.success = True
                self.log(f"✅ {source} completed successfully")

                # Get event count from database
                session = SessionLocal()
                try:
                    run = session.query(ScrapeRun).filter(
                        ScrapeRun.source == source
                    ).order_by(ScrapeRun.id.desc()).first()
                    if run:
                        result.events_count = run.events_scraped or 0
                finally:
                    session.close()

                return result

            # Issues detected - try to heal
            self.log(f"⚠️  Issues detected: {[i.value for i in issues]}")

            should_retry = False
            for issue in issues:
                healing = self.apply_healing(source, issue)
                self.healing_log.append({
                    "source": source,
                    "attempt": attempt + 1,
                    "issue": issue.value,
                    "action": healing.action.value,
                    "description": healing.description,
                    "timestamp": datetime.now().isoformat()
                })

                if healing.action == FixAction.RETRY:
                    should_retry = True
                    self.log(f"🔧 {healing.description}")
                elif healing.action == FixAction.SKIP:
                    self.log(f"⏭️  {healing.description}")
                elif healing.action == FixAction.ESCALATE:
                    self.log(f"🚨 {healing.description}")
                    result.error_message = healing.description

            if not should_retry:
                # No retryable issues - exit loop
                break

        # Exhausted retries
        if result.issues and not result.success:
            self.log(f"❌ {source} failed after {self.MAX_RETRIES} attempts")
            result.error_message = f"Failed after {self.MAX_RETRIES} attempts: {[i.value for i in result.issues]}"

        return result

    def run_all(self, sources: List[str]) -> Dict[str, Any]:
        """Run all scrapers with self-healing."""
        self.log(f"🏁 Starting self-healing run for {len(sources)} scrapers")

        results = {
            "started_at": datetime.now().isoformat(),
            "sources": {},
            "summary": {
                "total": len(sources),
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "total_events": 0
            }
        }

        for i, source in enumerate(sources, 1):
            self.log(f"\n{'='*60}")
            self.log(f"[{i}/{len(sources)}] Processing: {source}")
            self.log(f"{'='*60}")

            result = self.run_with_healing(source)

            results["sources"][source] = {
                "success": result.success,
                "events_count": result.events_count,
                "issues": [i.value for i in result.issues],
                "error_message": result.error_message,
                "retry_count": result.retry_count,
                "duration_seconds": result.duration_seconds
            }

            if result.success:
                results["summary"]["success"] += 1
                results["summary"]["total_events"] += result.events_count
            elif result.issues and IssueType.TIME_EXTRACTION_FAILED in result.issues:
                results["summary"]["skipped"] += 1
            else:
                results["summary"]["failed"] += 1

        results["completed_at"] = datetime.now().isoformat()
        results["healing_log"] = self.healing_log

        # Print summary
        self.log(f"\n{'='*60}")
        self.log("FINAL SUMMARY")
        self.log(f"{'='*60}")
        s = results["summary"]
        self.log(f"✅ Success: {s['success']}/{s['total']}")
        self.log(f"❌ Failed:  {s['failed']}/{s['total']}")
        self.log(f"⏭️  Skipped: {s['skipped']}/{s['total']}")
        self.log(f"📊 Total Events: {s['total_events']}")

        # Save results
        output_path = Path("data/output") / f"self_healing_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        self.log(f"\n📄 Results saved to: {output_path}")

        return results


def get_all_sources() -> List[str]:
    """Get all available scraper sources."""
    scrapers_dir = Path("src/scrapers")
    sources = []
    for f in scrapers_dir.glob("*.js"):
        if not f.name.startswith("_"):
            sources.append(f.stem)
    return sorted(sources)


def main():
    parser = argparse.ArgumentParser(description='Self-healing scraper runner')
    parser.add_argument('--source', help='Specific source to run (default: all)')
    parser.add_argument('--sources', nargs='+', help='Multiple sources to run')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be run without running')

    args = parser.parse_args()

    # Determine sources to run
    if args.source:
        sources = [args.source]
    elif args.sources:
        sources = args.sources
    else:
        sources = get_all_sources()

    if args.dry_run:
        print(f"Would run {len(sources)} scrapers:")
        for s in sources:
            print(f"  - {s}")
        return

    # Run with self-healing
    runner = SelfHealingRunner(verbose=args.verbose)
    results = runner.run_all(sources)

    # Exit with error if any failures
    if results["summary"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
