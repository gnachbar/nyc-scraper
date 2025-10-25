# Stagehand Scraper Generator

> **CRITICAL INSTRUCTIONS for Cursor Agent:**
> When the user says "Use stagehand-scraper-guide.md for [URL]", you MUST follow this process:
> 
> **STEP 1: PROMPT THE USER FIRST** ⚠️
> Before writing ANY code, you MUST ask the user to provide the following information:
>    - **URL:** What is the website URL to scrape?
>    - **Steps:** How should we navigate and extract? (numbered list)
>    - **Venue Name:** What is the venue name to hardcode for event location?
>    - **Source Name:** What is the database source identifier? (e.g., kings_theatre, msg_calendar, prospect_park)
> 
> **STEP 2: WAIT FOR USER RESPONSE**
> Do NOT proceed until the user provides all four pieces of information above.
> 
> **STEP 3: GENERATE SCRIPT**
> Only after receiving the user's input, generate a complete Stagehand TypeScript script using the patterns below
> 
> **STEP 4: INCLUDE REQUIREMENTS**
> Include proper error handling, types, and the Zod schema based on the standardized output structure

## Standardized Output Structure

**All scrapers must output the following standardized structure:**

- **Event Name** (string) - The name/title of the event
- **Event Date** (string) - The date of the event  
- **Event Time** (string, optional) - The time of the event
- **Event Location** (string) - **HARDCODED** venue name (NOT extracted from website)
- **Event URL** (string) - The URL to the event details page

**Important:** The Event Location should be hardcoded based on the venue name for the specific script, NOT extracted from the website. This ensures consistency across all scrapers.

---

## Stagehand API Reference

**Official Docs:** https://docs.stagehand.dev/

### Core Methods

#### `act()` - Perform Actions
Execute natural language instructions. Keep actions atomic (one action per call).
```typescript
await page.act("click the login button");
await page.act("type 'hello@example.com' into the email field");
```

#### `extract()` - Pull Data
Extract structured data using Zod schemas.
```typescript
const data = await page.extract({
  instruction: "get the product information",
  schema: z.object({
    name: z.string(),
    price: z.number()
  })
});
```

**For arrays:**
```typescript
schema: z.object({
  items: z.array(z.object({
    name: z.string(),
    price: z.number()
  }))
})
```

**For URLs/Links:**
```typescript
schema: z.object({
  productUrl: z.string().url(),
  imageUrl: z.string().url()
})
```

#### `observe()` - Discover Actions
Find available actions before executing.
```typescript
const [action] = await page.observe("click the submit button");
await page.act(action);
```

---

## Script Generation Guidelines

### Structure
Every generated script should follow this pattern:

```typescript
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

async function scrape[SiteName]() {
  const stagehand = new Stagehand({
    env: "LOCAL",
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

    // Implement steps from user's input
    await page.goto("URL");
    
    // Navigation/actions
    // ...
    
    // Extract data
    const result = await page.extract({
      instruction: "Extract all visible events. For each event, get the event name, date, time (if available), and the URL by clicking on the 'View Event Details' button or similar link to get the event page URL",
      schema: StandardEventSchema
    });

    // Add hardcoded venue name to all events
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "[VENUE_NAME]" // Replace with actual venue name
    }));

    console.log(JSON.stringify({ events: eventsWithLocation }, null, 2));
    
    // Write events directly to raw_events table
    console.log("Writing events to database...");
    const { execSync } = await import('child_process');
    const fs = await import('fs');
    const path = await import('path');
    
    // Create temporary JSON file for import
    const tempFile = path.join(process.cwd(), `temp_${Date.now()}.json`);
    fs.writeFileSync(tempFile, JSON.stringify({ events: eventsWithLocation }, null, 2));
    
    try {
      // Import to database using existing import script
      const sourceName = "[SOURCE_NAME]"; // Replace with actual source (kings_theatre, msg_calendar, prospect_park)
      execSync(`python3 src/import_scraped_data.py --source ${sourceName} --file ${tempFile}`, { stdio: 'inherit' });
      console.log(`Successfully imported ${eventsWithLocation.length} events to database`);
    } catch (importError) {
      console.error("Database import failed:", importError);
      throw importError;
    } finally {
      // Clean up temporary file
      fs.unlinkSync(tempFile);
    }
    
    return { events: eventsWithLocation };

  } catch (error) {
    console.error("Scraping failed:", error);
    throw error;
  } finally {
    await stagehand.close();
  }
}

scrape[SiteName]();
```

### Best Practices for Generated Code

1. **Auto-Open Browserbase Session** - Always include auto-open functionality to watch scraping live
2. **Use Playwright for Navigation** - `page.goto()`, `page.waitForLoadState('networkidle')`
3. **Be Specific in act() Instructions** - Include identifying details (color, position, text)
4. **Wait Between Actions** - Add `await page.waitForLoadState('networkidle')` after dynamic actions
5. **Handle Pagination** - Use loops with a max iteration safety limit
6. **Type Safety** - Define clear Zod schemas matching the extracted data structure
7. **Database Integration** - Always write scraped events directly to raw_events table using import script

### Common Patterns

**Simple Single-Page Scrape:**
```typescript
await page.goto(url);
const data = await page.extract({
  instruction: "extract all products",
  schema: DataSchema
});
```

**With Navigation:**
```typescript
await page.goto(url);
await page.act("click 'Show All' button");
await page.waitForLoadState('networkidle');
const data = await page.extract({ ... });
```

**Pagination Loop:**
```typescript
const allData = [];
const maxPages = 10;

for (let i = 0; i < maxPages; i++) {
  const pageData = await page.extract({
    instruction: "extract items on current page",
    schema: DataSchema
  });
  
  allData.push(...pageData.items);
  
  // Check if next page exists
  try {
    await page.act("click next page button");
    await page.waitForLoadState('networkidle');
  } catch {
    break; // No more pages
  }
}
```

---

## Example Template (For Reference)

### Website: [Site Name]
**URL:** `https://example.com`

**Steps:**
1. Navigate to the events/calendar page
2. Scroll to load any lazy-loaded content
3. Click "Load More Events" if available (limit to 3 clicks)
4. Extract all visible events

**Venue Name:** 
[Actual venue name to hardcode as eventLocation]

**Standardized Output:**
- Event Name (string)
- Event Date (string) 
- Event Time (string, optional)
- Event Location (string) - **HARDCODED** venue name
- Event URL (string)