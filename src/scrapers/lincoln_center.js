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

    await page.goto("https://www.lincolncenter.org/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    // Close the email signup modal if present
    console.log("Closing email signup modal if present...");
    try {
      await page.act("click close button or X to dismiss the popup modal");
      await page.waitForTimeout(2000);
    } catch (e) {
      console.log("No modal to close or close failed:", e.message);
    }

    // Try to navigate to calendar/events section
    console.log("Looking for events link...");
    try {
      await page.act("click See all events link or View full calendar link");
      await page.waitForTimeout(3000);
    } catch (e) {
      console.log("Could not find events link:", e.message);
    }

    await scrollToBottom(page);

    await clickButtonUntilGone(page, "Load More", 10, {
      scrollAfterClick: true,
      loadWaitTime: 2000
    });

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from this page. For each event, get the event name, date, time, venue/location within Lincoln Center if shown (e.g., David Geffen Hall, Alice Tully Hall), description if visible, and the event URL.",
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
