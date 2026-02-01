/**
 * Webster Hall Scraper
 *
 * Scrapes event listings from Webster Hall
 * URL: https://www.websterhall.com/events
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Webster Hall' });

export async function scrapeWebsterHall() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.websterhall.com/events", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events/concerts. For each event, get the artist/event name, date, time (doors/show time), description if visible, and the event URL. Set eventLocation to 'Webster Hall' for all events.",
      StandardEventSchema,
      { sourceName: 'webster_hall' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Webster Hall"
    }));

    logScrapingResults(events, 'Webster Hall');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'webster_hall');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Webster Hall');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeWebsterHall().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeWebsterHall;
