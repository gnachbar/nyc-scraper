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
      "Extract all events from the UPCOMING section only. Do not extract events from the PAST EVENTS section. For each event, get the event name (eventName), date (eventDate), time (eventTime, if available otherwise empty string), description (eventDescription, if available otherwise empty string), set eventLocation to 'Farm.One' for all events. IMPORTANT: For eventUrl, look for any link/href on the event card - this could be a 'More info' button, 'BOOK' button, or the event title itself. Extract the full URL from the href attribute. If no URL is found, use the base page URL 'https://www.farm.one/farm-one-events'.",
      StandardEventSchema,
      { sourceName: 'farm_one' }
    );

    // Add hardcoded venue name to all events and normalize URLs
    const eventsWithLocation = result.events.map(event => {
      // Normalize URL - convert relative to absolute or use default
      let eventUrl = event.eventUrl || "";
      if (!eventUrl || eventUrl.trim() === "") {
        eventUrl = "https://www.farm.one/farm-one-events";
      } else if (!eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
        if (eventUrl.startsWith('/')) {
          eventUrl = `https://www.farm.one${eventUrl}`;
        } else {
          eventUrl = `https://www.farm.one/${eventUrl}`;
        }
      }

      return {
        ...event,
        eventUrl: eventUrl,
        eventLocation: "Farm.One"
      };
    });

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

