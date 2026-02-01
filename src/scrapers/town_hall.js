/**
 * Town Hall Scraper
 *
 * Scrapes event listings from The Town Hall
 * URL: https://www.thetownhall.org/events
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Town Hall' });

export async function scrapeTownHall() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.thetownhall.org/events", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events and shows. For each event, get the event name, date, time, description if visible, and the event URL. Set eventLocation to 'Town Hall' for all events.",
      StandardEventSchema,
      { sourceName: 'town_hall' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Town Hall"
    }));

    logScrapingResults(events, 'Town Hall');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'town_hall');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Town Hall');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeTownHall().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeTownHall;
