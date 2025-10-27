/**
 * Brooklyn Paramount Scraper
 * 
 * Scrapes events from Brooklyn Paramount theater
 * Uses calendar view approach: click calendar button, paginate through months
 * 
 * Key Features:
 * - Uses shared utility functions from src/lib/ to reduce code duplication
 * - Single-venue scraper (hardcodes 'Brooklyn Paramount' as eventLocation)
 * - Calendar pagination: extracts events from calendar view across 6 months
 * - Hardcoded event time to "7:00 PM" for all events
 * - Automatically saves to database and runs consistency tests
 * 
 * Known Issue:
 * - URLs are not being extracted properly from calendar view (returning placeholder values)
 * - This is acceptable for now as primary goal is name, date, time, and location
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession } from '../lib/scraper-utils.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';
import { z } from 'zod';

/**
 * Main scraper function for Brooklyn Paramount
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase (shared utility)
 * 2. Open Browserbase session URL in browser (shared utility)
 * 3. Navigate to Brooklyn Paramount shows page
 * 4. Click calendar button to switch to calendar view
 * 5. Extract events from current month
 * 6. Click arrow to move to next month
 * 7. Repeat for 6 months total
 * 8. Log results (shared utility)
 * 9. Save to database and run tests (shared utility)
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeBrooklynParamount() {
  // Initialize Stagehand using shared utility function
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session URL in default browser using shared utility
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the Brooklyn Paramount shows page
    await page.goto("https://www.brooklynparamount.com/shows");
    // Brooklyn Paramount has continuous network activity, so use timeout instead of networkidle
    await page.waitForTimeout(5000);
    
    // Step 2: Click the calendar button on the top right
    console.log("Clicking calendar button...");
    await page.act("click the calendar button on the top right");
    await page.waitForTimeout(2000); // Wait for calendar view to load
    
    // Step 3: Paginate through calendar months and extract events
    // We'll extract events from each month for 6 months
    
    const allEvents = [];
    const monthsToScrape = 6;
    
    // Schema for extracting multiple events from calendar view
    // Hardcode eventTime to 7:00 PM and eventLocation to Brooklyn Paramount
    const calendarEventSchema = z.object({
      events: z.array(z.object({
        eventName: z.string(),
        eventDate: z.string(),
        eventTime: z.string().default("7:00 PM"),
        eventUrl: z.string().url(),
        eventLocation: z.string().default("Brooklyn Paramount")
      }))
    });
    
    for (let month = 0; month < monthsToScrape; month++) {
      console.log(`\n--- Scraping Month ${month + 1}/${monthsToScrape} ---`);
      
      // Extract all events visible in the current calendar view
      const result = await page.extract({
        instruction: `Extract all events visible in the calendar view. For each event, get:
- eventName: The full name/title of the event
- eventDate: The FULL date including day, month, and YEAR (e.g., "Monday, October 27, 2025" or "Oct 27, 2025")
- eventTime: Set to '7:00 PM' for all events (do not extract from page)
- eventUrl: The URL to the event (click on the event to get the URL from the event page or link)
- eventLocation: Set to 'Brooklyn Paramount' for all events

Extract from the calendar grid where events are displayed. Return all visible events as an array.`,
        schema: calendarEventSchema
      });
      
      console.log(`Found ${result.events.length} events in month ${month + 1}`);
      allEvents.push(...result.events);
      
      // Move to next month by clicking the arrow to the right of the month
      if (month < monthsToScrape - 1) {
        console.log("Clicking arrow to move to next month...");
        await page.act("click the arrow to the right of the month name to move to the next month");
        await page.waitForTimeout(2000); // Wait for calendar to update
      }
    }
    
    console.log(`\nSuccessfully extracted ${allEvents.length} total events across ${monthsToScrape} months`);
    
    // Backup: Add hardcoded venue name and time to all events
    const eventsWithDefaults = allEvents.map(event => ({
      ...event,
      eventLocation: "Brooklyn Paramount",
      eventTime: "7:00 PM"
    }));

    // Log scraping results using shared utility function
    logScrapingResults(eventsWithDefaults, 'Brooklyn Paramount');
    
    // Save to database and run tests using shared utility function
    if (eventsWithDefaults.length > 0) {
      await saveEventsToDatabase(eventsWithDefaults, 'brooklyn_paramount');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithDefaults };

  } catch (error) {
    // Handle errors using shared utility function
    await handleScraperError(error, page, 'Brooklyn Paramount');
  } finally {
    // Always close Stagehand session to clean up browser resources
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBrooklynParamount().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeBrooklynParamount;

