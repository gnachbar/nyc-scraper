/**
 * Brooklyn Bridge Park Scraper
 *
 * Scrapes event listings from Brooklyn Bridge Park
 * URL: https://www.brooklynbridgepark.org/events/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, clickButtonUntilGone } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Brooklyn Bridge Park' });

export async function scrapeBrooklynBridgePark() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.brooklynbridgepark.org/events/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);

    await clickButtonUntilGone(page, "Load More", 10, {
      scrollAfterClick: true,
      loadWaitTime: 2000
    });

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, time, description if visible, and the event URL. Set eventLocation to 'Brooklyn Bridge Park' for all events.",
      StandardEventSchema,
      { sourceName: 'brooklyn_bridge_park' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Brooklyn Bridge Park"
    }));

    logScrapingResults(events, 'Brooklyn Bridge Park');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'brooklyn_bridge_park');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Brooklyn Bridge Park');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBrooklynBridgePark().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeBrooklynBridgePark;
