import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { extractEventTimesWithPython } from '../lib/extract-event-times-python.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Union Hall default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Union Hall' });

export async function scrapeUnionHall() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the calendar page
    await page.goto("https://unionhallny.com/calendar");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Scroll to the bottom repeatedly to load all events
    // Events auto-load when scrolling, so we'll scroll multiple times
    console.log("Starting to scroll and load events...");
    
    let previousEventCount = 0;
    let currentEventCount = 0;
    const maxScrollAttempts = 15; // Maximum number of scroll attempts
    let scrollAttempt = 0;
    
    for (scrollAttempt = 0; scrollAttempt < maxScrollAttempts; scrollAttempt++) {
      console.log(`Scroll attempt ${scrollAttempt + 1}/${maxScrollAttempts}...`);
      
      // Scroll to bottom
      await scrollToBottom(page, 3000); // Wait 3 seconds after each scroll
      
      // Wait for network to be idle after scrolling
      await page.waitForLoadState('networkidle');
      
      // Try to count events on the page to see if more loaded
      try {
        // This is a rough check - we'll do the full extraction later
        const checkResult = await page.evaluate(() => {
          // Count elements that look like event containers
          const events = document.querySelectorAll('[class*="event"], [class*="Event"], .calendar-item, [data-event]');
          return events.length;
        });
        
        currentEventCount = checkResult || 0;
        console.log(`  Current event count: ${currentEventCount}`);
        
        // If no new events loaded in the last scroll, we're probably done
        if (currentEventCount > 0 && currentEventCount === previousEventCount) {
          console.log(`No new events loaded. Stopping scroll attempts.`);
          break;
        }
        
        previousEventCount = currentEventCount;
        
      } catch (error) {
        console.log(`  Could not count events: ${error.message}`);
        // Continue anyway
      }
      
      // Additional wait between scrolls
      await page.waitForTimeout(2000);
    }
    
    console.log(`Completed ${scrollAttempt + 1} scroll attempts. Proceeding to extraction...`);
    
    // Step 3: Extract all visible events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from the calendar. For each event, get the event name/title, the date (like 'Oct 28', 'Nov 01', etc.), set eventLocation to 'Union Hall' for all events, and get the event URL by finding the link to the event detail page. Do not try to extract event time from this page - leave eventTime as empty string.",
      StandardEventSchema,
      { sourceName: 'union_hall' }
    );

    // Add hardcoded venue name and ensure URLs are absolute
    let eventsWithLocation = result.events.map(event => {
      // Convert relative URLs to absolute URLs
      let eventUrl = event.eventUrl;
      if (!eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
        eventUrl = `https://unionhallny.com${eventUrl.startsWith('/') ? eventUrl : '/' + eventUrl}`;
      }
      
      return {
        ...event,
        eventUrl: eventUrl,
        eventLocation: "Union Hall" // Hardcoded venue name
      };
    });

    console.log(`Successfully extracted ${eventsWithLocation.length} events from main calendar`);

    // Step 4: Extract event times from individual event pages using Python
    if (eventsWithLocation.length > 0) {
      eventsWithLocation = await extractEventTimesWithPython(eventsWithLocation, {
        workers: 10,
        rateLimit: 1.0
      });
    }

    // Log results
    logScrapingResults(eventsWithLocation, 'Union Hall');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'union_hall');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Union Hall');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeUnionHall().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeUnionHall;

