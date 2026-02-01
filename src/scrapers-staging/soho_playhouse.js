/**
 * Soho Playhouse Scraper
 *
 * Scrapes event listings from Soho Playhouse
 * URL: https://www.sohoplayhouse.com/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Soho Playhouse' });

export async function scrapeSohoPlayhouse() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.sohoplayhouse.com/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible shows and events. For each event, get the show name, dates, times, description if visible, and the event URL. Set eventLocation to 'Soho Playhouse' for all events.",
      StandardEventSchema,
      { sourceName: 'soho_playhouse' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Soho Playhouse"
    }));

    logScrapingResults(events, 'Soho Playhouse');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'soho_playhouse');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Soho Playhouse');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeSohoPlayhouse().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeSohoPlayhouse;
