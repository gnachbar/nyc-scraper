/**
 * Village East Cinema (Angelika) Scraper
 *
 * Scrapes event listings from Village East Cinema
 * URL: https://www.villageeastcinema.com/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Village East Cinema' });

export async function scrapeVillageEast() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.villageeastcinema.com/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible movie screenings and special events, especially director talks and Q&A sessions. For each event, get the movie/event name, date, time, description if visible, and any special event details. Set eventLocation to 'Village East Cinema' for all events.",
      StandardEventSchema,
      { sourceName: 'village_east' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Village East Cinema"
    }));

    logScrapingResults(events, 'Village East Cinema');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'village_east');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Village East Cinema');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeVillageEast().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeVillageEast;
