/**
 * Joe's Pub Scraper
 *
 * Scrapes event listings from Joe's Pub at The Public Theater
 * URL: https://publictheater.org/programs/joes-pub/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: "Joe's Pub" });

export async function scrapeJoesPub() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://publictheater.org/programs/joes-pub/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible shows and events at Joe's Pub. For each event, get the artist/show name, date, time, description if visible, and the event URL (the actual href link starting with https://publictheater.org/). Set eventLocation to \"Joe's Pub\" for all events.",
      StandardEventSchema,
      { sourceName: 'joes_pub' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Joe's Pub"
    }));

    // Extract times from individual event pages
    console.log("Extracting times from individual event pages...");
    events = await extractEventTimesFromPages(stagehand, events, {
      timeout: 30000,
      delay: 1000,
      useNetworkIdle: false,
      domWaitMs: 3000
    });

    logScrapingResults(events, "Joe's Pub");

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'joes_pub');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, "Joe's Pub");
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeJoesPub().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeJoesPub;
