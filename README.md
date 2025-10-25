# NYC Events Scraper

A web scraping project for collecting event data from various NYC venues and locations.

## Project Structure

```
nyc-scraper/
├── src/                    # Source code
│   ├── app/               # Test applications
│   ├── config/            # Configuration files
│   ├── lib/               # Shared libraries
│   ├── scrapers/          # Scraper implementations
│   └── transforms/        # Data transformation utilities
├── docs/                  # Documentation and guides
├── tasks/                 # Project management files
├── test-output/           # Test results and scraped data (gitignored)
├── config.py              # Python configuration
├── database.py            # Database utilities
├── logger.py              # Logging configuration
├── models.py              # Data models
└── requirements.txt       # Python dependencies
```

## Scrapers

Current scrapers are located in `src/scrapers/`:
- `kings.js` - Kings Theatre events
- `msg_calendar.js` - MSG calendar events  
- `prospect_park.js` - Prospect Park events

## Development

The project uses both Node.js and Python:
- Node.js for web scraping with Stagehand
- Python for data processing and storage

## Documentation

Workflow guides and documentation are in the `docs/` directory:
- `stagehand-scraper-guide.md` - Guide for using Stagehand
- Other workflow files for AI-assisted development

## Test Outputs

Test results and scraped data are stored in `test-output/` and are gitignored to keep the repository clean.