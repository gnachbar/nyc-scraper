import "../config/index.js";
import { withStagehand } from '../lib/stagehand.js';
import { scrapeProspectPark } from '../scrapers/prospect_park.js';

export async function testProspectPark() {
  await withStagehand(async (page) => {
    try {
      console.log("Testing Prospect Park scraper...");
      const events = await scrapeProspectPark(page);
      
      console.log(`\n=== Prospect Park Scraping Results ===`);
      console.log(`Total events found: ${events.length}`);
      
      if (events.length > 0) {
        console.log(`\nFirst few events:`);
        events.slice(0, 5).forEach((event, index) => {
          console.log(`${index + 1}. ${event.event_name}`);
          console.log(`   Date: ${event.date}`);
          console.log(`   Time: ${event.event_time}`);
          console.log(`   Location: ${event.location}`);
          console.log(`   Category: ${event.category}`);
          console.log(`   Price: ${event.price_info}`);
          if (event.description) {
            console.log(`   Description: ${event.description.substring(0, 100)}...`);
          }
          console.log('');
        });
        
        // Save to JSON for inspection
        const fs = await import('fs');
        fs.writeFileSync('prospect_park_events.json', JSON.stringify(events, null, 2));
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
