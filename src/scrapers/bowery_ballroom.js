/**
 * Bowery Ballroom Scraper
 *
 * Scrapes event listings from Bowery Ballroom
 * URL: https://mercuryeastpresents.com/boweryballroom/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Bowery Ballroom' });

export async function scrapeBoweryBallroom() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Navigate to Bowery Ballroom calendar
    await page.goto("https://mercuryeastpresents.com/boweryballroom/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    // Scroll to load all events
    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    // Extract events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events/shows. For each event, get the event name, date, time, description if visible, and the event URL. Set eventLocation to 'Bowery Ballroom' for all events.",
      StandardEventSchema,
      { sourceName: 'bowery_ballroom' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Bowery Ballroom"
    }));

    logScrapingResults(events, 'Bowery Ballroom');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'bowery_ballroom');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Bowery Ballroom');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBoweryBallroom().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeBoweryBallroom;
