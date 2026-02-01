#!/usr/bin/env python3
"""
Unified Scraper Creation & Self-Healing Workflow

This is the main entry point for creating new scrapers. It combines:
1. Template-based scraper generation
2. Automated testing and validation
3. Self-healing with visual verification
4. Browserbase session analysis
5. Iterative fixing until success

Usage:
    # Create a new scraper from scratch
    python src/create_scraper.py "Brooklyn Bowl" "https://www.brooklynbowl.com/events"

    # Create with specific template
    python src/create_scraper.py "Brooklyn Bowl" "https://www.brooklynbowl.com/events" --template scroll

    # Run self-healing on existing scraper
    python src/create_scraper.py --heal brooklyn_bowl

    # Diagnose an existing scraper
    python src/create_scraper.py --diagnose brooklyn_bowl
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.diagnose_scraper import diagnose_scraper, DiagnosticReport
from src.visual_self_healer import VisualSelfHealer
from src.browserbase_feedback import extract_session_id_from_output, analyze_session_for_healing


# =============================================================================
# SCRAPER TEMPLATES
# =============================================================================

SCROLL_TEMPLATE = '''import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom, capturePageScreenshot } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with venue default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: '${VENUE_NAME}' });

export async function scrape${FUNCTION_NAME}() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the events page with extended timeout
    console.log("Navigating to events page...");
    await page.goto("${URL}", { timeout: 60000, waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3000);

    // Step 2: Scroll to load all events (for infinite scroll / lazy loading)
    console.log("Scrolling to load all events...");
    let previousHeight = 0;
    let currentHeight = await page.evaluate(() => document.body.scrollHeight);
    let scrollAttempts = 0;
    const maxScrollAttempts = 10;

    while (previousHeight !== currentHeight && scrollAttempts < maxScrollAttempts) {
      console.log(`Scroll attempt ${scrollAttempts + 1}/${maxScrollAttempts}`);
      previousHeight = currentHeight;
      await scrollToBottom(page, 3000);
      currentHeight = await page.evaluate(() => document.body.scrollHeight);
      scrollAttempts++;
    }
    console.log(`Completed ${scrollAttempts} scroll attempts`);

    // Step 3: Take screenshot for verification
    try {
      await capturePageScreenshot(page, '${SOURCE_NAME}');
    } catch (e) {
      console.log('Screenshot capture failed:', e.message);
    }

    // Step 4: Extract events
    const currentYear = new Date().getFullYear();
    const result = await extractEventsFromPage(
      page,
      `Extract all visible events. For each event, get:
       - eventName: the event title
       - eventDate: the date (add year ${currentYear} if not shown)
       - eventTime: the time if visible, otherwise empty string
       - eventUrl: the link to the event page (full URL)
       - eventLocation: set to '${VENUE_NAME}'
       - eventDescription: brief description if visible, otherwise empty string`,
      StandardEventSchema,
      { sourceName: '${SOURCE_NAME}' }
    );

    // Normalize URLs
    const events = result.events.map(event => {
      let eventUrl = event.eventUrl || '';
      if (eventUrl && !eventUrl.startsWith('http')) {
        eventUrl = new URL(eventUrl, '${URL}').href;
      }
      if (!eventUrl) {
        eventUrl = '${URL}';
      }
      return {
        ...event,
        eventUrl,
        eventLocation: '${VENUE_NAME}'
      };
    });

    console.log(`Extracted ${events.length} events`);

    // Log and save results
    logScrapingResults(events, '${VENUE_NAME}');

    if (events.length > 0) {
      await saveEventsToDatabase(events, '${SOURCE_NAME}');
    } else {
      console.log("No events found!");
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, '${VENUE_NAME}');
  } finally {
    await stagehand.close();
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrape${FUNCTION_NAME}().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrape${FUNCTION_NAME};
'''

CLICK_PAGINATION_TEMPLATE = '''import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom, capturePageScreenshot } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with venue default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: '${VENUE_NAME}' });

// Check if browser session is still healthy
async function isSessionHealthy(page) {
  try {
    await page.evaluate(() => document.title);
    return true;
  } catch (e) {
    console.log('Session health check failed:', e.message);
    return false;
  }
}

// Click pagination button with resilience
async function clickLoadMoreWithResilience(page, buttonText, maxClicks = 20) {
  let clickCount = 0;

  for (let i = 0; i < maxClicks; i++) {
    try {
      if (!await isSessionHealthy(page)) {
        console.log(`Session unhealthy after ${clickCount} clicks`);
        break;
      }

      // Case-insensitive button search
      const button = await page.$(`text=/${buttonText}/i`);
      if (!button) {
        console.log(`No more "${buttonText}" button found after ${clickCount} clicks`);
        break;
      }

      await Promise.race([
        button.click(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Click timeout')), 10000))
      ]);

      clickCount++;
      console.log(`Clicked "${buttonText}" (${clickCount}/${maxClicks})`);
      await page.waitForTimeout(2500);
      await page.evaluate(() => window.scrollBy(0, 500));
      await page.waitForTimeout(1000);

    } catch (error) {
      if (error.message.includes('closed') || error.message.includes('Target')) {
        console.log(`Browser session closed after ${clickCount} clicks`);
        break;
      }
      console.log(`Click attempt ${i + 1} failed: ${error.message}`);
      await page.waitForTimeout(2000);
    }
  }

  return clickCount;
}

export async function scrape${FUNCTION_NAME}() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate with retry
    let navigationSuccess = false;
    for (let attempt = 1; attempt <= 3 && !navigationSuccess; attempt++) {
      try {
        console.log(`Navigation attempt ${attempt}/3...`);
        await page.goto("${URL}", { timeout: 60000, waitUntil: "domcontentloaded" });
        navigationSuccess = true;
      } catch (navError) {
        console.log(`Navigation attempt ${attempt} failed: ${navError.message}`);
        if (attempt === 3) throw navError;
        await page.waitForTimeout(5000);
      }
    }
    await page.waitForTimeout(3000);

    // Step 2: Initial scroll
    await scrollToBottom(page);

    // Step 3: Click "Load More" / "View More" button until done
    // TODO: Update button text to match actual button on page
    await clickLoadMoreWithResilience(page, 'load more|view more|show more', 20);

    // Step 4: Take screenshot
    try {
      await capturePageScreenshot(page, '${SOURCE_NAME}');
    } catch (e) {
      console.log('Screenshot capture failed:', e.message);
    }

    // Step 5: Extract events
    const currentYear = new Date().getFullYear();
    const result = await extractEventsFromPage(
      page,
      `Extract all visible events. For each event, get:
       - eventName: the event title
       - eventDate: the date (add year ${currentYear} if not shown)
       - eventTime: the time if visible, otherwise empty string
       - eventUrl: the link to the event page (full URL)
       - eventLocation: set to '${VENUE_NAME}'
       - eventDescription: brief description if visible, otherwise empty string`,
      StandardEventSchema,
      { sourceName: '${SOURCE_NAME}' }
    );

    // Normalize URLs
    const events = result.events.map(event => {
      let eventUrl = event.eventUrl || '';
      if (eventUrl && !eventUrl.startsWith('http')) {
        eventUrl = new URL(eventUrl, '${URL}').href;
      }
      if (!eventUrl) {
        eventUrl = '${URL}';
      }
      return {
        ...event,
        eventUrl,
        eventLocation: '${VENUE_NAME}'
      };
    });

    console.log(`Extracted ${events.length} events`);

    // Log and save
    logScrapingResults(events, '${VENUE_NAME}');

    if (events.length > 0) {
      await saveEventsToDatabase(events, '${SOURCE_NAME}');
    } else {
      console.log("No events found!");
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, '${VENUE_NAME}');
  } finally {
    await stagehand.close();
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrape${FUNCTION_NAME}().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrape${FUNCTION_NAME};
'''

TEMPLATES = {
    'scroll': SCROLL_TEMPLATE,
    'click': CLICK_PAGINATION_TEMPLATE,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def venue_name_to_source_name(venue_name: str) -> str:
    """Convert venue name to source name (snake_case)."""
    # Remove special characters and convert to snake_case
    source = re.sub(r'[^a-zA-Z0-9\s]', '', venue_name)
    source = re.sub(r'\s+', '_', source.strip())
    return source.lower()


def venue_name_to_function_name(venue_name: str) -> str:
    """Convert venue name to function name (PascalCase)."""
    # Remove special characters and convert to PascalCase
    words = re.sub(r'[^a-zA-Z0-9\s]', '', venue_name).split()
    return ''.join(word.capitalize() for word in words)


def generate_scraper_code(venue_name: str, url: str, template: str = 'scroll') -> str:
    """Generate scraper code from template."""
    template_code = TEMPLATES.get(template, TEMPLATES['scroll'])

    source_name = venue_name_to_source_name(venue_name)
    function_name = venue_name_to_function_name(venue_name)

    code = template_code.replace('${VENUE_NAME}', venue_name)
    code = code.replace('${SOURCE_NAME}', source_name)
    code = code.replace('${FUNCTION_NAME}', function_name)
    code = code.replace('${URL}', url)

    return code


# =============================================================================
# MAIN WORKFLOW
# =============================================================================

@dataclass
class ScraperCreationResult:
    """Result of scraper creation workflow."""
    source_name: str
    venue_name: str
    scraper_path: str
    success: bool
    events_scraped: int = 0
    iterations: int = 0
    issues_found: List[str] = field(default_factory=list)
    fixes_applied: List[str] = field(default_factory=list)
    final_diagnosis: Optional[DiagnosticReport] = None
    error_message: str = ""


def create_scraper(
    venue_name: str,
    url: str,
    template: str = 'scroll',
    staging: bool = True,
    max_healing_iterations: int = 5,
    verbose: bool = True
) -> ScraperCreationResult:
    """
    Create a new scraper with automatic testing and self-healing.

    Args:
        venue_name: Human-readable venue name (e.g., "Brooklyn Bowl")
        url: Events page URL
        template: Template to use ('scroll' or 'click')
        staging: Whether to create in staging directory
        max_healing_iterations: Max self-healing attempts
        verbose: Print progress

    Returns:
        ScraperCreationResult with status and details
    """
    source_name = venue_name_to_source_name(venue_name)

    # Determine output path
    if staging:
        scraper_dir = Path("src/scrapers-staging")
    else:
        scraper_dir = Path("src/scrapers")

    scraper_dir.mkdir(exist_ok=True)
    scraper_path = scraper_dir / f"{source_name}.js"

    result = ScraperCreationResult(
        source_name=source_name,
        venue_name=venue_name,
        scraper_path=str(scraper_path),
        success=False
    )

    if verbose:
        print(f"\n{'='*60}")
        print(f"CREATING SCRAPER: {venue_name}")
        print(f"{'='*60}")
        print(f"  Source name: {source_name}")
        print(f"  URL: {url}")
        print(f"  Template: {template}")
        print(f"  Path: {scraper_path}")

    # Step 1: Generate scraper code
    if verbose:
        print(f"\n[1/4] Generating scraper code...")

    code = generate_scraper_code(venue_name, url, template)
    scraper_path.write_text(code)

    if verbose:
        print(f"  ✓ Created {scraper_path}")

    # Step 2: Run initial test
    if verbose:
        print(f"\n[2/4] Running initial test...")

    success, events, stdout, stderr = run_scraper(str(scraper_path), verbose)

    if success and events > 0:
        result.success = True
        result.events_scraped = events
        result.iterations = 1
        if verbose:
            print(f"  ✓ Success! Scraped {events} events on first try")
        return result

    # Step 3: Run self-healing loop
    if verbose:
        print(f"\n[3/4] Running self-healing loop...")
        print(f"  Initial result: success={success}, events={events}")

    healer = VisualSelfHealer(source_name, verbose=verbose)
    healer.scraper_path = str(scraper_path)
    healer.MAX_ITERATIONS = max_healing_iterations

    healing_result = healer.heal()

    result.iterations = len(healing_result.get("iterations", []))
    result.events_scraped = healing_result.get("final_events_count", 0)
    result.success = healing_result.get("final_status") == "success"

    # Collect all issues and fixes
    for iteration in healing_result.get("iterations", []):
        result.issues_found.extend(iteration.get("issues", []))
        result.fixes_applied.extend(iteration.get("fixes_applied", []))

    # Step 4: Final diagnosis
    if verbose:
        print(f"\n[4/4] Final diagnosis...")

    if not result.success:
        result.final_diagnosis = diagnose_scraper(source_name, verbose=False)
        result.error_message = f"Failed after {result.iterations} iterations"
        if result.final_diagnosis:
            result.error_message += f" - {result.final_diagnosis.failure_pattern}"

    # Summary
    if verbose:
        print(f"\n{'='*60}")
        print(f"CREATION RESULT: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"{'='*60}")
        print(f"  Events scraped: {result.events_scraped}")
        print(f"  Iterations: {result.iterations}")
        print(f"  Issues found: {len(result.issues_found)}")
        print(f"  Fixes applied: {len(result.fixes_applied)}")
        if result.error_message:
            print(f"  Error: {result.error_message}")

    return result


def run_scraper(scraper_path: str, verbose: bool = True) -> Tuple[bool, int, str, str]:
    """
    Run a scraper and return results.

    Returns: (success, events_count, stdout, stderr)
    """
    try:
        result = subprocess.run(
            ["node", scraper_path],
            capture_output=True,
            text=True,
            timeout=300
        )

        success = result.returncode == 0
        stdout = result.stdout
        stderr = result.stderr

        # Try to extract events count from output
        events = 0
        events_match = re.search(r'(\d+) events', stdout)
        if events_match:
            events = int(events_match.group(1))

        return success, events, stdout, stderr

    except subprocess.TimeoutExpired:
        return False, 0, "", "Timeout after 5 minutes"
    except Exception as e:
        return False, 0, "", str(e)


def heal_existing_scraper(source_name: str, max_iterations: int = 5, verbose: bool = True) -> Dict:
    """Run self-healing on an existing scraper."""
    print(f"\n{'='*60}")
    print(f"HEALING SCRAPER: {source_name}")
    print(f"{'='*60}")

    healer = VisualSelfHealer(source_name, verbose=verbose)
    healer.MAX_ITERATIONS = max_iterations
    return healer.heal()


def diagnose_existing_scraper(source_name: str, verbose: bool = True) -> DiagnosticReport:
    """Run diagnosis on an existing scraper."""
    print(f"\n{'='*60}")
    print(f"DIAGNOSING SCRAPER: {source_name}")
    print(f"{'='*60}")

    return diagnose_scraper(source_name, verbose=verbose)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Create, test, and heal scrapers automatically',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new scraper
  python src/create_scraper.py "Brooklyn Bowl" "https://www.brooklynbowl.com/events"

  # Create with click pagination template
  python src/create_scraper.py "Barclays Center" "https://www.barclayscenter.com/events" --template click

  # Heal an existing scraper
  python src/create_scraper.py --heal barclays_center

  # Diagnose an existing scraper
  python src/create_scraper.py --diagnose barclays_center

  # List available templates
  python src/create_scraper.py --list-templates
        """
    )

    # Positional arguments for creation
    parser.add_argument('venue_name', nargs='?', help='Venue name (e.g., "Brooklyn Bowl")')
    parser.add_argument('url', nargs='?', help='Events page URL')

    # Options
    parser.add_argument('--template', '-t', choices=['scroll', 'click'], default='scroll',
                        help='Template to use (default: scroll)')
    parser.add_argument('--production', '-p', action='store_true',
                        help='Create in production directory (default: staging)')
    parser.add_argument('--max-iterations', '-m', type=int, default=5,
                        help='Max self-healing iterations (default: 5)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Quiet mode')

    # Alternative modes
    parser.add_argument('--heal', metavar='SOURCE', help='Heal an existing scraper')
    parser.add_argument('--diagnose', metavar='SOURCE', help='Diagnose an existing scraper')
    parser.add_argument('--explore', metavar='SOURCE', help='Explore a page to discover the right interaction pattern')
    parser.add_argument('--list-templates', action='store_true', help='List available templates')

    args = parser.parse_args()

    # Handle alternative modes
    if args.list_templates:
        print("\nAvailable templates:")
        print("  scroll - For sites with infinite scroll or lazy loading")
        print("  click  - For sites with 'Load More' / 'View More' buttons")
        return

    if args.heal:
        result = heal_existing_scraper(args.heal, args.max_iterations, not args.quiet)
        sys.exit(0 if result.get("final_status") == "success" else 1)

    if args.diagnose:
        report = diagnose_existing_scraper(args.diagnose, not args.quiet)
        sys.exit(0 if report.confidence > 0.5 else 1)

    if args.explore:
        from src.exploratory_healer import ExploratoryHealer
        import re

        source = args.explore
        # Try to find URL from existing scraper
        scraper_path = Path(f"src/scrapers/{source}.js")
        url = None
        if scraper_path.exists():
            content = scraper_path.read_text()
            url_match = re.search(r'page\.goto\(["\']([^"\']+)["\']', content)
            if url_match:
                url = url_match.group(1)

        if not url:
            print(f"Error: Could not find URL for {source}. Provide URL as second argument.")
            sys.exit(1)

        print(f"Exploring {source} at {url}...")
        healer = ExploratoryHealer(source, url, verbose=not args.quiet)
        results = healer.explore_and_discover()

        if results.get("best_pattern"):
            print(f"\nDiscovered pattern: {results['best_pattern']['actions']}")
            print(f"Events found: {results['best_pattern']['events']}")
            if results.get("generated_scraper"):
                print("\nGenerated scraper code available in results file.")
            sys.exit(0)
        else:
            print("\nCould not discover a working pattern.")
            sys.exit(1)

    # Creation mode - require venue_name and url
    if not args.venue_name or not args.url:
        parser.error("venue_name and url are required for creating a new scraper")

    result = create_scraper(
        venue_name=args.venue_name,
        url=args.url,
        template=args.template,
        staging=not args.production,
        max_healing_iterations=args.max_iterations,
        verbose=not args.quiet
    )

    # Save result
    output_dir = Path("data/output/scraper_creation")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"create_{result.source_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            "source_name": result.source_name,
            "venue_name": result.venue_name,
            "scraper_path": result.scraper_path,
            "success": result.success,
            "events_scraped": result.events_scraped,
            "iterations": result.iterations,
            "issues_found": result.issues_found,
            "fixes_applied": result.fixes_applied,
            "error_message": result.error_message
        }, f, indent=2)

    print(f"\nResult saved to: {output_file}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
