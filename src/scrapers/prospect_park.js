import { initStagehand, openBrowserbaseSession, createStandardSchema } from '../lib/scraper-utils.js';
import { paginateThroughPages, extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema for Prospect Park events
const StandardEventSchema = createStandardSchema();

export async function scrapeProspectPark() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the Prospect Park events page
    await page.goto("https://www.prospectpark.org/events/");
    
    // Step 2: Paginate through pages and extract events
    const allEvents = await paginateThroughPages(
      page,
      async () => {
        return await extractEventsFromPage(
          page,
          "Extract all visible events on the current page. For each event, get the event name (as eventName), date (as eventDate), time (as eventTime, if available), subvenue/location (as eventLocation - this is the text below the event name like 'Grand Army Plaza', 'Prospect Park Zoo', etc.), and the URL (as eventUrl) by clicking on the event name to get the event page URL. If no time is visible on the page, return an empty string for eventTime.",
          StandardEventSchema,
          { sourceName: 'prospect_park' }
        );
      },
      10, // maxPages
      {
        nextButtonText: "Next events",
        pageWaitTime: 3000
      }
    );

    // Log results
    logScrapingResults(allEvents, 'Prospect Park');
    
    // Save to database and run tests
    if (allEvents.length > 0) {
      await saveEventsToDatabase(allEvents, 'prospect_park');
    } else {
      console.log("No events found!");
    }

    return { events: allEvents };

  } catch (error) {
    await handleScraperError(error, page, 'Prospect Park');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeProspectPark().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeProspectPark;
