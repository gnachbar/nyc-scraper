/**
 * BRIC House Scraper
 * 
 * Scrapes events from BRIC Arts Media
 * Uses calendar view approach: load calendar page, paginate through months
 * 
 * Key Features:
 * - Uses shared utility functions from src/lib/ to reduce code duplication
 * - Single-venue scraper (hardcodes 'BRIC House' as eventLocation)
 * - Calendar pagination: extracts events from calendar view across 6 months
 * - Extracts event times from the page
 * - Automatically saves to database and runs consistency tests
 * 
 * Known Issue:
 * - URLs may not be extracted properly from calendar view
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession } from '../lib/scraper-utils.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';
import { z } from 'zod';

/**
 * Main scraper function for BRIC House
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase (shared utility)
 * 2. Open Browserbase session URL in browser (shared utility)
 * 3. Navigate to BRIC calendar page
 * 4. Extract events from current month
 * 5. Click arrow to move to next month
 * 6. Repeat for 6 months total
 * 7. Log results (shared utility)
 * 8. Save to database and run tests (shared utility)
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeBRICHouse() {
  // Initialize Stagehand using shared utility function
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session URL in default browser using shared utility
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the BRIC calendar page
    await page.goto("https://bricartsmedia.org/events/calendar/?date_from=2025-10-01&date_to=2025-10-31&location=75%2C344%2C243%2C455%2C265");
    // BRIC site has continuous network activity, so use timeout instead of networkidle
    await page.waitForTimeout(5000);
    
    // Step 2: Paginate through calendar months and extract events
    // We'll extract events from each month for 6 months
    
    const allEvents = [];
    const monthsToScrape = 6;
    
    // Schema for extracting multiple events from calendar view
    // Extract eventTime from page and hardcode eventLocation to BRIC House
    const calendarEventSchema = z.object({
      events: z.array(z.object({
        eventName: z.string(),
        eventDate: z.string(),
        eventTime: z.string().default(""),
        eventDescription: z.string().default(""),
        eventUrl: z.string().url(),
        eventLocation: z.string().default("BRIC House")
      }))
    });
    
    for (let month = 0; month < monthsToScrape; month++) {
      console.log(`\n--- Scraping Month ${month + 1}/${monthsToScrape} ---`);
      
      // Extract all events visible in the current calendar view
      const result = await page.extract({
        instruction: `Extract all events visible in the calendar view. For each event, get:
- eventName: The full name/title of the event
- eventDate: The FULL date including day, month, and YEAR (e.g., "Monday, October 27, 2025" or "Oct 27, 2025")
- eventTime: The time of the event if visible (e.g., "7:00 PM", "7:30 PM") - extract from the calendar if available
- eventDescription: The event description if visible, otherwise return an empty string
- eventUrl: The URL to the event (click on the event name to get the URL from the event page or link)
- eventLocation: Set to 'BRIC House' for all events

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
    
    // Backup: Add hardcoded venue name to all events
    const eventsWithDefaults = allEvents.map(event => ({
      ...event,
      eventLocation: "BRIC House"
    }));

    // Log scraping results using shared utility function
    logScrapingResults(eventsWithDefaults, 'BRIC House');
    
    // Save to database and run tests using shared utility function
    if (eventsWithDefaults.length > 0) {
      await saveEventsToDatabase(eventsWithDefaults, 'bric_house');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithDefaults };

  } catch (error) {
    // Handle errors using shared utility function
    await handleScraperError(error, page, 'BRIC House');
  } finally {
    // Always close Stagehand session to clean up browser resources
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBRICHouse().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeBRICHouse;

