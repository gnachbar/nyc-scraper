import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
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
    await page.goto("https://www.brooklynmuseum.org/programs");
    console.log("Navigated to Brooklyn Museum programs page");
    
    // Wait for page to load
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000); // Additional wait for dynamic content
    console.log("Page loaded");

    // Step 2: Click "Show more events" until the button is no longer there (unique Brooklyn Museum logic)
    // Note: Brooklyn Museum uses either "Show more events" or "Show more" button text
    // We need to handle both variants, so we'll use a more flexible approach
    let showMoreClicks = 0;
    const maxShowMoreClicks = 20;
    
    for (let i = 0; i < maxShowMoreClicks; i++) {
      try {
        console.log(`Attempting to click "Show more events" (attempt ${i + 1}/${maxShowMoreClicks})`);
        
        // Look for either button variant
        const [showMoreAction] = await page.observe("click the 'Show more events' button or 'Show more' button");
        
        if (showMoreAction) {
          await page.act(showMoreAction);
          showMoreClicks++;
          console.log(`Successfully clicked "Show more events" (${showMoreClicks}/${maxShowMoreClicks})`);
          
          // Wait for new content to load
          await page.waitForLoadState('networkidle');
          await page.waitForTimeout(2000);
          
          // Scroll to bottom again to trigger any additional lazy loading
          await scrollToBottom(page, 1000);
        } else {
          console.log("No 'Show more events' button found. All events may be loaded.");
          break;
        }
      } catch (error) {
        console.log(`Failed to click "Show more events" on attempt ${i + 1}: ${error.message}`);
        break;
      }
    }
    
    console.log(`Total "Show more events" clicks: ${showMoreClicks}`);

    // Step 3: Extract all visible events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from the Brooklyn Museum programs page. For each event, get the event name (as eventName), date (as eventDate), time (as eventTime, if available), description (as eventDescription, if available), location (as eventLocation - set to 'Brooklyn Museum' for all events), and the URL (as eventUrl) from the actual href attribute of the event link element. Do NOT construct URLs from event names. Extract the real href value from the HTML. If the href is relative (starts with /), prepend 'https://www.brooklynmuseum.org' to make it absolute. If description is not visible, return an empty string for eventDescription.",
      StandardEventSchema,
      { sourceName: 'brooklyn_museum' }
    );

    // Add hardcoded venue name to all events
    const eventsWithLocation = result.events.map(event => ({
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

