/**
 * The Shed Scraper
 *
 * Scrapes event listings from The Shed
 * URL: https://theshed.org/program
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, clickButtonUntilGone, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'The Shed' });

export async function scrapeTheShed() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://theshed.org/program", {
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
      "Extract all visible events/programs. For each event, get the event name, date range (e.g., 'Jan 9 - Mar 1'), and the event URL (must be a valid https URL). Set eventLocation to 'The Shed' for all events.",
      StandardEventSchema,
      { sourceName: 'the_shed' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "The Shed"
    }));

    // Visit individual event pages to extract times (The Shed doesn't show times on listing)
    console.log("Extracting times from individual event pages...");
    events = await extractEventTimesFromPages(stagehand, events, {
      timeout: 30000,
      delay: 1000,
      useNetworkIdle: false,
      domWaitMs: 3000
    });

    logScrapingResults(events, 'The Shed');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'the_shed');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'The Shed');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeTheShed().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeTheShed;
