/**
 * Greenwich House Theatre Scraper
 *
 * Scrapes event listings from Greenwich House Theatre
 * URL: https://www.greenwichhouse.org/arts/theatre/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Greenwich House Theatre' });

export async function scrapeGreenwichHouse() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.greenwichhouse.org/arts/theatre/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible shows and events. For each event, get the show name, dates, times, description if visible, and the event URL. Set eventLocation to 'Greenwich House Theatre' for all events.",
      StandardEventSchema,
      { sourceName: 'greenwich_house' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Greenwich House Theatre"
    }));

    logScrapingResults(events, 'Greenwich House Theatre');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'greenwich_house');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Greenwich House Theatre');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeGreenwichHouse().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeGreenwichHouse;
