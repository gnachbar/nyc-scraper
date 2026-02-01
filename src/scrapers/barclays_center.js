import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom, capturePageScreenshot } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { extractEventTimesWithPython } from '../lib/extract-event-times-python.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with Barclays Center default location
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Barclays Center' });

// Check if browser session is still healthy
async function isSessionHealthy(page) {
  try {
    await page.evaluate(() => document.title);
    return true;
  } catch (e) {
    console.log('⚠️ Session health check failed:', e.message);
    return false;
  }
}

// Click "View more events" with resilience - returns number of successful clicks
async function clickViewMoreWithResilience(page, maxClicks = 25) {
  let clickCount = 0;

  for (let i = 0; i < maxClicks; i++) {
    try {
      // Check session health before each click
      if (!await isSessionHealthy(page)) {
        console.log(`⚠️ Session unhealthy after ${clickCount} clicks, stopping pagination`);
        break;
      }

      // Look for the "View more events" button (case-insensitive)
      const button = await page.$('text=/view more events/i');
      if (!button) {
        console.log(`✓ No more "View more events" button found after ${clickCount} clicks`);
        break;
      }

      // Click with timeout protection
      await Promise.race([
        button.click(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Click timeout')), 10000))
      ]);

      clickCount++;
      console.log(`Clicked "View more events" (${clickCount}/${maxClicks})`);

      // Wait for content to load
      await page.waitForTimeout(2500);

      // Scroll to ensure new content is visible
      await page.evaluate(() => window.scrollBy(0, 500));
      await page.waitForTimeout(1000);

    } catch (error) {
      if (error.message.includes('closed') || error.message.includes('Target')) {
        console.log(`⚠️ Browser session closed after ${clickCount} clicks: ${error.message}`);
        break;
      }
      console.log(`Click attempt ${i + 1} failed: ${error.message}`);
      // Try to continue if it's not a session-closed error
      await page.waitForTimeout(2000);
    }
  }

  return clickCount;
}

export async function scrapeBarclaysCenter() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;
  let allEvents = [];

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the events page with retry and extended timeout
    let navigationSuccess = false;
    for (let attempt = 1; attempt <= 3 && !navigationSuccess; attempt++) {
      try {
        console.log(`Navigation attempt ${attempt}/3...`);
        await page.goto("https://www.barclayscenter.com/events", {
          timeout: 60000,
          waitUntil: "domcontentloaded"
        });
        navigationSuccess = true;
        console.log("Navigation successful!");
      } catch (navError) {
        console.log(`Navigation attempt ${attempt} failed: ${navError.message}`);
        if (attempt === 3) throw navError;
        await page.waitForTimeout(5000); // Wait before retry
      }
    }
    await page.waitForTimeout(3000); // Extra wait for JS to execute

    // Step 2: Scroll to the bottom initially
    await scrollToBottom(page);

    // Step 3: Click "View more events" with resilience
    // Extract in batches to avoid losing all data if session dies
    const CLICKS_PER_BATCH = 5;
    let totalClicks = 0;
    const MAX_TOTAL_CLICKS = 25;

    while (totalClicks < MAX_TOTAL_CLICKS) {
      // Click a batch of times
      const clicksThisBatch = await clickViewMoreWithResilience(page, CLICKS_PER_BATCH);
      totalClicks += clicksThisBatch;

      // If we couldn't click any more, we're done with pagination
      if (clicksThisBatch < CLICKS_PER_BATCH) {
        console.log(`Pagination complete after ${totalClicks} total clicks`);
        break;
      }

      // Check session health before continuing
      if (!await isSessionHealthy(page)) {
        console.log(`Session died after ${totalClicks} clicks, proceeding with extraction`);
        break;
      }

      console.log(`Completed batch, ${totalClicks} total clicks so far...`);
    }

    // Take screenshot for visual verification before extraction
    try {
      await capturePageScreenshot(page, 'barclays_center');
    } catch (e) {
      console.log('Screenshot capture failed:', e.message);
    }

    // Step 4: Extract all events from the page (if session still healthy)
    if (await isSessionHealthy(page)) {
      const result = await extractEventsFromPage(
        page,
        "Extract all visible events. For each event, get the event name, date, description (if visible), and extract the href attribute from the event link (NOT the 'Buy Tickets' button link) to get the event page URL. Make sure to extract the full absolute URL. Set eventLocation to 'Barclays Center' for all events. The event time is not visible on the listing page - return an empty string for eventTime as it will be extracted from individual pages later. If description is not visible, return an empty string for eventDescription.",
        StandardEventSchema,
        { sourceName: 'barclays_center' }
      );

      // Add hardcoded venue name to all events and ensure URLs are absolute
      allEvents = result.events.map(event => {
        // Convert relative URLs to absolute URLs
        let eventUrl = event.eventUrl || '';
        if (eventUrl && !eventUrl.startsWith('http://') && !eventUrl.startsWith('https://')) {
          eventUrl = `https://www.barclayscenter.com${eventUrl.startsWith('/') ? eventUrl : '/' + eventUrl}`;
        }
        // Fallback URL if extraction failed
        if (!eventUrl) {
          eventUrl = 'https://www.barclayscenter.com/events';
        }

        return {
          ...event,
          eventUrl: eventUrl,
          eventLocation: "Barclays Center"
        };
      });

      console.log(`Extracted ${allEvents.length} events from page`);
    } else {
      console.log('⚠️ Session unhealthy, skipping extraction');
    }

    // Extract event times from individual event pages using Python
    if (allEvents.length > 0) {
      allEvents = await extractEventTimesWithPython(allEvents, {
        workers: 10,
        rateLimit: 1.0
      });
    }

    // Log results
    logScrapingResults(allEvents, 'Barclays Center');

    // Save to database and run tests
    if (allEvents.length > 0) {
      await saveEventsToDatabase(allEvents, 'barclays_center');
    } else {
      console.log("No events found!");
    }

    return { events: allEvents };

  } catch (error) {
    // Even on error, try to save any partial results
    if (allEvents.length > 0) {
      console.log(`⚠️ Error occurred but saving ${allEvents.length} partial events`);
      try {
        await saveEventsToDatabase(allEvents, 'barclays_center');
      } catch (saveError) {
        console.log('Failed to save partial results:', saveError.message);
      }
    }
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

