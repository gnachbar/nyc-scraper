# Contributing to NYC Events Scraper

Welcome! This guide will help you add new scrapers to the NYC Events Scraper project.

## Project Overview

NYC Events Scraper is a web scraping project that collects event data from various NYC venues and locations. The project uses:

- **Stagehand** - AI-powered browser automation for scraping
- **Browserbase** - Cloud browser sessions for remote scraping
- **Node.js** - For scraper implementations
- **Python** - For data processing, cleaning, validation, and self-healing
- **PostgreSQL** - For event data storage

## Architecture

The project uses a **shared utilities architecture** to ensure consistency and reduce code duplication:

- `src/lib/scraper-utils.js` - Stagehand initialization, schema creation, scrolling, screenshots
- `src/lib/scraper-actions.js` - Button clicking, event extraction, pagination
- `src/lib/scraper-persistence.js` - Logging, database operations, error handling

All scrapers follow standardized patterns and output a consistent schema.

---

## Quick Start: Creating a New Scraper (Automated)

The easiest way to create a new scraper is using the automated creation tool with built-in self-healing:

```bash
# Create a new scraper with automatic testing and self-healing
python src/create_scraper.py "Brooklyn Bowl" "https://www.brooklynbowl.com/events"

# Use click pagination template (for sites with "Load More" buttons)
python src/create_scraper.py "Barclays Center" "https://www.barclayscenter.com/events" --template click
```

This will:
1. **Generate** a scraper from a template
2. **Test** it automatically
3. **Diagnose** any issues using code analysis and Browserbase session logs
4. **Fix** common issues automatically (navigation timeouts, selector case sensitivity, etc.)
5. **Iterate** until success or max attempts reached

### Available Templates

- `scroll` (default) - For sites with infinite scroll or lazy loading
- `click` - For sites with "Load More" / "View More" buttons

### Self-Healing Capabilities

The automated workflow can detect and fix:

| Issue | Detection | Auto-Fix |
|-------|-----------|----------|
| Navigation timeout | "Timeout exceeded" in logs | Extended timeout, retry logic |
| Case-sensitive selectors | "button found after 0 clicks" | Make selectors case-insensitive |
| Missing Python modules | "ModuleNotFoundError" | Use venv Python path |
| No scroll events | Browserbase session analysis | Add scroll verification |
| Session crashes | "Target page closed" | Add health checks, batch extraction |

---

## Manual Scraper Creation

If you prefer to create scrapers manually:

### 1. Choose a Venue

Pick a NYC venue or location to scrape. Check `src/scrapers/` to see which venues are already covered.

### 2. Gather Information

Before coding, collect this information:

- **Website URL**: What's the events/calendar page URL?
- **Venue Name**: What should be displayed as the event location? (e.g., "Madison Square Garden")
- **Source Name**: Database identifier (lowercase with underscores, e.g., `msg_calendar`)
- **Page Type**: Does it use scroll loading or pagination buttons?

### 3. Create the Scraper (Staging)

Save your new scraper to `src/scrapers-staging/{source_name}.js` following this template:

```javascript
import { initStagehand, openBrowserbaseSession, createStandardSchema, scrollToBottom, capturePageScreenshot } from '../lib/scraper-utils.js';
import { extractEventsFromPage } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';

// Create standardized schema with venue default
const StandardEventSchema = createStandardSchema({ eventLocationDefault: '[VENUE_NAME]' });

export async function scrape[VenueName]() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Navigate with extended timeout and retry
    let navigationSuccess = false;
    for (let attempt = 1; attempt <= 3 && !navigationSuccess; attempt++) {
      try {
        console.log(`Navigation attempt ${attempt}/3...`);
        await page.goto("[URL]", { timeout: 60000, waitUntil: "domcontentloaded" });
        navigationSuccess = true;
      } catch (navError) {
        console.log(`Navigation attempt ${attempt} failed: ${navError.message}`);
        if (attempt === 3) throw navError;
        await page.waitForTimeout(5000);
      }
    }
    await page.waitForTimeout(3000);

    // Scroll to load lazy-loaded content
    await scrollToBottom(page);

    // Take screenshot for verification
    try {
      await capturePageScreenshot(page, '[source_name]');
    } catch (e) {
      console.log('Screenshot capture failed:', e.message);
    }

    // Extract all visible events
    const currentYear = new Date().getFullYear();
    const result = await extractEventsFromPage(
      page,
      `Extract all visible events. For each event, get:
       - eventName: the event title
       - eventDate: the date (add year ${currentYear} if not shown)
       - eventTime: the time if visible, otherwise empty string
       - eventUrl: the link to the event page (full URL)
       - eventLocation: set to '[VENUE_NAME]'
       - eventDescription: brief description if visible, otherwise empty string`,
      StandardEventSchema,
      { sourceName: '[source_name]' }
    );

    // Normalize URLs and add location
    const events = result.events.map(event => {
      let eventUrl = event.eventUrl || '';
      if (eventUrl && !eventUrl.startsWith('http')) {
        eventUrl = new URL(eventUrl, '[URL]').href;
      }
      if (!eventUrl) {
        eventUrl = '[URL]';
      }
      return {
        ...event,
        eventUrl,
        eventLocation: "[VENUE_NAME]"
      };
    });

    // Log results
    logScrapingResults(events, '[Venue Name]');

    // Save to database
    if (events.length > 0) {
      await saveEventsToDatabase(events, '[source_name]');
    } else {
      console.log("No events found!");
    }

    return { events };

  } catch (error) {
    await handleScraperError(error, page, '[Venue Name]');
  } finally {
    await stagehand.close();
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrape[VenueName]().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

export default scrape[VenueName];
```

### 4. Test and Heal

If your scraper has issues, use the self-healing tools:

```bash
# Diagnose issues
python src/create_scraper.py --diagnose [source_name]

# Run self-healing loop
python src/create_scraper.py --heal [source_name]
```

### 5. Promote to Production

Once your scraper works correctly:

```bash
python src/promote_scraper.py [source_name]
```

---

## Self-Healing Tools

### Diagnosis

Get a comprehensive diagnosis of scraper issues:

```bash
python src/diagnose_scraper.py [source_name]
```

This analyzes:
- Historical run data (success rate, days since last success)
- Scraper code (pagination method, patterns used)
- Comparison with similar working scrapers
- Browserbase session logs (scroll events, clicks, errors)

### Visual Self-Healer

Run the visual self-healing loop:

```bash
python src/visual_self_healer.py [source_name] --max-iterations 5
```

This iteratively:
1. Runs the scraper
2. Captures Browserbase session feedback
3. Takes screenshots
4. Diagnoses issues
5. Applies fixes
6. Repeats until success

### Browserbase Diagnostics

Analyze a specific Browserbase session:

```bash
node src/lib/browserbase-diagnostics.js [session_id]
```

Or via Python:

```bash
python src/browserbase_feedback.py [session_id]
```

---

## Best Practices

### Use Shared Utilities

**Always use** the shared utilities from `src/lib/`:
- `initStagehand()` - Instead of manual Stagehand initialization
- `createStandardSchema()` - Instead of custom Zod schemas
- `extractEventsFromPage()` - Instead of manual extraction
- `saveEventsToDatabase()` - Instead of manual database operations
- `handleScraperError()` - Instead of basic try-catch
- `capturePageScreenshot()` - For visual verification

### Navigation Best Practices

```javascript
// GOOD: Extended timeout, domcontentloaded, retry logic
await page.goto(url, { timeout: 60000, waitUntil: "domcontentloaded" });

// BAD: Default timeout, waiting for full load
await page.goto(url);  // May timeout on slow sites
```

### Button Selectors

```javascript
// GOOD: Case-insensitive regex selector
const button = await page.$('text=/view more events/i');

// BAD: Exact case match (may not find button)
const button = await page.$('text="View more events"');
```

### Standardized Output Schema

All scrapers must output events with this structure:

```typescript
{
  eventName: string,        // The name/title of the event
  eventDate: string,        // The date of the event
  eventTime: string,        // The time (empty string if not available)
  eventDescription: string, // Description (empty string if not available)
  eventLocation: string,    // HARDCODED venue name
  eventUrl: string          // URL to event details page
}
```

### Dynamic Year Handling

Always use the current year dynamically:

```javascript
// GOOD: Dynamic year
const currentYear = new Date().getFullYear();
const instruction = `Extract events, add year ${currentYear} if not shown`;

// BAD: Hardcoded year
const instruction = `Extract events, add year 2025 if not shown`;
```

---

## Troubleshooting

### "Navigation timeout"
- Use `waitUntil: "domcontentloaded"` instead of waiting for full load
- Increase timeout to 60000ms
- Add retry logic for transient failures

### "No events found"
- Take screenshot to verify page loaded
- Check extraction instruction is specific enough
- Add scrolling if content is lazy-loaded

### "Button not found after 0 clicks"
- Check button text case sensitivity
- Use case-insensitive selector: `text=/button text/i`
- Take screenshot to see actual button text

### "ModuleNotFoundError: No module named 'bs4'"
- Python is using system interpreter instead of venv
- Fixed automatically in latest scraper-persistence.js

### Browserbase Session Crashes
- Add session health checks between operations
- Extract in batches rather than all at once
- Use `capturePageScreenshot()` before extraction

---

## Directory Structure

```
src/
├── scrapers/              # Production scrapers
├── scrapers-staging/      # Development scrapers
├── lib/
│   ├── scraper-utils.js       # Core utilities
│   ├── scraper-actions.js     # Action utilities
│   ├── scraper-persistence.js # Data persistence
│   └── browserbase-diagnostics.js  # Session analysis
├── create_scraper.py      # Automated creation with self-healing
├── diagnose_scraper.py    # Scraper diagnosis
├── visual_self_healer.py  # Visual self-healing loop
├── browserbase_feedback.py # Python wrapper for BB diagnostics
├── promote_scraper.py     # Staging to production promotion
└── ...
```

---

## Resources

- **Stagehand Guide**: `docs/stagehand-scraper-guide.md`
- **Quality Plan**: `docs/SCRAPER_QUALITY_PLAN.md`
- **Example Scraper**: `src/scrapers/msg_calendar.js`

## Getting Help

If you run into issues:
1. Run diagnosis: `python src/diagnose_scraper.py [source_name]`
2. Check logs in `logs/scraper.log`
3. Review existing scrapers in `src/scrapers/`
4. Read Stagehand docs: https://docs.stagehand.dev/

Happy scraping! 🎭🎪🎸
