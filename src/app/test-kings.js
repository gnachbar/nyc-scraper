import "../config/index.js";
import { withStagehand } from '../lib/stagehand.js';
import { scrapeKingsTheatre } from '../scrapers/kings.js';

export async function testKingsTheatre() {
  await withStagehand(async (page) => {
    try {
      console.log("Testing Kings Theatre scraper...");
      const events = await scrapeKingsTheatre(page);
      
      console.log(`\n=== Kings Theatre Scraping Results ===`);
      console.log(`Total events found: ${events.length}`);
      
      if (events.length > 0) {
        console.log(`\nFirst few events:`);
        events.slice(0, 3).forEach((event, index) => {
          console.log(`${index + 1}. ${event.event_name}`);
          console.log(`   Date: ${event.date}`);
          console.log(`   Time: ${event.event_time}`);
          console.log(`   Venue: ${event.venue}`);
          console.log('');
        });
        
        // Save to JSON for inspection
        const fs = await import('fs');
        fs.writeFileSync('kings_events.json', JSON.stringify(events, null, 2));
        console.log(`Events saved to kings_events.json`);
      } else {
        console.log("No events found!");
      }
      
    } catch (error) {
      console.error("Error testing Kings Theatre scraper:", error.message);
      console.error(error.stack);
    }
  });
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testKingsTheatre().catch(err => { 
    console.error(err); 
    process.exit(1); 
  });
}
