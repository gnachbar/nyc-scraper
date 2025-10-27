# Contributing to NYC Events Scraper

Welcome! This guide will help you add new scrapers to the NYC Events Scraper project.

## Project Overview

NYC Events Scraper is a web scraping project that collects event data from various NYC venues and locations. The project uses:

- **Stagehand** - AI-powered browser automation for scraping
- **Browserbase** - Cloud browser sessions for remote scraping
- **Node.js** - For scraper implementations
- **Python** - For data processing, cleaning, and validation
- **PostgreSQL** - For event data storage

## Architecture

The project uses a **shared utilities architecture** to ensure consistency and reduce code duplication:

- `src/lib/scraper-utils.js` - Stagehand initialization, schema creation, scrolling
- `src/lib/scraper-actions.js` - Button clicking, event extraction, pagination
- `src/lib/scraper-persistence.js` - Logging, database operations, error handling

All scrapers follow standardized patterns and output a consistent schema.

## Quick Start: Adding a New Scraper

### 1. Choose a Venue

Pick a NYC venue or location to scrape. Check `src/scrapers/` to see which venues are already covered.

### 2. Gather Information

Before coding, collect this information:

- **Website URL**: What's the events/calendar page URL?
- **Venue Name**: What should be displayed as the event location? (e.g., "Madison Square Garden")
- **Source Name**: Database identifier (lowercase with underscores, e.g., `msg_calendar`)
- **Scraping Steps**: How should we navigate the page? (e.g., "Navigate to calendar → Scroll down → Click 'Load More' → Extract events")

### 3. Create the Scraper (Staging)

Save your new scraper to `src/scrapers-staging/{venue_name}.js` following this template:

```javascript
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom } from '../lib/scraper-utils.js';
import { clickButtonUntilGone, extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with venue default
const StandardEventSchema = createStandardSchema({ eventLocationDefault: '[VENUE_NAME]' });

export async function scrape[VenueName]() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session for live viewing
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Navigate to the page
    await page.goto("[URL]");
    await page.waitForLoadState('networkidle');
    
    // Scroll to load lazy-loaded content
    await scrollToBottom(page);
    
    // Click "Load More" button if needed
    await clickButtonUntilGone(page, "[Button Text]", 5, {
      scrollAfterClick: true,
      scrollWaitTime: 2000,
      loadWaitTime: 2000
    });
    
    // Extract all visible events
    const result = await extractEventsFromPage(
      page,
      "Extract all visible events. For each event, get the event name, date, time (if available), set eventLocation to '[VENUE_NAME]' for all events, and the URL by clicking on the event link to get the event page URL",
      StandardEventSchema,
      { sourceName: '[source_name]' }
    );

    // Add hardcoded venue name to all events
    const eventsWithLocation = result.events.map(event => ({
      ...event,
      eventLocation: "[VENUE_NAME]"
    }));

    // Log results
    logScrapingResults(eventsWithLocation, '[Venue Name]');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, '[source_name]');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, '[Venue Name]');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrape[VenueName]().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrape[VenueName];
```

### 4. Prepare Configuration Files

Update configuration files so the scraper can be tested:

```bash
python src/promote_scraper.py {venue_name} --prepare
```

This adds your scraper to:
- Import script (`src/import_scraped_data.py`)
- Clean script (`src/clean_events.py`)
- Test script (`src/test_scrapers.py`)
- Pipeline config (`src/run_pipeline.py`)

**Note:** This does NOT promote the scraper - it just prepares configs for testing.

### 5. Test Manually

Run your scraper to verify it works:

```bash
node src/scrapers-staging/{venue_name}.js
```

This will:
- Open a Browserbase session (watch live in your browser)
- Scrape events from the website
- Save events to the database
- Run basic consistency tests

**Expected Result:** Events successfully scraped and imported into `raw_events` table.

### 6. Promote to Production

Once your scraper works correctly, promote it to production:

```bash
python src/promote_scraper.py {venue_name}
```

This will:
- Run validation tests (schema, instructions, location handling)
- Move scraper from `scrapers-staging/` to `scrapers/`
- Run first production test (scrape → clean → test pipeline)

**Expected Result:** Full pipeline runs successfully!

### 7. Done!

Your scraper is now in production and will run automatically with the full pipeline!

## Best Practices

### Use Shared Utilities

**Always use** the shared utilities from `src/lib/`:
- `initStagehand()` - Instead of manual Stagehand initialization
- `createStandardSchema()` - Instead of custom Zod schemas
- `extractEventsFromPage()` - Instead of manual extraction
- `saveEventsToDatabase()` - Instead of manual database operations
- `handleScraperError()` - Instead of basic try-catch

### Standardized Output Schema

All scrapers must output events with this structure:

```typescript
{
  eventName: string,      // The name/title of the event
  eventDate: string,      // The date of the event
  eventTime: string,      // The time of the event (optional)
  eventLocation: string,  // HARDCODED venue name
  eventUrl: string        // URL to event details page
}
```

### Event Location Handling

**Single Venue Scrapers** (e.g., MSG, Kings Theatre):
- MUST hardcode the venue name in BOTH the extraction instruction AND the schema
- Use `createStandardSchema({ eventLocationDefault: 'Venue Name' })`
- Add hardcoded location in post-processing: `eventLocation: "Venue Name"`

**Multi-Venue Scrapers** (e.g., Prospect Park):
- Extract the actual subvenue from the page
- Still include `eventLocation` in the schema

### Error Handling

Always wrap your scraper logic in try-catch and use `handleScraperError()`:

```javascript
try {
  // ... scraper logic ...
} catch (error) {
  await handleScraperError(error, page, 'Venue Name');
} finally {
  await stagehand.close();
}
```

### Debugging Tips

1. **Watch Live**: Browserbase sessions open automatically - watch your scraper run in real-time
2. **Take Screenshots**: Use `await page.screenshot()` to debug extraction issues
3. **Check Database**: Query `raw_events` table to verify data was saved
4. **Check Logs**: See `logs/scraper.log` for detailed logs

## Example: Working Scraper

Check out `src/scrapers/msg_calendar.js` for a complete working example that follows all best practices.

## Troubleshooting

### "No events found"
- Check extraction instruction is specific enough
- Verify elements are visible on the page
- Add scrolling/waiting steps if content is lazy-loaded

### "Schema validation failed"
- Ensure all required fields are extracted
- Check field types match schema (string, number, etc.)
- Verify URLs are absolute (start with http:// or https://)

### "Button click failed"
- Make button text more specific in instruction
- Add unique identifiers (color, position, nearby text)
- Check if button is visible/clickable

### Browserbase Session Issues
- Check Browserbase API key is set: `export BROWSERBASE_API_KEY=your_key`
- Verify API key has credits available
- Check network connectivity

## Resources

- **Stagehand Guide**: `docs/stagehand-scraper-guide.md` - Detailed guide for using Stagehand
- **Staging README**: `src/scrapers-staging/README.md` - Staging workflow details
- **Main README**: `README.md` - Project overview and structure

## Getting Help

If you run into issues:
1. Check the logs in `logs/scraper.log`
2. Review existing scrapers in `src/scrapers/` for patterns
3. Read the Stagehand documentation: https://docs.stagehand.dev/

## Next Steps

Once your scraper is in production:
- Monitor it in the main pipeline runs
- Check cleaned data in `clean_events` table
- Verify events appear in the web app at `http://localhost:5001`

Happy scraping! 🎭🎪🎸

