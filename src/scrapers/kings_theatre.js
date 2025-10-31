import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { extractEventTimesWithPython } from '../lib/extract-event-times-python.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Kings Theatre default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Kings Theatre' });

export async function scrapeKingsTheatre() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Open the web page
    await page.goto("https://www.kingstheatre.com/events/");
    
    // Step 2: Scroll to the bottom
    await scrollToBottom(page);
    
    // Step 3 & 4: Click Show More and continue until no more button
    await clickButtonUntilGone(page, "Show more", 20, {
      scrollAfterClick: true,
      scrollWaitTime: 1000,
      loadWaitTime: 2500
    });
    
    // Step 5: Extract the required data for all events on the page
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, description (if visible), and the URL by clicking on the 'See more' button (NOT the 'Buy tickets' button) to get the event page URL. Set eventLocation to 'Kings Theatre' for all events. If time is visible on the listing, include it as eventTime. If no time is visible, return an empty string for eventTime. If description is not visible, return an empty string for eventDescription.",
      StandardEventSchema,
      { sourceName: 'kings_theatre' }
    );

    // Add hardcoded venue name to all events and ensure URLs are absolute
    let eventsWithLocation = result.events.map(event => {
      // Convert relative URLs to absolute URLs
      let eventUrl = event.eventUrl;
      if (!eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
        eventUrl = `https://www.kingstheatre.com${eventUrl.startsWith('/') ? eventUrl : '/' + eventUrl}`;
      }
      
      return {
        ...event,
        eventUrl: eventUrl,
        eventLocation: "Kings Theatre" // Hardcoded venue name
      };
    });

    // Step 6: Extract event times from individual event pages using Python
    eventsWithLocation = await extractEventTimesWithPython(eventsWithLocation, {
      workers: 10,
      rateLimit: 1.0
    });

    // Log results
    logScrapingResults(eventsWithLocation, 'Kings Theatre');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'kings_theatre');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Kings Theatre');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeKingsTheatre().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeKingsTheatre;
