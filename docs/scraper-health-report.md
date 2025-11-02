## Scraper Health Report (last two runs)

- Recent runs analyzed:
  - 2025-11-01 23:55:37 (report: `data/output/pipeline_report_20251101_235537.json`)
  - 2025-11-01 23:50:08 (report: `data/output/pipeline_report_20251101_235008.json`)

Legend:
- Healthy = success on both runs
- Flaky = success on exactly one run
- Failing = failed on both runs
- Note: tests can fail independently; health is based on scraper success

### Overview
- Overall success: ✗ (both runs)
- Successful scrapers per run: 11/20 (both runs)
- Total events scraped: 437 (23:50), 537 (23:55)

### Per-scraper status

| Scraper | 23:50 success | 23:50 events | 23:55 success | 23:55 events | Health | Notes |
|---|---:|---:|---:|---:|---|---|
| kings_theatre | ✓ | 34 | ✓ | 34 | Healthy |  |
| msg_calendar | ✗ | 0 | ✓ | 145 | Flaky | Stagehand parse error on 23:50 |
| prospect_park | ✗ | 0 | ✗ | 0 | Failing | Browser/page closed both runs |
| brooklyn_museum | ✗ | 0 | ✗ | 0 | Failing | Browser/page closed both runs |
| public_theater | ✗ | 0 | ✗ | 0 | Failing | Browser/page closed both runs |
| brooklyn_paramount | ✗ | 0 | ✗ | 0 | Failing | Browser/page closed both runs |
| bric_house | ✓ | 16 | ✓ | 16 | Healthy |  |
| barclays_center | ✗ | 0 | ✗ | 0 | Failing | Browser/page closed, >15m on 23:50 |
| bam | ✗ | 0 | ✗ | 0 | Failing | Module not found (staging-only scraper) |
| lepistol | ✓ | 181 | ✓ | 181 | Healthy |  |
| roulette | ✓ | 26 | ✓ | 26 | Healthy | Tests failed both runs |
| crown_hill_theatre | ✓ | 8 | ✓ | 8 | Healthy | Tests failed both runs |
| soapbox_gallery | ✓ | 4 | ✓ | 4 | Healthy | Tests failed both runs |
| farm_one | ✓ | 5 | ✓ | 5 | Healthy |  |
| union_hall | ✗ | 0 | ✗ | 0 | Failing | Module not found (staging-only scraper) |
| bell_house | ✓ | 67 | ✓ | 67 | Healthy |  |
| littlefield | ✓ | 43 | ✓ | 43 | Healthy |  |
| shapeshifter_plus | ✗ | 0 | ✗ | 0 | Failing | Browser/page closed both runs |
| concerts_on_the_slope | ✓ | 8 | ✓ | 8 | Healthy |  |
| public_records | ✓ | 45 | ✗ | 0 | Flaky | Stagehand parse error on 23:55 |

### Key follow-ups
- Remove staging-only scrapers from production: `bam`, `union_hall`.
- Stabilize timeouts/session longevity on: `prospect_park`, `brooklyn_museum`, `public_theater`, `brooklyn_paramount`, `barclays_center`, `shapeshifter_plus`.
- Investigate Stagehand parse errors: `msg_calendar` (23:50), `public_records` (23:55).
- Review failing tests (despite scraper success): `roulette`, `crown_hill_theatre`, `soapbox_gallery`.
