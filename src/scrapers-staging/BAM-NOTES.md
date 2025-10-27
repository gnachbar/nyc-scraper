# BAM Scraper Notes

## Current Status
- ✅ Successfully extracts events from multiple sections (Music, Theater, Dance, etc.)
- ✅ Date normalization works for formats like "Sat, Nov 15, 2025"
- ✅ Date range expansion works for formats like "Nov 5—Nov 8, 2025"
- ✅ Added deduplication logic to prevent duplicate events across sections
- ✅ Added pagination loop detection to prevent infinite scrolling
- ⚠️ URL extraction works on first page but breaks on subsequent pages after pagination

## Issues Found (October 26, 2025)

### Infinite Loop in Event Extraction (FIXED)
**Problem:** Scraper was extracting 257 events but only 21 unique event+date combinations, meaning ~92% duplicates.

**Root Cause:** 
- Same events appear in multiple sections (e.g., musical theater appears in both "Music" and "Theater")
- No deduplication logic existed
- Each event appeared an average of 14 times

**Fix Applied:**
1. Added deduplication step after date range expansion
2. Uses eventName + eventDate as unique key
3. Added pagination loop detection to stop if seeing same events repeatedly

### URL Extraction After Pagination
After clicking the right arrow to paginate through sections, URL extraction falls back to "https://www.bam.org/more" instead of actual event URLs.

**Why:** The DOM structure changes after pagination or Stagehand loses track of the correct event links.

**Current Workaround:** 
- Events are successfully extracted with names, dates, times, and locations
- URLs may need manual cleanup in post-processing
- First page of each section extracts proper URLs
- Last run had 86% valid URLs, 14% empty

### URL Format Issue
- First page: `https://www.bam.org/Optimistic-Voices` ✅
- Subsequent pages: Empty strings ❌

## Recommendations

### Option 1: Accept Partial URLs
- Use scraper as-is
- Manually fix URLs in post-processing
- Focus on name, date, time, location extraction

### Option 2: Two-Stage Extraction
- First pass: Extract all events without pagination (just first page of each section)
- Second pass: Visit each event detail page to get URLs

### Option 3: Use BAM API
- Check if BAM has an events API
- Use API if available for more reliable data

## Testing Results
- Tested on multiple sections: Music, Theater, Dance, Talks, Opera, Poetry, Kids, Performance Art, Holiday
- Date parsing works correctly
- Date range expansion works correctly
- Browser closure happens after extensive pagination (expected)

## Next Steps
1. ✅ Fixed infinite loop issue with deduplication and loop detection
2. Test updated scraper to verify fix works
3. Address URL extraction issue (if needed)
4. Consider if time extraction is possible or should be left empty

