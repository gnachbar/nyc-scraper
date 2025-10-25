import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";

// Define standardized schema for all scrapers
const StandardEventSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().optional(),
    eventLocation: z.string(), // Will extract subvenue from website
    eventUrl: z.string().url()
  }))
});

export async function scrapeProspectPark() {
  const stagehand = new Stagehand({
    env: "BROWSERBASE",
    verbose: 1,
  });

  try {
    await stagehand.init();
    const page = stagehand.page;

    // Auto-Open Browserbase session in default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    
    // Automatically open the session URL in the browser
    const { exec } = await import('child_process');
    const openCommand = process.platform === 'darwin' ? 'open' : 
                       process.platform === 'win32' ? 'start' : 'xdg-open';
    
    exec(`${openCommand} https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`, (error) => {
      if (error) {
        console.log('Could not automatically open browser. Please manually open the URL above.');
      } else {
        console.log('Opened Browserbase session in your default browser');
      }
    });

    // Step 1: Navigate to the Prospect Park events page
    await page.goto("https://www.prospectpark.org/events/");
    
    // Step 2: Extract all the information on the screen
    const allEvents = [];
    let pageCount = 0;
    const maxPages = 10;

    while (pageCount < maxPages) {
      console.log(`Extracting events from page ${pageCount + 1}/${maxPages}...`);
      
      const result = await page.extract({
        instruction: "Extract all visible events on the current page. For each event, get the event name (as eventName), date (as eventDate), time (as eventTime, if available), subvenue/location (as eventLocation - this is the text below the event name like 'Grand Army Plaza', 'Prospect Park Zoo', etc.), and the URL (as eventUrl) by clicking on the event name to get the event page URL",
        schema: StandardEventSchema
      });

      allEvents.push(...result.events);
      console.log(`Found ${result.events.length} events on page ${pageCount + 1}`);

      // Step 3: Click "Next events" button
      try {
        const [nextEventsAction] = await page.observe("click the 'Next events' button");
        
        if (nextEventsAction) {
          await page.act(nextEventsAction);
          pageCount++;
          console.log(`Successfully clicked 'Next events' button (${pageCount}/${maxPages})`);
          
          // Wait for new content to load
          await page.waitForLoadState('domcontentloaded');
          await page.waitForTimeout(3000); // Increased wait time for content to load
        } else {
          console.log("No more 'Next events' button found. All pages processed.");
          break;
        }
      } catch (error) {
        console.log(`Failed to click 'Next events' button: ${error.message}`);
        console.log("Continuing to extract from current page...");
        // Don't break, continue to extract from current page
      }
    }

    console.log(`Total pages processed: ${pageCount}`);
    console.log(`Total events found: ${allEvents.length}`);

    if (allEvents.length > 0) {
      console.log("\nFirst few events:");
      allEvents.slice(0, 5).forEach((event, index) => {
        console.log(`${index + 1}. ${event.eventName}`);
        console.log(`   Date: ${event.eventDate}`);
        console.log(`   Time: ${event.eventTime || 'N/A'}`);
        console.log(`   Location: ${event.eventLocation}`);
        console.log(`   URL: ${event.eventUrl}`);
        console.log('');
      });
      
      // Write events directly to raw_events table
      console.log("Writing events to database...");
      const { execSync } = await import('child_process');
      const fs = await import('fs');
      const path = await import('path');
      
      // Create temporary JSON file for import
      const tempFile = path.join(process.cwd(), `temp_prospect_${Date.now()}.json`);
      fs.writeFileSync(tempFile, JSON.stringify({ events: allEvents }, null, 2));
      
      try {
        // Import to database using existing import script
        execSync(`python3 scripts/import_scraped_data.py --source prospect_park --file ${tempFile}`, { stdio: 'inherit' });
        console.log(`Successfully imported ${allEvents.length} events to database`);
      } catch (importError) {
        console.error("Database import failed:", importError);
        throw importError;
      } finally {
        // Clean up temporary file
        fs.unlinkSync(tempFile);
      }
    } else {
      console.log("No events found!");
    }

    return { events: allEvents };

  } catch (error) {
    console.error("Prospect Park scraping failed:", error);
    throw error;
  } finally {
    await stagehand.close();
  }
}
