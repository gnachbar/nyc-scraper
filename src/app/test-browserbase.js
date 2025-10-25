import "../config/index.js";
import { withStagehand } from '../lib/stagehand.js';
import { z } from 'zod';

export async function testBrowserbaseConnection() {
  console.log("Testing Browserbase connection...");
  
  await withStagehand(async (page) => {
    try {
      console.log("✅ Browserbase session created successfully!");
      
      // Test basic navigation
      console.log("Testing basic navigation...");
      await page.goto("https://www.google.com");
      
      // Test basic page interaction
      console.log("Testing basic page interaction...");
      const title = await page.title();
      console.log(`✅ Page title: ${title}`);
      
      // Test basic extraction
      console.log("Testing basic extraction...");
      const searchBox = await page.extract({
        instruction: "Find the Google search box",
        schema: z.object({
          searchBoxExists: z.boolean()
        })
      });
      
      if (searchBox.searchBoxExists) {
        console.log("✅ Successfully extracted page elements!");
      } else {
        console.log("⚠️ Search box not found, but extraction worked");
      }
      
      console.log("\n🎉 All Browserbase tests passed!");
      console.log("Browserbase integration is working correctly.");
      
    } catch (error) {
      console.error("❌ Browserbase test failed:", error.message);
      console.error(error.stack);
      throw error;
    }
  });
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  testBrowserbaseConnection().catch(err => { 
    console.error(err); 
    process.exit(1); 
  });
}
