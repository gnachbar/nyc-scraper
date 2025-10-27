# Scrapers Staging Directory

This directory contains work-in-progress scrapers that are being developed and tested before being promoted to production.

## Purpose

The staging directory allows you to:
- Develop new scrapers without affecting production pipeline
- Test and validate scrapers before they're added to the main pipeline
- Iterate on scraper implementations safely

## Workflow

**Goal: 2 BrowserBase Sessions** (one for manual test, one for promotion)

**Note:** It's perfectly fine to run multiple sessions while testing/iterating on the scraper. The "2 sessions" target is when everything works correctly. If you need to debug or fix issues, you may run more sessions - that's expected during development!

### 1. Create New Scraper

Follow the guide in `docs/stagehand-scraper-guide.md` to generate a new scraper. Save it to this directory:

```bash
# Save your new scraper as:
src/scrapers-staging/{venue_name}.js
```

**Important**: Use the shared utilities from `src/lib/` (scraper-utils.js, scraper-actions.js, scraper-persistence.js) and follow the standard schema patterns.

### 2. Prepare Configurations

Update all configuration files so the scraper can work properly:

```bash
python src/promote_scraper.py {venue_name} --prepare
```

This updates:
- `import_scraped_data.py` - adds source to valid sources
- `clean_events.py` - adds source to clean pipeline
- `test_scrapers.py` - adds source to test suite
- `run_pipeline.py` - adds source to pipeline

**This does NOT promote the scraper** - it just prepares configs for testing.

### 3. Test Manually (FIRST BrowserBase Session)

Now run the scraper to test it:

```bash
node src/scrapers-staging/{venue_name}.js
```

This will:
- Scrape events using Browserbase
- Save to database
- Run basic tests

**Expected Results:** Should successfully scrape and import events.

**Note:** If you encounter issues (extraction fails, wrong data, etc.), you can run this multiple times while debugging. Each run creates a new Browserbase session.

### 4. Promote to Production (SECOND BrowserBase Session)

Once manual test succeeds, promote the scraper:

```bash
python src/promote_scraper.py {venue_name}
```

This will:
- **Run validation tests** (schema, instructions, location handling, etc.)
- **Move scraper** from `scrapers-staging/` to `scrapers/`
- **Run first production test** (scrape → clean → test) automatically

**Expected Results:** Full pipeline run successfully (scrape + clean + test).

### 5. Done!

The scraper is now in production and will run automatically with the full pipeline!

**Target: 2 BrowserBase Sessions**
- Session 1: Manual test after configuration
- Session 2: Promotion (validation + first production run)

**Reality:** You may run more sessions while:
- Debugging extraction issues
- Fixing date/time parsing
- Adjusting extraction instructions
- Testing different button clicking strategies
- That's totally normal! The goal is to get it down to 2 sessions when everything works correctly.

## Naming Convention

- Use lowercase with underscores: `{venue_name}.js`
- Examples: `kings_theatre.js`, `msg_calendar.js`, `prospect_park.js`

## Standards

All scrapers must:
- Use shared utilities from `src/lib/`
- Output standardized schema (eventName, eventDate, eventTime, eventLocation, eventUrl)
- Handle errors gracefully with screenshots
- Save to database using saveEventsToDatabase()
- Run tests using run_scraper_consistency()

## Common Issues & Best Practices

### Page Loading

**ALWAYS use `waitForLoadState('networkidle')` after `page.goto()`**:

```javascript
await page.goto("https://example.com/shows");
await page.waitForLoadState('networkidle');
```

**Why:** This ensures the page is fully loaded before proceeding. Without it, the first scraper run often fails because:
- JavaScript hasn't finished executing
- AJAX calls haven't completed
- Content hasn't rendered yet

**Exception:** If `networkidle` times out (exceeds 30 seconds), the page may have continuous network activity. In this case, use:
```javascript
await page.goto("https://example.com/shows");
await page.waitForTimeout(3000); // Wait 3 seconds for initial load
```

But this should be rare - most sites work fine with `networkidle`.

### Date Formatting

**ALWAYS include the YEAR** in extracted dates:
- ✅ Good: "Monday, October 27, 2025"
- ✅ Good: "MON OCT 27 2025"
- ❌ Bad: "MON 27 OCT" (missing year)

The database import script needs a full date to parse correctly.

### URL Extraction

**ALWAYS extract complete URLs**:
- ✅ Good: "https://www.ticketmaster.com/event/123456"
- ❌ Bad: "0-338" or "/events/123"

Use relative URL logic if needed to convert to absolute URLs.

## Current Staging Scrapers

### lepistol.js
- **Status:** 🆕 Testing
- **Created:** January 2025
- **Notes:** Scrapes Le Pistol weekly recurring events. Uses new `convertWeeklyToDatedEvents()` utility to convert weekly schedule into individual dated events for the next 6 months
- **Special Features:** Handles expandable day sections, generates future dated events from weekly recurring schedule
- **BrowserBase Sessions:** 0 (not yet tested)

### public_theater.js
- **Status:** ✅ Promoted to production
- **Created:** October 2024
- **Notes:** Scrapes The Public Theater calendar events (200 events)
- **Result:** Successfully running in production
- **BrowserBase Sessions:** 4 (iterated on extraction instructions and date parsing)

