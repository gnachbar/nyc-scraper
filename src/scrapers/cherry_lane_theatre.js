/**
 * Cherry Lane Theatre Scraper
 *
 * Scrapes event listings from Cherry Lane Theatre
 * URL: https://www.cherrylanetheatre.org/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Cherry Lane Theatre' });

export async function scrapeCherryLaneTheatre() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.cherrylanetheatre.org/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    // Click "Explore all shows" to see all events
    console.log("Clicking 'Explore all shows'...");
    try {
      await page.act("click Explore all shows");
      await page.waitForTimeout(3000);
    } catch (e) {
      console.log("'Explore all shows' click failed (continuing):", e.message);
    }

    await scrollToBottom(page);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible shows and events. For each event, get the show name, dates, times, description if visible, and the event URL. Set eventLocation to 'Cherry Lane Theatre' for all events.",
      StandardEventSchema,
      { sourceName: 'cherry_lane_theatre' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Cherry Lane Theatre"
    }));

    logScrapingResults(events, 'Cherry Lane Theatre');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'cherry_lane_theatre');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Cherry Lane Theatre');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeCherryLaneTheatre().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeCherryLaneTheatre;
