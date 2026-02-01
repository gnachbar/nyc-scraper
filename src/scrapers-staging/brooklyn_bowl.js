/**
 * Brooklyn Bowl Scraper
 *
 * Scrapes events from Brooklyn Bowl (Williamsburg location).
 * URL: https://www.brooklynbowl.com/brooklyn/shows/all
 *
 * Key Features:
 * - Single-venue scraper (Brooklyn Bowl, 61 Wythe Avenue, Brooklyn, NY)
 * - Uses shared utility functions from src/lib/
 * - Handles "Load More Events" button for pagination
 * - Captures screenshot for visual verification
 */

// Import shared utilities from src/lib/
import { z } from "zod";
import { initStagehand, openBrowserbaseSession, scrollToBottom, capturePageScreenshot } from '../lib/scraper-utils.js';
import { clickButtonUntilGone } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

/**
 * Custom schema for Brooklyn Bowl - uses lenient URL validation
 * since the AI might extract partial URLs that we'll fix up later
 */
const BrooklynBowlSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().default(""),
    eventDescription: z.string().nullable().transform(v => v ?? "").default(""),
    eventLocation: z.string().default("Brooklyn Bowl"),
    eventUrl: z.string() // Lenient - just require string, we'll validate/fix URLs later
  }))
});

/**
 * Main scraper function for Brooklyn Bowl
 *
 * Flow:
 * 1. Initialize Stagehand with Browserbase
 * 2. Navigate to Brooklyn Bowl shows page
 * 3. Capture screenshot for visual verification
 * 4. Scroll and click "Load More Events" to get all events
 * 5. Extract all visible events
 * 6. Save to database and run tests
 *
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeBrooklynBowl() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to Brooklyn Bowl shows page
    await page.goto("https://www.brooklynbowl.com/brooklyn/shows/all", { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);

    // Step 2: Scroll to bottom to trigger lazy loading
    await scrollToBottom(page);

    // Step 3: Click "Load More Events" button repeatedly until it disappears
    // This loads all available events on the page
    await clickButtonUntilGone(page, "Load More Events", 10, {
      scrollAfterClick: true,
      scrollWaitTime: 2000,
      loadWaitTime: 2000
    });

    // Step 4: Capture screenshot for visual verification AFTER all content is loaded
    const screenshotPath = await capturePageScreenshot(page, 'brooklyn_bowl');
    console.log(`Screenshot for verification: ${screenshotPath}`);

    // Step 5: Extract all visible events
    // Note: Brooklyn Bowl dates don't include year (e.g., "Sat 01/31"), so instruct to add current/next year
    const result = await page.extract({
      instruction: `Extract all visible events from the Brooklyn Bowl shows page. For each event:
      - eventName: The event/artist name (exclude VIP add-ons and "Closed" entries)
      - eventDate: The date shown (e.g., "Sat 01/31"). Convert to full format with year: "Saturday, January 31, 2026". If the month is earlier than the current month (January), use 2027.
      - eventTime: The show time (prefer "Show" time over "Doors" time, e.g., "8:00 PM"). If only doors time shown, use that.
      - eventLocation: Set to "Brooklyn Bowl" for all events
      - eventUrl: Get the href/link to the event detail page. If it's a relative URL like "/brooklyn/events/detail/...", include just that path.

      Skip any entries that say "Closed" or are VIP add-on packages.`,
      schema: BrooklynBowlSchema
    });

    // Filter out any "Closed" entries or VIP add-ons that might have slipped through
    const filteredEvents = result.events.filter(event => {
      const name = event.eventName.toLowerCase();
      return !name.includes('closed') && !name.includes('vip bowling lane add on');
    });

    // Fix URLs and ensure location is set for all events
    const BASE_URL = 'https://www.brooklynbowl.com';
    const eventsWithLocation = filteredEvents.map(event => {
      let url = event.eventUrl || '';

      // Fix relative URLs
      if (url.startsWith('/')) {
        url = BASE_URL + url;
      } else if (!url.startsWith('http')) {
        // If it's just a slug or partial path, construct full URL
        url = `${BASE_URL}/brooklyn/events/detail/${url}`;
      }

      return {
        ...event,
        eventLocation: "Brooklyn Bowl",
        eventUrl: url
      };
    });

    // Log results
    logScrapingResults(eventsWithLocation, 'Brooklyn Bowl');

    // Save to database
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'brooklyn_bowl');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation, screenshotPath };

  } catch (error) {
    await handleScraperError(error, page, 'Brooklyn Bowl');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBrooklynBowl().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeBrooklynBowl;
