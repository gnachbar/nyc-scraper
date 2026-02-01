/**
 * Visual Verification Script
 *
 * Takes a screenshot of a venue's event page for visual comparison
 * with scraped data. This helps identify:
 * - Pagination that stopped early
 * - Events that weren't extracted
 * - Venue limitations (actually only has X events posted)
 */

import { initStagehand, openBrowserbaseSession, capturePageScreenshot, scrollToBottom } from './lib/scraper-utils.js';

// Venue URLs for verification - must match what the scrapers actually use
const VENUE_URLS = {
  barclays_center: 'https://www.barclayscenter.com/events',
  public_theater: 'https://publictheater.org/productions/',
  kings_theatre: 'https://www.kingstheatre.com/events',
  brooklyn_museum: 'https://www.brooklynmuseum.org/calendar',
  littlefield: 'https://littlefieldnyc.com/all-shows/',
  prospect_park: 'https://www.prospectpark.org/visit-the-park/things-to-do/calendar/',
  bam: 'https://www.bam.org/visit/calendar',
  brooklyn_bowl: 'https://www.brooklynbowl.com/events',
  bell_house: 'https://www.thebellhouseny.com/calendar',
  roulette: 'https://rfroulette.org/events/',
};

async function captureVenueScreenshot(venueName) {
  const url = VENUE_URLS[venueName];
  if (!url) {
    console.error(`Unknown venue: ${venueName}`);
    console.log('Available venues:', Object.keys(VENUE_URLS).join(', '));
    return null;
  }

  console.log(`\n=== Capturing screenshot for ${venueName} ===`);
  console.log(`URL: ${url}`);

  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Navigate to the page
    await page.goto(url);
    await page.waitForLoadState('networkidle');

    // Scroll to bottom to load all lazy content
    await scrollToBottom(page);
    await page.waitForTimeout(2000);

    // Take screenshot
    const screenshotPath = await capturePageScreenshot(page, venueName);

    console.log(`\nScreenshot saved: ${screenshotPath}`);
    console.log(`\nTo verify, compare this screenshot against the scraped events in the database.`);

    return screenshotPath;

  } catch (error) {
    console.error(`Error capturing screenshot for ${venueName}:`, error.message);
    return null;
  } finally {
    await stagehand.close();
  }
}

// Main
const venueName = process.argv[2];

if (!venueName) {
  console.log('Usage: node src/verify_scraper_visually.js <venue_name>');
  console.log('');
  console.log('Available venues:');
  Object.entries(VENUE_URLS).forEach(([name, url]) => {
    console.log(`  ${name}: ${url}`);
  });
  process.exit(1);
}

captureVenueScreenshot(venueName).then(path => {
  if (path) {
    console.log('\nVerification complete.');
  }
  process.exit(path ? 0 : 1);
});
