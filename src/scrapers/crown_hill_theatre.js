import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Crown Hill Theatre default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Crown Hill Theatre' });

export async function scrapeCrownHillTheatre() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the calendar page
    await page.goto("https://crownhilltheatre.com/calendar");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Scroll to the bottom to ensure all content is loaded
    await scrollToBottom(page);
    
    // Step 3: Extract all visible events
    // All events are already visible on load, no pagination needed
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, description (if visible), and extract the href attribute from the 'Tickets' link (NOT the event name link) to get the event page URL. Make sure to extract the full absolute URL. Set eventLocation to 'Crown Hill Theatre' for all events. The event time is not visible on the listing page - return an empty string for eventTime as it will be extracted from individual pages later. If description is not visible, return an empty string for eventDescription.",
      StandardEventSchema,
      { sourceName: 'crown_hill_theatre' }
    );

    // Add hardcoded venue name to all events and ensure URLs are absolute
    let eventsWithLocation = result.events.map(event => {
      // Convert relative URLs to absolute URLs
      let eventUrl = event.eventUrl;
      if (!eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
        eventUrl = `https://crownhilltheatre.com${eventUrl.startsWith('/') ? eventUrl : '/' + eventUrl}`;
      }
      
      return {
        ...event,
        eventUrl: eventUrl,
        eventLocation: "Crown Hill Theatre" // Hardcoded venue name
      };
    });

    // Step 4: Skip time extraction - eventim.us ticketing pages are heavily protected
    // and don't allow automated access. Times are not available for this venue.
    console.log('Skipping time extraction - eventim.us pages are protected');

    // Log results
    logScrapingResults(eventsWithLocation, 'Crown Hill Theatre');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'crown_hill_theatre');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Crown Hill Theatre');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeCrownHillTheatre().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeCrownHillTheatre;

