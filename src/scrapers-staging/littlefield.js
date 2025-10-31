/**
 * Littlefield Scraper
 * 
 * Scrapes event listings from Littlefield NYC
 * URL: https://littlefieldnyc.com/all-shows/
 * 
 * Key Features:
 * - Single-venue scraper (hardcodes 'Littlefield' as eventLocation)
 * - Uses shared utility functions from src/lib/
 * - Simple single-page scraper with scroll to load all content
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

/**
 * Create standardized event schema with venue default for single-venue scraper
 * The schema will automatically set eventLocation to 'Littlefield' for all events
 */
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Littlefield' });

/**
 * Main scraper function for Littlefield
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase
 * 2. Open Browserbase session URL in browser
 * 3. Navigate to Littlefield all-shows page
 * 4. Scroll to bottom to trigger lazy loading (if any)
 * 5. Extract all visible events
 * 6. Log results and save to database
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeLittlefield() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session URL in default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to Littlefield all-shows page
    await page.goto("https://littlefieldnyc.com/all-shows/");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Scroll to bottom to ensure all events are loaded
    // Scroll multiple times with waiting to trigger any lazy loading
    console.log("Scrolling to bottom to load all events...");
    let previousHeight = 0;
    let currentHeight = await page.evaluate(() => document.body.scrollHeight);
    let scrollAttempts = 0;
    const maxScrollAttempts = 5;
    
    while (previousHeight !== currentHeight && scrollAttempts < maxScrollAttempts) {
      console.log(`Scroll attempt ${scrollAttempts + 1}/${maxScrollAttempts}`);
      previousHeight = currentHeight;
      
      // Scroll to bottom
      await scrollToBottom(page, 2000); // Wait 2 seconds for content to load
      
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
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from the Littlefield all-shows page. For each event, get the event name (as eventName), date (as eventDate - MUST include full year like 'Wednesday, October 29, 2025' - if you see 'WED OCT 29' you need to convert it to 'Wednesday, October 29, 2025' by adding the current year 2025), time (as eventTime - extract just the time like '8:00 PM' from patterns like 'SHOW: 8:00 PM' or 'Doors: 7:00 pm | Show: 8:00 pm'), set eventLocation to 'Littlefield' for all events, and extract the complete URL (as eventUrl) to the event details page by finding the link or 'GET TICKETS' button on each event card.",
      StandardEventSchema,
      { sourceName: 'littlefield' }
    );

    // Backup: Add hardcoded venue name to all events
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "Littlefield"
    }));

    // Log scraping results
    logScrapingResults(eventsWithLocation, 'Littlefield');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'littlefield');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Littlefield');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeLittlefield().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeLittlefield;

