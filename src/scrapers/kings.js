import { z } from 'zod';
import { convertToMMDDYYYY } from '../transforms/dates.js';

export async function scrapeKingsTheatre(page) {
  console.log("Starting Kings Theatre scraping...");
  
  await page.goto("https://www.kingstheatre.com/events/");

  // Load all events by clicking "Show more" button repeatedly
  console.log("Loading all events by clicking 'Show more'...");

  let clickCount = 0;
  let hasMoreButton = true;

  while (hasMoreButton) {
    // Use observe to check if "Show more" button exists
    const [showMoreAction] = await page.observe("click the 'Show more' button");
    
    if (showMoreAction) {
      clickCount++;
      console.log(`Clicking 'Show more' button (attempt ${clickCount})...`);
      
      try {
        await page.act(showMoreAction);
        console.log(`Successfully clicked 'Show more' button`);
        
        // Wait for new content to load (2-3 seconds)
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

  const events = await page.extract({
    instruction: "Extract all the events at the Kings Theatre, including event names, dates, and event times.",
    schema: z.object({
      list_of_events: z.array(
        z.object({
          event_name: z.string(),
          date: z.string(),
          event_time: z.string(),
        }),
      ),
    })
  });

  console.log("Kings Theatre events extracted:", events.list_of_events.length);
  
  // Add venue information and format dates
  const formattedEvents = events.list_of_events.map(event => ({
    venue: "Kings Theater",
    event_name: event.event_name,
    date: convertToMMDDYYYY(event.date),
    event_time: event.event_time
  }));

  // Write events directly to raw_events table
  console.log("Writing events to database...");
  const { execSync } = await import('child_process');
  const fs = await import('fs');
  const path = await import('path');
  
  // Create temporary JSON file for import
  const tempFile = path.join(process.cwd(), `temp_kings_${Date.now()}.json`);
  fs.writeFileSync(tempFile, JSON.stringify({ events: formattedEvents }, null, 2));
  
  try {
    // Import to database using existing import script
    execSync(`python3 scripts/import_scraped_data.py --source kings_theatre --file ${tempFile}`, { stdio: 'inherit' });
    console.log(`Successfully imported ${formattedEvents.length} events to database`);
  } catch (importError) {
    console.error("Database import failed:", importError);
    throw importError;
  } finally {
    // Clean up temporary file
    fs.unlinkSync(tempFile);
  }

  return formattedEvents;
}
