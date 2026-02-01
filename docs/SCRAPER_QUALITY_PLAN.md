# Scraper Quality Assurance Plan

## The Core Problem

We need to distinguish between:
1. **Scraper failure**: Pagination stopped, timeout, extraction error
2. **Venue limitation**: Site only posts events X months ahead (expected behavior)

## Solution: Venue Baseline + Anomaly Detection

### 1. Establish Venue Baselines

Create a configuration file that tracks each venue's expected behavior:

```yaml
# src/config/venue_baselines.yaml
venues:
  brooklyn_bowl:
    typical_horizon_months: 8      # How far ahead they typically post
    typical_event_count: 50-80     # Expected event count range
    has_pagination: true           # Does site have "Load More" or pagination?
    posts_recurring: false         # Weekly recurring events?

  farm_one:
    typical_horizon_months: 24     # Posts very far ahead (workshops)
    typical_event_count: 150-250
    has_pagination: true
    posts_recurring: true

  soapbox_gallery:
    typical_horizon_months: 1      # Small venue, few events
    typical_event_count: 1-5
    has_pagination: false
    posts_recurring: false
```

### 2. Detection Mechanisms

#### A. Pagination Completion Detection
**Problem**: How do we know pagination finished vs. stopped early?

**Solution**: Track pagination signals in the scraper:
```javascript
// In scraper output, report:
{
  "pagination": {
    "load_more_clicks": 5,
    "load_more_still_visible": false,  // Key signal!
    "final_scroll_position": "bottom",
    "events_after_last_click": 0       // No new events = done
  }
}
```

**Detection rules**:
- ✅ `load_more_still_visible: false` → Pagination complete
- ✅ `events_after_last_click: 0` for 2+ clicks → Pagination complete
- ❌ `load_more_still_visible: true` but clicks stopped → Pagination incomplete
- ❌ Browser timeout/crash → Pagination incomplete

#### B. Historical Comparison
**Problem**: Did we get fewer events than usual?

**Solution**: Compare to previous successful runs:
```python
def check_event_count_anomaly(source, current_count):
    # Get last 5 successful runs
    historical_counts = get_historical_counts(source, limit=5)
    avg = mean(historical_counts)

    if current_count < avg * 0.5:
        return "CRITICAL: 50%+ fewer events than usual"
    elif current_count < avg * 0.8:
        return "WARNING: 20%+ fewer events than usual"
    return "OK"
```

#### C. Date Horizon Analysis
**Problem**: Are events stopping at an unusual date?

**Solution**: Compare latest event date to baseline:
```python
def check_date_horizon(source, latest_date, baseline):
    expected_horizon = baseline.typical_horizon_months
    expected_latest = today + timedelta(months=expected_horizon)

    # Allow 30-day tolerance
    if latest_date < expected_latest - timedelta(days=30):
        return f"WARNING: Events stop {days_short} days earlier than typical"
    return "OK"
```

#### D. Pagination Pattern Detection
**Problem**: Detect when pagination stops working mid-stream

**Solution**: Track events per pagination click:
```
Click 1: +20 events
Click 2: +18 events
Click 3: +22 events
Click 4: +0 events   ← If button still visible, this is a FAILURE
Click 5: +0 events
```

If we see 2+ clicks with 0 new events BUT the button is still there, pagination broke.

### 3. Implementation: Enhanced Validation Framework

```python
# src/validate_scraper_results.py enhancements

class ScraperValidator:
    def __init__(self, source: str):
        self.source = source
        self.baseline = load_baseline(source)
        self.historical = get_historical_runs(source)

    def validate(self, current_run) -> ValidationResult:
        checks = [
            self.check_field_completeness(),
            self.check_event_count_vs_historical(),
            self.check_date_horizon_vs_baseline(),
            self.check_pagination_completion(),
            self.check_time_extraction(),
            self.check_url_validity(),
        ]
        return ValidationResult(checks)

    def check_date_horizon_vs_baseline(self):
        """Compare to venue's typical posting horizon."""
        latest = self.get_latest_event_date()
        expected = today + months(self.baseline.typical_horizon_months)

        # Key insight: if we're PAST the typical horizon, that's fine
        # Only flag if we're significantly SHORT
        if latest < expected - days(30):
            # But first check: did pagination complete?
            if not self.pagination_completed:
                return Issue("CRITICAL", "Pagination incomplete - events may be missing")
            else:
                return Issue("INFO", f"Venue only posting to {latest} (typical: {expected})")
        return OK()
```

### 4. Scraper Output Contract

Every scraper should output structured metadata:

```javascript
// At end of scraper, output:
const scraperMetadata = {
  source: "brooklyn_bowl",
  run_id: 123,

  // Pagination info
  pagination: {
    type: "load_more",           // or "next_page", "infinite_scroll", "none"
    clicks_attempted: 10,
    clicks_successful: 8,
    button_still_visible: false, // KEY: did we exhaust pagination?
    stopped_reason: "button_gone" // or "max_clicks", "timeout", "no_new_events"
  },

  // Event extraction
  extraction: {
    total_events: 62,
    events_with_times: 62,
    events_with_urls: 62,
    events_with_descriptions: 45,
  },

  // Date range
  date_range: {
    earliest: "2026-01-31",
    latest: "2026-08-29",
    months_covered: 8
  },

  // Timing
  timing: {
    started: "2026-01-31T20:25:00Z",
    completed: "2026-01-31T20:27:00Z",
    duration_seconds: 120
  }
};

console.log("SCRAPER_METADATA:" + JSON.stringify(scraperMetadata));
```

### 5. Automated Quality Gates

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCRAPER QUALITY GATES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GATE 1: Execution                                              │
│  ├─ Did scraper complete without crash?                         │
│  └─ Was browser session maintained?                             │
│                                                                 │
│  GATE 2: Pagination                                             │
│  ├─ Did pagination exhaust? (button gone OR no new events)      │
│  └─ If not, why? (timeout, max_clicks, error)                   │
│                                                                 │
│  GATE 3: Field Completeness                                     │
│  ├─ title: >95% required                                        │
│  ├─ start_time: >90% required (or flag as known issue)          │
│  ├─ url: >90% required                                          │
│  └─ venue: >95% required                                        │
│                                                                 │
│  GATE 4: Historical Comparison                                  │
│  ├─ Event count within 50% of historical average?               │
│  └─ Date horizon within 30 days of historical?                  │
│                                                                 │
│  GATE 5: Baseline Comparison                                    │
│  ├─ Event count in expected range for venue?                    │
│  └─ Date horizon matches venue's typical posting pattern?       │
│                                                                 │
│  RESULT: PASS / WARN / FAIL                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6. Issue Classification

| Signal | Diagnosis | Action |
|--------|-----------|--------|
| Pagination incomplete + fewer events | Scraper bug | Fix pagination |
| Pagination complete + fewer events than history | Site changed | Investigate site |
| Pagination complete + events match baseline | Normal | No action |
| All events have midnight time | Time extraction broken | Fix scraper |
| URLs mostly empty | URL extraction broken | Fix scraper |
| Events stop at specific month | Check if site posts more | Manual verify |

### 7. Files to Create/Modify

| File | Purpose |
|------|---------|
| `src/config/venue_baselines.yaml` | Store expected behavior per venue |
| `src/lib/scraper-metadata.js` | Helper to output structured metadata |
| `src/validate_scraper_results.py` | Enhanced with baseline comparison |
| `src/lib/scraper-utils.js` | Add pagination completion tracking |
| `src/run_staging_scraper.py` | Parse and validate scraper metadata |

### 8. Implementation Order

1. **Create venue baselines** from current successful runs
2. **Add metadata output** to scraper utilities
3. **Enhance pagination tracking** to report completion status
4. **Update validation framework** to use baselines + historical comparison
5. **Add quality gates** to run_staging_scraper.py
6. **Test with all scrapers** and refine baselines

### 9. Success Criteria

A scraper run is considered successful when:

1. ✅ Execution completed without browser crash
2. ✅ Pagination exhausted (or max reasonable clicks reached)
3. ✅ Event count within expected range OR explained by venue pattern
4. ✅ Date horizon matches venue's typical posting pattern
5. ✅ Required fields (title, time, url) >90% filled
6. ✅ No time regression (not all events at midnight)

A scraper run needs investigation when:

1. ⚠️ Event count 20-50% below historical average
2. ⚠️ Date horizon 30+ days shorter than historical
3. ⚠️ Pagination stopped but button still visible

A scraper run is failed when:

1. ❌ Browser crash or timeout
2. ❌ Event count >50% below historical average
3. ❌ 0 events extracted
4. ❌ Required field <50% filled
5. ❌ All events have identical time (regression)
