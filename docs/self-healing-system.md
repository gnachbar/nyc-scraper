# Self-Healing Scraper System

This document describes the automated diagnosis and self-healing system for scrapers.

## Overview

The self-healing system automatically detects, diagnoses, and fixes common scraper issues. It combines:

1. **Code Analysis** - Examines scraper code for patterns and potential issues
2. **Historical Data** - Reviews past run success/failure rates
3. **Browserbase Session Logs** - Analyzes actual browser events (scrolls, clicks, errors)
4. **Screenshot Verification** - Visual comparison of scraped data vs. page content
5. **Automated Fixes** - Applies targeted fixes based on diagnosis

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-HEALING LOOP                            │
├─────────────────────────────────────────────────────────────────┤
│  1. RUN: Execute scraper, capture screenshot & session ID       │
│  2. BROWSERBASE: Analyze session logs (scroll/click/errors)     │
│  3. DIAGNOSE: Code analysis + history + pattern matching        │
│  4. VISUAL: Compare screenshot to scraped data                  │
│  5. FIX: Apply targeted fixes based on evidence                 │
│  6. REPEAT: Until success or max iterations                     │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### `src/diagnose_scraper.py`

Core diagnostic engine that analyzes scrapers.

**Usage:**
```bash
python src/diagnose_scraper.py [source_name]
```

**What it analyzes:**
- Scraper code structure (pagination method, patterns)
- Historical run data (success rate, last success date)
- Comparison with similar scrapers
- Error output patterns

### `src/visual_self_healer.py`

Main self-healing loop that iteratively fixes scrapers.

**Usage:**
```bash
python src/visual_self_healer.py [source_name] --max-iterations 5
```

**Process:**
1. Runs scraper and captures output
2. Extracts Browserbase session ID
3. Fetches session logs for analysis
4. Runs comprehensive diagnosis
5. Takes screenshot for visual verification
6. Combines all issues and applies fixes
7. Repeats until success

### `src/lib/browserbase-diagnostics.js`

JavaScript module that fetches and analyzes Browserbase session logs.

**Usage:**
```bash
node src/lib/browserbase-diagnostics.js [session_id]
```

**What it detects:**
- Scroll events (or lack thereof)
- Click events
- JavaScript errors
- Session duration
- Navigation patterns

### `src/browserbase_feedback.py`

Python wrapper for Browserbase diagnostics.

**Usage:**
```bash
python src/browserbase_feedback.py [session_id]
```

### `src/create_scraper.py`

Unified workflow that creates new scrapers with automatic self-healing.

**Usage:**
```bash
# Create new scraper
python src/create_scraper.py "Venue Name" "https://events-url.com"

# Heal existing scraper
python src/create_scraper.py --heal [source_name]

# Diagnose existing scraper
python src/create_scraper.py --diagnose [source_name]
```

---

## Diagnostic Categories

### `navigation_timeout`

**Detection:** `"Timeout exceeded"` in error output

**Observations:**
- Page took too long to load
- Navigation timeout after X seconds

**Recommended Fixes:**
1. `increase_navigation_timeout` - Extend timeout to 60s, use domcontentloaded
2. `add_retry_on_timeout` - Add retry logic (3 attempts)

**Confidence:** 90%

---

### `session_crash`

**Detection:** `"Target page, context or browser has been closed"` in error output

**Observations:**
- Browser session crashes during operation
- Session dies after N clicks

**Recommended Fixes:**
1. `extract_before_pagination` - Get partial data before risky operations
2. `add_session_recovery` - Add health checks between operations
3. `switch_to_scroll` - Replace click pagination with scroll

**Confidence:** 70-80%

---

### `button_not_found`

**Detection:** `"button found after 0 clicks"` in error output

**Observations:**
- Button selector found 0 matches
- Likely case sensitivity issue

**Recommended Fixes:**
1. `fix_button_selector_case` - Make selectors case-insensitive using regex
2. `take_screenshot_and_inspect` - Visual inspection needed

**Confidence:** 85%

---

### `python_dependency_missing`

**Detection:** `"ModuleNotFoundError"` or `"No module named"` in error output

**Observations:**
- Missing Python module: [module_name]
- May be using system Python instead of venv

**Recommended Fixes:**
1. `fix_python_path` - Update JavaScript to use venv Python
2. `install_python_dependency` - Install missing module

**Confidence:** 90%

---

### `stale_data`

**Detection:** All events in database are in the past, last success > N days ago

**Observations:**
- Last successful run was X days ago
- All Y events in DB are past events

**Recommended Fixes:**
1. `rerun_scraper` - Simply rerun the scraper

**Confidence:** 40%

---

### `empty_results`

**Detection:** `events_scraped: 0` or no events in database

**Observations:**
- No events extracted from page

**Recommended Fixes:**
1. `increase_wait_times` - Add longer waits for page load
2. `check_page_structure` - Take screenshot for analysis

**Confidence:** 50%

---

## Browserbase Session Analysis

### What We Detect

| Metric | Detection Method | Significance |
|--------|-----------------|--------------|
| Scroll events | `Runtime.evaluate` with scroll functions | Page content loading |
| Click events | `Input.dispatchMouseEvent` | Pagination interaction |
| Errors | `exceptionDetails` in responses | Runtime failures |
| Session duration | Timestamp of first/last event | Session stability |
| Navigation | `Page.navigate*` methods | Page loading |

### Key Insights

**NO_SCROLL Issue:**
- Detected when scroll events = 0
- Indicates page content may not have loaded
- Fix: Add scroll verification, ensure scrollToBottom is called

**INSUFFICIENT_SCROLL Issue:**
- Detected when scroll events < 3
- May not have scrolled enough to load all content
- Fix: Increase scroll attempts

**SESSION_CRASH Issue:**
- Detected when session duration < 10s with errors
- Browser died prematurely
- Fix: Add health checks, batch operations

---

## Fix Implementations

### `increase_navigation_timeout`

**What it does:**
1. Finds `page.goto()` calls in scraper
2. Adds `timeout: 60000` option
3. Changes `waitUntil` to `"domcontentloaded"`

**Code change:**
```javascript
// Before
await page.goto(url);

// After
await page.goto(url, { timeout: 60000, waitUntil: "domcontentloaded" });
```

---

### `add_retry_on_timeout`

**What it does:**
1. Wraps `page.goto()` in retry loop
2. Attempts navigation up to 3 times
3. Waits 5 seconds between retries

**Code change:**
```javascript
let navigationSuccess = false;
for (let attempt = 1; attempt <= 3 && !navigationSuccess; attempt++) {
  try {
    console.log(`Navigation attempt ${attempt}/3...`);
    await page.goto(url, { timeout: 60000, waitUntil: "domcontentloaded" });
    navigationSuccess = true;
  } catch (navError) {
    if (attempt === 3) throw navError;
    await page.waitForTimeout(5000);
  }
}
```

---

### `fix_button_selector_case`

**What it does:**
1. Finds button selectors with pagination-related text
2. Converts exact match to case-insensitive regex

**Code change:**
```javascript
// Before
const button = await page.$('text="View more events"');

// After
const button = await page.$('text=/view more events/i');
```

---

### `extract_before_pagination`

**What it does:**
1. Adds extraction step before pagination
2. Captures partial results as safety backup
3. Continues with pagination if extraction succeeds

**Code change:**
```javascript
// Extract visible events BEFORE pagination
let initialEvents = [];
try {
  const initialResult = await extractEventsFromPage(page, ...);
  initialEvents = initialResult.events || [];
  console.log(`Got ${initialEvents.length} events before pagination`);
} catch (e) {
  console.log("Initial extraction failed, continuing:", e.message);
}

// Then proceed with pagination...
```

---

### `add_scroll_verification`

**What it does:**
1. Adds logging after scrollToBottom call
2. Checks if scroll actually worked
3. Warns if scrollY is too low

**Code change:**
```javascript
await scrollToBottom(page);

// Scroll verification
const scrollHeight = await page.evaluate(() => document.body.scrollHeight);
const scrollY = await page.evaluate(() => window.scrollY);
console.log(`Scroll result: scrollY=${scrollY}, pageHeight=${scrollHeight}`);
if (scrollY < 100) {
  console.warn("Scroll may not have worked - scrollY is very low");
}
```

---

## Adding New Diagnostics

To add a new diagnostic category:

### 1. Add detection in `diagnose_scraper.py`

```python
# In _analyze_failure method
elif "your_error_pattern" in error_output:
    report.failure_category = "your_category"
    report.failure_pattern = "Description of what went wrong"
    report.observations.append("Specific observation")
```

### 2. Add recommendations

```python
# In _generate_recommendations method
if report.failure_category == "your_category":
    report.recommended_fixes = [
        {
            "priority": 1,
            "action": "your_fix_action",
            "description": "What the fix does",
            "confidence": 0.8,
            "rationale": "Why this fix should work"
        }
    ]
    report.confidence = 0.8
```

### 3. Add fix implementation in `visual_self_healer.py`

```python
# In _apply_diagnostic_fix method
elif action == "your_fix_action":
    return self._your_fix_method()

# Add the actual fix method
def _your_fix_method(self) -> Tuple[bool, str]:
    path = Path(self.scraper_path)
    content = path.read_text()

    # Modify content...

    path.write_text(content)
    return True, "Description of fix applied"
```

### 4. Add issue handler

```python
# In apply_fix method
elif issue == "YOUR_CATEGORY":
    return self._your_fix_method()
```

---

## Best Practices

### For Diagnosis

1. **Be specific** - Detection patterns should be precise
2. **Multiple observations** - Gather evidence from multiple sources
3. **Compare with working scrapers** - Use pattern matching
4. **Confidence scoring** - Rate your diagnosis confidence

### For Fixes

1. **One fix at a time** - Apply fixes incrementally
2. **Preserve functionality** - Don't break existing behavior
3. **Add verification** - Include logging to verify fix worked
4. **Document changes** - Log what was modified

### For Testing

1. **Test on failing scrapers** - Use real failure cases
2. **Verify fixes work** - Run scraper after applying fix
3. **Check for regressions** - Ensure fix doesn't break other things
4. **Save diagnostic reports** - Keep history of diagnoses

---

## Troubleshooting the Self-Healer

### "Could not retrieve Browserbase session data"

- Check BROWSERBASE_API_KEY is set in .env
- Verify session ID is valid
- Check network connectivity

### "No fix available for: [issue]"

- Issue type not yet implemented
- Add new fix in visual_self_healer.py
- Consider manual intervention

### "Failed after max iterations"

- Issue is complex, requires manual investigation
- Check saved diagnostic reports
- Review screenshots for visual clues

---

## Files Reference

| File | Purpose |
|------|---------|
| `src/diagnose_scraper.py` | Core diagnostic engine |
| `src/visual_self_healer.py` | Self-healing loop with fixes |
| `src/browserbase_feedback.py` | Python Browserbase analysis |
| `src/lib/browserbase-diagnostics.js` | JS Browserbase analysis |
| `src/create_scraper.py` | Unified creation + healing workflow |
| `src/auto_fix_rules.py` | Legacy auto-fix rules |
| `data/output/diagnostics/` | Saved diagnostic reports |
| `screenshots/` | Captured screenshots |
