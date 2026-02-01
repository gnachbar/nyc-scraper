/**
 * Radio City Music Hall Scraper
 *
 * Scrapes event listings from Radio City Music Hall (MSG venue)
 * URL: https://www.msg.com/radio-city-music-hall
 */

import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Radio City Music Hall' });

export async function scrapeRadioCity() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    await page.goto("https://www.msg.com/radio-city-music-hall", {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    const result = await extractEventsFromPage(
      page,
      "Extract all visible events/shows. For each event, get the event name, date, time, description if visible, and the event URL. Set eventLocation to 'Radio City Music Hall' for all events.",
      StandardEventSchema,
      { sourceName: 'radio_city' }
    );

    let events = result.events.map(event => ({
      ...event,
      eventLocation: "Radio City Music Hall"
    }));

    logScrapingResults(events, 'Radio City Music Hall');

    if (events.length > 0) {
      await saveEventsToDatabase(events, 'radio_city');
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, 'Radio City Music Hall');
  } finally {
    await stagehand.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeRadioCity().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrapeRadioCity;
