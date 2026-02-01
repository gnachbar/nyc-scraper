#!/usr/bin/env python3
"""
Exploratory Self-Healer

When a scraper fails to find events, this module:
1. Takes a screenshot of the page
2. Uses Claude's vision to analyze what's on the page
3. Identifies interactive elements (buttons, tabs, navigation)
4. Suggests and tries different interaction patterns
5. Learns the correct sequence to extract events

This is "creative exploration" rather than "fix known errors".
"""

import openai
from dotenv import load_dotenv
load_dotenv()
import base64
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ExplorationResult:
    """Result of an exploration attempt."""
    action_taken: str
    screenshot_before: str
    screenshot_after: str
    events_found: int
    success: bool
    observations: List[str] = field(default_factory=list)


@dataclass
class InteractionPattern:
    """A discovered interaction pattern."""
    name: str
    actions: List[str]
    description: str
    events_found: int


class ExploratoryHealer:
    """
    Explores a page to discover the right interaction pattern for scraping.

    Instead of just fixing errors, this class:
    1. Analyzes screenshots to understand page structure
    2. Tries different interactions (clicks, navigation)
    3. Tracks which actions reveal more content
    4. Generates the correct scraper logic
    """

    def __init__(self, source: str, url: str, verbose: bool = True):
        self.source = source
        self.url = url
        self.verbose = verbose
        self.client = openai.OpenAI()
        self.explorations: List[ExplorationResult] = []
        self.discovered_patterns: List[InteractionPattern] = []

    def log(self, message: str):
        if self.verbose:
            print(f"[EXPLORE] {message}")

    def analyze_screenshot(self, screenshot_path: str, context: str = "") -> Dict[str, Any]:
        """
        Use Claude's vision to analyze a screenshot and identify:
        - Interactive elements (buttons, tabs, links)
        - Navigation patterns (arrows, pagination)
        - View switchers (list/grid/calendar)
        - Current state of the page
        """
        self.log(f"Analyzing screenshot: {screenshot_path}")

        # Read and encode the image
        with open(screenshot_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        prompt = f"""Analyze this screenshot of an events/calendar page.

Context: {context if context else "Looking for events to scrape"}

Please identify:

1. **Current Page State**: What view is shown? (calendar grid, list view, etc.)

2. **Interactive Elements**: List ALL clickable elements you see:
   - Buttons (especially "List", "Grid", "Calendar", "Load More", "Show More")
   - Navigation arrows (left/right, prev/next month)
   - Tabs or view switchers
   - Date pickers or filters

3. **Events Visible**: How many events can you see on the page right now?

4. **Recommended Actions**: What should we click to:
   a) Switch to a better view for scraping (e.g., list view)
   b) Load more events (pagination, arrows)
   c) Navigate to see future events

5. **Suggested Click Sequence**: Give a specific sequence of actions to get all events.
   Format each action as: "click [description of element]"

Return your analysis as JSON:
{{
  "current_view": "description of current view",
  "events_visible": number,
  "interactive_elements": [
    {{"type": "button/link/tab", "text": "visible text", "location": "top-right/bottom/etc", "purpose": "what it does"}}
  ],
  "recommended_actions": [
    {{"action": "click [element]", "reason": "why this helps", "priority": 1-3}}
  ],
  "suggested_sequence": [
    "click LIST button on top right",
    "click right arrow to go to next month",
    "repeat arrow clicks for more months"
  ]
}}
"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        # Parse the response
        response_text = response.choices[0].message.content

        # Try to extract JSON from the response
        try:
            # Look for JSON block
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                analysis = json.loads(json_match.group())
                return analysis
        except json.JSONDecodeError:
            pass

        # If JSON parsing fails, return structured response
        return {
            "raw_analysis": response_text,
            "events_visible": 0,
            "interactive_elements": [],
            "recommended_actions": [],
            "suggested_sequence": []
        }

    def generate_exploration_scraper(self, actions: List[str]) -> str:
        """
        Generate a temporary scraper that performs the specified actions
        and takes screenshots before/after each action.
        """
        actions_js = []
        for i, action in enumerate(actions):
            # Parse the action
            if action.lower().startswith("click "):
                element_desc = action[6:]  # Remove "click "
                actions_js.append(f'''
    // Action {i+1}: {action}
    console.log("Trying action: {action}");
    try {{
      await page.act("{action}");
      await page.waitForTimeout(2000);

      // Take screenshot after action
      const screenshot{i} = await page.screenshot();
      fs.writeFileSync('screenshots/explore_{self.source}_action{i}.png', screenshot{i});
      console.log("Action {i+1} completed, screenshot saved");
    }} catch (e) {{
      console.log("Action {i+1} failed:", e.message);
    }}
''')
            elif action.lower().startswith("wait "):
                wait_time = int(re.search(r'\d+', action).group()) if re.search(r'\d+', action) else 2000
                actions_js.append(f'''
    // Action {i+1}: {action}
    await page.waitForTimeout({wait_time});
''')

        return f'''
import {{ initStagehand, createStandardSchema, capturePageScreenshot }} from '../lib/scraper-utils.js';
import {{ extractEventsFromPage }} from '../lib/scraper-actions.js';
import fs from 'fs';

const StandardEventSchema = createStandardSchema({{ eventLocationDefault: '{self.source}' }});

async function explore() {{
  const stagehand = await initStagehand({{ env: 'BROWSERBASE' }});
  const page = stagehand.page;

  try {{
    console.log("Starting exploration for {self.source}");
    console.log("Session:", stagehand.browserbaseSessionID);

    // Navigate to page
    await page.goto("{self.url}", {{ waitUntil: 'domcontentloaded', timeout: 60000 }});
    await page.waitForTimeout(5000);

    // Initial screenshot
    await capturePageScreenshot(page, '{self.source}_explore_initial');
    console.log("Initial screenshot captured");

    // Perform exploration actions
    {"".join(actions_js)}

    // Final screenshot
    await capturePageScreenshot(page, '{self.source}_explore_final');

    // Try to extract events
    console.log("Attempting extraction...");
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events with their names, dates, times, and URLs",
      StandardEventSchema,
      {{ sourceName: '{self.source}_explore' }}
    );

    console.log("Events found:", result.events.length);
    console.log("EXPLORATION_RESULT:", JSON.stringify({{
      events_count: result.events.length,
      sample_events: result.events.slice(0, 3)
    }}));

    return result;
  }} catch (error) {{
    console.error("Exploration error:", error.message);
  }} finally {{
    await stagehand.close();
  }}
}}

explore();
'''

    def run_exploration(self, actions: List[str]) -> Tuple[int, str]:
        """
        Run an exploration with the specified actions.
        Returns (events_found, output)
        """
        # Generate the exploration scraper
        scraper_code = self.generate_exploration_scraper(actions)

        # Write to temp file
        temp_path = Path(f"src/scrapers-staging/_explore_{self.source}.js")
        temp_path.write_text(scraper_code)

        self.log(f"Running exploration with actions: {actions}")

        try:
            # Run the exploration
            result = subprocess.run(
                ["node", str(temp_path)],
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout
            )

            output = result.stdout + result.stderr

            # Parse events count from output
            events_match = re.search(r'EXPLORATION_RESULT:\s*(\{.*\})', output)
            if events_match:
                try:
                    exploration_result = json.loads(events_match.group(1))
                    return exploration_result.get('events_count', 0), output
                except:
                    pass

            # Fallback: look for "Events found: X"
            count_match = re.search(r'Events found:\s*(\d+)', output)
            if count_match:
                return int(count_match.group(1)), output

            return 0, output

        except subprocess.TimeoutExpired:
            return 0, "Exploration timed out"
        except Exception as e:
            return 0, f"Exploration error: {str(e)}"
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

    def explore_and_discover(self, max_iterations: int = 5) -> Dict[str, Any]:
        """
        Main exploration loop:
        1. Take initial screenshot
        2. Analyze with Claude vision
        3. Try suggested actions
        4. Track what works
        5. Generate correct scraper logic
        """
        self.log(f"Starting exploration for {self.source}")
        self.log(f"URL: {self.url}")

        results = {
            "source": self.source,
            "url": self.url,
            "started_at": datetime.now().isoformat(),
            "iterations": [],
            "best_pattern": None,
            "events_found": 0
        }

        # First, run with no actions to get initial state
        self.log("\n=== Initial State ===")
        events_found, output = self.run_exploration([])

        results["iterations"].append({
            "iteration": 0,
            "actions": [],
            "events_found": events_found
        })

        if events_found > 0:
            self.log(f"Found {events_found} events without any actions!")
            results["best_pattern"] = {"actions": [], "events": events_found}
            results["events_found"] = events_found

            # If we found some events but not many, continue exploring to find more
            if events_found < 20:
                self.log(f"Only {events_found} events - will try to find more...")
            else:
                return results

        # Find the initial screenshot
        screenshots = list(Path("screenshots").glob(f"{self.source}_explore_initial*.png"))
        if not screenshots:
            self.log("No initial screenshot found, cannot analyze")
            return results

        latest_screenshot = max(screenshots, key=lambda p: p.stat().st_mtime)

        # Analyze the screenshot
        self.log("\n=== Analyzing Page ===")
        analysis = self.analyze_screenshot(str(latest_screenshot),
            context=f"This is {self.source}. We found 0 events. What should we click?")

        self.log(f"Events visible: {analysis.get('events_visible', 'unknown')}")
        self.log(f"Suggested sequence: {analysis.get('suggested_sequence', [])}")

        # Try the suggested sequence
        suggested_actions = analysis.get('suggested_sequence', [])
        if suggested_actions:
            self.log(f"\n=== Trying Suggested Sequence ===")
            events_found, output = self.run_exploration(suggested_actions)

            results["iterations"].append({
                "iteration": 1,
                "actions": suggested_actions,
                "events_found": events_found,
                "analysis": analysis
            })

            if events_found > results["events_found"]:
                results["best_pattern"] = {
                    "actions": suggested_actions,
                    "events": events_found
                }
                results["events_found"] = events_found

            self.log(f"Found {events_found} events with suggested sequence")

        # If still no events, try individual actions from recommendations
        if results["events_found"] == 0:
            recommended = analysis.get('recommended_actions', [])
            for i, rec in enumerate(recommended[:3]):  # Try top 3 recommendations
                action = rec.get('action', '')
                if not action:
                    continue

                self.log(f"\n=== Trying Action: {action} ===")
                events_found, output = self.run_exploration([action])

                results["iterations"].append({
                    "iteration": i + 2,
                    "actions": [action],
                    "events_found": events_found
                })

                if events_found > results["events_found"]:
                    results["best_pattern"] = {
                        "actions": [action],
                        "events": events_found
                    }
                    results["events_found"] = events_found

                if events_found > 0:
                    self.log(f"Found {events_found} events!")
                    break

        # Generate scraper code if we found a working pattern
        if results["best_pattern"]:
            self.log(f"\n=== Best Pattern Found ===")
            self.log(f"Actions: {results['best_pattern']['actions']}")
            self.log(f"Events: {results['best_pattern']['events']}")

            # Generate the scraper code
            results["generated_scraper"] = self._generate_final_scraper(
                results["best_pattern"]["actions"]
            )

        results["completed_at"] = datetime.now().isoformat()

        # Save results
        output_path = Path(f"data/output/exploration_{self.source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        self.log(f"\nResults saved to: {output_path}")

        return results

    def _generate_final_scraper(self, actions: List[str]) -> str:
        """Generate final scraper code based on discovered pattern."""

        actions_code = []
        for action in actions:
            if action.lower().startswith("click "):
                element = action[6:]
                actions_code.append(f'''
    // {action}
    console.log("{action}...");
    try {{
      await page.act("{action}");
      await page.waitForTimeout(2000);
    }} catch (e) {{
      console.log("Action failed (continuing):", e.message);
    }}''')

        return f'''
// Auto-generated scraper for {self.source}
// Generated by exploratory self-healer

import {{ initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom, capturePageScreenshot }} from '../lib/scraper-utils.js';
import {{ extractEventsFromPage }} from '../lib/scraper-actions.js';
import {{ logScrapingResults, saveEventsToDatabase, handleScraperError }} from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({{ eventLocationDefault: '{self.source.replace("_", " ").title()}' }});

export async function scrape{self.source.replace("_", " ").title().replace(" ", "")}() {{
  const stagehand = await initStagehand({{ env: 'BROWSERBASE' }});
  const page = stagehand.page;

  try {{
    console.log("Stagehand Session Started");
    console.log("Watch live:", stagehand.browserbaseSessionID);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Navigate to page
    await page.goto("{self.url}", {{
      waitUntil: 'domcontentloaded',
      timeout: 60000
    }});
    await page.waitForTimeout(3000);

    // Discovered interaction pattern:
    {"".join(actions_code)}

    // Scroll to load more content
    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    // Take screenshot for verification
    await capturePageScreenshot(page, '{self.source}');

    // Extract events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events with their names, dates, times (if shown), descriptions, and URLs",
      StandardEventSchema,
      {{ sourceName: '{self.source}' }}
    );

    const events = result.events.map(e => ({{
      ...e,
      eventLocation: "{self.source.replace("_", " ").title()}"
    }}));

    logScrapingResults(events, '{self.source.replace("_", " ").title()}');

    if (events.length > 0) {{
      await saveEventsToDatabase(events, '{self.source}');
    }}

    return {{ events }};

  }} catch (error) {{
    await handleScraperError(error, page, '{self.source.replace("_", " ").title()}');
  }} finally {{
    await stagehand.close();
  }}
}}

if (import.meta.url === `file://${{process.argv[1]}}`) {{
  scrape{self.source.replace("_", " ").title().replace(" ", "")}();
}}

export default scrape{self.source.replace("_", " ").title().replace(" ", "")};
'''


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Exploratory self-healer')
    parser.add_argument('source', help='Source name (e.g., public_theater)')
    parser.add_argument('--url', help='URL to scrape (optional, will try to detect)')
    parser.add_argument('--max-iterations', type=int, default=5, help='Max exploration iterations')

    args = parser.parse_args()

    # Try to detect URL from existing scraper
    url = args.url
    if not url:
        scraper_path = Path(f"src/scrapers/{args.source}.js")
        if scraper_path.exists():
            content = scraper_path.read_text()
            url_match = re.search(r'page\.goto\(["\']([^"\']+)["\']', content)
            if url_match:
                url = url_match.group(1)

    if not url:
        print(f"Error: Could not detect URL for {args.source}. Please provide --url")
        sys.exit(1)

    healer = ExploratoryHealer(args.source, url)
    results = healer.explore_and_discover(max_iterations=args.max_iterations)

    if results.get("best_pattern"):
        print(f"\n{'='*60}")
        print("SUCCESS: Found working pattern!")
        print(f"Actions: {results['best_pattern']['actions']}")
        print(f"Events found: {results['best_pattern']['events']}")
        print(f"{'='*60}")

        if results.get("generated_scraper"):
            print("\nGenerated scraper code saved in results file.")
    else:
        print(f"\n{'='*60}")
        print("Could not find a working pattern.")
        print("Manual investigation needed.")
        print(f"{'='*60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
