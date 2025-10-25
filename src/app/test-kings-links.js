import "../config/index.js";
import { withStagehand } from '../lib/stagehand.js';
import { z } from 'zod';

export async function extractKingsEventLinks(page) {
  console.log("Starting Kings Theatre event links extraction...");
  
  await page.goto("https://www.kingstheatre.com/events/");

  // Wait for the page to load completely
  console.log("Waiting for page to load...");
  await new Promise(resolve => setTimeout(resolve, 3000));

  // Extract the event links directly
  console.log("Extracting event links...");
  const eventLinks = await page.extract({
    instruction: "Find the first 10 events on the Kings Theatre events page and extract the URLs that lead to the event detail pages (not the ticket/calendar pages). Look for links that go to the main event information page, not the 'Buy tickets' or 'Calendar' buttons. Avoid URLs that end with '/calendar' - those are ticket pages, not event detail pages.",
    schema: z.object({
      event_links: z.array(
        z.object({
          event_title: z.string(),
          event_url: z.string().url(), // Use .url() for URL validation
          event_date: z.string().optional(),
          event_time: z.string().optional(),
        })
      ).max(10) // Limit to 10 events as requested
    })
  });

  console.log(`Extracted ${eventLinks.event_links.length} event links`);
  
  return eventLinks.event_links;
}

export async function testKingsEventLinks() {
  await withStagehand(async (page) => {
    try {
      console.log("Testing Kings Theatre event links extraction...");
      const eventLinks = await extractKingsEventLinks(page);
      
      console.log(`\n=== Kings Theatre Event Links ===`);
      console.log(`Total event links found: ${eventLinks.length}`);
      
      if (eventLinks.length > 0) {
        console.log(`\nEvent Links:`);
        eventLinks.forEach((event, index) => {
          console.log(`${index + 1}. ${event.event_title}`);
          console.log(`   URL: ${event.event_url}`);
          if (event.event_date) {
            console.log(`   Date: ${event.event_date}`);
          }
          if (event.event_time) {
            console.log(`   Time: ${event.event_time}`);
          }
          console.log('');
        });
        
        // Save to JSON for inspection
        const fs = await import('fs');
        fs.writeFileSync('kings_event_links.json', JSON.stringify(eventLinks, null, 2));
        console.log(`Event links saved to kings_event_links.json`);
      } else {
        console.log("No event links found!");
      }
      
    } catch (error) {
      console.error("Error extracting Kings Theatre event links:", error.message);
      console.error(error.stack);
    }
  });
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testKingsEventLinks().catch(err => { 
    console.error(err); 
    process.exit(1); 
  });
}
