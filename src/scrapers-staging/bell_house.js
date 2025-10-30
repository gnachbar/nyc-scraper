/**
 * The Bell House Scraper
 * 
 * Scrapes event listings from The Bell House (Live Nation venue)
 * URL: https://www.thebellhouseny.com/shows
 * 
 * Key Features:
 * - Single-venue scraper (hardcodes 'The Bell House' as eventLocation)
 * - Live Nation website with dynamic content loading
 * - Uses shared utility functions from src/lib/
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

/**
 * Create standardized event schema with venue default for single-venue scraper
 * The schema will automatically set eventLocation to 'The Bell House' for all events
 */
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'The Bell House' });

/**
 * Main scraper function for The Bell House
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase
 * 2. Open Browserbase session URL in browser
 * 3. Navigate to The Bell House shows page
 * 4. Scroll repeatedly to bottom until all events auto-load
 * 5. Extract all visible events (including URLs if possible)
 * 6. Log results and save to database
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeBellHouse() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session URL in default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to The Bell House shows page
    await page.goto("https://www.thebellhouseny.com/shows");
    // Note: networkidle times out on this site (continuous network activity)
    // Using timeout instead for initial page load
    await page.waitForTimeout(5000); // Wait 5 seconds for initial load
    
    // Step 2: Scroll repeatedly to bottom until all events auto-load
    // Events load automatically when scrolling to bottom
    console.log("Scrolling to load all events...");
    let previousHeight = 0;
    let currentHeight = await page.evaluate(() => document.body.scrollHeight);
    let scrollAttempts = 0;
    const maxScrollAttempts = 10;
    
    while (previousHeight !== currentHeight && scrollAttempts < maxScrollAttempts) {
      console.log(`Scroll attempt ${scrollAttempts + 1}/${maxScrollAttempts}`);
      previousHeight = currentHeight;
      
      // Scroll to bottom
      await scrollToBottom(page, 3000); // Wait 3 seconds for content to load
      
      // Get new height after content loads
      currentHeight = await page.evaluate(() => document.body.scrollHeight);
      scrollAttempts++;
      
      if (previousHeight === currentHeight) {
        console.log("No new content loaded - all events loaded");
        break;
      }
    }
    
    console.log(`Completed ${scrollAttempts} scroll attempts`);
    
    // Step 3: Extract all visible events
    // Note: URL extraction may not be possible depending on site structure
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from The Bell House shows page. For each event, get the event name (as eventName), date (as eventDate - include the full year like 'Friday, November 15, 2025'), time (as eventTime, if available like '8:00 PM'), set eventLocation to 'The Bell House' for all events, and try to extract the complete URL (as eventUrl) to the event details page by finding the link on each event card. If URL cannot be determined, use the base URL 'https://www.thebellhouseny.com/shows'",
      StandardEventSchema,
      { sourceName: 'bell_house' }
    );

    // Backup: Add hardcoded venue name to all events
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "The Bell House"
    }));

    // Log scraping results
    logScrapingResults(eventsWithLocation, 'The Bell House');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'bell_house');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'The Bell House');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBellHouse().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeBellHouse;

