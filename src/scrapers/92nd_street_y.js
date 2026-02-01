/**
 * 92nd Street Y Scraper
 *
 * Scrapes event listings from 92nd Street Y
 * URL: https://www.92ny.org/events
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, clickButtonUntilGone, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: '92nd Street Y' });

export async function scrape92ndStreetY() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.92ny.org/events", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);

    await clickButtonUntilGone(page, "Load More", 15, {
      scrollAfterClick: true,
      loadWaitTime: 2000
    });

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, and the event URL (must be a valid https URL). Set eventLocation to '92nd Street Y' for all events.",
      StandardEventSchema,
      { sourceName: '92nd_street_y' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "92nd Street Y"
    }));

    // Visit individual event pages to extract times (improves time extraction accuracy)
    console.log("Extracting times from individual event pages...");
    events = await extractEventTimesFromPages(stagehand, events, {
      timeout: 30000,
      delay: 1000,
      useNetworkIdle: false,
      domWaitMs: 3000
    });

    logScrapingResults(events, '92nd Street Y');

    if (events.length > 0) {
      await saveEventsToDatabase(events, '92nd_street_y');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, '92nd Street Y');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrape92ndStreetY().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrape92ndStreetY;
