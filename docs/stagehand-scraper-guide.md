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

**Important:** The Event Location handling varies by scraper type:
- **Single Venue Scrapers** (e.g., MSG Calendar, Kings Theatre): MUST hardcode the venue name in BOTH the extraction instruction AND the schema
- **Multi-Venue Scrapers** (e.g., Prospect Park): Extract the actual subvenue from the page
- **ALWAYS include `eventLocation` in the Zod schema** to ensure validation passes
- **ALWAYS tell Stagehand explicitly** how to populate eventLocation in the extraction instruction

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

## Shared Utilities Architecture

All scrapers use shared utility functions from `src/lib/` to reduce code duplication and ensure consistency. **Always use these shared utilities instead of writing custom code.**

### Utility Modules

#### `src/lib/scraper-utils.js` - Initialization & Schema Creation
**Purpose:** Initialize Stagehand, create standardized schemas, and handle scrolling.

**Functions:**
- `initStagehand(options)` - Initialize Stagehand with Browserbase. Returns initialized instance.
  - `options.env` - Environment ('BROWSERBASE' or 'LOCAL', default: 'BROWSERBASE')
  - `options.verbose` - Verbosity level (default: 1)
- `openBrowserbaseSession(sessionId)` - Open Browserbase session URL in default browser
- `createStandardSchema(options)` - Create standardized event schema with Zod validation
  - `options.eventLocationDefault` - Default value for eventLocation field (for single-venue scrapers)
- `scrollToBottom(page, waitTime)` - Scroll page to bottom and wait for content to load
  - Default wait: 2000ms, minimum enforced

**When to use:** Use `initStagehand()` to start every scraper. Use `createStandardSchema()` with `eventLocationDefault` for single-venue scrapers (MSG, Kings Theatre, Brooklyn Museum). Use regular schema for multi-venue scrapers (Prospect Park).

#### `src/lib/scraper-actions.js` - Page Actions & Extraction
**Purpose:** Handle button clicking, event extraction, and pagination.

**Functions:**
- `clickButtonUntilGone(page, buttonText, maxClicks, options)` - Click a button repeatedly until it disappears
  - `buttonText` - Text or description of button to click
  - `maxClicks` - Maximum number of clicks to attempt
  - `options.scrollAfterClick` - Whether to scroll after each click (default: true)
  - `options.scrollWaitTime` - Time to wait after scrolling (default: 2000ms)
  - `options.loadWaitTime` - Time to wait for content to load (default: 2000ms)
- `extractEventsFromPage(page, instruction, schema, options)` - Extract events with error handling
  - Automatically captures screenshot on failure
  - Returns extraction result with events array
- `paginateThroughPages(page, extractFn, maxPages, options)` - Extract events from multiple pages
  - `extractFn` - Function to extract events from current page
  - `maxPages` - Maximum number of pages to process
  - `options.nextButtonText` - Text of next button (default: "Next events")
  - `options.pageWaitTime` - Time to wait after clicking next (default: 3000ms)
- `extractEventTimesFromPages(stagehand, events, options)` - Extract times from individual event pages
  - Used by Kings Theatre scraper for time extraction

**When to use:** Use `clickButtonUntilGone()` for "Load More" or "Show More" buttons. Use `extractEventsFromPage()` for all extractions. Use `paginateThroughPages()` for sites with explicit pagination buttons.

#### `src/lib/scraper-persistence.js` - Logging & Database Operations
**Purpose:** Log results, save to database, and handle errors.

**Functions:**
- `logScrapingResults(events, sourceName, options)` - Log scraping results with time validation
  - Reports events with/without times
  - Shows first few events as sample
- `saveEventsToDatabase(events, sourceName, options)` - Save events to database and run tests
  - Creates temporary JSON file
  - Calls import script
  - Runs scraper consistency tests
  - Cleans up temp file automatically
- `handleScraperError(error, page, sourceName)` - Handle errors with screenshot capture
  - Captures screenshot on error
  - Re-throws error for upstream handling

**When to use:** Always use `logScrapingResults()` before saving. Always use `saveEventsToDatabase()` instead of manual import. Wrap try-catch blocks with `handleScraperError()`.

### Migration Guide: Old Pattern → New Pattern

**Old Pattern (Don't Use):**
```typescript
const stagehand = new Stagehand({ env: "BROWSERBASE", verbose: 1 });
await stagehand.init();
const page = stagehand.page;
// ... custom code ...
const result = await page.extract({ ... });
// ... manual database save ...
```

**New Pattern (Use This):**
```typescript
import { initStagehand, openBrowserbaseSession, createStandardSchema } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const stagehand = await initStagehand({ env: 'BROWSERBASE' });
const page = stagehand.page;
openBrowserbaseSession(stagehand.browserbaseSessionID);
// ... use shared functions ...
await saveEventsToDatabase(events, 'source_name');
```

---

## Scraper Development Workflow

This project uses a **staging-to-production workflow** for developing new scrapers:

1. **Create scraper** → Save to `src/scrapers-staging/{venue_name}.js`
2. **Test manually** → `node src/scrapers-staging/{venue_name}.js`
3. **Validate** → `python src/test_staging_scraper.py {venue_name}`
4. **Promote** → `python src/promote_scraper.py {venue_name}`
5. **First production run** → `python src/run_pipeline.py --source {venue_name}`
6. **Verify data** → Check database tables
7. **Done!** → Scraper runs automatically with full pipeline

See `src/scrapers-staging/README.md` for detailed workflow instructions.

---

## Script Generation Guidelines

### Structure
Every generated script should follow this pattern using shared utilities:

```typescript
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with venue default for single-venue scrapers
const StandardEventSchema = createStandardSchema({ eventLocationDefault: '[VENUE_NAME]' });

export async function scrape[SiteName]() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in the default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the page
    await page.goto("[URL]");
    await page.waitForLoadState('networkidle');
    
    // Step 2: Scroll to bottom (if needed for lazy loading)
    await scrollToBottom(page);
    
    // Step 3: Click "Load More" button if needed (use unique logic)
    await clickButtonUntilGone(page, "[Button Text]", [maxClicks], {
      scrollAfterClick: true,
      scrollWaitTime: 2000,
      loadWaitTime: 2000
    });
    
    // Step 4: Extract all visible events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, time (if available), set eventLocation to '[VENUE_NAME]' for all events, and the URL by clicking on the event link to get the event page URL",
      StandardEventSchema,
      { sourceName: '[SOURCE_NAME]' }
    );

    // Add hardcoded venue name to all events (backup in case schema default fails)
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "[VENUE_NAME]"
    }));

    // Log results
    logScrapingResults(eventsWithLocation, '[Source Name]');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, '[source_name]');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, '[Source Name]');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrape[SiteName]().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrape[SiteName];
```

### Best Practices for Generated Code

1. **Auto-Open Browserbase Session** - Always include auto-open functionality to watch scraping live
2. **ALWAYS Use waitForLoadState('networkidle')** - **CRITICAL:** Must use `await page.waitForLoadState('networkidle')` after `page.goto()` to ensure page is fully loaded before scraping
3. **Be Specific in act() Instructions** - Include identifying details (color, position, text)
4. **Wait Between Actions** - Add `await page.waitForLoadState('networkidle')` after dynamic actions
5. **Handle Pagination** - Use loops with a max iteration safety limit
6. **Type Safety** - Define clear Zod schemas matching the extracted data structure
7. **Database Integration** - Always write scraped events directly to raw_events table using import script

### Common Patterns

**Simple Single-Page Scrape:**
```typescript
await page.goto(url);
await page.waitForLoadState('networkidle');
const result = await extractEventsFromPage(
  page,
  "Extract all visible events...",
  StandardEventSchema,
  { sourceName: 'source_name' }
);
```

**With "Load More" Button:**
```typescript
await page.goto(url);
await scrollToBottom(page);
await clickButtonUntilGone(page, "Load More Events", 5, {
  scrollAfterClick: true,
  scrollWaitTime: 2000,
  loadWaitTime: 2000
});
const result = await extractEventsFromPage(page, instruction, schema, options);
```

**Pagination with Explicit "Next" Button:**
```typescript
const allEvents = await paginateThroughPages(
  page,
  async () => {
    return await extractEventsFromPage(
      page,
      "Extract all visible events on the current page...",
      StandardEventSchema,
      { sourceName: 'source_name' }
    );
  },
  10, // maxPages
  {
    nextButtonText: "Next events",
    pageWaitTime: 3000
  }
);
```

**Real-World Example: MSG Calendar**
```typescript
// See src/scrapers/msg_calendar.js for complete working example
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Madison Square Garden' });

export async function scrapeMSGCalendar() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;
  
  try {
    openBrowserbaseSession(stagehand.browserbaseSessionID);
    await page.goto("https://www.msg.com/calendar?venues=KovZpZA7AAEA");
    await page.waitForLoadState('networkidle');
    await scrollToBottom(page);
    await clickButtonUntilGone(page, "Load More Events", 3);
    const result = await extractEventsFromPage(page, instruction, StandardEventSchema, { sourceName: 'msg_calendar' });
    logScrapingResults(result.events, 'MSG Calendar');
    await saveEventsToDatabase(result.events, 'msg_calendar');
    return { events: result.events };
  } catch (error) {
    await handleScraperError(error, page, 'MSG Calendar');
  } finally {
    await stagehand.close();
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