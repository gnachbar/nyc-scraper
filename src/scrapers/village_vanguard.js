/**
 * Village Vanguard Scraper
 *
 * Scrapes event listings from Village Vanguard
 * URL: https://villagevanguard.com/
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Village Vanguard' });

export async function scrapeVillageVanguard() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://villagevanguard.com/", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible jazz shows and events. For each event, get the artist/band name, dates, show times (sets), description if visible, and any event URL. Set eventLocation to 'Village Vanguard' for all events.",
      StandardEventSchema,
      { sourceName: 'village_vanguard' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Village Vanguard"
    }));

    logScrapingResults(events, 'Village Vanguard');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'village_vanguard');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Village Vanguard');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeVillageVanguard().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeVillageVanguard;
