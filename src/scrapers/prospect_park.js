import { z } from 'zod';
import { convertToMMDDYYYY } from '../transforms/dates.js';

export async function scrapeProspectPark(page) {
  console.log("Starting Prospect Park events scraping...");
  
  await page.goto("https://www.prospectpark.org/events/");

  // Wait for the page to load completely
  console.log("Waiting for page to load...");
  await new Promise(resolve => setTimeout(resolve, 3000));

  // Try to load more events if there's a "Show more" or similar button
  console.log("Checking for 'Show more' or pagination...");
  
  let clickCount = 0;
  let hasMoreButton = true;
  const maxClicks = 10; // Prevent infinite loops

  while (hasMoreButton && clickCount < maxClicks) {
    // Look for various "show more" button patterns
    const [showMoreAction] = await page.observe("click the 'Show more' button or 'Load more' button or 'Next' button");
    
    if (showMoreAction) {
      clickCount++;
      console.log(`Clicking 'Show more' button (attempt ${clickCount})...`);
      
      try {
        await page.act(showMoreAction);
        console.log(`Successfully clicked 'Show more' button`);
        
        // Wait for new content to load
        await new Promise(resolve => setTimeout(resolve, 2500));
      } catch (error) {
        console.log(`Failed to click 'Show more': ${error.message}`);
        hasMoreButton = false;
      }
    } else {
      console.log("No more 'Show more' button found. All events loaded.");
      hasMoreButton = false;
    }
  }

  console.log(`Total clicks: ${clickCount}`);

  // Extract events with a comprehensive schema
  const events = await page.extract({
    instruction: "Extract all the events from Prospect Park, including event names, dates, times, locations, descriptions, and categories. Look for events in the main content area.",
    schema: z.object({
      list_of_events: z.array(
        z.object({
          event_name: z.string(),
          date: z.string(),
          event_time: z.string().optional(),
          location: z.string().optional(),
          description: z.string().optional(),
          category: z.string().optional(),
          price_info: z.string().optional(),
        }),
      ),
    })
  });

  console.log("Prospect Park events extracted:", events.list_of_events.length);
  
  // Add venue information and format dates
  const formattedEvents = events.list_of_events.map(event => ({
    venue: "Prospect Park",
    event_name: event.event_name,
    date: convertToMMDDYYYY(event.date),
    event_time: event.event_time || "TBD",
    location: event.location || "Prospect Park",
    description: event.description || "",
    category: event.category || "General",
    price_info: event.price_info || "Free"
  }));

  return formattedEvents;
}
