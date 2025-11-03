import { initStagehand, openBrowserbaseSession, createStandardSchema } from '../lib/scraper-utils.js';
import { clickAndExtractIncrementally } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Brooklyn Museum default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Brooklyn Museum' });

export async function scrapeBrooklynMuseum() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    console.log("Starting Brooklyn Museum scraping...");

    // Step 1: Navigate to the Brooklyn Museum programs page
    await page.goto("https://www.brooklynmuseum.org/programs", { waitUntil: 'domcontentloaded' });
    console.log("Navigated to Brooklyn Museum programs page");
    console.log("Page loaded (using Browserbase recommended approach)");

    // Step 2: Click "Show more events" and extract incrementally
    // Note: Brooklyn Museum uses either "Show more events" or "Show more" button text
    // Brooklyn Museum has continuous network activity, so skip networkidle
    // Using incremental extraction to prevent losing work if extraction fails after many clicks
    const allEvents = await clickAndExtractIncrementally(
      page,
      "Show more events' button or 'Show more'",
      async () => {
        const result = await page.extract({
          instruction: "Extract all visible events from the Brooklyn Museum programs page. For each event, get the event name (as eventName), date (as eventDate), time (as eventTime, if available), description (as eventDescription, if available), location (as eventLocation - set to 'Brooklyn Museum' for all events), and the URL (as eventUrl) from the actual href attribute of the event link element. Do NOT construct URLs from event names. Extract the real href value from the HTML. If the href is relative (starts with /), prepend 'https://www.brooklynmuseum.org' to make it absolute. If description is not visible, return an empty string for eventDescription.",
          schema: StandardEventSchema
        });
        return result;
      },
      20, // maxClicks
      {
        scrollAfterClick: true,
        scrollWaitTime: 1000,
        loadWaitTime: 2000,
        skipNetworkIdle: true
      }
    );

    // Add hardcoded venue name to all events (backup in case schema default failed)
    const eventsWithLocation = allEvents.map(event => ({
      ...event,
      eventLocation: "Brooklyn Museum"
    }));

    // Log results
    logScrapingResults(eventsWithLocation, 'Brooklyn Museum');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'brooklyn_museum');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Brooklyn Museum');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBrooklynMuseum().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeBrooklynMuseum;

