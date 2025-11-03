import { initStagehand, openBrowserbaseSession, createStandardSchema } from '../lib/scraper-utils.js';
import { paginateThroughPages, extractEventsFromPage, filterDuplicateEvents } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Brooklyn Public Library default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Brooklyn Public Library' });

export async function scrapeBrooklynLibrary() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the Brooklyn Public Library BPL Presents events page
    await page.goto("https://discover.bklynlibrary.org/?event=true&eventtags=BPL+Presents");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Paginate through pages and extract events with duplicate detection
    const allEvents = [];
    const seenEventUrls = new Set();
    let pageCount = 0;
    const maxPages = 5; // Limit to 5 pages (website typically has 2 pages)
    
    while (pageCount < maxPages) {
      console.log(`Extracting events from page ${pageCount + 1}/${maxPages}...`);
      
      const result = await extractEventsFromPage(
        page,
        "Extract all visible events on the current page. For each event, get the event name (as eventName), date with full year (as eventDate - must include year like 'Mon, Nov 24, 2025'), time (as eventTime, if available), description (as eventDescription, if available), set eventLocation to 'Brooklyn Public Library' for all events, and the full absolute URL (as eventUrl) by clicking on the event name or event link to get the complete event page URL starting with 'https://'. If no time is visible on the page, return an empty string for eventTime. If description is not visible, return an empty string for eventDescription.",
        StandardEventSchema,
        { sourceName: 'brooklyn_library' }
      );
      
      // Check for duplicates - if all events are duplicates, we've reached the end
      const { newEvents, newEventsCount } = filterDuplicateEvents(result.events, seenEventUrls);
      
      allEvents.push(...newEvents);
      console.log(`Found ${result.events.length} events on page ${pageCount + 1}, ${newEventsCount} new events`);
      
      // If no new events found, we've likely reached the end
      if (newEventsCount === 0 && pageCount > 0) {
        console.log("No new events found - reached end of pagination");
        break;
      }
      
      // Try to click next button
      try {
        const [nextAction] = await page.observe(`click the 'right arrow button' or 'next page' button, but only if it is enabled and not disabled`);
        
        if (nextAction) {
          await page.act(nextAction);
          pageCount++;
          console.log(`Successfully clicked next button (${pageCount}/${maxPages})`);
          
          // Wait for new content to load
          await page.waitForLoadState('domcontentloaded');
          await page.waitForTimeout(3000);
        } else {
          console.log(`No enabled next button found. All pages processed.`);
          break;
        }
      } catch (error) {
        console.log(`Failed to click next button: ${error.message}`);
        console.log("Reached end of pagination");
        break;
      }
    }
    
    console.log(`Total pages processed: ${pageCount + 1}`);
    console.log(`Total unique events found: ${allEvents.length}`);

    // Add hardcoded venue name and fix URLs to be absolute
    const eventsWithLocation = allEvents.map(event => {
      let eventUrl = event.eventUrl;
      // Convert relative URLs to absolute
      if (eventUrl && !eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
        // If URL is just a number or ID, construct full URL
        if (/^\d+$/.test(eventUrl) || eventUrl.startsWith('0-')) {
          eventUrl = `https://discover.bklynlibrary.org/event/${eventUrl}`;
        } else {
          eventUrl = `https://discover.bklynlibrary.org${eventUrl.startsWith('/') ? eventUrl : '/' + eventUrl}`;
        }
      }
      
      return {
        ...event,
        eventUrl: eventUrl,
        eventLocation: "Brooklyn Public Library"
      };
    });

    // Log results
    logScrapingResults(eventsWithLocation, 'Brooklyn Public Library');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'brooklyn_library');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Brooklyn Public Library');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBrooklynLibrary().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeBrooklynLibrary;

