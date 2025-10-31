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
import { z } from 'zod';
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

/**
 * Create standardized event schema with venue default for single-venue scraper
 * We'll make eventUrl a plain string to handle invalid/missing URLs gracefully
 */
const StandardEventSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().default(""),
    eventUrl: z.string(), // Plain string to handle any format
    eventLocation: z.string().default("Littlefield")
  }))
});

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
      "Extract all visible events from the Littlefield all-shows page. For each event, get the event name (as eventName), date (as eventDate - MUST include full year like 'Wednesday, October 29, 2025' - if you see 'WED OCT 29' you need to convert it to 'Wednesday, October 29, 2025' by adding the current year 2025), time (as eventTime - extract just the time like '8:00 PM' from patterns like 'SHOW: 8:00 PM' or 'Doors: 7:00 pm | Show: 8:00 pm'), description (as eventDescription, if available), set eventLocation to 'Littlefield' for all events, and extract the complete URL (as eventUrl) from the href attribute of the 'GET TICKETS' button or link. Look for the href attribute on the link/button element and extract the full URL. The URL format should be like 'https://littlefieldnyc.com/event/?wfea_eb_id=...' or similar full URLs. If description is not visible, return an empty string for eventDescription.",
      StandardEventSchema,
      { sourceName: 'littlefield' }
    );

    // Backup: Add hardcoded venue name to all events and clean up URLs
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "Littlefield",
      // Clean up URLs - remove the invalid "?wfea_eb_id=0-" prefix or set fallback
      eventUrl: event.eventUrl && !event.eventUrl.includes('?wfea_eb_id=0-') ? event.eventUrl : "https://littlefieldnyc.com/all-shows/"
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

