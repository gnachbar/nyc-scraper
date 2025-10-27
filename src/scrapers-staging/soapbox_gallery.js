import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { extractEventTimesWithPython } from '../lib/extract-event-times-python.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Soapbox Gallery default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Soapbox Gallery' });

export async function scrapeSoapboxGallery() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Open the web page
    await page.goto("https://www.soapboxgallery.org/calendar");
    await page.waitForTimeout(5000); // Wait 5 seconds for initial load
    
    // Step 2: Scroll to the bottom to ensure all content is loaded
    await scrollToBottom(page);
    
    // Step 3: Extract the required data for all events on the page
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, and extract the FULL date including day name if available (e.g., 'Sunday, November 9, 2025' or 'Nov 9, 2025'). For the event URL, look for a clickable link associated with the event (often the event name or title itself) and get its href attribute to get the full event page URL. Make sure to extract the complete URL. Set eventLocation to 'Soapbox Gallery' for all events. The event time is not visible on the listing page - return an empty string for eventTime as it will be extracted from individual pages later.",
      StandardEventSchema,
      { sourceName: 'soapbox_gallery' }
    );

    // Add hardcoded venue name to all events and ensure URLs are absolute
    let eventsWithLocation = result.events.map(event => {
      // Convert relative URLs to absolute URLs
      let eventUrl = event.eventUrl;
      if (!eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
        eventUrl = `https://www.soapboxgallery.org${eventUrl.startsWith('/') ? eventUrl : '/' + eventUrl}`;
      }
      
      return {
        ...event,
        eventUrl: eventUrl,
        eventLocation: "Soapbox Gallery" // Hardcoded venue name
      };
    });

    // Step 4: Extract event times from individual event pages using Python
    eventsWithLocation = await extractEventTimesWithPython(eventsWithLocation, {
      workers: 10,
      rateLimit: 1.0
    });

    // Log results
    logScrapingResults(eventsWithLocation, 'Soapbox Gallery');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'soapbox_gallery');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Soapbox Gallery');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeSoapboxGallery().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeSoapboxGallery;

