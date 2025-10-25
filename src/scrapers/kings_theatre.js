import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";

// Define standardized schema for all scrapers
const StandardEventSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().optional(),
    eventLocation: z.string(), // Hardcoded venue name
    eventUrl: z.string().url()
  }))
});

export async function scrapeKingsTheatre() {
  const stagehand = new Stagehand({
    env: "BROWSERBASE",
    verbose: 1,
  });

  try {
    await stagehand.init();
    const page = stagehand.page;

    // Open the Browserbase session URL in the default browser
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

    // Step 1: Open the web page
    await page.goto("https://www.kingstheatre.com/events/");
    
    // Step 2: Scroll to the bottom
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await page.waitForTimeout(2000);
    
    // Step 3 & 4: Click Show More and continue until no more button
    let hasMoreButton = true;
    let clickCount = 0;
    const maxClicks = 20; // Safety limit

    while (hasMoreButton && clickCount < maxClicks) {
      try {
        const [showMoreAction] = await page.observe("click the 'Show more' button");
        
        if (showMoreAction) {
          await page.act(showMoreAction);
          clickCount++;
          console.log(`Clicked 'Show more' button (${clickCount})`);
          
          // Wait for content to load
          await page.waitForLoadState('networkidle');
          await page.waitForTimeout(2500);
          
          // Scroll to the bottom again
          await page.evaluate(() => {
            window.scrollTo(0, document.body.scrollHeight);
          });
          await page.waitForTimeout(1000);
        } else {
          console.log("No more 'Show more' button found. All events loaded.");
          hasMoreButton = false;
        }
      } catch {
        console.log("Failed to find or click 'Show more' button. Stopping.");
        hasMoreButton = false;
      }
    }
    
    console.log(`Total 'Show more' clicks: ${clickCount}`);
    
    // Step 5: Extract the required data for all events on the page
    const result = await page.extract({
      instruction: "Extract all visible events. For each event, get the event name, date, time (if available), and the URL by clicking on the 'See more' button (NOT the 'Buy tickets' button) to get the event page URL",
      schema: StandardEventSchema
    });

    // Add hardcoded venue name to all events
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "Kings Theatre" // Hardcoded venue name
    }));

    console.log("=== Kings Theatre Scraping Results ===");
    console.log(`Total events found: ${eventsWithLocation.length}`);
    
    if (eventsWithLocation.length > 0) {
      console.log("\nFirst few events:");
      eventsWithLocation.slice(0, 5).forEach((event, index) => {
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
      const tempFile = path.join(process.cwd(), `temp_kings_${Date.now()}.json`);
      fs.writeFileSync(tempFile, JSON.stringify({ events: eventsWithLocation }, null, 2));
      
      try {
        // Import to database using existing import script
        execSync(`python3 src/import_scraped_data.py --source kings_theatre --file ${tempFile}`, { stdio: 'inherit' });
        console.log(`Successfully imported ${eventsWithLocation.length} events to database`);
        
        // Run scraper test to compare with previous run
        console.log("Running scraper test...");
        try {
          execSync(`python3 src/test_scrapers.py --source kings_theatre`, { stdio: 'inherit' });
          console.log("Scraper test completed successfully");
        } catch (testError) {
          console.warn("Scraper test failed (non-critical):", testError.message);
          // Don't throw - test failure shouldn't stop the scraper
        }
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

    return { events: eventsWithLocation };

  } catch (error) {
    console.error("Scraping failed:", error);
    throw error;
  } finally {
    await stagehand.close();
  }
}