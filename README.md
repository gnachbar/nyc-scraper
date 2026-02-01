# NYC Events Scraper

A web scraping project for collecting event data from various NYC venues and locations.

## Project Structure

```
nyc-scraper/
├── src/                    # Source code
│   ├── web/               # Flask web application
│   │   ├── app.py         # Flask app and routes
│   │   ├── models.py      # Database models
│   │   └── database.py    # Database utilities
│   ├── config.py          # Python configuration
│   ├── logger.py          # Logging configuration
│   ├── app/               # Test applications
│   ├── config/            # JavaScript configuration
│   ├── lib/               # Shared libraries
│   ├── scrapers/          # Scraper implementations
│   ├── scripts/           # Utility scripts
│   └── transforms/        # Data transformation utilities
├── docs/                  # Documentation and guides
├── tasks/                 # Project management files
├── templates/             # Flask templates
├── static/               # Flask static files
├── data/                 # Data directory
├── logs/                 # Log directory
├── requirements.txt       # Python dependencies
└── package.json           # Node.js dependencies
```

## Scrapers

### Production Scrapers

Current production scrapers are located in `src/scrapers/`:
- `kings_theatre.js` - Kings Theatre events
- `msg_calendar.js` - MSG calendar events  
- `prospect_park.js` - Prospect Park events
- `brooklyn_museum.js` - Brooklyn Museum events

All scrapers use a shared utilities architecture to reduce code duplication and ensure consistency.

### Staging Scrapers

Work-in-progress scrapers are located in `src/scrapers-staging/`. See the [scraper development workflow](#creating-new-scrapers) below.

## Development

The project uses both Node.js and Python:
- Node.js for web scraping with Stagehand
- Python for data processing and storage

### Shared Utilities Architecture

All scrapers use shared utility functions from `src/lib/`:

- **`scraper-utils.js`** - Initialization, schema creation, and scrolling helpers
- **`scraper-actions.js`** - Button clicking, event extraction, and pagination logic
- **`scraper-persistence.js`** - Logging, database operations, and error handling

This architecture ensures:
- Consistent error handling across all scrapers
- Automatic database saving and test execution
- Reduced code duplication
- Easier maintenance and updates

### Creating New Scrapers (Automated)

The easiest way to create a new scraper is using the automated creation tool with built-in **self-healing**:

```bash
# Create a new scraper with automatic testing and self-healing
python src/create_scraper.py "Brooklyn Bowl" "https://www.brooklynbowl.com/events"

# Use click pagination template (for "Load More" buttons)
python src/create_scraper.py "Barclays Center" "https://barclayscenter.com/events" --template click
```

This will:
1. **Generate** a scraper from a template
2. **Test** it automatically
3. **Diagnose** issues using code analysis and Browserbase session logs
4. **Fix** common issues automatically
5. **Iterate** until success

### Self-Healing System

The project includes an intelligent self-healing system that can automatically detect and fix:

| Issue | Detection | Auto-Fix |
|-------|-----------|----------|
| Navigation timeout | "Timeout exceeded" | Extended timeout, retry logic |
| Case-sensitive selectors | "button found after 0 clicks" | Case-insensitive regex |
| Missing Python modules | "ModuleNotFoundError" | Use venv Python |
| No scroll events | Browserbase session analysis | Add scroll verification |
| Session crashes | "Target page closed" | Health checks, batching |

**Heal an existing scraper:**
```bash
python src/create_scraper.py --heal [source_name]
```

**Diagnose scraper issues:**
```bash
python src/create_scraper.py --diagnose [source_name]
```

See `docs/self-healing-system.md` for full documentation.

### Manual Workflow

If you prefer manual control:

1. **Create scraper** → Save to `src/scrapers-staging/{venue_name}.js`
2. **Test manually** → `node src/scrapers-staging/{venue_name}.js`
3. **Validate** → `python src/test_staging_scraper.py {venue_name}`
4. **Promote** → `python src/promote_scraper.py {venue_name}`
5. **Production run** → `python src/run_pipeline.py --source {venue_name}`

**New to adding scrapers?** Check out **[CONTRIBUTING.md](CONTRIBUTING.md)** for a complete guide.

## Running the Application

### Running the Flask Web App

To start the web application:

```bash
python run_app.py
```

The app will be available at `http://localhost:5001`

### Running the Scraping Pipeline

To run all scrapers and process the data:

```bash
python src/run_pipeline.py
```

## Documentation

- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Complete guide for adding new scrapers (start here!)
- `docs/self-healing-system.md` - Self-healing diagnostics and auto-fix documentation
- `docs/stagehand-scraper-guide.md` - Detailed guide for using Stagehand
- `docs/SCRAPER_QUALITY_PLAN.md` - Quality standards for scrapers
- `src/scrapers-staging/README.md` - Staging workflow instructions

## Test Outputs

Test results and scraped data are stored in `test-output/` and are gitignored to keep the repository clean.