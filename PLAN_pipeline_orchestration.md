# Plan: Data Pipeline Orchestration

## Goal
Create an end-to-end data pipeline orchestration script that runs all scrapers sequentially with automatic cleaning, validation, and comprehensive reporting.

## Current State
- Each Node.js scraper (kings_theatre.js, msg_calendar.js, prospect_park.js) runs independently
- Scrapers automatically import to raw_events table
- Manual steps required: run cleaning, test scrapers
- No unified reporting or error handling

## Proposed Solution
Create `src/run_pipeline.py` that orchestrates the entire data pipeline with:
- Sequential scraper execution
- Automatic cleaning after each scraper
- Automatic validation after each scraper
- Comprehensive error handling (continue on failure)
- Dual output format (JSON + human-readable)
- Proper exit codes for GitHub Actions

## Implementation Steps

### Step 1: Create Orchestration Script (`src/run_pipeline.py`)

**File structure:**
```python
#!/usr/bin/env python3
"""
Data Pipeline Orchestration Script

Runs all scrapers sequentially with automatic cleaning and validation.
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class ScraperResult:
    source: str
    success: bool
    events_scraped: int
    events_cleaned: int
    test_passed: bool
    error_message: Optional[str]
    duration_seconds: float

@dataclass
class PipelineReport:
    timestamp: str
    overall_success: bool
    total_duration: float
    scrapers: List[ScraperResult]
    summary: Dict[str, Any]

def run_scraper(source: str) -> ScraperResult:
    """Run a single scraper and return results"""
    # Implementation here
    
def run_cleaning(source: str) -> bool:
    """Run cleaning script for a source"""
    # Implementation here
    
def run_tests(source: str) -> bool:
    """Run test script for a source"""
    # Implementation here
    
def generate_reports(report: PipelineReport):
    """Generate JSON and console reports"""
    # Implementation here

def main():
    """Main orchestration logic"""
    # Implementation here
```

**Key functions:**
1. `run_scraper(source)` - Run Node.js scraper via subprocess, return ScraperResult
2. `run_cleaning(source)` - Run `python3 src/clean_events.py --source {source}`
3. `run_tests(source)` - Run `python3 src/test_scrapers.py --source {source}`
4. `generate_reports(report)` - Create JSON file + console output
5. `main()` - Orchestrate all scrapers, collect results, generate reports

**Features:**
- Error handling: Try-catch around each scraper
- Continue on failure: Don't stop pipeline if one scraper fails
- Metrics collection: Track events scraped, cleaned, duration
- Progress logging: Clear console output showing pipeline progress
- Exit codes: 0 if all successful, 1 if any failures

### Step 2: Command-Line Interface

Add CLI arguments:
- `--source {source}` - Run single scraper (optional, default: all)
- `--skip-cleaning` - Skip cleaning step (for testing)
- `--skip-tests` - Skip validation step (for faster runs)
- `--output-dir {dir}` - Specify report output directory

### Step 3: Output Files

Generate in `data/output/`:
- `pipeline_report_{timestamp}.json` - Structured JSON report
- `pipeline_summary_{timestamp}.md` - Human-readable markdown (optional)

**JSON structure:**
```json
{
  "timestamp": "2025-10-25T18:30:00",
  "overall_success": true,
  "total_duration": 245.3,
  "scrapers": [
    {
      "source": "kings_theatre",
      "success": true,
      "events_scraped": 40,
      "events_cleaned": 40,
      "test_passed": true,
      "error_message": null,
      "duration_seconds": 82.5
    },
    ...
  ],
  "summary": {
    "total_events_scraped": 224,
    "total_events_cleaned": 224,
    "successful_scrapers": 3,
    "failed_scrapers": 0
  }
}
```

### Step 4: Integration with Existing Code

**No changes needed to:**
- Existing Node.js scrapers (they already auto-import)
- `src/clean_events.py` (works as-is)
- `src/test_scrapers.py` (works as-is)
- `src/import_scraped_data.py` (called by scrapers)

**The orchestration script simply calls these existing tools in sequence.**

### Step 5: Local Testing

Test pipeline locally:
```bash
# Test with all scrapers
python3 src/run_pipeline.py

# Test with single scraper
python3 src/run_pipeline.py --source msg_calendar

# Test with dry-run (skip actual scraping)
python3 src/run_pipeline.py --skip-cleaning --skip-tests
```

### Step 6: GitHub Actions Integration

Update `.github/workflows/scrape.yml` to use the pipeline script:
```yaml
name: Scrape Events

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2 AM
  workflow_dispatch:  # Manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - uses: actions/setup-python@v4
      - run: npm install
      - run: pip install -r requirements.txt
      - run: python3 src/run_pipeline.py
        env:
          BROWSERBASE_API_KEY: ${{ secrets.BROWSERBASE_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
      - uses: actions/upload-artifact@v3
        with:
          name: pipeline-report
          path: data/output/pipeline_report_*.json
```

## Success Criteria

1. Pipeline runs all scrapers sequentially
2. Automatic cleaning runs after each scraper
3. Automatic validation runs after each scraper
4. Pipeline continues even if one scraper fails
5. Comprehensive reports generated (JSON + console)
6. Works both locally and in GitHub Actions
7. Exit codes properly indicate success/failure

## Files to Create/Modify

**Create:**
- `src/run_pipeline.py` - Main orchestration script

**Modify:**
- `.github/workflows/scrape.yml` - Use run_pipeline.py as entry point
- `tasks/tasks-0001-prd-nyc-events-scraping-app.md` - Update task 9.6

**No changes needed:**
- Existing Node.js scrapers
- Existing Python scripts (clean_events.py, test_scrapers.py, import_scraped_data.py)

