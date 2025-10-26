## Relevant Files

- `src/lib/scraper-utils.js` - NEW: Shared utility functions for all scrapers (initialization, browser session, schema creation, scrolling)
- `src/lib/scraper-actions.js` - NEW: Shared action helpers (button clicking, extraction, validation)
- `src/lib/scraper-persistence.js` - NEW: Shared output and database persistence functions (logging, saving, error handling)
- `src/scrapers/kings_theatre.js` - MODIFY: Refactor to use shared utilities
- `src/scrapers/msg_calendar.js` - MODIFY: Refactor to use shared utilities
- `src/scrapers/prospect_park.js` - MODIFY: Refactor to use shared utilities
- `src/scrapers/brooklyn_museum.js` - MODIFY: Refactor to use shared utilities
- `docs/stagehand-scraper-guide.md` - MODIFY: Update to reference shared utilities

### Notes

- All scrapers currently have 60-80% duplicate code across initialization, extraction, logging, and database persistence
- Refactoring will reduce code duplication, improve maintainability, and make it easier to add new scrapers
- Each scraper will retain its unique navigation/extraction logic while using shared infrastructure
- Shared functions should be generic enough to support different scraper patterns (single-page, pagination, load-more buttons)

## Tasks

- [x] 1.0 Create Shared Utilities Module (Foundation)
  - [x] 1.1 Create `src/lib/scraper-utils.js` file
  - [x] 1.2 Implement `initStagehand(options)` - Initialize Stagehand with Browserbase, return stagehand instance
  - [x] 1.3 Implement `openBrowserbaseSession(sessionId)` - Auto-open session URL in browser with platform detection
  - [x] 1.4 Implement `createStandardSchema(options)` - Generate StandardEventSchema with configurable eventLocation default
  - [x] 1.5 Implement `scrollToBottom(page, waitTime)` - Scroll page to bottom with configurable wait time
  - [x] 1.6 Add JSDoc documentation for all functions in scraper-utils.js
- [ ] 2.0 Create Shared Action Helpers Module
  - [ ] 2.1 Create `src/lib/scraper-actions.js` file
  - [ ] 2.2 Implement `clickButtonUntilGone(page, buttonText, maxClicks, options)` - Generic "load more" button clicking with retry logic and scroll-after-click option
  - [ ] 2.3 Implement `extractEventsFromPage(page, instruction, schema, options)` - Wrapper for page.extract() with error handling and screenshot on failure
  - [ ] 2.4 Implement `validateExtractionResult(result, options)` - Check if extraction succeeded, return validation object
  - [ ] 2.5 Implement `extractEventTimesFromPages(stagehand, events, options)` - Kings Theatre-specific: iterate through event URLs and extract times
  - [ ] 2.6 Implement `paginateThroughPages(page, extractFn, maxPages, options)` - Prospect Park-specific: click "Next" and accumulate results
  - [ ] 2.7 Add JSDoc documentation for all functions in scraper-actions.js
- [ ] 3.0 Create Shared Persistence Module
  - [ ] 3.1 Create `src/lib/scraper-persistence.js` file
  - [ ] 3.2 Implement `logScrapingResults(events, sourceName, options)` - Display results summary with time validation warnings
  - [ ] 3.3 Implement `saveEventsToDatabase(events, sourceName, options)` - Write temp file, call import script, run tests, cleanup temp file
  - [ ] 3.4 Implement `handleScraperError(error, page, sourceName)` - Standardized error handling with screenshot capture
  - [ ] 3.5 Add JSDoc documentation for all functions in scraper-persistence.js
- [ ] 4.0 Refactor Existing Scrapers to Use Shared Functions
  - [ ] 4.1 Refactor `kings_theatre.js` - Replace duplicate code with shared function calls, keep unique time extraction logic
  - [ ] 4.2 Refactor `msg_calendar.js` - Replace duplicate code with shared function calls, keep unique "Load More Events" logic
  - [ ] 4.3 Refactor `prospect_park.js` - Replace duplicate code with shared function calls, use `paginateThroughPages()` helper
  - [ ] 4.4 Refactor `brooklyn_museum.js` - Replace duplicate code with shared function calls, keep unique "Show more events" logic
  - [ ] 4.5 Verify all scrapers still export their main function and support direct execution
- [ ] 5.0 Testing & Validation
  - [ ] 5.1 Run `kings_theatre.js` end-to-end and verify events are scraped correctly
  - [ ] 5.2 Run `msg_calendar.js` end-to-end and verify events are scraped correctly
  - [ ] 5.3 Run `prospect_park.js` end-to-end and verify events are scraped correctly
  - [ ] 5.4 Run `brooklyn_museum.js` end-to-end and verify events are scraped correctly
  - [ ] 5.5 Run full pipeline (`python src/run_pipeline.py`) and verify all scrapers work together
  - [ ] 5.6 Run scraper consistency tests (`python src/test_scraper_consistency.py`) and verify all pass
- [ ] 6.0 Documentation & Cleanup
  - [ ] 6.1 Update `docs/stagehand-scraper-guide.md` to include shared utilities section
  - [ ] 6.2 Add examples of using shared functions to the guide
  - [ ] 6.3 Create inline code comments explaining shared function usage in one refactored scraper as a reference
  - [ ] 6.4 Commit all changes with descriptive commit messages
  - [ ] 6.5 Update project README if necessary to mention shared utilities architecture

