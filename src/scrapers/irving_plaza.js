/**
 * Irving Plaza Scraper
 *
 * Scrapes event listings from Irving Plaza
 * URL: https://www.irvingplaza.com/events
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Irving Plaza' });

export async function scrapeIrvingPlaza() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.irvingplaza.com/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    // Click "Shows" link to navigate to events
    console.log("Clicking Shows link...");
    try {
      await page.act("click Shows link");
      await page.waitForTimeout(3000);
    } catch (e) {
      console.log("Shows link click failed:", e.message);
    }

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events/concerts. For each event, get the artist/event name, date, time (doors/show time), description if visible, and the event URL. Set eventLocation to 'Irving Plaza' for all events.",
      StandardEventSchema,
      { sourceName: 'irving_plaza' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Irving Plaza"
    }));

    logScrapingResults(events, 'Irving Plaza');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'irving_plaza');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Irving Plaza');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeIrvingPlaza().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeIrvingPlaza;
