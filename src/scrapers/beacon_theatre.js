/**
 * Beacon Theatre Scraper
 *
 * Scrapes event listings from Beacon Theatre (MSG venue)
 * URL: https://www.msg.com/beacon-theatre
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, clickButtonUntilGone } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Beacon Theatre' });

export async function scrapeBeaconTheatre() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Navigate to Beacon Theatre page
    await page.goto("https://www.msg.com/beacon-theatre", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    // Scroll to load events
    await scrollToBottom(page);

    // Click "Load More" or "See More" if available
    await clickButtonUntilGone(page, "Load More", 10, {
      scrollAfterClick: true,
      loadWaitTime: 2000
    });

    // Extract events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events/shows. For each event, get the event name, date, time, description if visible, and the event URL. Set eventLocation to 'Beacon Theatre' for all events.",
      StandardEventSchema,
      { sourceName: 'beacon_theatre' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Beacon Theatre"
    }));

    logScrapingResults(events, 'Beacon Theatre');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'beacon_theatre');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Beacon Theatre');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBeaconTheatre().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeBeaconTheatre;
