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

    console.log(JSON.stringify({ events: eventsWithLocation }, null, 2));
    return { events: eventsWithLocation };

  } catch (error) {
    console.error("Scraping failed:", error);
    throw error;
  } finally {
    await stagehand.close();
  }
}