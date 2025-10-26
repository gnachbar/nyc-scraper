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

Current scrapers are located in `src/scrapers/`:
- `kings_theatre.js` - Kings Theatre events
- `msg_calendar.js` - MSG calendar events  
- `prospect_park.js` - Prospect Park events
- `brooklyn_museum.js` - Brooklyn Museum events

All scrapers use a shared utilities architecture to reduce code duplication and ensure consistency.

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

### Creating New Scrapers

To create a new scraper:
1. Follow the guide in `docs/stagehand-scraper-guide.md`
2. Use the shared utilities from `src/lib/`
3. Reference `src/scrapers/msg_calendar.js` as a complete working example
4. Add your scraper to `src/scrapers/` and register it in `src/run_pipeline.py`

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

Workflow guides and documentation are in the `docs/` directory:
- `stagehand-scraper-guide.md` - Guide for using Stagehand
- Other workflow files for AI-assisted development

## Test Outputs

Test results and scraped data are stored in `test-output/` and are gitignored to keep the repository clean.