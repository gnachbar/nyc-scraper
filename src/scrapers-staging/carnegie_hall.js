/**
 * Carnegie Hall Scraper
 *
 * Scrapes event listings from Carnegie Hall
 * URL: https://www.carnegiehall.org/calendar
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, clickButtonUntilGone } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Carnegie Hall' });

export async function scrapeCarnegieHall() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.carnegiehall.org/calendar", {
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
      "Extract all visible events/concerts. For each event, get the event name, date, time, venue/hall name if shown (Stern Auditorium, Zankel Hall, Weill Recital Hall), description if visible, and the event URL. Include the specific hall in eventLocation if visible, otherwise use 'Carnegie Hall'.",
      StandardEventSchema,
      { sourceName: 'carnegie_hall' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: event.eventLocation || "Carnegie Hall"
    }));

    logScrapingResults(events, 'Carnegie Hall');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'carnegie_hall');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Carnegie Hall');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeCarnegieHall().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeCarnegieHall;
