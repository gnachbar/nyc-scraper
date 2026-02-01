/**
 * Caveat Scraper
 *
 * Scrapes event listings from Caveat NYC
 * URL: https://www.caveat.nyc/events
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Caveat' });

export async function scrapeCaveat() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Navigate to Caveat events page
    await page.goto("https://www.caveat.nyc/events", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    // Scroll to load all events
    console.log("Scrolling to load all events...");
    let previousHeight = 0;
    let currentHeight = await page.evaluate(() => document.body.scrollHeight);
    let scrollAttempts = 0;
    const maxScrollAttempts = 10;

    while (previousHeight !== currentHeight && scrollAttempts < maxScrollAttempts) {
      previousHeight = currentHeight;
      await scrollToBottom(page, 2000);
      currentHeight = await page.evaluate(() => document.body.scrollHeight);
      scrollAttempts++;
    }

    // Extract events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, time, description if visible, and the event URL. Set eventLocation to 'Caveat' for all events.",
      StandardEventSchema,
      { sourceName: 'caveat' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Caveat"
    }));

    logScrapingResults(events, 'Caveat');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'caveat');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Caveat');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeCaveat().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeCaveat;
