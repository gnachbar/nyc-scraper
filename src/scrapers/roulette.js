import { initStagehand, openBrowserbaseSession, createStandardSchema } from '../lib/scraper-utils.js';
import { paginateThroughPages, extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with venue default
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Roulette' });

export async function scrapeRoulette() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the calendar page
    await page.goto("https://roulette.org/calendar/");
    await page.waitForTimeout(3000); // Wait 3 seconds for initial load

    // Step 2: Extract events from all pages using pagination
    const allEvents = await paginateThroughPages(
      page,
      async () => {
        return await extractEventsFromPage(
          page,
          "Extract all visible events on the current page. For each event, get the event name, date, time (if available), and the event URL by extracting the href attribute from the event name link. Set eventLocation to 'Roulette' for all events. Make sure to extract the full absolute URL.",
          StandardEventSchema,
          { sourceName: 'roulette' }
        );
      },
      20, // maxPages - adjust if needed
      {
        nextButtonText: "next page",
        pageWaitTime: 3000
      }
    );

    // Add hardcoded venue name to all events (backup in case schema default fails)
    const eventsWithLocation = allEvents.map(event => ({
      ...event,
      eventLocation: "Roulette"
    }));

    // Log results
    logScrapingResults(eventsWithLocation, 'Roulette');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'roulette');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Roulette');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeRoulette().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeRoulette;

