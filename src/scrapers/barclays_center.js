import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { extractEventTimesWithPython } from '../lib/extract-event-times-python.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Barclays Center default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Barclays Center' });

export async function scrapeBarclaysCenter() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the events page
    await page.goto("https://www.barclayscenter.com/events");
    await page.waitForTimeout(3000); // Wait 3 seconds for initial load
    
    // Step 2: Scroll to the bottom
    await scrollToBottom(page);
    
    // Step 3: Click "View more events" until all events are loaded
    await clickButtonUntilGone(page, "View more events", 20, {
      scrollAfterClick: true,
      scrollWaitTime: 2000,
      loadWaitTime: 2500
    });
    
    // Step 4: Extract all events from the page
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, and extract the href attribute from the event link (NOT the 'Buy Tickets' button link) to get the event page URL. Make sure to extract the full absolute URL. Set eventLocation to 'Barclays Center' for all events. The event time is not visible on the listing page - return an empty string for eventTime as it will be extracted from individual pages later.",
      StandardEventSchema,
      { sourceName: 'barclays_center' }
    );

    // Add hardcoded venue name to all events and ensure URLs are absolute
    let eventsWithLocation = result.events.map(event => {
      // Convert relative URLs to absolute URLs
      let eventUrl = event.eventUrl;
      if (!eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
        eventUrl = `https://www.barclayscenter.com${eventUrl.startsWith('/') ? eventUrl : '/' + eventUrl}`;
      }
      
      return {
        ...event,
        eventUrl: eventUrl,
        eventLocation: "Barclays Center" // Hardcoded venue name
      };
    });

    // Extract event times from individual event pages using Python
    eventsWithLocation = await extractEventTimesWithPython(eventsWithLocation, {
      workers: 10,
      rateLimit: 1.0
    });

    // Log results
    logScrapingResults(eventsWithLocation, 'Barclays Center');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'barclays_center');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Barclays Center');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBarclaysCenter().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeBarclaysCenter;

