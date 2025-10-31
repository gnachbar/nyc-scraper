/**
 * Public Records Scraper
 * 
 * Scrapes event listings from Public Records on Dice.fm
 * URL: https://dice.fm/venue/public-records-w2qg
 * 
 * Key Features:
 * - Single-venue scraper (hardcodes 'Public Records' as eventLocation)
 * - Uses shared utility functions from src/lib/
 * - Loads page, scrolls, clicks "Load More" until all events are visible
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

/**
 * Create standardized event schema with venue default for single-venue scraper
 * The schema will automatically set eventLocation to 'Public Records' for all events
 */
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Public Records' });

/**
 * Main scraper function for Public Records
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase
 * 2. Open Browserbase session URL in browser
 * 3. Navigate to Public Records Dice.fm venue page
 * 4. Scroll to bottom to trigger lazy loading (if any)
 * 5. Click "Load More" button repeatedly until it disappears
 * 6. Extract all visible events
 * 7. Log results and save to database
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapePublicRecords() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session URL in default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to Public Records venue page
    await page.goto("https://dice.fm/venue/public-records-w2qg");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Scroll to bottom to ensure initial events are loaded
    console.log("Scrolling to bottom to load initial events...");
    await scrollToBottom(page);
    
    // Step 3: Click "Load More" button repeatedly until it disappears
    // Maximum of 20 clicks should be more than enough for any venue
    console.log("Clicking 'Load More' button until all events are loaded...");
    await clickButtonUntilGone(page, "Load More", 20, {
      scrollAfterClick: true,
      scrollWaitTime: 2000,
      loadWaitTime: 2000
    });
    
    // Step 4: Extract all visible events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from the Public Records venue page. For each event, get: (1) eventName: the full event title; (2) eventDate: RETURN IN EXACT FORMAT 'Monday, October 27, 2025' using full weekday and full month names with a comma after weekday and after day, and include the 4-digit year; DO NOT use abbreviated weekday/month (e.g., NOT 'Thu, Oct 30, 2025'); (3) eventTime: the time if visible (e.g., '7:00 PM'); if no time is shown, return an empty string; (4) eventDescription: the event description if available; if no description is shown, return an empty string; (5) eventLocation: set to 'Public Records' for all events; (6) eventUrl: the full absolute URL to the event details page by clicking the event title or tickets link and capturing the href. Ensure eventDate strictly matches 'Monday, October 27, 2025'.",
      StandardEventSchema,
      { sourceName: 'public_records' }
    );

    // Backup: Add hardcoded venue name to all events
    let eventsWithLocation = result.events.map(event => {
      // Ensure absolute URLs
      let url = event.eventUrl || "";
      if (url && !url.startsWith("http")) {
        url = url.startsWith("/") ? `https://dice.fm${url}` : `https://dice.fm/${url}`;
      }
      return {
        ...event,
        eventUrl: url,
        eventLocation: "Public Records"
      };
    });

    // Step 5: Visit each event URL and extract event times (Kings Theatre pattern)
    // This fills in eventTime where listing pages don't include times
    eventsWithLocation = await extractEventTimesFromPages(stagehand, eventsWithLocation, {
      timeout: 60000,
      delay: 500,
      useNetworkIdle: false,
      domWaitMs: 4000,
      // Dice pages often show time in blocks with words like 'Doors' or explicit time patterns
      waitForSelector: "text=Doors,text=Show,text=PM,text=AM"
    });

    // Step 6: Default time fallback – set 7:00 PM if time is missing
    eventsWithLocation = eventsWithLocation.map(event => ({
      ...event,
      eventTime: event.eventTime && event.eventTime.trim() !== "" ? event.eventTime : "7:00 PM"
    }));

    // Log scraping results
    logScrapingResults(eventsWithLocation, 'Public Records');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'public_records');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Public Records');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapePublicRecords().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapePublicRecords;

