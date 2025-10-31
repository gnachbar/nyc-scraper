/**
 * MSG Calendar Scraper
 * 
 * This scraper demonstrates the shared utilities architecture pattern used by all scrapers.
 * It serves as a reference implementation with detailed inline comments explaining each step.
 * 
 * Key Features:
 * - Uses shared utility functions from src/lib/ to reduce code duplication
 * - Single-venue scraper (hardcodes 'Madison Square Garden' as eventLocation)
 * - Handles "Load More Events" button clicking (unique to MSG)
 * - Automatically saves to database and runs consistency tests
 */

// Import shared utilities from src/lib/
// scraper-utils.js: Provides initialization, schema creation, and scrolling helpers
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
// scraper-actions.js: Provides button clicking and event extraction with error handling
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
// scraper-persistence.js: Provides logging, database saving, and error handling
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

/**
 * Create standardized event schema using shared utility function.
 * Using eventLocationDefault parameter because MSG is a single-venue scraper.
 * The schema will automatically set eventLocation to 'Madison Square Garden' for all events.
 */
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Madison Square Garden' });

/**
 * Main scraper function for MSG Calendar
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase (shared utility)
 * 2. Open Browserbase session URL in browser (shared utility)
 * 3. Navigate to MSG calendar page
 * 4. Scroll to bottom to trigger lazy loading (shared utility)
 * 5. Click "Load More Events" button multiple times (shared utility with MSG-specific config)
 * 6. Extract all visible events (shared utility with error handling)
 * 7. Log results (shared utility)
 * 8. Save to database and run tests (shared utility)
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeMSGCalendar() {
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

    // Step 1: Navigate to the MSG calendar page
    // Wait for network idle to ensure page is fully loaded
    await page.goto("https://www.msg.com/calendar?venues=KovZpZA7AAEA");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Scroll to the bottom using shared utility function
    // This triggers any lazy-loaded content on the page
    // Shared utility ensures minimum wait time (2000ms) for content to load
    await scrollToBottom(page);
    
    // Step 3: Click "Load More Events" button repeatedly until it disappears
    // Using shared utility function with MSG-specific configuration:
    // - Maximum 3 clicks (MSG typically has only a few batches)
    // - Scroll after each click to trigger additional lazy loading
    // - Custom wait times optimized for MSG's page behavior
    // This is MSG-specific logic different from other scrapers
    await clickButtonUntilGone(page, "Load More Events", 3, {
      scrollAfterClick: true,
      scrollWaitTime: 1000,
      loadWaitTime: 2000
    });
    
    // Step 4: Extract all visible events using shared utility function
    // The extraction instruction tells Stagehand exactly what to extract
    // The schema validates the extracted data structure
    // The sourceName is used for error reporting and test file naming
    // The shared utility automatically captures a screenshot if extraction fails
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from the MSG calendar page. For each event, get the event name (as eventName), date (as eventDate), time (as eventTime, if available), description (as eventDescription, if available), location (as eventLocation - set to 'Madison Square Garden' for all events), and the FULL URL (as eventUrl) from the href attribute of the 'View Event Details' link or the event card link by clicking on it. Extract the complete URL starting with https://www.msg.com/events-tickets/",
      StandardEventSchema,
      { sourceName: 'msg_calendar' }
    );

    // Backup: Add hardcoded venue name to all events
    // This ensures eventLocation is set even if schema default fails
    // This is scraper-specific logic, not shared utility
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "Madison Square Garden"
    }));

    // Log scraping results using shared utility function
    // This logs total events, events with/without times, and sample events
    // No need to manually count or format - the shared utility handles it
    logScrapingResults(eventsWithLocation, 'MSG Calendar');
    
    // Save to database and run tests using shared utility function
    // This shared utility:
    // 1. Creates a temporary JSON file
    // 2. Calls the Python import script
    // 3. Runs scraper consistency tests
    // 4. Cleans up the temporary file
    // All error handling is built-in
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'msg_calendar');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    // Handle errors using shared utility function
    // This captures a screenshot for debugging and re-throws the error
    await handleScraperError(error, page, 'MSG Calendar');
  } finally {
    // Always close Stagehand session to clean up browser resources
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeMSGCalendar().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeMSGCalendar;
