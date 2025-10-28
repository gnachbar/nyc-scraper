import { initStagehand, openBrowserbaseSession, createStandardSchema } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with venue default for single-venue scraper
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Farm.One' });

export async function scrapeFarmOne() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the page
    await page.goto("https://www.farm.one/farm-one-events");
    // Farm.One has continuous network activity, so use fixed timeout instead of networkidle
    await page.waitForTimeout(3000);
    
    // Step 2: Extract all visible events from UPCOMING section only
    const result = await extractEventsFromPage(
      page,
      "Extract all events from the UPCOMING section only. Do not extract events from the PAST EVENTS section. For each event, get the event name, date, time (if available), set eventLocation to 'Farm.One' for all events, and the URL to the event details page. Look for the 'More info' or 'BOOK' links to get the event page URL.",
      StandardEventSchema,
      { sourceName: 'farm_one' }
    );

    // Add hardcoded venue name to all events (backup in case schema default fails)
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "Farm.One"
    }));

    // Log results
    logScrapingResults(eventsWithLocation, 'Farm.One');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'farm_one');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Farm.One');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeFarmOne().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeFarmOne;

