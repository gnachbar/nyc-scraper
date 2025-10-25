import "../config/index.js";
import { Stagehand } from "@browserbasehq/stagehand";
import { exec } from "child_process";
import fs from "fs/promises";
import { z } from 'zod';

// Replay utility function from Stagehand docs
async function replay(result) {
  const history = result.actions;
  const replay = history
    .map((action) => {
      switch (action.type) {
        case "act":
          if (!action.playwrightArguments) {
            console.log(`Skipping act action without playwright arguments:`, action);
            return `// Skipped act action: ${JSON.stringify(action)}`;
          }
          return `await page.act(${JSON.stringify(
            action.playwrightArguments
          )})`;
        case "scroll":
          return `await page.evaluate(() => window.scrollBy(0, ${action.pixels || 500}))`;
        case "ariaTree":
          return `// Aria tree exploration - handled by agent automatically`;
        case "extract":
          if (action.instruction && action.schema) {
            return `await page.extract({
  instruction: "${action.instruction}",
  schema: ${action.schema}
})`;
          }
          return `await page.extract("${action.parameters || action.instruction || 'extract events'}")`;
        case "goto":
          return `await page.goto("${action.parameters}")`;
        case "wait":
          return `await page.waitForTimeout(${parseInt(
            action.parameters
          )})`;
        case "navback":
          return `await page.goBack()`;
        case "refresh":
          return `await page.reload()`;
        case "close":
          return `await stagehand.close()`;
        default:
          console.log(`Unknown action type: ${action.type}`, action);
          return `// Unknown action: ${JSON.stringify(action)}`;
      }
    })
    .join("\n");

  console.log("Replay:");
  const boilerplate = `
import { Page, BrowserContext, Stagehand } from "@browserbasehq/stagehand";
import { z } from 'zod';

export async function main(stagehand) {
    const page = stagehand.page;
    ${replay}
}
  `;
  await fs.writeFile("prospect_park_replay.ts", boilerplate);

  // Format the replay file with prettier
  await new Promise((resolve, reject) => {
    exec(
      "npx prettier --write prospect_park_replay.ts",
      (error, stdout, stderr) => {
        if (error) {
          console.error(`Error formatting prospect_park_replay.ts: ${error}`);
          reject(error);
          return;
        }
        resolve(stdout);
      }
    );
  });
}

export async function testAgentReplay() {
  // Check if OpenAI API key is set
  if (!process.env.OPENAI_API_KEY) {
    console.error("❌ OPENAI_API_KEY is not set!");
    console.log("Please set your OpenAI API key:");
    console.log("1. Copy .env.example to .env");
    console.log("2. Add your OpenAI API key to the .env file");
    console.log("3. Run: export OPENAI_API_KEY=your_key_here");
    return;
  }

  const stagehand = new Stagehand({ env: "BROWSERBASE" });
  await stagehand.init();
  
  console.log(`Stagehand Session Started`);
  console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
  
  try {
    // Navigate to Prospect Park events page
    await stagehand.page.goto("https://www.prospectpark.org/events/");

    // Create an agent with default configuration
    const agent = stagehand.agent({
      instructions: "You are a helpful assistant that can use a web browser to scrape event information from websites."
    });

    console.log("Agent created, executing task...");

    // Execute the scraping task
    const result = await agent.execute(`
      Scrape all events from the Prospect Park events page. 
      
      Your task:
      1. Navigate to the events page (already done)
      2. Load all events by clicking any "Show more" or "Load more" buttons if they exist
      3. Extract all events with the following information:
         - Event name
         - Date
         - Time (if available)
         - Location (if available) 
         - Description (if available)
         - Category (if available)
         - Price information (if available)
      
      Use the extract method with a proper schema to get structured data.
    `);

    console.log("Agent execution completed!");
    console.log("Result message:", result.message);
    console.log("Actions taken:", result.actions.length);

    // Generate replay script
    console.log("\nGenerating replay script...");
    await replay(result);
    console.log("Replay script saved to prospect_park_replay.ts");

    // Also save the raw result for inspection
    await fs.writeFile("agent_result.json", JSON.stringify(result, null, 2));
    console.log("Raw agent result saved to agent_result.json");

  } catch (error) {
    console.error("Error during agent execution:", error.message);
    console.error(error.stack);
  } finally {
    await stagehand.close();
  }
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testAgentReplay().catch(err => { 
    console.error(err); 
    process.exit(1); 
  });
}
