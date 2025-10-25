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

export async function testMSGInitialLoad() {
  const stagehand = new Stagehand({
    env: "BROWSERBASE",
    verbose: 1,
  });

  try {
    await stagehand.init();
    const page = stagehand.page;

    console.log("Testing MSG Calendar - Initial Load Only...");

    // Step 1: Navigate to the MSG calendar page
    await page.goto("https://www.msg.com/calendar?venues=KovZpZA7AAEA");
    console.log("Navigated to MSG calendar page");
    
    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    console.log("Page loaded");

    // Step 2: Wait 10 seconds to let any dynamic content load
    console.log("Waiting 10 seconds for any dynamic content to load...");
    await page.waitForTimeout(10000);

    // Step 3: Scroll to bottom to trigger any lazy loading
    console.log("Scrolling to bottom to trigger lazy loading...");
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await page.waitForTimeout(3000); // Wait for any lazy loading

    // Step 4: Extract ONLY what's visible (no Load More clicks)
    console.log("Extracting only initially visible events...");
    const result = await page.extract({
      instruction: "Extract all currently visible events from the MSG calendar page. Only extract events that are visible on the page right now. For each event, get the event name, date, time (if available), and the URL by clicking on the 'View Event Details' button or similar link to get the event page URL",
      schema: MSGEventSchema
    });

    console.log("=== MSG Calendar Initial Load Results ===");
    console.log(`Total events found on initial load: ${result.events.length}`);
    
    if (result.events.length > 0) {
      console.log("\nAll initially visible events:");
      result.events.forEach((event, index) => {
        console.log(`${index + 1}. ${event.eventName}`);
        console.log(`   Date: ${event.date}`);
        console.log(`   Time: ${event.time || 'N/A'}`);
        console.log(`   URL: ${event.eventUrl}`);
        console.log('');
      });
      
      // Save results to file
      const fs = await import('fs');
      fs.writeFileSync('msg_initial_load_events.json', JSON.stringify(result, null, 2));
      console.log("Initial load events saved to msg_initial_load_events.json");
    } else {
      console.log("No events found on initial page load!");
    }

    return result;

  } catch (error) {
    console.error("MSG Calendar initial load test failed:", error);
    throw error;
  } finally {
    await stagehand.close();
  }
}

// Run the test
testMSGInitialLoad().catch(err => { 
  console.error(err); 
  process.exit(1); 
});
