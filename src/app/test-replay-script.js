import "../config/index.js";
import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";

// Import the generated replay function
async function main(stagehand) {
  const page = stagehand.page;
  await page.act({
    description:
      "Button labeled 'Search Input Toggle' which could be related to loading more events or interacting with event search results.",
    method: "click",
    arguments: [],
    selector:
      "xpath=/html[1]/body[1]/div[1]/header[1]/div[2]/nav[1]/div[3]/a[3]",
  });
  await page.act({
    description: "Scrollable area of the page to perform scroll down action",
    method: "scrollTo",
    arguments: ["100%"],
    selector: "xpath=/html[1]",
  });
  // Aria tree exploration - handled by agent automatically
  const result = await page.extract({
    instruction:
      "extract all events with event name, date, time, location, description, category, and price information",
    schema: z.object({
      events: z.array(
        z.object({
          name: z.string(),
          date: z.string(),
          time: z.string().optional(),
          location: z.string().optional(),
          description: z.string().optional(),
          category: z.string().optional(),
          price: z.string().optional(),
        }),
      ),
    }),
  });
  
  console.log("=== Generated Replay Script Results ===");
  console.log(`Total events extracted: ${result.events.length}`);
  
  if (result.events.length > 0) {
    console.log("\nFirst few events:");
    result.events.slice(0, 3).forEach((event, index) => {
      console.log(`${index + 1}. ${event.name}`);
      console.log(`   Date: ${event.date}`);
      console.log(`   Time: ${event.time || 'N/A'}`);
      console.log(`   Location: ${event.location || 'N/A'}`);
      console.log(`   Price: ${event.price || 'N/A'}`);
      console.log('');
    });
    
    // Save results
    const fs = await import('fs');
    fs.writeFileSync('replay_test_results.json', JSON.stringify(result, null, 2));
    console.log("Results saved to replay_test_results.json");
  }
  
  await stagehand.close();
}

export async function testGeneratedReplayScript() {
  const stagehand = new Stagehand({ env: "BROWSERBASE" });
  await stagehand.init();
  
  console.log(`Testing Generated Replay Script`);
  console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
  
  try {
    // Navigate to Prospect Park events page first
    await stagehand.page.goto("https://www.prospectpark.org/events/");
    
    // Run the generated replay script
    await main(stagehand);
    
  } catch (error) {
    console.error("Error testing replay script:", error.message);
    console.error(error.stack);
  }
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testGeneratedReplayScript().catch(err => { 
    console.error(err); 
    process.exit(1); 
  });
}

