/**
 * Greenwich House Scraper
 *
 * Scrapes event listings from Greenwich House
 * URL: https://www.greenwichhouse.org/calendar-of-events/
 * Note: The /arts/theatre/ page is 404, use the calendar page instead
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Greenwich House' });

export async function scrapeGreenwichHouse() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Start at homepage and navigate to calendar
    await page.goto("https://www.greenwichhouse.org/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    // Click "CALENDAR OF EVENTS" in the footer to navigate to calendar page
    console.log("Navigating to Calendar of Events...");
    try {
      await page.act("click CALENDAR OF EVENTS link");
      await page.waitForTimeout(3000);
    } catch (e) {
      console.log("Calendar link click failed:", e.message);
    }

    await scrollToBottom(page);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible shows and events. For each event, get the show name, dates, times, description if visible, and the event URL. Set eventLocation to 'Greenwich House' for all events.",
      StandardEventSchema,
      { sourceName: 'greenwich_house' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Greenwich House"
    }));

    logScrapingResults(events, 'Greenwich House');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'greenwich_house');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Greenwich House');
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
