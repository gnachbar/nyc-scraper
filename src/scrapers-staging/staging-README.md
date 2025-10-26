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

## Current Staging Scrapers

### public_theater.js
- **Status:** ✅ Promoted to production
- **Created:** October 2024
- **Notes:** Scrapes The Public Theater calendar events (200 events)
- **Result:** Successfully running in production
- **BrowserBase Sessions:** 4 (iterated on extraction instructions and date parsing)

