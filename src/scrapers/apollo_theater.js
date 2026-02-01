/**
 * Apollo Theater Scraper
 *
 * Scrapes event listings from Apollo Theater
 * URL: https://www.apollotheater.org/
 * Note: The /events/ page returns 404, events are on the homepage
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Apollo Theater' });

export async function scrapeApolloTheater() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Use homepage - the /events/ page is 404
    await page.goto("https://www.apollotheater.org/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events from this page. For each event, get the event name, date, time, description if visible, and the event URL. Set eventLocation to 'Apollo Theater' for all events.",
      StandardEventSchema,
      { sourceName: 'apollo_theater' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Apollo Theater"
    }));

    logScrapingResults(events, 'Apollo Theater');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'apollo_theater');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Apollo Theater');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeApolloTheater().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeApolloTheater;
