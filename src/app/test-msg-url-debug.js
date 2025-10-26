import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";

// Define simplified schema for debugging
const DebugEventSchema = z.object({
  firstEvent: z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().optional(),
    eventUrl: z.string()
  })
});

async function debugMSGUrlExtraction() {
  const stagehand = new Stagehand({
    env: "BROWSERBASE",
    verbose: 1,
  });

  try {
    await stagehand.init();
    const page = stagehand.page;

    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    
    // Open browser
    const { exec } = await import('child_process');
    const openCommand = process.platform === 'darwin' ? 'open' : 
                       process.platform === 'win32' ? 'start' : 'xdg-open';
    
    exec(`${openCommand} https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`, (error) => {
      if (error) {
        console.log('Could not automatically open browser. Please manually open the URL above.');
      }
    });

    console.log("Navigating to MSG calendar...");
    await page.goto("https://www.msg.com/calendar?venues=KovZpZA7AAEA");
    await page.waitForLoadState('networkidle');
    console.log("Page loaded");

    // Take a screenshot before extraction
    await page.screenshot({ path: 'msg_before_extract.png' });
    console.log("Screenshot saved: msg_before_extract.png");

    // Step 1: Try to inspect the actual links on the page
    console.log("\n=== Inspecting actual links on the page ===");
    const linkData = await page.evaluate(() => {
      // Find all links on the page that might be event links
      const allLinks = document.querySelectorAll('a[href*="/events-tickets/"]');
      const links = [];
      
      allLinks.forEach((link, index) => {
        if (index < 5) { // Check first 5 event links
          links.push({
            href: link.href,
            text: link.textContent?.trim().substring(0, 50),
            innerHTML: link.innerHTML.substring(0, 100),
            index: index
          });
        }
      });
      
      return links;
    });
    
    console.log("Found links:", JSON.stringify(linkData, null, 2));

    // Step 2: Try extraction with current instruction
    console.log("\n=== Testing current instruction ===");
    try {
      const result = await page.extract({
        instruction: "Extract the FIRST visible event from the MSG calendar page. Get the event name (as eventName), date (as eventDate), time (as eventTime), and the FULL URL (as eventUrl) from the href attribute of the 'View Event Details' link or the event card link. Extract the complete URL starting with https://www.msg.com/events-tickets/",
        schema: DebugEventSchema
      });
      
      console.log("\n=== Extraction Result ===");
      console.log(JSON.stringify(result, null, 2));
      
      if (result.firstEvent) {
        console.log("\n=== Comparison ===");
        console.log(`Event Name: ${result.firstEvent.eventName}`);
        console.log(`Event Date: ${result.firstEvent.eventDate}`);
        console.log(`Event Time: ${result.firstEvent.eventTime || 'N/A'}`);
        console.log(`Event URL from extraction: ${result.firstEvent.eventUrl}`);
        console.log(`Event URL from links[0]: ${linkData[0]?.href || 'N/A'}`);
        console.log(`URL starts with https://www.msg.com: ${result.firstEvent.eventUrl.startsWith('https://www.msg.com')}`);
      }
    } catch (error) {
      console.error("Extraction failed:", error.message);
      await page.screenshot({ path: 'msg_extract_failed.png' });
    }

    // Take final screenshot
    await page.screenshot({ path: 'msg_after_extract.png' });
    console.log("\nScreenshot saved: msg_after_extract.png");

    console.log("\n=== Debug session complete ===");

  } catch (error) {
    console.error("Error:", error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run if executed directly
if (process.argv[1] === new URL(import.meta.url).pathname) {
  debugMSGUrlExtraction().catch(err => { 
    console.error(err); 
    process.exit(1); 
  });
}

export { debugMSGUrlExtraction };

