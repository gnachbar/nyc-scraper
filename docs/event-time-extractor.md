# Event Time Extractor

A reusable Python utility for extracting event times from individual event pages. This tool is designed to work with any venue website that embeds time data in JSON within script tags.

## Features

- **Fast parallel processing**: Extract times from multiple URLs simultaneously
- **Multiple time patterns**: Supports various JSON field names (`startTime`, `doorsOpen`, `eventTime`, etc.)
- **Fallback extraction**: If JSON extraction fails, tries to find times in HTML content
- **Error handling**: Gracefully handles network errors and parsing failures
- **Reusable**: Works with any venue, not just Kings Theatre

## Installation

Install the required dependencies:

```bash
pip install requests beautifulsoup4
```

Or install all project dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python src/extract_event_times.py input.json output.json
```

### With Options

```bash
python src/extract_event_times.py input.json output.json --workers 20 --rate-limit 2.0 --timeout 15
```

### Command Line Options

- `input_file`: JSON file containing events with `eventUrl` fields
- `output_file`: JSON file for events with extracted times
- `--workers, -w`: Number of parallel workers (default: 10)
- `--timeout, -t`: Request timeout in seconds (default: 10)
- `--rate-limit, -r`: Maximum requests per second (default: 1.0)

## Input Format

The input JSON file should contain an array of events:

```json
[
  {
    "eventName": "PINKPANTHERESS",
    "eventDate": "SATURDAY, OCTOBER 25",
    "eventLocation": "Kings Theatre",
    "eventUrl": "https://www.kingstheatre.com/events/pinkpantheress-saturday/"
  },
  {
    "eventName": "CUCO",
    "eventDate": "FRIDAY, OCTOBER 31", 
    "eventLocation": "Kings Theatre",
    "eventUrl": "https://www.kingstheatre.com/events/cuco-friday/"
  }
]
```

## Output Format

The output JSON file will contain the same events with `eventTime` fields added:

```json
[
  {
    "eventName": "PINKPANTHERESS",
    "eventDate": "SATURDAY, OCTOBER 25",
    "eventLocation": "Kings Theatre",
    "eventUrl": "https://www.kingstheatre.com/events/pinkpantheress-saturday/",
    "eventTime": "8:00 PM"
  },
  {
    "eventName": "CUCO",
    "eventDate": "FRIDAY, OCTOBER 31",
    "eventLocation": "Kings Theatre", 
    "eventUrl": "https://www.kingstheatre.com/events/cuco-friday/",
    "eventTime": "8:00 PM"
  }
]
```

## Supported Time Patterns

The extractor looks for these JSON field names in script tags:

- `startTime`: "8:00 PM"
- `doorsOpen`: "7:00 PM"
- `eventTime`: "8:00 PM"
- `showTime`: "8:00 PM"
- `performanceTime`: "8:00 PM"
- `time`: "8:00 PM"

If JSON extraction fails, it falls back to finding time patterns in HTML content using regex.

## Integration with Existing Scrapers

### Kings Theatre Integration

1. **Run the Kings Theatre scraper** to get events with URLs:
   ```bash
   node -e "import('./src/scrapers/kings_theatre.js').then(m => m.scrapeKingsTheatre())"
   ```

2. **Extract times** from the scraped events:
   ```bash
   python src/extract_event_times.py kings_events.json kings_events_with_times.json
   ```

3. **Import to database**:
   ```bash
   python src/import_scraped_data.py kings_theatre kings_events_with_times.json
   ```

### Automated Integration

Use the integration script for a complete workflow:

```bash
python src/scripts/integrate_time_extraction.py
```

This will:
1. Run the Kings Theatre scraper
2. Extract times from all event URLs
3. Import the enriched events to the database
4. Show a summary of results

## Testing

Test the extractor with sample data:

```bash
python test_time_extractor.py
```

## Rate Limiting

The extractor includes built-in rate limiting to be respectful to venue servers:

- **Default rate**: 1 request per second (very conservative)
- **Configurable**: Use `--rate-limit` to adjust (e.g., `--rate-limit 2.0` for 2 requests/second)
- **Thread-safe**: Rate limiting works correctly with parallel workers
- **Respectful**: Prevents overwhelming venue servers and reduces risk of IP blocking

### Rate Limiting Benefits

- **Avoid IP blocking**: Prevents getting banned by venue servers
- **Server-friendly**: Reduces load on venue websites
- **Reliable**: More consistent success rates
- **Scalable**: Can safely increase workers without overwhelming servers

## Performance

- **Speed**: Processes ~1-2 events per second with rate limiting (respectful to servers)
- **Parallel processing**: Uses ThreadPoolExecutor for concurrent requests
- **Memory efficient**: Processes events in batches
- **Error resilient**: Continues processing even if some URLs fail

## Error Handling

The extractor handles various error conditions:

- **Network errors**: Timeouts, connection failures, HTTP errors
- **Parsing errors**: Invalid JSON, malformed HTML
- **Missing data**: URLs without time information
- **Rate limiting**: Built-in delays and retry logic

## Customization

To support new venues or time patterns, modify the `time_patterns` list in `extract_time_from_page()`:

```python
time_patterns = [
    r'"startTime":\s*"([^"]+)"',           # "startTime": "8:00 PM"
    r'"doorsOpen":\s*"([^"]+)"',           # "doorsOpen": "7:00 PM"
    r'"customTime":\s*"([^"]+)"',          # Add new pattern
]
```

## Examples

### Extract times for 3 Kings Theatre events

```bash
# Create test data
echo '[{"eventName":"PINKPANTHERESS","eventUrl":"https://www.kingstheatre.com/events/pinkpantheress-saturday/"}]' > test.json

# Extract times
python src/extract_event_times.py test.json result.json

# View results
cat result.json
```

### High-performance extraction (with rate limiting)

```bash
python src/extract_event_times.py events.json enriched.json --workers 20 --rate-limit 2.0 --timeout 5
```

### Conservative extraction (very respectful)

```bash
python src/extract_event_times.py events.json enriched.json --workers 5 --rate-limit 0.5
```

## Troubleshooting

### Common Issues

1. **"No module named 'requests'"**
   ```bash
   pip install requests beautifulsoup4
   ```

2. **"No time found" for all events**
   - Check if the website requires JavaScript rendering
   - Verify the JSON field names match the website's structure
   - Try increasing the timeout: `--timeout 30`

3. **Network errors**
   - Check internet connection
   - Verify URLs are accessible
   - Try reducing workers: `--workers 5`

### Debug Mode

For debugging, you can modify the script to print more information:

```python
# Add this to extract_time_from_page() for debugging
print(f"Processing URL: {url}")
print(f"Response status: {response.status_code}")
print(f"Script tags found: {len(soup.find_all('script'))}")
```

## Future Enhancements

- Support for more time formats
- JavaScript rendering support (Selenium/Playwright)
- Caching to avoid re-processing URLs
- Batch processing for very large datasets
- Integration with more venue scrapers
