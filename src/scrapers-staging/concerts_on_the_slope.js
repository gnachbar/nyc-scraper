/**
 * Concerts on the Slope Scraper
 * 
 * Scrapes events from Concerts on the Slope 2025-2026 season
 * https://www.concertsontheslope.org/season/2025-2026
 * 
 * Key Features:
 * - Uses shared utility functions from src/lib/ to reduce code duplication
 * - Single-venue scraper (hardcodes 'St. John's Episcopal Church' as eventLocation)
 * - Simple single-page extraction (no pagination or "Load More" needed)
 * - Extracts event times from the page
 * - Automatically saves to database and runs consistency tests
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession, scrollToBottom, createStandardSchema } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';
import { z } from 'zod';

// Local schema: allow any string for eventUrl, hardcode location via default
const SeasonEventSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().default(""),
    eventUrl: z.string().default(""),
    eventLocation: z.string().default("St. John's Episcopal Church")
  }))
});

// Define shared standard schema for validation (not used for extraction due to relaxed URL)
const StandardEventSchema = createStandardSchema({ eventLocationDefault: "St. John's Episcopal Church" });

/**
 * Main scraper function for Concerts on the Slope
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase (shared utility)
 * 2. Open Browserbase session URL in browser (shared utility)
 * 3. Navigate to season page
 * 4. Scroll to bottom to ensure all content is loaded
 * 5. Extract all visible events
 * 6. Log results (shared utility)
 * 7. Save to database and run tests (shared utility)
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeConcertsOnTheSlope() {
  // Initialize Stagehand using shared utility function
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;
  const seasonUrl = "https://www.concertsontheslope.org/season/2025-2026";

  try {
    // Open Browserbase session URL in default browser using shared utility
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the season page
    await page.goto(seasonUrl);
    await page.waitForLoadState('networkidle');
    
    // Step 2: Scroll to bottom to ensure all content is loaded (in case of lazy loading)
    await scrollToBottom(page);
    
    // Step 3: Extract all visible events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible concerts on this 2025-2026 season page. For each event, get eventName, eventDate with YEAR, eventTime (format like 3:00 PM), eventUrl (full href of the tickets or title link; if relative, prepend https://www.concertsontheslope.org; do not return internal IDs), and set eventLocation to 'St. John's Episcopal Church' for all events.",
      SeasonEventSchema,
      { sourceName: 'concerts_on_the_slope' }
    );

    // Backup: Add hardcoded venue name to all events (in case schema default fails)
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "St. John's Episcopal Church",
      // Hardcode eventUrl to the season page per guidance
      eventUrl: seasonUrl
    }));

    // Log scraping results using shared utility function
    logScrapingResults(eventsWithLocation, 'Concerts on the Slope');
    
    // Save to database and run tests using shared utility function
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'concerts_on_the_slope');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    // Handle errors using shared utility function
    await handleScraperError(error, page, 'Concerts on the Slope');
  } finally {
    // Always close Stagehand session to clean up browser resources
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeConcertsOnTheSlope().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeConcertsOnTheSlope;

