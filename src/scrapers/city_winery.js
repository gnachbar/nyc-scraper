/**
 * City Winery NYC Scraper
 *
 * Scrapes event listings from City Winery New York
 * URL: https://citywinery.com/newyork/events
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'City Winery' });

export async function scrapeCityWinery() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Go to main site first, then navigate to Shows
    await page.goto("https://citywinery.com/newyork", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    // Click "Shows" link in header to navigate to events
    console.log("Clicking Shows link...");
    try {
      await page.act("click Shows link in the header navigation");
      await page.waitForTimeout(3000);
    } catch (e) {
      console.log("Shows link click failed:", e.message);
    }

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible concerts and events. For each event, get the artist/event name, date, time, description if visible, and the event URL (the actual href link starting with https://citywinery.com/). Set eventLocation to 'City Winery' for all events.",
      StandardEventSchema,
      { sourceName: 'city_winery' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "City Winery"
    }));

    logScrapingResults(events, 'City Winery');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'city_winery');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'City Winery');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeCityWinery().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeCityWinery;
