import { withStagehand } from '../lib/stagehand.js';
import { scrapeProspectPark } from '../scrapers/prospect_park_new.js';
import fs from 'fs';

async function testProspectPark() {
  await withStagehand(async (page) => {
    try {
      console.log("Testing Prospect Park scraper...");
      const result = await scrapeProspectPark();

      console.log(`\n=== Prospect Park Scraping Results ===`);
      console.log(`Total events found: ${result.events.length}`);

      if (result.events.length > 0) {
        console.log("\nFirst few events:");
        result.events.slice(0, 5).forEach((event, index) => {
          console.log(`${index + 1}. ${event.eventName}`);
          console.log(`   Date: ${event.eventDate}`);
          console.log(`   Time: ${event.eventTime || "N/A"}`);
          console.log(`   Location: ${event.eventLocation}`);
          console.log(`   URL: ${event.eventUrl}`);
          console.log('');
        });

        fs.writeFileSync('prospect_park_events.json', JSON.stringify(result.events, null, 2));
        console.log(`Events saved to prospect_park_events.json`);
      } else {
        console.log("No events found!");
      }

    } catch (error) {
      console.error("Error testing Prospect Park scraper:", error.message);
      console.error(error.stack);
    }
  });
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testProspectPark().catch(err => {
    console.error(err);
    process.exit(1);
  });
}
