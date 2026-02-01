/**
 * Connolly Theatre Scraper
 *
 * Scrapes event listings from Connolly Theatre
 * URL: https://www.connollytheatre.com/events
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Connolly Theatre' });

export async function scrapeConnollyTheatre() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.connollytheatre.com/events", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible shows and events. For each event, get the show name, dates, times, description if visible, and the event URL. Set eventLocation to 'Connolly Theatre' for all events.",
      StandardEventSchema,
      { sourceName: 'connolly_theatre' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Connolly Theatre"
    }));

    logScrapingResults(events, 'Connolly Theatre');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'connolly_theatre');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Connolly Theatre');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeConnollyTheatre().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeConnollyTheatre;
