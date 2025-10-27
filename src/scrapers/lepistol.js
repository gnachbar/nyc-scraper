import { initStagehand, openBrowserbaseSession, createStandardSchema, convertWeeklyToDatedEvents } from '../lib/scraper-utils.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';
import { z } from 'zod';

// Schema for a single weekly recurring event
const WeeklyEventSchema = z.object({
  eventName: z.string(),
  day: z.string(), // Day of week (Monday, Tuesday, etc.)
  eventTime: z.string().default(""),
  eventDescription: z.string().optional(),
  eventLocation: z.string().default("Le Pistol"),
  eventUrl: z.string().default("https://www.lepistolbk.com/events")
});

export async function scrapeLePistol() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the events page
    await page.goto("https://www.lepistolbk.com/events");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Extract Monday's event (already visible)
    console.log("Extracting Monday event...");
    const mondayEvent = await page.extract({
      instruction: "Extract ONLY the MONDAY event information. Get the event name (e.g., 'Industry Night'), day='Monday', time if mentioned, and description. Set eventLocation to 'Le Pistol' and eventUrl to 'https://www.lepistolbk.com/events'",
      schema: WeeklyEventSchema
    });
    
    // Step 3: Click the plus sign next to Tuesday to expand it
    console.log("Expanding Tuesday...");
    await page.act("click the plus sign or expand icon next to Tuesday");
    await page.waitForTimeout(1000);
    
    // Step 4: Extract Tuesday's event
    console.log("Extracting Tuesday event...");
    const tuesdayEvent = await page.extract({
      instruction: "Extract ONLY the TUESDAY event information. Get the event name (e.g., 'Trivia Night'), day='Tuesday', time if mentioned, and description. Set eventLocation to 'Le Pistol' and eventUrl to 'https://www.lepistolbk.com/events'",
      schema: WeeklyEventSchema
    });
    
    // Step 5: Expand Wednesday
    console.log("Expanding Wednesday...");
    await page.act("click the plus sign or expand icon next to Wednesday");
    await page.waitForTimeout(1000);
    
    // Step 6: Extract Wednesday's event
    console.log("Extracting Wednesday event...");
    const wednesdayEvent = await page.extract({
      instruction: "Extract ONLY the WEDNESDAY event information. Get the event name (e.g., 'LIVE JAZZ'), day='Wednesday', time if mentioned, and description. Set eventLocation to 'Le Pistol' and eventUrl to 'https://www.lepistolbk.com/events'",
      schema: WeeklyEventSchema
    });
    
    // Step 7: Expand Thursday
    console.log("Expanding Thursday...");
    await page.act("click the plus sign or expand icon next to Thursday");
    await page.waitForTimeout(1000);
    
    // Step 8: Extract Thursday's event
    console.log("Extracting Thursday event...");
    const thursdayEvent = await page.extract({
      instruction: "Extract ONLY the THURSDAY event information. Get the event name (e.g., 'Philosophy Club'), day='Thursday', time if mentioned, and description. Set eventLocation to 'Le Pistol' and eventUrl to 'https://www.lepistolbk.com/events'",
      schema: WeeklyEventSchema
    });
    
    // Step 9: Expand Friday
    console.log("Expanding Friday...");
    await page.act("click the plus sign or expand icon next to Friday");
    await page.waitForTimeout(1000);
    
    // Step 10: Extract Friday's event
    console.log("Extracting Friday event...");
    const fridayEvent = await page.extract({
      instruction: "Extract ONLY the FRIDAY event information. Get the event name (e.g., 'Late Night DJ'), day='Friday', time if mentioned, and description. Set eventLocation to 'Le Pistol' and eventUrl to 'https://www.lepistolbk.com/events'",
      schema: WeeklyEventSchema
    });
    
    // Step 11: Expand Weekends
    console.log("Expanding Weekends...");
    await page.act("click the plus sign or expand icon next to WEEKENDS");
    await page.waitForTimeout(1000);
    
    // Step 12: Extract Weekends event
    console.log("Extracting Weekends event...");
    const weekendsEvent = await page.extract({
      instruction: "Extract ONLY the WEEKENDS event information. Get the event name (e.g., 'Brunch Specials'), day='WEEKENDS', time if mentioned, and description. Set eventLocation to 'Le Pistol' and eventUrl to 'https://www.lepistolbk.com/events'",
      schema: WeeklyEventSchema
    });
    
    // Combine all weekly events
    const weeklyEvents = [
      mondayEvent,
      tuesdayEvent,
      wednesdayEvent,
      thursdayEvent,
      fridayEvent,
      weekendsEvent
    ];
    
    console.log(`\nExtracted ${weeklyEvents.length} weekly recurring events`);
    console.log("Sample weekly events:", weeklyEvents.slice(0, 3));
    
    // Convert weekly events to dated events for the next 6 months
    console.log("\nConverting weekly events to dated events...");
    const datedEvents = convertWeeklyToDatedEvents(weeklyEvents, {
      monthsAhead: 6,
      baseUrl: "https://www.lepistolbk.com/events"
    });
    
    console.log(`Generated ${datedEvents.length} dated events`);
    
    // Log results
    logScrapingResults(datedEvents, 'Le Pistol');
    
    // Save to database and run tests
    if (datedEvents.length > 0) {
      await saveEventsToDatabase(datedEvents, 'lepistol');
    } else {
      console.log("No events found!");
    }

    return { events: datedEvents };

  } catch (error) {
    await handleScraperError(error, page, 'Le Pistol');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeLePistol().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeLePistol;

