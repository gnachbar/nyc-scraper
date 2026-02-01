/**
 * The Public Theater Scraper
 * 
 * This scraper demonstrates the shared utilities architecture pattern used by all scrapers.
 * 
 * Key Features:
 * - Uses shared utility functions from src/lib/ to reduce code duplication
 * - Single-venue scraper (hardcodes 'The Public Theater' as eventLocation)
 * - Handles "Load More" button clicking (unique to The Public Theater)
 * - Automatically saves to database and runs consistency tests
 */

// Import shared utilities from src/lib/
// scraper-utils.js: Provides initialization, schema creation, and scrolling helpers
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom, capturePageScreenshot } from '../lib/scraper-utils.js';
// scraper-actions.js: Provides button clicking and event extraction with error handling
import { clickButtonUntilGone, extractEventsFromPage, extractEventTimesFromPages } from '../lib/scraper-actions.js';
// scraper-persistence.js: Provides logging, database saving, and error handling
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

/**
 * Create standardized event schema using shared utility function.
 * Using eventLocationDefault parameter because The Public Theater is a single-venue scraper.
 * The schema will automatically set eventLocation to 'The Public Theater' for all events.
 */
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'The Public Theater' });

/**
 * Main scraper function for The Public Theater
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase (shared utility)
 * 2. Open Browserbase session URL in browser (shared utility)
 * 3. Navigate to The Public Theater calendar page
 * 4. Click the list button to switch to list view
 * 5. Scroll to bottom to trigger lazy loading (shared utility)
 * 6. Click "Load More" button multiple times (shared utility with Public Theater-specific config)
 * 7. Extract all visible events (shared utility with error handling)
 * 8. Log results (shared utility)
 * 9. Save to database and run tests (shared utility)
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapePublicTheater() {
  // Initialize Stagehand using shared utility function
  // This handles environment setup, verbose logging, and Browserbase configuration
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session URL in default browser using shared utility
    // This allows watching the scraping live at https://browserbase.com/sessions/{id}
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to The Public Theater calendar page
    // The site has aggressive navigation behavior, so wait for load event
    console.log("Navigating to calendar page...");
    await page.goto("https://publictheater.org/calendar/", {
      waitUntil: 'load',
      timeout: 90000
    });

    // Wait for any redirects to complete
    console.log("Waiting for page to stabilize...");
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(5000);

    // Take a screenshot to see the page state
    try {
      await capturePageScreenshot(page, 'public_theater_before_extract');
      console.log("Screenshot captured");
    } catch (e) {
      console.log("Screenshot failed:", e.message);
    }

    // Try to wait for calendar events to appear
    try {
      await page.waitForSelector('.event-card, .calendar-event, [data-event], .production-card', {
        timeout: 10000
      });
      console.log("Found event elements on page");
    } catch (e) {
      console.log("No event elements found yet, continuing anyway...");
    }
    
    // Step 5: Extract all visible events using shared utility function
    // The extraction instruction tells Stagehand exactly what to extract
    // The schema validates the extracted data structure
    // The sourceName is used for error reporting and test file naming
    // The shared utility automatically captures a screenshot if extraction fails
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from The Public Theater calendar page. For each event, get the event name (as eventName), date (as eventDate), time (as eventTime, if available), description (as eventDescription, if available), location (as eventLocation - set to 'The Public Theater' for all events), and the FULL URL (as eventUrl) by clicking on the event name/link to get the complete event page URL starting with https://publictheater.org/productions/. If description is not visible, return an empty string for eventDescription.",
      StandardEventSchema,
      { sourceName: 'public_theater' }
    );

    // Backup: Add hardcoded venue name to all events
    // This ensures eventLocation is set even if schema default fails
    // This is scraper-specific logic, not shared utility
    let eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "The Public Theater"
    }));

    // Visit individual event pages to extract times (improves time extraction accuracy)
    console.log("Extracting times from individual event pages...");
    eventsWithLocation = await extractEventTimesFromPages(stagehand, eventsWithLocation, {
      timeout: 30000,
      delay: 1000,
      useNetworkIdle: false,
      domWaitMs: 3000
    });

    // Log scraping results using shared utility function
    // This logs total events, events with/without times, and sample events
    // No need to manually count or format - the shared utility handles it
    logScrapingResults(eventsWithLocation, 'The Public Theater');
    
    // Save to database and run tests using shared utility function
    // This shared utility:
    // 1. Creates a temporary JSON file
    // 2. Calls the Python import script
    // 3. Runs scraper consistency tests
    // 4. Cleans up the temporary file
    // All error handling is built-in
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'public_theater');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    // Handle errors using shared utility function
    // This captures a screenshot for debugging and re-throws the error
    await handleScraperError(error, page, 'The Public Theater');
  } finally {
    // Always close Stagehand session to clean up browser resources
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapePublicTheater().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapePublicTheater;

