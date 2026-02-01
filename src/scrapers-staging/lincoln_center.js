/**
 * Lincoln Center Scraper
 *
 * Scrapes event listings from Lincoln Center
 * URL: https://www.lincolncenter.org/calendar
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage, clickButtonUntilGone } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Lincoln Center' });

export async function scrapeLincolnCenter() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.lincolncenter.org/calendar", {
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
      "Extract all visible events. For each event, get the event name, date, time, venue/location within Lincoln Center if shown, description if visible, and the event URL. Include the specific venue name (e.g., David Geffen Hall, Alice Tully Hall) in eventLocation if visible, otherwise use 'Lincoln Center'.",
      StandardEventSchema,
      { sourceName: 'lincoln_center' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: event.eventLocation || "Lincoln Center"
    }));

    logScrapingResults(events, 'Lincoln Center');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'lincoln_center');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Lincoln Center');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeLincolnCenter().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeLincolnCenter;
