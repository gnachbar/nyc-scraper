import "../config/index.js";
import { scrapeMSGCalendar } from '../scrapers/msg_calendar.js';

export async function testMSGCalendar() {
  try {
    console.log("Testing MSG Calendar scraper...");
    const events = await scrapeMSGCalendar();
    
    console.log(`\n=== MSG Calendar Scraping Results ===`);
    console.log(`Total events found: ${events.events.length}`);
    
    if (events.events.length > 0) {
      console.log(`\nAll events:`);
      events.events.forEach((event, index) => {
        console.log(`${index + 1}. ${event.eventName}`);
        console.log(`   Date: ${event.date}`);
        console.log(`   Time: ${event.time || 'N/A'}`);
        console.log(`   URL: ${event.eventUrl}`);
        console.log('');
      });
    } else {
      console.log("No events found!");
    }
    
  } catch (error) {
    console.error("Error testing MSG Calendar scraper:", error.message);
    console.error(error.stack);
  }
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testMSGCalendar().catch(err => { 
    console.error(err); 
    process.exit(1); 
  });
}
