#!/usr/bin/env python3
"""
Visual Self-Healing Scraper

Uses screenshots, diagnostics, and visual analysis to diagnose and fix scraper issues.
This creates an iterative loop:

1. RUN: Execute scraper, capture screenshot
2. DIAGNOSE: Run comprehensive diagnosis (history, code analysis, pattern matching)
3. ANALYZE: Compare screenshot to scraped data (visual verification)
4. FIX: Apply fixes based on diagnosis
5. REPEAT: Until success or max iterations

The key insight is that diagnosis comes BEFORE fixing - we gather evidence
and understand WHY something is broken before attempting fixes.

For automated operation, this integrates with Claude API for visual analysis.
For manual operation, it saves screenshots and data for human/Claude review.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal
from src.diagnose_scraper import diagnose_scraper, DiagnosticReport
from src.browserbase_feedback import (
    extract_session_id_from_output,
    analyze_session_for_healing,
    get_session_diagnostics
)


@dataclass
class VisualAnalysis:
    """Results of visual analysis of a screenshot."""
    screenshot_path: str
    events_visible_estimate: int = 0
    has_load_more_button: bool = False
    has_pagination: bool = False
    page_appears_complete: bool = True
    issues_detected: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    raw_analysis: str = ""


@dataclass
class ScraperIteration:
    """Results of a single scraper iteration."""
    iteration: int
    success: bool
    events_scraped: int
    screenshot_path: str
    duration_seconds: float
    issues: List[str] = field(default_factory=list)
    fixes_applied: List[str] = field(default_factory=list)
    visual_analysis: Optional[VisualAnalysis] = None
    diagnostic_report: Optional[DiagnosticReport] = None


class VisualSelfHealer:
    """
    Self-healing scraper that uses visual analysis.
    """

    MAX_ITERATIONS = 5

    def __init__(self, source: str, verbose: bool = True):
        self.source = source
        self.verbose = verbose
        self.iterations: List[ScraperIteration] = []
        self.scraper_path = f"src/scrapers/{source}.js"

    def log(self, message: str):
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")

    def run_scraper_with_screenshot(self) -> Tuple[bool, int, str, str, str, str]:
        """
        Run scraper and capture screenshot.
        Returns: (success, events_count, screenshot_path, stdout, stderr, session_id)
        """
        self.log(f"🚀 Running scraper: {self.source}")

        # Run the scraper
        start_time = time.time()
        try:
            result = subprocess.run(
                ["node", self.scraper_path],
                capture_output=True,
                text=True,
                timeout=300
            )
            success = result.returncode == 0
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired:
            return False, 0, "", "", "Timeout after 5 minutes", ""
        except Exception as e:
            return False, 0, "", "", str(e), ""

        duration = time.time() - start_time
        self.log(f"⏱️  Scraper completed in {duration:.1f}s")

        # Extract Browserbase session ID from output
        session_id = extract_session_id_from_output(stdout) or extract_session_id_from_output(stderr) or ""
        if session_id:
            self.log(f"🔗 Browserbase session: {session_id}")

        # Get events count from database
        events_count = self._get_events_count()
        self.log(f"📊 Events in database: {events_count}")

        # Capture screenshot for analysis
        screenshot_path = self._capture_screenshot()
        self.log(f"📸 Screenshot: {screenshot_path}")

        return success, events_count, screenshot_path, stdout, stderr, session_id

    def _get_events_count(self) -> int:
        """Get event count from latest scrape run."""
        session = SessionLocal()
        try:
            run = session.query(ScrapeRun).filter(
                ScrapeRun.source == self.source
            ).order_by(ScrapeRun.id.desc()).first()
            return run.events_scraped if run else 0
        finally:
            session.close()

    def _get_sample_events(self, limit: int = 10) -> List[Dict]:
        """Get sample events from database."""
        session = SessionLocal()
        try:
            run = session.query(ScrapeRun).filter(
                ScrapeRun.source == self.source
            ).order_by(ScrapeRun.id.desc()).first()

            if not run:
                return []

            events = session.query(RawEvent).filter(
                RawEvent.scrape_run_id == run.id
            ).order_by(RawEvent.start_time).limit(limit).all()

            return [
                {
                    "title": e.title,
                    "date": e.start_time.strftime("%Y-%m-%d %H:%M") if e.start_time else None,
                    "url": e.url
                }
                for e in events
            ]
        finally:
            session.close()

    def _capture_screenshot(self) -> str:
        """Capture screenshot of the venue page."""
        try:
            result = subprocess.run(
                ["node", "src/verify_scraper_visually.js", self.source],
                capture_output=True,
                text=True,
                timeout=120
            )

            # Extract screenshot path from output
            for line in result.stdout.split('\n'):
                if 'Screenshot saved:' in line:
                    return line.split('Screenshot saved:')[1].strip()

            # Find latest screenshot if capture didn't report path
            screenshots = list(Path('screenshots').glob(f'{self.source}_*.png'))
            if screenshots:
                return str(max(screenshots, key=lambda p: p.stat().st_mtime))

        except Exception as e:
            self.log(f"⚠️  Screenshot capture failed: {e}")

        return ""

    def analyze_visually(self, screenshot_path: str, events_scraped: int) -> VisualAnalysis:
        """
        Analyze screenshot and compare with scraped data.

        In automated mode, this would call Claude API.
        For now, we save the data for manual/interactive analysis.
        """
        analysis = VisualAnalysis(screenshot_path=screenshot_path)

        # Save analysis context for Claude to review
        context = {
            "source": self.source,
            "screenshot_path": screenshot_path,
            "events_scraped": events_scraped,
            "sample_events": self._get_sample_events(10),
            "timestamp": datetime.now().isoformat(),
            "analysis_prompt": f"""
Please analyze this screenshot of {self.source} events page.

1. COUNT: Approximately how many events are visible on the page?
2. PAGINATION: Is there a "Load More" button, pagination controls, or infinite scroll?
3. COMPLETENESS: Does the page appear to show all events, or does it look cut off?
4. COMPARISON: We scraped {events_scraped} events. Does this match what's visible?
5. ISSUES: Are there any obvious issues (page not loaded, error messages, captcha)?
6. RECOMMENDATIONS: What should we fix in the scraper?

Scraped events sample:
{json.dumps(self._get_sample_events(5), indent=2)}
"""
        }

        # Save context file
        context_path = Path("data/output") / f"visual_analysis_{self.source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        context_path.parent.mkdir(parents=True, exist_ok=True)
        with open(context_path, "w") as f:
            json.dump(context, f, indent=2)

        self.log(f"📝 Analysis context saved to: {context_path}")
        analysis.raw_analysis = str(context_path)

        return analysis

    def diagnose_issues(self, stdout: str, stderr: str, events_count: int, analysis: VisualAnalysis) -> List[str]:
        """Diagnose issues based on scraper output and visual analysis."""
        issues = []

        # Check for site blocking (learned: connolly_theatre, village_east)
        if "ERR_TUNNEL_CONNECTION_FAILED" in stderr or "ERR_TUNNEL_CONNECTION_FAILED" in stdout:
            issues.append("SITE_BLOCKED")
            return issues  # No point checking other issues if site is blocked

        # Check for browser crashes specifically after Load More click
        # (learned: beacon_theatre, carnegie_hall crash after Load More)
        if ("browser has been closed" in stderr or "Target page" in stderr):
            if "Load More" in stdout or "clickButtonUntilGone" in stdout:
                issues.append("LOAD_MORE_CRASH")
            else:
                issues.append("BROWSER_CRASHED")

        # Check for 404 pages (learned: apollo_theater, greenwich_house)
        if "404" in stdout or "Page Not Found" in stdout or "couldn't find anything" in stdout.lower():
            issues.append("PAGE_404")

        # Check for bad URL extraction (learned: bowery_ballroom)
        if "Event Image Link" in stdout or "eventUrl" in stdout and "http" not in stdout:
            issues.append("BAD_URL_EXTRACTION")

        # Check for empty results
        if events_count == 0:
            issues.append("EMPTY_RESULTS")

        # Check for timeout
        if "timeout" in stderr.lower():
            issues.append("TIMEOUT")

        # Check for pagination issues (based on output patterns)
        if "Load More" in stdout and events_count < 20:
            issues.append("PAGINATION_INCOMPLETE")

        # Check if we got fewer events than expected from baseline
        baseline = self._get_baseline()
        if baseline:
            min_expected = baseline.get("typical_event_count_min", 0)
            if events_count < min_expected * 0.5:
                issues.append("LOW_EVENT_COUNT")

        return issues

    def _get_baseline(self) -> Dict:
        """Get baseline config for this source."""
        baseline_path = Path("src/config/venue_baselines.yaml")
        if baseline_path.exists():
            import yaml
            with open(baseline_path) as f:
                data = yaml.safe_load(f)
                return data.get("venues", {}).get(self.source, {})
        return {}

    def apply_fix(self, issue: str, diagnostic_report: Optional[DiagnosticReport] = None) -> Tuple[bool, str]:
        """Apply a fix for the detected issue, using diagnostic recommendations when available."""

        # First, check if we have diagnostic recommendations
        if diagnostic_report and diagnostic_report.recommended_fixes:
            return self._apply_diagnostic_fix(diagnostic_report)

        # Fall back to issue-based fixes

        # NEW: Handle site blocking (learned from connolly_theatre, village_east)
        if issue == "SITE_BLOCKED":
            return False, "Site is blocking Browserbase (ERR_TUNNEL_CONNECTION_FAILED). Cannot auto-fix - site may need different proxy or manual investigation."

        # NEW: Handle Load More causing crash (learned from beacon_theatre, carnegie_hall)
        elif issue == "LOAD_MORE_CRASH":
            return self._remove_load_more_clicking()

        # NEW: Handle 404 pages (learned from apollo_theater, greenwich_house)
        elif issue == "PAGE_404":
            return self._fix_404_navigation()

        # NEW: Handle bad URL extraction (learned from bowery_ballroom)
        elif issue == "BAD_URL_EXTRACTION":
            return self._fix_url_extraction_prompt()

        elif issue == "BROWSER_CRASHED" or issue == "SESSION_CRASH" or issue == "DIAG_SESSION_CRASH":
            # Just retry - browser issues are often transient
            return True, "Will retry with fresh browser session"

        elif issue == "EMPTY_RESULTS" or issue == "DIAG_EMPTY_RESULTS":
            # Try adding longer waits
            return self._add_longer_waits()

        elif issue == "PAGINATION_INCOMPLETE":
            # Increase pagination clicks
            return self._increase_pagination()

        elif issue == "LOW_EVENT_COUNT":
            # Could be pagination or page structure issue
            return self._increase_pagination()

        elif issue == "TIMEOUT":
            # Reduce scope or increase timeout
            return True, "Will retry - timeout may be transient"

        elif issue == "STALE_DATA" or issue == "DIAG_STALE_DATA":
            # Just needs a fresh run
            return True, "Will run scraper to refresh stale data"

        elif issue == "NO_SCROLL" or issue == "INSUFFICIENT_SCROLL":
            # Fix scroll implementation
            return self._fix_scroll_implementation()

        elif issue == "CLICK_FAILURE":
            # Add extraction before click as fallback
            return self._add_extract_before_pagination()

        elif issue == "DIAG_NAVIGATION_TIMEOUT":
            # Fix navigation timeout
            return self._fix_navigation_timeout()

        return False, f"No fix available for: {issue}"

    def _apply_diagnostic_fix(self, report: DiagnosticReport) -> Tuple[bool, str]:
        """Apply fix based on diagnostic recommendations."""
        if not report.recommended_fixes:
            return False, "No recommendations available"

        # Get top recommendation
        fix = report.recommended_fixes[0]
        action = fix['action']

        self.log(f"🔧 Applying diagnostic fix: {action}")
        self.log(f"   Rationale: {fix['rationale']}")

        if action == "switch_to_scroll":
            return self._switch_to_scroll_pagination()

        elif action == "extract_before_pagination":
            return self._add_extract_before_pagination()

        elif action == "use_direct_dom_click":
            return self._switch_to_direct_dom_click()

        elif action == "increase_wait_times":
            return self._add_longer_waits()

        elif action == "check_page_structure":
            # This requires visual inspection - just note it
            return False, "Requires visual inspection of screenshot"

        elif action == "rerun_scraper":
            return True, "Will rerun scraper"

        elif action == "manual_investigation":
            return False, "Requires manual investigation"

        elif action == "add_session_recovery":
            return self._add_session_recovery()

        elif action == "investigate_session_crash":
            return False, "Requires manual investigation of session crash"

        elif action == "fix_scroll":
            return self._fix_scroll_implementation()

        elif action == "verify_scroll":
            return self._add_scroll_verification()

        elif action == "verify_scroll_implementation":
            return self._add_scroll_verification()

        elif action == "increase_navigation_timeout":
            return self._fix_navigation_timeout()

        elif action == "add_retry_on_timeout":
            return self._add_navigation_retry()

        elif action == "fix_button_selector_case":
            return self._fix_button_selector_case()

        elif action == "take_screenshot_and_inspect":
            # This requires visual inspection - can't auto-fix
            return False, "Requires manual inspection of screenshot"

        elif action == "hide_overlay_elements":
            return self._add_hide_overlay_elements()

        elif action == "handle_cookie_consent":
            return self._add_cookie_consent_handling()

        elif action == "use_force_click":
            return self._add_force_click()

        elif action == "check_page_state":
            return False, "Requires investigation of page state"

        elif action == "try_alternative_selector":
            return False, "Requires manual selector investigation"

        elif action == "skip_missing_element":
            return self._make_element_optional()

        return False, f"No implementation for fix action: {action}"

    def _fix_scroll_implementation(self) -> Tuple[bool, str]:
        """Fix scroll implementation by adding explicit scroll calls."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # Check if scrollToBottom is being called
        if 'scrollToBottom' not in content:
            # Need to add scrollToBottom import and call
            self.log("⚠️  scrollToBottom not found in scraper - needs manual fix")
            return False, "scrollToBottom not found - needs manual addition"

        # Check if there's a scroll call before extraction
        if 'scrollToBottom(page)' in content:
            # Already has scroll, but maybe not working - add verification
            return self._add_scroll_verification()

        return False, "Could not fix scroll implementation"

    def _add_scroll_verification(self) -> Tuple[bool, str]:
        """Add scroll verification and logging."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # Check if already has scroll verification
        if 'Scroll result' in content or 'scroll verification' in content:
            return False, "Already has scroll verification"

        # Find scrollToBottom call and add verification after it
        import re
        pattern = r'(await scrollToBottom\(page[^)]*\);?)'
        match = re.search(pattern, content)

        if not match:
            return False, "Could not find scrollToBottom call"

        # Add verification after scroll
        verification = '''

    // Scroll verification
    const scrollHeight = await page.evaluate(() => document.body.scrollHeight);
    const scrollY = await page.evaluate(() => window.scrollY);
    console.log(`Scroll result: scrollY=${scrollY}, pageHeight=${scrollHeight}`);
    if (scrollY < 100) {
      console.warn("⚠️ Scroll may not have worked - scrollY is very low");
    }
'''
        content = content.replace(match.group(0), match.group(0) + verification, 1)

        path.write_text(content)
        return True, "Added scroll verification logging"

    def _fix_navigation_timeout(self) -> Tuple[bool, str]:
        """Fix navigation timeout by increasing timeout and using domcontentloaded."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re
        modified = False

        # Pattern 1: page.goto with no options - add timeout and waitUntil
        pattern1 = r'await page\.goto\("([^"]+)"\);'
        if re.search(pattern1, content):
            content = re.sub(
                pattern1,
                r'await page.goto("\1", { timeout: 60000, waitUntil: "domcontentloaded" });',
                content
            )
            modified = True

        # Pattern 2: page.goto with options but no timeout
        pattern2 = r'await page\.goto\("([^"]+)",\s*\{([^}]*)\}\);'
        matches = list(re.finditer(pattern2, content))
        for match in matches:
            options = match.group(2)
            if 'timeout' not in options:
                new_options = options.strip()
                if new_options:
                    new_options += ', '
                new_options += 'timeout: 60000'
                if 'waitUntil' not in options:
                    new_options += ', waitUntil: "domcontentloaded"'
                content = content.replace(match.group(0), f'await page.goto("{match.group(1)}", {{ {new_options} }});')
                modified = True

        if modified:
            path.write_text(content)
            return True, "Increased navigation timeout to 60s and using domcontentloaded"

        return False, "Could not find page.goto call to modify"

    def _add_navigation_retry(self) -> Tuple[bool, str]:
        """Add retry logic for navigation timeout."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re

        # Check if already has retry logic
        if 'navigation retry' in content.lower() or 'retryNavigation' in content:
            return False, "Already has navigation retry logic"

        # Find the page.goto call
        pattern = r'(await page\.goto\([^)]+\);)'
        match = re.search(pattern, content)
        if not match:
            return False, "Could not find page.goto call"

        goto_call = match.group(1)

        # Wrap in retry logic
        retry_wrapper = f'''
    // Navigation with retry
    let navigationSuccess = false;
    for (let attempt = 1; attempt <= 3 && !navigationSuccess; attempt++) {{
      try {{
        console.log(`Navigation attempt ${{attempt}}/3...`);
        {goto_call}
        navigationSuccess = true;
      }} catch (navError) {{
        console.log(`Navigation attempt ${{attempt}} failed: ${{navError.message}}`);
        if (attempt === 3) throw navError;
        await page.waitForTimeout(5000); // Wait before retry
      }}
    }}
'''
        content = content.replace(goto_call, retry_wrapper, 1)
        path.write_text(content)
        return True, "Added navigation retry logic (3 attempts)"

    def _fix_button_selector_case(self) -> Tuple[bool, str]:
        """Fix button selector to be case-insensitive."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re
        modified = False

        # Pattern: text="..." selectors that should be case-insensitive
        # Convert text="Some Text" to text=/some text/i
        pattern = r'text="([^"]+)"'
        matches = list(re.finditer(pattern, content))

        for match in matches:
            text = match.group(1)
            # Check if it's likely a button text (contains common pagination words)
            if any(word in text.lower() for word in ['more', 'load', 'show', 'next', 'view']):
                old_selector = match.group(0)
                # Escape special regex characters
                escaped_text = re.escape(text.lower())
                new_selector = f'text=/{escaped_text}/i'
                content = content.replace(old_selector, new_selector, 1)
                modified = True
                self.log(f"🔧 Changed selector: {old_selector} -> {new_selector}")

        if modified:
            path.write_text(content)
            return True, "Made button selectors case-insensitive"

        return False, "No button selectors found to modify"

    def _add_session_recovery(self) -> Tuple[bool, str]:
        """Add session health checks and recovery between clicks."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # Check if already has session health check
        if 'isSessionHealthy' in content:
            return False, "Already has session health checks"

        # Add a simple retry wrapper - this is a lightweight fix
        # For barclays, we already added this, so it may already exist
        if 'Session unhealthy' in content:
            return False, "Already has session recovery pattern"

        # Add longer waits as a simple recovery mechanism
        return self._add_longer_waits()

    def _switch_to_scroll_pagination(self) -> Tuple[bool, str]:
        """Switch from click-based to scroll-based pagination."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # Check if it uses clickButtonUntilGone
        if 'clickButtonUntilGone' not in content:
            return False, "Scraper doesn't use click-based pagination"

        # This is a significant change - for now, just add extract-before-click
        # Full scroll-based rewrite would need more context about the page structure
        self.log("⚠️  Full scroll-based rewrite not implemented, adding extract-before-pagination instead")
        return self._add_extract_before_pagination()

    def _add_extract_before_pagination(self) -> Tuple[bool, str]:
        """Add extraction before pagination to get partial results."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # Check if already has this pattern
        if 'extractBeforePagination' in content or 'Extract visible events first' in content:
            return False, "Already has extract-before-pagination"

        # Find the clickButtonUntilGone call and add extraction before it
        import re
        pattern = r'(await clickButtonUntilGone\(page,)'
        if not re.search(pattern, content):
            return False, "Could not find pagination call to modify"

        # Add a pre-extraction step (using raw string for JS template literals)
        pre_extract = r'''
    // Extract visible events BEFORE pagination (in case pagination fails)
    console.log("Extracting visible events before pagination...");
    let initialEvents = [];
    try {
      const initialResult = await extractEventsFromPage(
        page,
        "Extract all currently visible events as a safety backup",
        StandardEventSchema,
        { sourceName: '${SOURCE_NAME}_initial' }
      );
      initialEvents = initialResult.events || [];
      console.log(`Got ${initialEvents.length} events before pagination`);
    } catch (e) {
      console.log("Initial extraction failed, continuing with pagination:", e.message);
    }

    '''
        content = re.sub(pattern, pre_extract + r'\1', content, count=1)
        content = content.replace('${SOURCE_NAME}', self.source)

        path.write_text(content)
        return True, "Added extract-before-pagination pattern"

    def _switch_to_direct_dom_click(self) -> Tuple[bool, str]:
        """Switch from Stagehand observe/act to direct DOM clicking."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # Check if it uses observe/act pattern (via clickButtonUntilGone)
        if 'clickButtonUntilGone' not in content:
            return False, "Scraper doesn't use Stagehand click pattern"

        # This is complex - would need to know the actual button selector
        # For now, log that manual intervention is needed
        self.log("⚠️  Direct DOM click requires knowing the button selector")
        self.log("   Recommendation: Inspect the page and find the button's CSS selector")

        return False, "Direct DOM click requires manual selector identification"

    def _add_longer_waits(self) -> Tuple[bool, str]:
        """Add longer wait times to scraper."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # Look for waitForTimeout calls and increase them
        import re
        modified = False

        # Increase existing timeouts
        def increase_timeout(match):
            nonlocal modified
            old_val = int(match.group(1))
            new_val = min(old_val + 2000, 10000)  # Add 2s, max 10s
            if new_val > old_val:
                modified = True
                return f"waitForTimeout({new_val})"
            return match.group(0)

        content = re.sub(r"waitForTimeout\((\d+)\)", increase_timeout, content)

        # Add networkidle wait if not present
        if "networkidle" not in content and "waitForLoadState" in content:
            content = content.replace(
                "waitForLoadState('domcontentloaded')",
                "waitForLoadState('networkidle')"
            )
            modified = True

        if modified:
            path.write_text(content)
            return True, "Increased wait times in scraper"

        return False, "Could not modify wait times"

    def _increase_pagination(self) -> Tuple[bool, str]:
        """Increase pagination attempts."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re

        # Look for max clicks/pages patterns
        patterns = [
            (r"(\d+)\s*//\s*max\s*clicks", "max clicks"),
            (r"maxClicks\s*[:=]\s*(\d+)", "maxClicks"),
            (r"maxPages\s*[:=]\s*(\d+)", "maxPages"),
            (r"clickButtonUntilGone\([^,]+,\s*['\"][^'\"]+['\"],\s*(\d+)", "clickButtonUntilGone"),
        ]

        modified = False
        for pattern, name in patterns:
            match = re.search(pattern, content)
            if match:
                old_num = int(match.group(1))
                new_num = old_num + 5
                old_text = match.group(0)
                new_text = old_text.replace(str(old_num), str(new_num))
                content = content.replace(old_text, new_text, 1)
                modified = True
                self.log(f"🔧 Increased {name}: {old_num} -> {new_num}")

        if modified:
            path.write_text(content)
            return True, f"Increased pagination limits"

        return False, "No pagination settings found to modify"

    def _add_cookie_consent_handling(self) -> Tuple[bool, str]:
        """Add code to handle cookie consent overlays (OneTrust, etc.)."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re

        # Check if already has cookie consent handling
        if 'onetrust' in content.lower() or 'cookie-consent' in content.lower():
            return False, "Already has cookie consent handling"

        # Find the navigation/goto call and add cookie consent handling after it
        pattern = r'(await page\.goto\([^)]+\)[^;]*;[^}]*?await page\.waitForTimeout\(\d+\);)'
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            # Try simpler pattern
            pattern = r'(await page\.goto\([^)]+\);)'
            match = re.search(pattern, content)

        if not match:
            return False, "Could not find page.goto call"

        # Add cookie consent handling code after navigation
        cookie_consent_code = '''

    // Handle cookie consent overlays (OneTrust, etc.)
    try {
      await page.evaluate(() => {
        // Hide OneTrust consent overlay
        const onetrust = document.getElementById('onetrust-consent-sdk');
        if (onetrust) onetrust.style.display = 'none';

        // Try clicking accept button if it exists
        const acceptSelectors = [
          '#onetrust-accept-btn-handler',
          '.onetrust-close-btn-handler',
          '[aria-label*="Accept"]',
          '[aria-label*="accept"]',
          'button[id*="accept"]',
          '.cookie-consent-accept'
        ];
        for (const sel of acceptSelectors) {
          const btn = document.querySelector(sel);
          if (btn) {
            btn.click();
            break;
          }
        }
      });
      console.log("Handled cookie consent overlay");
    } catch (e) {
      console.log("Cookie consent handling skipped:", e.message);
    }
'''
        content = content.replace(match.group(0), match.group(0) + cookie_consent_code, 1)
        path.write_text(content)
        return True, "Added cookie consent handling (OneTrust, etc.)"

    def _add_hide_overlay_elements(self) -> Tuple[bool, str]:
        """Add code to hide chat widgets and overlay elements before clicking."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re

        # Check if already has overlay hiding
        if 'hideOverlays' in content or 'beacon-container' in content:
            return False, "Already has overlay hiding code"

        # Find the navigation/goto call and add overlay hiding after it
        pattern = r'(await page\.goto\([^)]+\)[^;]*;[^}]*?await page\.waitForTimeout\(\d+\);)'
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            # Try simpler pattern
            pattern = r'(await page\.goto\([^)]+\);)'
            match = re.search(pattern, content)

        if not match:
            return False, "Could not find page.goto call"

        # Add overlay hiding code after navigation
        hide_overlay_code = '''

    // Hide overlay elements (chat widgets, popups) that can block clicks
    await page.evaluate(() => {
      // Hide Help Scout Beacon
      const beacon = document.getElementById('beacon-container');
      if (beacon) beacon.style.display = 'none';

      // Hide other common chat widgets
      const selectors = [
        '[class*="beacon"]',
        '[class*="intercom"]',
        '[class*="drift"]',
        '[class*="zendesk"]',
        '[class*="chat-widget"]',
        '[id*="chat"]',
        'iframe[title*="chat"]',
        'iframe[title*="beacon"]',
        'iframe[title*="Help"]'
      ];
      selectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
          el.style.display = 'none';
        });
      });
    });
    console.log("Hidden overlay elements (chat widgets, etc.)");
'''
        content = content.replace(match.group(0), match.group(0) + hide_overlay_code, 1)
        path.write_text(content)
        return True, "Added code to hide overlay elements (chat widgets)"

    def _add_force_click(self) -> Tuple[bool, str]:
        """Add JavaScript force click to bypass overlays."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()

        # This is a more targeted fix - add { force: true } to specific clicks
        # For now, just hide overlays which is more reliable
        self.log("⚠️  Force click not implemented - using hide_overlay_elements instead")
        return self._add_hide_overlay_elements()

    def _make_element_optional(self) -> Tuple[bool, str]:
        """Make the missing element optional by wrapping in try-catch."""
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re

        # Find clickButtonUntilGone calls and make them optional
        pattern = r'(await clickButtonUntilGone\([^)]+\);)'
        match = re.search(pattern, content)

        if not match:
            return False, "Could not find element to make optional"

        original_call = match.group(1)

        # Wrap in try-catch
        optional_wrapper = f'''try {{
      {original_call}
    }} catch (clickError) {{
      console.log("Optional button click failed (may not exist on page):", clickError.message);
    }}'''

        content = content.replace(original_call, optional_wrapper, 1)
        path.write_text(content)
        return True, "Made pagination button click optional (wrapped in try-catch)"

    def _remove_load_more_clicking(self) -> Tuple[bool, str]:
        """
        Remove Load More clicking that causes session crashes.
        Learned from: beacon_theatre, carnegie_hall where clicking Load More
        caused 'Target page, context or browser has been closed' errors.

        Fix: Remove clickButtonUntilGone call entirely, just extract visible events.
        """
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re

        # Remove clickButtonUntilGone calls
        pattern = r'\n\s*await clickButtonUntilGone\([^)]+\);?\n'
        if not re.search(pattern, content):
            return False, "No clickButtonUntilGone call found"

        content = re.sub(pattern, '\n', content)

        # Add comment explaining why it was removed
        scroll_pattern = r'(await scrollToBottom\(page\);?)'
        if re.search(scroll_pattern, content):
            content = re.sub(
                scroll_pattern,
                r'\1\n    await page.waitForTimeout(2000);\n\n    // Load More clicking removed - causes session crashes',
                content,
                count=1
            )

        path.write_text(content)
        self.log("✅ Removed Load More clicking (was causing session crashes)")
        return True, "Removed Load More clicking - extract visible events only"

    def _fix_404_navigation(self) -> Tuple[bool, str]:
        """
        Fix scraper when initial URL returns 404.
        Learned from: apollo_theater (/events/ -> homepage), greenwich_house (via footer link).

        Fix: Use exploratory healer to find working navigation pattern.
        """
        self.log("🔍 Page returned 404 - will use exploratory healer to find correct navigation")

        # This requires the exploratory healer to find the right pattern
        # For now, flag it for exploration
        return False, "Page returned 404 - run exploratory_healer.py to discover correct navigation pattern"

    def _fix_url_extraction_prompt(self) -> Tuple[bool, str]:
        """
        Fix URL extraction when scraper extracts descriptions instead of real URLs.
        Learned from: bowery_ballroom where URLs were 'Event Image Link-...' instead of http URLs.

        Fix: Update extraction prompt to be explicit about URL format.
        """
        path = Path(self.scraper_path)
        if not path.exists():
            return False, "Scraper file not found"

        content = path.read_text()
        import re

        # Find extraction prompt and improve it
        pattern = r'(extractEventsFromPage\(\s*page,\s*["\'])([^"\']+)(["\'])'
        match = re.search(pattern, content)

        if not match:
            return False, "Could not find extraction prompt"

        original_prompt = match.group(2)

        # Add URL extraction guidance if not already present
        if "eventUrl should be" not in original_prompt and "real URL" not in original_prompt.lower():
            improved_prompt = original_prompt + " IMPORTANT: eventUrl must be an actual URL starting with http/https, not image descriptions or text."
            content = content.replace(match.group(0), match.group(1) + improved_prompt + match.group(3), 1)
            path.write_text(content)
            self.log("✅ Improved extraction prompt to require proper URLs")
            return True, "Added URL format requirement to extraction prompt"

        return False, "Prompt already has URL guidance"

    def _try_write_fix(self, diagnostic_report: DiagnosticReport, issues: List[str]) -> bool:
        """
        When we have a diagnosed error but no pre-built fix, use Claude to write one.

        This analyzes:
        - The error/diagnosis
        - The current scraper code
        - Similar working scrapers

        And writes a targeted fix.
        """
        try:
            import openai
            import os
            from dotenv import load_dotenv
            load_dotenv()

            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                self.log("   Cannot write fix - OPENAI_API_KEY not set")
                return False

            client = openai.OpenAI(api_key=api_key)

            # Read current scraper code
            scraper_path = Path(self.scraper_path)
            if not scraper_path.exists():
                return False

            current_code = scraper_path.read_text()

            # Find a working scraper for reference
            reference_code = ""
            for ref_scraper in Path("src/scrapers").glob("*.js"):
                if ref_scraper.stem != self.source:
                    reference_code = ref_scraper.read_text()
                    break

            prompt = f"""You are a web scraping expert. A scraper is failing and needs a fix.

## Diagnosis
- **Failure Category**: {diagnostic_report.failure_category}
- **Pattern**: {diagnostic_report.failure_pattern}
- **Observations**: {diagnostic_report.observations}
- **Issues Detected**: {issues}

## Current Scraper Code
```javascript
{current_code[:3000]}  // truncated
```

## Reference Working Scraper
```javascript
{reference_code[:2000]}  // truncated
```

## Task
Write the MINIMAL code changes needed to fix this issue.

Return your response as JSON:
{{
  "can_fix": true/false,
  "explanation": "what the fix does",
  "search_replace": [
    {{
      "search": "exact code to find",
      "replace": "code to replace it with"
    }}
  ]
}}

If you can't determine a fix, set can_fix to false and explain why.
Be precise with the search strings - they must match exactly.
"""

            response = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.choices[0].message.content

            # Parse JSON response
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                self.log("   Could not parse fix response")
                return False

            fix_data = json.loads(json_match.group())

            if not fix_data.get("can_fix"):
                self.log(f"   Cannot auto-fix: {fix_data.get('explanation', 'unknown reason')}")
                return False

            # Apply the fix
            modified_code = current_code
            for change in fix_data.get("search_replace", []):
                search = change.get("search", "")
                replace = change.get("replace", "")
                if search and search in modified_code:
                    modified_code = modified_code.replace(search, replace, 1)
                    self.log(f"   Applied change: {fix_data.get('explanation', 'fix')}")

            if modified_code != current_code:
                # Backup and save
                backup_path = scraper_path.with_suffix('.js.backup_written_fix')
                if not backup_path.exists():
                    import shutil
                    shutil.copy(scraper_path, backup_path)

                scraper_path.write_text(modified_code)
                self.log(f"   Fix written to scraper")
                return True

            return False

        except ImportError:
            self.log("   Cannot write fix - anthropic module not installed")
            return False
        except Exception as e:
            self.log(f"   Error writing fix: {e}")
            return False

    def _try_exploratory_healing(self) -> bool:
        """
        Try exploratory healing when standard fixes fail.
        Uses Claude vision to analyze the page and discover interaction patterns.
        """
        try:
            from src.exploratory_healer import ExploratoryHealer
            import re

            # Get URL from scraper
            scraper_path = Path(self.scraper_path)
            if not scraper_path.exists():
                self.log("   Cannot explore - scraper file not found")
                return False

            content = scraper_path.read_text()
            url_match = re.search(r'page\.goto\(["\']([^"\']+)["\']', content)
            if not url_match:
                self.log("   Cannot explore - URL not found in scraper")
                return False

            url = url_match.group(1)
            self.log(f"   Exploring: {url}")

            # Run exploratory healing
            healer = ExploratoryHealer(self.source, url, verbose=False)
            results = healer.explore_and_discover(max_iterations=3)

            if results.get("best_pattern") and results["events_found"] > 0:
                self.log(f"   Found pattern with {results['events_found']} events!")
                self.log(f"   Actions: {results['best_pattern']['actions']}")

                # If we have generated scraper code, update the scraper
                if results.get("generated_scraper"):
                    # Backup and update
                    backup_path = scraper_path.with_suffix('.js.backup')
                    scraper_path.rename(backup_path)
                    scraper_path.write_text(results["generated_scraper"])
                    self.log(f"   Updated scraper with discovered pattern")
                    return True

            return False

        except ImportError:
            self.log("   Exploratory healer not available")
            return False
        except Exception as e:
            self.log(f"   Exploration failed: {e}")
            return False

    def run_iteration(self, iteration: int, previous_error: str = "") -> ScraperIteration:
        """Run a single iteration of scrape -> diagnose -> analyze -> fix."""
        self.log(f"\n{'='*60}")
        self.log(f"ITERATION {iteration}/{self.MAX_ITERATIONS}")
        self.log(f"{'='*60}")

        start_time = time.time()

        # Step 1: Run scraper and capture screenshot
        self.log("📦 Step 1: Running scraper...")
        success, events_count, screenshot_path, stdout, stderr, session_id = self.run_scraper_with_screenshot()

        # Step 2: Get LIVE FEEDBACK from Browserbase session
        # This tells us exactly what happened in the browser
        self.log("📡 Step 2: Getting Browserbase session feedback...")
        bb_analysis = None
        if session_id:
            bb_analysis = analyze_session_for_healing(session_id)
            self._print_browserbase_feedback(bb_analysis)

        # Step 3: Run comprehensive diagnosis
        # Combines code analysis, history, and Browserbase feedback
        self.log("🔍 Step 3: Running diagnosis...")
        error_output = stderr if stderr else previous_error
        diagnostic_report = diagnose_scraper(
            self.source,
            error_output=error_output,
            verbose=False  # We'll print our own summary
        )

        # Enrich diagnostic report with Browserbase insights
        if bb_analysis:
            self._enrich_diagnosis_with_browserbase(diagnostic_report, bb_analysis)

        # Print key diagnostic findings
        self._print_diagnostic_summary(diagnostic_report)

        # Step 4: Visual analysis (if screenshot available)
        self.log("👁️ Step 4: Visual analysis...")
        visual_analysis = None
        if screenshot_path:
            visual_analysis = self.analyze_visually(screenshot_path, events_count)

        # Step 5: Combine all issue sources (including Browserbase feedback)
        issues = self._combine_issues(stdout, stderr, events_count, visual_analysis, diagnostic_report, bb_analysis)

        # Determine success: scraper ran AND got events
        # Issues like NO_SCROLL are warnings, not failures if we got data
        informational_issues = {"NO_SCROLL", "INSUFFICIENT_SCROLL", "STALE_DATA"}
        blocking_issues = [i for i in issues if i not in informational_issues]

        # Success = scraper ran + got events + no blocking issues
        is_success = success and events_count > 0 and len(blocking_issues) == 0

        result = ScraperIteration(
            iteration=iteration,
            success=is_success,
            events_scraped=events_count,
            screenshot_path=screenshot_path,
            duration_seconds=time.time() - start_time,
            issues=issues,
            visual_analysis=visual_analysis,
            diagnostic_report=diagnostic_report
        )

        if blocking_issues:
            self.log(f"⚠️  Issues detected: {blocking_issues}")
        elif issues:
            self.log(f"ℹ️  Warnings (non-blocking): {issues}")

        return result

    def _print_browserbase_feedback(self, bb_analysis: Dict):
        """Print Browserbase session feedback."""
        if not bb_analysis or not bb_analysis.get("success"):
            self.log("   ⚠️  Could not retrieve Browserbase session data")
            return

        self.log(f"   Duration: {bb_analysis.get('duration', 0):.1f}s")
        self.log(f"   Scroll events: {bb_analysis.get('scroll_count', 0)}")
        self.log(f"   Click events: {bb_analysis.get('click_count', 0)}")
        self.log(f"   Errors: {bb_analysis.get('error_count', 0)}")

        if bb_analysis.get("issues"):
            for issue in bb_analysis["issues"]:
                severity_icon = "🔴" if issue["severity"] == "critical" else "🟡" if issue["severity"] == "high" else "🟠"
                self.log(f"   {severity_icon} {issue['message']}")

    def _enrich_diagnosis_with_browserbase(self, report: DiagnosticReport, bb_analysis: Dict):
        """Add Browserbase insights to diagnostic report."""
        if not bb_analysis.get("success"):
            return

        # Add Browserbase issues to observations
        for issue in bb_analysis.get("issues", []):
            report.observations.append(f"[BB] {issue['message']}")

        # Check for scroll issues
        if bb_analysis.get("scroll_count", 0) == 0:
            report.observations.append("[BB] NO SCROLL EVENTS - page may not have loaded content")

            # Add scroll-related recommendation
            scroll_fix = {
                "priority": 0,  # Highest priority
                "action": "fix_scroll",
                "description": "Verify and fix scroll implementation - no scroll events detected",
                "confidence": 0.9,
                "rationale": "Browserbase logs show no scroll events. Content may not have loaded."
            }
            report.recommended_fixes.insert(0, scroll_fix)
            report.confidence = max(report.confidence, 0.8)

        # Check for early session termination
        if bb_analysis.get("duration", 0) < 10 and bb_analysis.get("error_count", 0) > 0:
            report.observations.append(f"[BB] Session crashed after {bb_analysis['duration']:.1f}s")

        # Add Browserbase recommendations
        for rec in bb_analysis.get("recommendations", []):
            bb_rec = {
                "priority": rec.get("priority", 2),
                "action": rec.get("action", "unknown"),
                "description": f"[BB] {rec.get('description', '')}",
                "confidence": 0.7,
                "rationale": "Based on Browserbase session analysis"
            }
            # Add if not already present
            existing_actions = [r["action"] for r in report.recommended_fixes]
            if bb_rec["action"] not in existing_actions:
                report.recommended_fixes.append(bb_rec)

        # Re-sort recommendations by priority
        report.recommended_fixes.sort(key=lambda x: x.get("priority", 99))

    def _print_diagnostic_summary(self, report: DiagnosticReport):
        """Print a summary of diagnostic findings."""
        self.log(f"   Failure category: {report.failure_category}")
        self.log(f"   Pattern: {report.failure_pattern}")
        if report.key_difference:
            self.log(f"   💡 Key insight: {report.key_difference}")
        if report.recommended_fixes:
            top_fix = report.recommended_fixes[0]
            self.log(f"   Top recommendation: {top_fix['action']} ({top_fix.get('confidence', 0):.0%} confidence)")

    def _combine_issues(self, stdout: str, stderr: str, events_count: int,
                        visual_analysis: Optional[VisualAnalysis],
                        diagnostic_report: DiagnosticReport,
                        bb_analysis: Optional[Dict] = None) -> List[str]:
        """Combine issues from all sources into a unified list."""
        issues = []

        # Get issues from legacy diagnosis method
        legacy_issues = self.diagnose_issues(stdout, stderr, events_count, visual_analysis)
        issues.extend(legacy_issues)

        # Add issues from diagnostic report
        if diagnostic_report.failure_category != "unknown":
            category_issue = f"DIAG_{diagnostic_report.failure_category.upper()}"
            if category_issue not in issues:
                issues.append(category_issue)

        # Add specific observations as issues
        for obs in diagnostic_report.observations:
            if "crash" in obs.lower():
                if "SESSION_CRASH" not in issues:
                    issues.append("SESSION_CRASH")
            if "stale" in obs.lower() or "past" in obs.lower():
                if "STALE_DATA" not in issues:
                    issues.append("STALE_DATA")
            # Browserbase-specific issues
            if "[BB] NO SCROLL" in obs:
                if "NO_SCROLL" not in issues:
                    issues.append("NO_SCROLL")

        # Add issues from Browserbase analysis
        if bb_analysis and bb_analysis.get("success"):
            for issue in bb_analysis.get("issues", []):
                issue_type = issue.get("type", "UNKNOWN")
                if issue_type not in issues:
                    issues.append(issue_type)

        return issues

    def heal(self) -> Dict[str, Any]:
        """
        Main healing loop with integrated diagnostics.

        Flow:
        1. RUN scraper
        2. DIAGNOSE (gather evidence, compare patterns, analyze code)
        3. ANALYZE visually (compare screenshot to data)
        4. FIX based on diagnosis
        5. REPEAT until success or max iterations
        """
        self.log(f"\n🏥 Starting Visual Self-Healing for: {self.source}")
        self.log(f"   Max iterations: {self.MAX_ITERATIONS}")

        results = {
            "source": self.source,
            "started_at": datetime.now().isoformat(),
            "iterations": [],
            "final_status": "unknown",
            "total_fixes_applied": 0,
            "final_events_count": 0,
            "diagnostic_summary": None
        }

        previous_error = ""

        for i in range(1, self.MAX_ITERATIONS + 1):
            iteration = self.run_iteration(i, previous_error)
            self.iterations.append(iteration)

            # Build iteration result with diagnostic info
            iteration_result = {
                "iteration": iteration.iteration,
                "success": iteration.success,
                "events_scraped": iteration.events_scraped,
                "screenshot_path": iteration.screenshot_path,
                "duration_seconds": iteration.duration_seconds,
                "issues": iteration.issues,
                "fixes_applied": iteration.fixes_applied,
            }

            # Add diagnostic summary if available
            if iteration.diagnostic_report:
                iteration_result["diagnosis"] = {
                    "failure_category": iteration.diagnostic_report.failure_category,
                    "key_difference": iteration.diagnostic_report.key_difference,
                    "confidence": iteration.diagnostic_report.confidence,
                    "top_recommendation": iteration.diagnostic_report.recommended_fixes[0]['action'] if iteration.diagnostic_report.recommended_fixes else None
                }
                results["diagnostic_summary"] = iteration_result["diagnosis"]

            results["iterations"].append(iteration_result)

            if iteration.success:
                self.log(f"\n✅ SUCCESS on iteration {i}!")
                self.log(f"   Events scraped: {iteration.events_scraped}")
                results["final_status"] = "success"
                results["final_events_count"] = iteration.events_scraped
                break

            # Apply fixes for detected issues, using diagnostic recommendations
            if iteration.issues:
                fix_applied = False
                for issue in iteration.issues:
                    fixed, description = self.apply_fix(issue, iteration.diagnostic_report)
                    if fixed:
                        iteration.fixes_applied.append(description)
                        results["total_fixes_applied"] += 1
                        self.log(f"🔧 Fix applied: {description}")
                        fix_applied = True
                        break  # Apply one fix at a time

                if not fix_applied and not iteration.fixes_applied:
                    # Step 1: If we have a diagnosis but no pre-built fix, try to WRITE a fix
                    if iteration.diagnostic_report and iteration.diagnostic_report.failure_category != "unknown":
                        self.log(f"🔧 No pre-built fix for '{iteration.diagnostic_report.failure_category}' - attempting to write one...")
                        write_success = self._try_write_fix(iteration.diagnostic_report, iteration.issues)
                        if write_success:
                            self.log("✨ Wrote a custom fix - will retry")
                            continue  # Retry with new fix

                    # Step 2: Try exploratory healing (discover interaction patterns)
                    self.log("🔍 Trying exploratory discovery...")
                    exploration_success = self._try_exploratory_healing()
                    if exploration_success:
                        self.log("✨ Exploration found a pattern - will retry")
                        continue  # Retry with new pattern

                    self.log("❌ No fixes could be applied - stopping")
                    results["final_status"] = "failed_no_fix"
                    break

            # Capture error for next iteration's diagnosis
            if iteration.issues:
                previous_error = "; ".join(iteration.issues)

            # Brief delay before retry
            if i < self.MAX_ITERATIONS:
                self.log("⏳ Waiting 5 seconds before retry...")
                time.sleep(5)

        else:
            # Exhausted all iterations
            results["final_status"] = "failed_max_iterations"
            self.log(f"\n❌ Failed after {self.MAX_ITERATIONS} iterations")

        results["completed_at"] = datetime.now().isoformat()

        # Save results
        output_path = Path("data/output") / f"visual_healing_{self.source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        self.log(f"\n📄 Results saved to: {output_path}")

        # Print summary
        self.log(f"\n{'='*60}")
        self.log("HEALING SUMMARY")
        self.log(f"{'='*60}")
        self.log(f"Status: {results['final_status']}")
        self.log(f"Iterations: {len(self.iterations)}")
        self.log(f"Fixes applied: {results['total_fixes_applied']}")
        self.log(f"Final events: {results['final_events_count']}")

        return results


def main():
    parser = argparse.ArgumentParser(description='Visual self-healing scraper')
    parser.add_argument('source', help='Source/venue to heal')
    parser.add_argument('--max-iterations', type=int, default=5, help='Max healing iterations')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode')

    args = parser.parse_args()

    healer = VisualSelfHealer(args.source, verbose=not args.quiet)
    healer.MAX_ITERATIONS = args.max_iterations
    results = healer.heal()

    # Exit with appropriate code
    if results["final_status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
