import { scrapeKingsTheatre } from '../scrapers/kings_theatre.js';
import fs from 'fs';

async function testKingsTheatre() {
  try {
    console.log("Testing Kings Theatre scraper...");
    const result = await scrapeKingsTheatre();

    console.log(`\n=== Kings Theatre Scraping Results ===`);
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

      fs.writeFileSync('kings_theatre_events.json', JSON.stringify(result.events, null, 2));
      console.log(`Events saved to kings_theatre_events.json`);
    } else {
      console.log("No events found!");
    }

  } catch (error) {
    console.error("Error testing Kings Theatre scraper:", error.message);
    console.error(error.stack);
  }
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testKingsTheatre().catch(err => {
    console.error(err);
    process.exit(1);
  });
}
