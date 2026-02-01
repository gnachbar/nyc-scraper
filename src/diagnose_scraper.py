#!/usr/bin/env python3
"""
Scraper Diagnostic Module

Performs comprehensive diagnosis before attempting fixes.
Gathers evidence, compares with working scrapers, and identifies patterns.

This is the "retrospective" step in self-healing - understand WHY something
is broken before trying to fix it.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter

sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal


@dataclass
class ScraperProfile:
    """Profile of a scraper's characteristics and history."""
    source: str
    scraper_path: str

    # Historical data
    total_runs: int = 0
    successful_runs: int = 0
    last_success: Optional[datetime] = None
    last_run: Optional[datetime] = None
    days_since_success: Optional[int] = None
    avg_events_when_working: float = 0

    # Current state
    events_in_db: int = 0
    oldest_event_date: Optional[datetime] = None
    newest_event_date: Optional[datetime] = None
    data_is_stale: bool = False

    # Scraper characteristics
    pagination_method: str = "unknown"  # scroll, click, none
    uses_stagehand_observe: bool = False
    uses_click_button_until_gone: bool = False
    has_time_extraction: bool = False
    extraction_instruction_length: int = 0

    # Comparison with similar scrapers
    similar_scrapers: List[str] = field(default_factory=list)
    similar_scrapers_status: Dict[str, str] = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    """Complete diagnostic report for a scraper."""
    source: str
    generated_at: datetime
    profile: ScraperProfile

    # Failure analysis
    failure_category: str = "unknown"  # session_crash, empty_results, stale_data, extraction_error
    failure_pattern: str = ""

    # Evidence
    error_messages: List[str] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)

    # Comparison insights
    working_scrapers_pattern: str = ""
    failing_scrapers_pattern: str = ""
    key_difference: str = ""

    # Recommendations
    recommended_fixes: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0  # 0-1 confidence in diagnosis

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "generated_at": self.generated_at.isoformat(),
            "failure_category": self.failure_category,
            "failure_pattern": self.failure_pattern,
            "observations": self.observations,
            "key_difference": self.key_difference,
            "recommended_fixes": self.recommended_fixes,
            "confidence": self.confidence,
            "profile": {
                "total_runs": self.profile.total_runs,
                "successful_runs": self.profile.successful_runs,
                "days_since_success": self.profile.days_since_success,
                "avg_events_when_working": self.profile.avg_events_when_working,
                "pagination_method": self.profile.pagination_method,
                "data_is_stale": self.profile.data_is_stale,
                "similar_scrapers_status": self.profile.similar_scrapers_status,
            }
        }


class ScraperDiagnostics:
    """
    Diagnoses scraper issues by gathering evidence and comparing patterns.
    """

    def __init__(self, source: str, verbose: bool = True):
        self.source = source
        self.verbose = verbose
        self.scraper_path = f"src/scrapers/{source}.js"

    def log(self, message: str):
        if self.verbose:
            print(f"[DIAG] {message}")

    def run_full_diagnosis(self, error_output: str = "") -> DiagnosticReport:
        """
        Run complete diagnosis and return a report.
        """
        self.log(f"Starting diagnosis for: {self.source}")

        # Build scraper profile
        profile = self._build_profile()

        # Create report
        report = DiagnosticReport(
            source=self.source,
            generated_at=datetime.now(),
            profile=profile
        )

        # Analyze the failure
        self._analyze_failure(report, error_output)

        # Compare with other scrapers
        self._compare_with_others(report)

        # Generate recommendations
        self._generate_recommendations(report)

        # Save report
        self._save_report(report)

        return report

    def _build_profile(self) -> ScraperProfile:
        """Build a complete profile of this scraper."""
        profile = ScraperProfile(
            source=self.source,
            scraper_path=self.scraper_path
        )

        # Get historical data from database
        self._populate_history(profile)

        # Analyze scraper code
        self._analyze_scraper_code(profile)

        # Find similar scrapers
        self._find_similar_scrapers(profile)

        return profile

    def _populate_history(self, profile: ScraperProfile):
        """Get historical run data from database."""
        session = SessionLocal()
        try:
            # Get all runs for this source
            runs = session.query(ScrapeRun).filter(
                ScrapeRun.source == self.source
            ).order_by(ScrapeRun.id.desc()).all()

            profile.total_runs = len(runs)
            profile.successful_runs = sum(1 for r in runs if r.status == 'completed' and r.events_scraped > 0)

            if runs:
                profile.last_run = runs[0].started_at

                # Find last successful run
                for run in runs:
                    if run.status == 'completed' and run.events_scraped > 0:
                        profile.last_success = run.started_at
                        break

                if profile.last_success:
                    profile.days_since_success = (datetime.now() - profile.last_success).days

                # Calculate average events when working
                successful_counts = [r.events_scraped for r in runs if r.status == 'completed' and r.events_scraped > 0]
                if successful_counts:
                    profile.avg_events_when_working = sum(successful_counts) / len(successful_counts)

            # Get event data
            events = session.query(RawEvent).join(ScrapeRun).filter(
                ScrapeRun.source == self.source
            ).order_by(RawEvent.start_time).all()

            profile.events_in_db = len(events)

            if events:
                profile.oldest_event_date = events[0].start_time
                profile.newest_event_date = events[-1].start_time

                # Check if data is stale (all events in the past)
                if profile.newest_event_date and profile.newest_event_date < datetime.now():
                    profile.data_is_stale = True

        finally:
            session.close()

    def _analyze_scraper_code(self, profile: ScraperProfile):
        """Analyze the scraper code to understand its approach."""
        scraper_path = Path(self.scraper_path)
        if not scraper_path.exists():
            return

        content = scraper_path.read_text()

        # Detect pagination method - check multiple patterns
        has_click_button_until_gone = 'clickButtonUntilGone' in content
        has_direct_click = '.click()' in content and ('View more' in content or 'Load more' in content or 'Show more' in content)
        has_scroll_only = 'scrollToBottom' in content and not has_click_button_until_gone and not has_direct_click

        if has_click_button_until_gone:
            profile.pagination_method = "click_stagehand"
            profile.uses_click_button_until_gone = True
        elif has_direct_click:
            profile.pagination_method = "click_direct"
        elif has_scroll_only:
            profile.pagination_method = "scroll"
        else:
            profile.pagination_method = "none"

        # Check for Stagehand observe/act pattern
        if 'page.observe' in content or 'page.act' in content:
            profile.uses_stagehand_observe = True

        # Check for time extraction
        if 'extractEventTimesWithPython' in content or 'eventTime' in content:
            profile.has_time_extraction = True

        # Get extraction instruction length (indicator of complexity)
        instruction_match = re.search(r'extractEventsFromPage\([^,]+,\s*[`"\'](.+?)[`"\'],', content, re.DOTALL)
        if instruction_match:
            profile.extraction_instruction_length = len(instruction_match.group(1))

    def _find_similar_scrapers(self, profile: ScraperProfile):
        """Find scrapers with similar characteristics."""
        scrapers_dir = Path("src/scrapers")
        if not scrapers_dir.exists():
            return

        similar = []
        status = {}

        session = SessionLocal()
        try:
            for scraper_file in scrapers_dir.glob("*.js"):
                if scraper_file.stem == self.source:
                    continue

                content = scraper_file.read_text()

                # Detect pagination method for this scraper
                uses_click_stagehand = 'clickButtonUntilGone' in content
                uses_click_direct = '.click()' in content and ('View more' in content or 'Load more' in content or 'Show more' in content)
                uses_scroll_only = 'scrollToBottom' in content and not uses_click_stagehand and not uses_click_direct

                is_similar = False
                # Match click-based scrapers together (both stagehand and direct)
                if profile.pagination_method in ["click_stagehand", "click_direct"]:
                    if uses_click_stagehand or uses_click_direct:
                        is_similar = True
                elif profile.pagination_method == "scroll" and uses_scroll_only:
                    is_similar = True

                if is_similar:
                    source_name = scraper_file.stem
                    similar.append(source_name)

                    # Get status of this scraper
                    run = session.query(ScrapeRun).filter(
                        ScrapeRun.source == source_name
                    ).order_by(ScrapeRun.id.desc()).first()

                    if run:
                        days_ago = (datetime.now() - run.started_at).days if run.started_at else None
                        if days_ago is not None and days_ago < 7 and run.events_scraped > 0:
                            status[source_name] = "working"
                        elif days_ago is not None and days_ago > 30:
                            status[source_name] = "stale"
                        else:
                            status[source_name] = "unknown"
                    else:
                        status[source_name] = "no_data"
        finally:
            session.close()

        profile.similar_scrapers = similar
        profile.similar_scrapers_status = status

    def _analyze_failure(self, report: DiagnosticReport, error_output: str):
        """Analyze the failure mode."""

        # Parse error output for patterns
        if error_output:
            report.error_messages = [line for line in error_output.split('\n') if 'error' in line.lower() or 'failed' in line.lower()]

        # Categorize the failure - check most specific first
        if "Timeout" in error_output and "goto" in error_output:
            report.failure_category = "navigation_timeout"
            report.failure_pattern = "Page navigation timed out"
            report.observations.append("Page took too long to load - navigation timeout")

            # Check for timeout duration
            timeout_match = re.search(r'Timeout (\d+)ms exceeded', error_output)
            if timeout_match:
                report.observations.append(f"Timeout after {int(timeout_match.group(1))/1000}s")

        elif "Target page, context or browser has been closed" in error_output:
            report.failure_category = "session_crash"
            report.failure_pattern = "Browser session dies during pagination"
            report.observations.append("Browser session crashes after clicking pagination button")

            # Check for click count - look for specific patterns
            # Pattern: "Successfully clicked ... (1/25)" or "after X clicks"
            click_patterns = [
                r'Successfully clicked[^(]+\((\d+)/',  # "Successfully clicked ... (1/25)"
                r'after (\d+) clicks?',  # "after 1 click"
                r'Total.*clicks?: (\d+)',  # "Total clicks: 1"
            ]
            for pattern in click_patterns:
                match = re.search(pattern, error_output)
                if match:
                    report.observations.append(f"Session dies after {match.group(1)} click(s)")
                    break

        elif "events_scraped: 0" in error_output or report.profile.events_in_db == 0:
            report.failure_category = "empty_results"
            report.failure_pattern = "Scraper returns no events"
            report.observations.append("No events extracted from page")

        elif "ModuleNotFoundError" in error_output or "No module named" in error_output:
            report.failure_category = "python_dependency_missing"
            report.failure_pattern = "Python module not installed or wrong Python interpreter"

            # Extract module name
            module_match = re.search(r"No module named ['\"]?([^'\"]+)['\"]?", error_output)
            if module_match:
                report.observations.append(f"Missing Python module: {module_match.group(1)}")
            report.observations.append("May be using system Python instead of venv Python")

        elif "No more" in error_output and "button found after 0 clicks" in error_output:
            report.failure_category = "button_not_found"
            report.failure_pattern = "Pagination button not found - possible case sensitivity issue"
            report.observations.append("Button selector found 0 matches - check case sensitivity")
            report.observations.append("Tip: Use case-insensitive regex selector like text=/button text/i")

        elif report.profile.data_is_stale:
            report.failure_category = "stale_data"
            report.failure_pattern = "Scraper hasn't run successfully in a long time"
            report.observations.append(f"Last successful run was {report.profile.days_since_success} days ago")
            report.observations.append(f"All {report.profile.events_in_db} events in DB are in the past")

        else:
            report.failure_category = "unknown"
            report.failure_pattern = "Unable to determine failure pattern"

    def _compare_with_others(self, report: DiagnosticReport):
        """Compare with other scrapers to find patterns."""
        profile = report.profile

        working = [s for s, status in profile.similar_scrapers_status.items() if status == "working"]
        failing = [s for s, status in profile.similar_scrapers_status.items() if status in ["stale", "unknown"]]

        if working:
            report.working_scrapers_pattern = f"Working scrapers with same pagination: {', '.join(working)}"

        if failing:
            report.failing_scrapers_pattern = f"Other failing scrapers with same pagination: {', '.join(failing)}"

        # Identify key difference
        if profile.pagination_method in ["click_stagehand", "click_direct"]:
            # Check if scroll-based scrapers are working
            session = SessionLocal()
            try:
                scroll_scrapers = []
                for scraper_file in Path("src/scrapers").glob("*.js"):
                    content = scraper_file.read_text()
                    has_click = 'clickButtonUntilGone' in content or ('.click()' in content and ('View more' in content or 'Load more' in content))
                    if 'scrollToBottom' in content and not has_click:
                        source = scraper_file.stem
                        run = session.query(ScrapeRun).filter(
                            ScrapeRun.source == source
                        ).order_by(ScrapeRun.id.desc()).first()
                        if run and run.started_at:
                            days_ago = (datetime.now() - run.started_at).days
                            if days_ago < 7 and run.events_scraped > 0:
                                scroll_scrapers.append(source)

                if scroll_scrapers and not working:
                    method_name = "Stagehand observe/act" if profile.pagination_method == "click_stagehand" else "direct DOM"
                    report.key_difference = f"CLICK-BASED PAGINATION ({method_name}) IS FAILING. Scroll-based scrapers work: {', '.join(scroll_scrapers[:3])}"
                    report.observations.append("Pattern: Click-based pagination fails, scroll-based works")
            finally:
                session.close()

    def _generate_recommendations(self, report: DiagnosticReport):
        """Generate fix recommendations based on diagnosis."""

        if report.failure_category == "python_dependency_missing":
            report.recommended_fixes = [
                {
                    "priority": 1,
                    "action": "fix_python_path",
                    "description": "Update JavaScript to use venv Python instead of system Python",
                    "confidence": 0.9,
                    "rationale": "Python modules are installed in venv but code is calling system Python"
                },
                {
                    "priority": 2,
                    "action": "install_python_dependency",
                    "description": "Install the missing Python module",
                    "confidence": 0.7,
                    "rationale": "Module may need to be installed"
                }
            ]
            report.confidence = 0.9

        elif report.failure_category == "button_not_found":
            report.recommended_fixes = [
                {
                    "priority": 1,
                    "action": "fix_button_selector_case",
                    "description": "Make button selector case-insensitive using regex",
                    "confidence": 0.85,
                    "rationale": "Button text on page may have different case than selector. Use text=/pattern/i"
                },
                {
                    "priority": 2,
                    "action": "take_screenshot_and_inspect",
                    "description": "Take screenshot and manually inspect button text",
                    "confidence": 0.7,
                    "rationale": "Visual inspection can reveal exact button text"
                }
            ]
            report.confidence = 0.85

        elif report.failure_category == "navigation_timeout":
            report.recommended_fixes = [
                {
                    "priority": 1,
                    "action": "increase_navigation_timeout",
                    "description": "Increase page.goto timeout and use domcontentloaded instead of load",
                    "confidence": 0.9,
                    "rationale": "Page is slow to load. Using domcontentloaded is faster than waiting for full load."
                },
                {
                    "priority": 2,
                    "action": "add_retry_on_timeout",
                    "description": "Add retry logic for navigation timeout",
                    "confidence": 0.7,
                    "rationale": "Timeout may be transient - retry can help"
                }
            ]
            report.confidence = 0.9

        elif report.failure_category == "session_crash":
            if report.profile.pagination_method == "click_stagehand":
                report.recommended_fixes = [
                    {
                        "priority": 1,
                        "action": "use_direct_dom_click",
                        "description": "Replace Stagehand observe/act with direct DOM selector clicking",
                        "confidence": 0.7,
                        "rationale": "Stagehand AI-powered clicking may be causing session instability"
                    },
                    {
                        "priority": 2,
                        "action": "extract_before_pagination",
                        "description": "Extract visible events first, then attempt pagination as bonus",
                        "confidence": 0.7,
                        "rationale": "Get partial data rather than nothing if pagination fails"
                    },
                    {
                        "priority": 3,
                        "action": "switch_to_scroll",
                        "description": "Replace click-based pagination with scroll-based loading",
                        "confidence": 0.6,
                        "rationale": "Scroll-based scrapers are working. May require page structure analysis."
                    }
                ]
                report.confidence = 0.7
            elif report.profile.pagination_method == "click_direct":
                # Already using direct click, so the issue is elsewhere
                report.recommended_fixes = [
                    {
                        "priority": 1,
                        "action": "extract_before_pagination",
                        "description": "Extract visible events first, then attempt pagination as bonus",
                        "confidence": 0.8,
                        "rationale": "Get partial data rather than nothing if pagination fails"
                    },
                    {
                        "priority": 2,
                        "action": "add_session_recovery",
                        "description": "Add session health checks and recovery between clicks",
                        "confidence": 0.6,
                        "rationale": "Browser session may need more time/recovery between operations"
                    },
                    {
                        "priority": 3,
                        "action": "switch_to_scroll",
                        "description": "Replace click-based pagination with scroll-based loading",
                        "confidence": 0.5,
                        "rationale": "Scroll-based scrapers are working, but requires page restructure."
                    }
                ]
                report.confidence = 0.7
            else:
                report.recommended_fixes = [
                    {
                        "priority": 1,
                        "action": "investigate_session_crash",
                        "description": "Session crash without pagination - may be page-specific issue",
                        "confidence": 0.4,
                        "rationale": "Need to investigate what's causing the session to crash"
                    }
                ]
                report.confidence = 0.4

        elif report.failure_category == "empty_results":
            report.recommended_fixes = [
                {
                    "priority": 1,
                    "action": "increase_wait_times",
                    "description": "Add longer waits for page load and JavaScript execution",
                    "confidence": 0.6,
                    "rationale": "Page may not be fully loaded before extraction"
                },
                {
                    "priority": 2,
                    "action": "check_page_structure",
                    "description": "Verify page structure hasn't changed - take screenshot for analysis",
                    "confidence": 0.5,
                    "rationale": "Website may have changed its HTML structure"
                }
            ]
            report.confidence = 0.5

        elif report.failure_category == "stale_data":
            report.recommended_fixes = [
                {
                    "priority": 1,
                    "action": "rerun_scraper",
                    "description": "Simply rerun the scraper - it may work now",
                    "confidence": 0.4,
                    "rationale": "Scraper hasn't been run in a while, issue may be resolved"
                }
            ]
            report.confidence = 0.4

        else:
            report.recommended_fixes = [
                {
                    "priority": 1,
                    "action": "manual_investigation",
                    "description": "Requires manual investigation - take screenshot and analyze",
                    "confidence": 0.2,
                    "rationale": "Unable to determine failure pattern automatically"
                }
            ]
            report.confidence = 0.2

    def _save_report(self, report: DiagnosticReport):
        """Save diagnostic report to file."""
        output_dir = Path("data/output/diagnostics")
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"diagnosis_{self.source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = output_dir / filename

        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2, default=str)

        self.log(f"Diagnostic report saved: {output_path}")
        return output_path

    def print_report(self, report: DiagnosticReport):
        """Print a human-readable diagnostic report."""
        print("\n" + "=" * 70)
        print(f"DIAGNOSTIC REPORT: {report.source}")
        print("=" * 70)

        print(f"\n📊 PROFILE:")
        print(f"   Total runs: {report.profile.total_runs}")
        print(f"   Successful runs: {report.profile.successful_runs}")
        print(f"   Days since success: {report.profile.days_since_success or 'Never succeeded'}")
        print(f"   Avg events when working: {report.profile.avg_events_when_working:.0f}")
        print(f"   Events in DB: {report.profile.events_in_db}")
        print(f"   Data is stale: {report.profile.data_is_stale}")
        print(f"   Pagination method: {report.profile.pagination_method}")

        print(f"\n🔍 FAILURE ANALYSIS:")
        print(f"   Category: {report.failure_category}")
        print(f"   Pattern: {report.failure_pattern}")

        if report.observations:
            print(f"\n👁️ OBSERVATIONS:")
            for obs in report.observations:
                print(f"   • {obs}")

        if report.key_difference:
            print(f"\n⚡ KEY INSIGHT:")
            print(f"   {report.key_difference}")

        if report.recommended_fixes:
            print(f"\n💡 RECOMMENDED FIXES (confidence: {report.confidence:.0%}):")
            for fix in report.recommended_fixes:
                print(f"   {fix['priority']}. [{fix['action']}] {fix['description']}")
                print(f"      Rationale: {fix['rationale']}")

        print("\n" + "=" * 70)


def diagnose_scraper(source: str, error_output: str = "", verbose: bool = True) -> DiagnosticReport:
    """
    Main entry point for diagnosing a scraper.

    Args:
        source: Name of the scraper to diagnose
        error_output: Optional error output from a recent run
        verbose: Whether to print progress

    Returns:
        DiagnosticReport with findings and recommendations
    """
    diagnostics = ScraperDiagnostics(source, verbose=verbose)
    report = diagnostics.run_full_diagnosis(error_output)

    if verbose:
        diagnostics.print_report(report)

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Diagnose scraper issues')
    parser.add_argument('source', help='Source/scraper name to diagnose')
    parser.add_argument('--error-file', help='File containing error output')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode')

    args = parser.parse_args()

    error_output = ""
    if args.error_file and Path(args.error_file).exists():
        error_output = Path(args.error_file).read_text()

    report = diagnose_scraper(args.source, error_output, verbose=not args.quiet)

    # Exit with code based on confidence
    if report.confidence < 0.3:
        sys.exit(2)  # Low confidence - needs manual intervention
    elif report.failure_category != "unknown":
        sys.exit(1)  # Issue identified
    else:
        sys.exit(0)
