/**
 * Jazz at Lincoln Center Scraper
 *
 * Scrapes event listings from Jazz at Lincoln Center
 * URL: https://jazz.org/concerts/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Jazz at Lincoln Center' });

export async function scrapeJazzLincolnCenter() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://jazz.org/concerts/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible concerts and events. For each event, get the event/artist name, date, time, venue within Jazz at Lincoln Center (Rose Theater, Appel Room, Dizzy's Club) if shown, and the event URL (the actual href link starting with https://jazz.org/). Set eventLocation to include the specific venue if visible.",
      StandardEventSchema,
      { sourceName: 'jazz_lincoln_center' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: event.eventLocation || "Jazz at Lincoln Center"
    }));

    // Extract times from individual event pages
    console.log("Extracting times from individual event pages...");
    events = await extractEventTimesFromPages(stagehand, events, {
      timeout: 30000,
      delay: 1000,
      useNetworkIdle: false,
      domWaitMs: 3000
    });

    logScrapingResults(events, 'Jazz at Lincoln Center');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'jazz_lincoln_center');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Jazz at Lincoln Center');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeJazzLincolnCenter().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeJazzLincolnCenter;
