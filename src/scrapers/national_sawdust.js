/**
 * National Sawdust Scraper
 *
 * Scrapes event listings from National Sawdust
 * URL: https://nationalsawdust.org/events/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'National Sawdust' });

export async function scrapeNationalSawdust() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Use /performances URL which has the actual event listings
    await page.goto("https://nationalsawdust.org/performances", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible concerts and performances. For each event, get the artist/event name, date, time (usually 7:30 PM or 8:00 PM format), description if visible, and the event URL (should start with /event/ or https://nationalsawdust.org/event/). Set eventLocation to 'National Sawdust' for all events.",
      StandardEventSchema,
      { sourceName: 'national_sawdust' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "National Sawdust",
      // Prepend base URL if relative
      eventUrl: event.eventUrl?.startsWith('/') ? `https://nationalsawdust.org${event.eventUrl}` : event.eventUrl
    }));

    // Extract times from individual event pages
    console.log("Extracting times from individual event pages...");
    events = await extractEventTimesFromPages(stagehand, events, {
      timeout: 30000,
      delay: 1000,
      useNetworkIdle: false,
      domWaitMs: 3000
    });

    logScrapingResults(events, 'National Sawdust');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'national_sawdust');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'National Sawdust');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeNationalSawdust().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeNationalSawdust;
