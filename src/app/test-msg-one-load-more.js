import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";

// Define schema based on data to extract
const MSGEventSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    date: z.string(),
    time: z.string().optional(),
    eventUrl: z.string().url()
  }))
});

export async function testMSGOneLoadMore() {
  const stagehand = new Stagehand({
    env: "BROWSERBASE",
    verbose: 1,
  });

  try {
    await stagehand.init();
    const page = stagehand.page;

    console.log("Testing MSG Calendar - 1 Load More Click...");

    // Step 1: Navigate to the MSG calendar page
    await page.goto("https://www.msg.com/calendar?venues=KovZpZA7AAEA");
    console.log("Navigated to MSG calendar page");
    
    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    console.log("Page loaded");

    // Step 2: Wait 5 seconds to let any dynamic content load
    console.log("Waiting 5 seconds for any dynamic content to load...");
    await page.waitForTimeout(5000);

    // Step 3: Scroll to bottom to trigger any lazy loading
    console.log("Scrolling to bottom to trigger lazy loading...");
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await page.waitForTimeout(3000);

    // Step 4: Click "Load More Events" exactly ONCE
    console.log("Attempting to click 'Load More Events' (1 time only)...");
    
    try {
      const [loadMoreAction] = await page.observe("click the 'Load More Events' button or 'Load More' button");
      
      if (loadMoreAction) {
        await page.act(loadMoreAction);
        console.log("Successfully clicked 'Load More Events' (1/1)");
        
        // Wait for new content to load
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(3000);
        
        // Scroll to bottom again to trigger any additional lazy loading
        await page.evaluate(() => {
          window.scrollTo(0, document.body.scrollHeight);
        });
        await page.waitForTimeout(2000);
      } else {
        console.log("No 'Load More Events' button found.");
      }
    } catch (error) {
      console.log(`Failed to click "Load More Events": ${error.message}`);
    }

    // Step 5: Extract all visible events after 1 Load More click
    console.log("Extracting all visible events after 1 Load More click...");
    const result = await page.extract({
      instruction: "Extract all currently visible events from the MSG calendar page. Only extract events that are visible on the page right now. For each event, get the event name, date, time (if available), and the URL by clicking on the 'View Event Details' button or similar link to get the event page URL",
      schema: MSGEventSchema
    });

    console.log("=== MSG Calendar - 1 Load More Results ===");
    console.log(`Total events found after 1 Load More click: ${result.events.length}`);
    
    if (result.events.length > 0) {
      console.log("\nAll visible events:");
      result.events.forEach((event, index) => {
        console.log(`${index + 1}. ${event.eventName}`);
        console.log(`   Date: ${event.date}`);
        console.log(`   Time: ${event.time || 'N/A'}`);
        console.log(`   URL: ${event.eventUrl}`);
        console.log('');
      });
      
      // Save results to file
      const fs = await import('fs');
      fs.writeFileSync('msg_one_load_more_events.json', JSON.stringify(result, null, 2));
      console.log("Events saved to msg_one_load_more_events.json");
    } else {
      console.log("No events found!");
    }

    return result;

  } catch (error) {
    console.error("MSG Calendar 1 Load More test failed:", error);
    throw error;
  } finally {
    await stagehand.close();
  }
}

// Run the test
testMSGOneLoadMore().catch(err => { 
  console.error(err); 
  process.exit(1); 
});
