## Relevant Files

- `src/run_pipeline.py` - Orchestrates scraping/import/post-processing. Integration point for classification and recurring flags.
- `src/import_scraped_data.py` - Imports scraper output into DB; hook to trigger classification and recurring detection post-import.
- `src/web/app.py` - Flask app routes and filters; update for new filters (recurring, category, new).
- `src/web/models.py` - SQLAlchemy models; add `category`, `category_confidence`, `is_recurring`, `recurrence_key`, optionally `first_seen_at`.
- `src/clean_events.py` - Data cleaning pipeline; now includes recurrence key calculation and recurring event detection post-import.
- `src/lib/recurrence_utils.py` - Utility for normalizing event titles into recurrence keys.
- `src/scripts/migrate_add_category_recurring.py` - DB migration for recurring events and category fields.
- `src/transforms/dates.js` - Date utilities; may aid pagination/latest-date checks.
- `src/lib/cache.py` - Generic cache utility; reuse for category cache (`data/cache/category_cache.json`).
- `src/lib/google_maps.py` - Reference for cache usage patterns.
- `src/lib/scraper-utils.js` - Shared scraper helpers; ensure standardized logging/metrics hooks.
- `src/lib/scraper-persistence.js` - Persistence helpers; ensure consistent error handling.
- `src/scrapers/*.js` - Production scrapers; apply logging/pagination/description improvements.
- `src/scrapers-staging/*.js` - Staging scrapers; apply patterns before promotion.
- `templates/index.html` - Sidebar filters UI for category and recurring toggles; "New" filter.
- `static/js/main.js` - Frontend filter toggling logic; hook into new filters.
- `docs/stagehand-scraper-guide.md` - Required flow for new scrapers and promotion.
- `docs/next-scrapers-to-build.md` - Source list for new scrapers to implement.
- `tests`: `src/test_scrapers.py`, `src/test_staging_scraper.py`, `src/test_scraper_consistency.py`, `src/test_database.py` - Extend for new fields and behaviors.

New files to create:

- `src/lib/category_classifier.py` - OpenAI-powered classifier with caching and heuristics fallback.
- `src/scripts/audit_pagination.py` - Report latest date per scraper and pagination completeness.
- `.github/workflows/scrape.yml` - Scheduled pipeline run with secrets and artifact uploads.

New files created:

- `src/scripts/migrate_add_category_recurring.py` - DB migration adding category/recurring fields (created, migration run).
- `src/lib/recurrence_utils.py` - Utility for normalizing event titles into recurrence keys (created).

### Notes

- Use `pytest` for backend tests: `pytest -q` (optionally filter with `-k`).
- Node-based scraper smoke tests can be run via existing test scripts in `src/app/`.
- Staging-first for new scrapers; promote only after passing manual and automated checks.

## Tasks

- [ ] **1.0 Simplify and standardize scrapers (baseline Stagehand/Browserbase template)**
  - [x] 1.1 barclays_center
  - [x] 1.2 bell_house
  - [x] 1.3 bric_house
  - [x] 1.4 brooklyn_museum
  - [x] 1.5 brooklyn_paramount
  - [x] 1.6 concerts_on_the_slope
  - [x] 1.7 crown_hill_theatre
  - [ ] 1.8 farm_one
  - [ ] 1.9 kings_theatre
  - [ ] 1.10 lepistol
  - [ ] 1.11 littlefield
  - [ ] 1.12 msg_calendar
  - [ ] 1.13 prospect_park
  - [ ] 1.14 public_records
  - [ ] 1.15 public_theater
  - [ ] 1.16 roulette
  - [ ] 1.17 shapeshifter_plus
  - [ ] 1.18 soapbox_gallery
- [ ] **2.0 Production fixes per scraper (based on last two runs)**
  - [ ] 2.1 msg_calendar: resolve Stagehand parse error; verify extraction schema; ensure `waitForLoadState('networkidle')` after `goto()`
  - [ ] 2.2 prospect_park: fix session closures; add robust waits; verify pagination button text; cap pages to avoid session timeout
  - [ ] 2.3 brooklyn_museum: fix session closures; add robust waits; confirm selectors; avoid long idle periods
  - [ ] 2.4 public_theater: fix session closures; add robust waits; confirm selectors
  - [ ] 2.5 brooklyn_paramount: fix session closures; add waits after calendar actions; cap months/pages
  - [ ] 2.6 barclays_center: reduce load-more cycles to stay under 15 minutes; add fallback timeout after clicks
  - [ ] 2.7 shapeshifter_plus: stabilize pagination waits; consider fewer attempts; address session closure
  - [ ] 2.8 public_records: investigate Stagehand parse error; validate instruction and schema
  - [ ] 2.9 roulette: address failing tests (adjust expectations or data shape)
  - [ ] 2.10 crown_hill_theatre: address failing tests (adjust expectations or data shape)
  - [ ] 2.11 soapbox_gallery: address failing tests (adjust expectations or data shape)
  - [ ] 2.12 Pipeline: remove staging-only scrapers from production run list (`bam`, `union_hall`) in `src/run_pipeline.py`
  - [ ] 2.13 Validate healthy scrapers continue to pass: kings_theatre, bric_house, lepistol, farm_one, bell_house, littlefield, concerts_on_the_slope
- [ ] **3.0 Implement recurring events flag (same-title across dates) and sidebar toggle**
  - [x] 3.1 Migration: add `is_recurring` (bool), `recurrence_key` (text) to events table
  - [x] 3.2 Define `recurrence_key = normalize(title)` function (lowercase, trim, collapse whitespace, strip punctuation)
  - [x] 3.3 Post-import job: group by `(venue, recurrence_key)` and set `is_recurring = true` when count of distinct dates ≥ 2
  - [x] 3.4 Backfill existing events to set flags accordingly
  - [x] 3.5 UI: add sidebar toggle "Recurring" (on/off) in `templates/index.html` and wire in `static/js/main.js`
  - [x] 3.6 Backend: filter param handling in `src/web/app.py` for recurring toggle
  - [x] 3.7 Tests: DB grouping correctness; UI filter integration
- [ ] **4.0 Add event category classification via OpenAI API with caching and heuristics fallback**
  - [ ] 4.1 Migration: add `category` (enum/text) and `category_confidence` (float) to events table
  - [ ] 4.2 Define category set: {Concert, Comedy, Talk, Theater, Dance, Exhibit, Workshop, Other}
  - [ ] 4.3 Caching design: use `src/lib/cache.py` to persist `data/cache/category_cache.json`
    - Key: `sha1(normalize(title) + '|' + venue + '|' + normalize(description[:500]))`
    - Value: `{category, confidence, model, timestamp}`
    - Invalidation: cache miss if title/venue/description segment changes; optional TTL (e.g., 90 days)
    - Batch classify new keys only; log cache hit rate
  - [ ] 4.4 Implement `src/lib/category_classifier.py` using OpenAI with retries and rate limiting
  - [ ] 4.5 Heuristics fallback (no API): venue-specific and global keywords when API fails
  - [ ] 4.6 Pipeline integration: after import, classify uncached events and write fields to DB
  - [ ] 4.7 Config: add `OPENAI_API_KEY` support (env var) and docs for secrets
  - [ ] 4.8 Tests: golden cases for each category; cache behavior; fallback path
- [ ] **5.0 Improve description extraction fidelity across scrapers**
  - [ ] 5.1 Define extraction order: event detail page main content → list card long text → meta/OG description → fallback synopsis
  - [ ] 5.2 Implement shared sanitize/normalize (strip HTML, normalize whitespace, cap length) utility
  - [ ] 5.3 Update priority scrapers (MSG, Prospect Park, Kings, Public Records) to use improved extraction
  - [ ] 5.4 Add tests asserting non-empty, meaningful descriptions and no boilerplate-only content
- [ ] **6.0 Validate pagination coverage and latest-date completeness per scraper**
  - [ ] 6.1 Instrument scrapers to record `max_date_seen` and `pagination_complete` (true/false)
  - [ ] 6.2 Create `src/scripts/audit_pagination.py` to report per-scraper latest date and gaps vs horizon (e.g., 6 months)
  - [ ] 6.3 Fix scrapers with load-more/infinite scroll to loop until exhaustion using `waitForLoadState('networkidle')`
  - [ ] 6.4 Persist audit report to `logs/` and surface summary in pipeline output
- [ ] **7.0 Verify "New" filter behavior for newly added scrapers**
  - [ ] 7.1 Define "New" semantics: events with `first_seen_at` within N days (e.g., 7), independent of venue
  - [ ] 7.2 Migration: add `first_seen_at` (timestamp) defaulted at import time if absent
  - [ ] 7.3 Backend: support `?filter=new` param and query by `first_seen_at`
  - [ ] 7.4 UI: ensure "New" toggle correctly filters; add small badge to event cards
  - [ ] 7.5 Tests: create synthetic events to validate filtering boundaries
- [ ] **8.0 Add next priority scrapers from docs/next-scrapers-to-build.md**
  - [ ] 8.1 Target set: Shapeshifter Plus (promote from staging), Concerts on the Slope, Public Records (improve/complete), Eastville Comedy, 333 Lounge, Barbès
  - [ ] 8.2 For each venue: follow `docs/stagehand-scraper-guide.md` strictly; save to `scrapers-staging/`
  - [ ] 8.3 Manual test in staging (2 BrowserBase sessions), then promote to `src/scrapers/`
  - [ ] 8.4 Ensure category classification and description extraction are applied
  - [ ] 8.5 Add venue config in `src/config/index.js` and update docs
- [ ] **9.0 Harden sandbox → production promotion flow with auto-cleanup**
  - [ ] 9.1 Enhance `src/promote_scraper.py` to enforce: move file to prod, update config, delete from `scrapers-staging/`
  - [ ] 9.2 Add validation checks (lint, smoke run, event count > 0) before promotion proceeds
  - [ ] 9.3 Document promotion checklist in `src/scrapers-staging/staging-README.md`
- [ ] **10.0 Schedule pipeline runs via GitHub Actions cron**
  - [ ] 10.1 Create `.github/workflows/scrape.yml` with nightly and hourly schedules
  - [ ] 10.2 Setup secrets: `OPENAI_API_KEY`, Browser automation keys, any DB paths
  - [ ] 10.3 Job steps: checkout, setup Python/Node, install deps, run `python src/run_pipeline.py`, run tests, upload logs
  - [ ] 10.4 Add concurrency and timeout controls; post summary to workflow logs
- [ ] **11.0 Optimize recurring event detection architecture**
  - [ ] 11.1 Add database index: `CREATE INDEX idx_recurring_lookup ON clean_events(display_venue, recurrence_key, start_time)`
  - [ ] 11.2 Make `mark_recurring_events()` accept optional `source` parameter for per-source scoping
  - [ ] 11.3 Add metrics/logging: log top 10 recurring patterns with venue, key, and date count
  - [ ] 11.4 Move `mark_recurring_events()` call from `clean_events.py` to `run_pipeline.py` to separate cleaning from enrichment concerns
