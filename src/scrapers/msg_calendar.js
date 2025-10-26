import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";

// Define standardized schema for all scrapers
const StandardEventSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().default(""), // Required field, empty string if not found
    eventUrl: z.string().url()
  }))
});

export async function scrapeMSGCalendar() {
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

    console.log("Starting MSG Calendar scraping...");

    // Step 1: Navigate to the MSG calendar page
    await page.goto("https://www.msg.com/calendar?venues=KovZpZA7AAEA");
    console.log("Navigated to MSG calendar page");
    
    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    console.log("Page loaded");

    // Step 2: Scroll all the way to the bottom
    console.log("Scrolling to bottom of page...");
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await page.waitForTimeout(2000); // Wait for any lazy loading

    // Step 3: Click "Load More Events" up to 3 times
    const maxLoadMoreClicks = 3;
    let loadMoreClicks = 0;

    for (let i = 0; i < maxLoadMoreClicks; i++) {
      try {
        console.log(`Attempting to click "Load More Events" (attempt ${i + 1}/${maxLoadMoreClicks})`);
        
        // Look for "Load More Events" button
        const [loadMoreAction] = await page.observe("click the 'Load More Events' button or 'Load More' button");
        
        if (loadMoreAction) {
          await page.act(loadMoreAction);
          loadMoreClicks++;
          console.log(`Successfully clicked "Load More Events" (${loadMoreClicks}/${maxLoadMoreClicks})`);
          
          // Wait for new content to load
          await page.waitForLoadState('networkidle');
          await page.waitForTimeout(2000);
          
          // Scroll to bottom again to trigger any additional lazy loading
          await page.evaluate(() => {
            window.scrollTo(0, document.body.scrollHeight);
          });
          await page.waitForTimeout(1000);
        } else {
          console.log("No 'Load More Events' button found. All events may be loaded.");
          break;
        }
      } catch (error) {
        console.log(`Failed to click "Load More Events" on attempt ${i + 1}: ${error.message}`);
        break;
      }
    }

    console.log(`Total "Load More Events" clicks: ${loadMoreClicks}`);

    // Step 4: Extract all visible events
    console.log("Extracting all visible events...");
    
    let result;
    try {
      result = await page.extract({
        instruction: "Extract all visible events from the MSG calendar page. For each event, get the event name (as eventName), date (as eventDate), time (as eventTime, if available), and the FULL URL (as eventUrl) from the href attribute of the 'View Event Details' link or the event card link. Extract the complete URL starting with https://www.msg.com/events-tickets/",
        schema: StandardEventSchema
      });
    } catch (extractError) {
      console.error("Extraction failed:", extractError.message);
      console.log("Taking screenshot for debugging...");
      await page.screenshot({ path: 'msg_extraction_failed.png' });
      throw new Error(`Failed to extract events: ${extractError.message}`);
    }
    
    // Validate result
    if (!result || !result.events) {
      console.error("No events extracted from page");
      await page.screenshot({ path: 'msg_no_events.png' });
      throw new Error("Extraction returned no events");
    }

    // Add hardcoded venue name to all events and fix URLs
    const eventsWithLocation = result.events.map(event => {
      // Fix URLs that are just IDs (like "0-6615") - convert to full MSG URLs
      let fullUrl = event.eventUrl;
      if (event.eventUrl && !event.eventUrl.startsWith('http')) {
        // If URL is just an ID, skip it - we can't construct a full URL from just an ID
        fullUrl = '';
      }
      
      return {
        ...event,
        eventUrl: fullUrl,
        eventLocation: "Madison Square Garden" // Hardcoded MSG venue name
      };
    });

    console.log("=== MSG Calendar Scraping Results ===");
    console.log(`Total events found: ${eventsWithLocation.length}`);
    
    // Count events with and without times
    const eventsWithTimes = eventsWithLocation.filter(e => e.eventTime && e.eventTime.trim() !== '').length;
    const eventsWithoutTimes = eventsWithLocation.length - eventsWithTimes;
    
    if (eventsWithoutTimes > 0) {
      console.log(`⚠ WARNING: ${eventsWithoutTimes}/${eventsWithLocation.length} events missing times`);
    } else {
      console.log(`✓ All ${eventsWithLocation.length} events have times`);
    }
    
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
      const tempFile = path.join(process.cwd(), `temp_msg_${Date.now()}.json`);
      fs.writeFileSync(tempFile, JSON.stringify({ events: eventsWithLocation }, null, 2));
      
      try {
        // Import to database using existing import script
        execSync(`python3 src/import_scraped_data.py --source msg_calendar --file ${tempFile}`, { stdio: 'inherit' });
        console.log(`Successfully imported ${eventsWithLocation.length} events to database`);
        
        // Run scraper test to compare with previous run
        console.log("Running scraper test...");
        try {
          execSync(`python3 src/test_scrapers.py --source msg_calendar`, { stdio: 'inherit' });
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
      console.log("No events found on the page.");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    console.error("MSG Calendar scraping failed:", error);
    throw error;
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeMSGCalendar().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
