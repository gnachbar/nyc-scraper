/**
 * Blue Note Jazz Club Scraper
 *
 * Scrapes event listings from Blue Note NYC
 * URL: https://www.bluenotejazz.com/nyc/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Blue Note' });

export async function scrapeBlueNote() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.bluenotejazz.com/nyc/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible jazz shows and events. For each event, get the artist/band name, date, show times (e.g., '8pm & 10:30pm'), description if visible, and the event URL (the actual href link starting with https://www.bluenotejazz.com/). Set eventLocation to 'Blue Note' for all events.",
      StandardEventSchema,
      { sourceName: 'blue_note' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Blue Note"
    }));

    // Extract times from individual event pages
    console.log("Extracting times from individual event pages...");
    events = await extractEventTimesFromPages(stagehand, events, {
      timeout: 30000,
      delay: 1000,
      useNetworkIdle: false,
      domWaitMs: 3000
    });

    logScrapingResults(events, 'Blue Note');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'blue_note');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Blue Note');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBlueNote().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeBlueNote;
