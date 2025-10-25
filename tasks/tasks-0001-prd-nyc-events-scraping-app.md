## Relevant Files

- `scrapers/kings_theatre.py` - Kings Theatre scraper using Browserbase
- `scrapers/prospect_park.py` - Prospect Park events scraper using Browserbase  
- `scrapers/brooklyn_paper.py` - Brooklyn Paper events scraper using Browserbase
- `database.py` - Simple database connection and operations
- `models.py` - Simple SQLAlchemy models for raw_events and clean_events
- `process_data.py` - Data cleaning and deduplication script
- `app.py` - Simple Flask web app for browsing events
- `templates/index.html` - Basic HTML template for event listing
- `static/style.css` - Simple CSS styling
- `requirements.txt` - Minimal Python dependencies
- `config.py` - Configuration file (Neon DB URL, Browserbase API key)
- `README.md` - Setup and usage instructions

### Notes

- Using hosted PostgreSQL (Neon) instead of local Docker setup
- Simple SQLAlchemy models without complex migrations
- Minimal dependencies to get started quickly
- Focus on working end-to-end first, optimize later

## Tasks

- [x] 1.0 Basic Project Setup
  - [x] 1.1 Create simple requirements.txt with minimal dependencies
  - [x] 1.2 Set up basic project structure (scrapers/, templates/, static/)
  - [x] 1.3 Create config.py for local DB and Browserbase API key
  - [x] 1.4 Set up basic logging
  - [x] 1.5 Add code linter (flake8 or black)
- [ ] 2.0 Local Database Setup
  - [x] 2.1 Install PostgreSQL locally (or use SQLite for even simpler start)
  - [x] 2.2 Create simple SQLAlchemy models (raw_events, clean_events)
  - [x] 2.3 Set up database connection and create tables
  - [x] 2.4 Test database connection
- [ ] 3.0 Browserbase Integration
  - [ ] 3.1 Install and configure Browserbase Python SDK
  - [ ] 3.2 Create simple Browserbase client wrapper
  - [ ] 3.3 Test basic browser session creation
- [ ] 4.0 Simple Scrapers (3 scrapers)
  - [ ] 4.1 Create Kings Theatre scraper (https://www.kingstheatre.com/)
  - [ ] 4.2 Create Prospect Park events scraper (https://www.prospectpark.org/events/)
  - [ ] 4.3 Create Brooklyn Paper events scraper (https://events.brooklynpaper.com/)
  - [ ] 4.4 Test each scraper individually
- [ ] 5.0 Data Processing
  - [ ] 5.1 Create script to clean and deduplicate data in local database
  - [ ] 5.2 Ensure all events have start_time (quality control)
  - [ ] 5.3 Move cleaned data to clean_events table
- [ ] 6.0 Simple Web Interface
  - [ ] 6.1 Create basic Flask app that reads from clean_events table
  - [ ] 6.2 Build simple HTML template to display events
  - [ ] 6.3 Add basic filtering by date and category
  - [ ] 6.4 Add simple search functionality
- [ ] 7.0 Migrate to Neon (Optional)
  - [ ] 7.1 Create Neon PostgreSQL database
  - [ ] 7.2 Update config.py to use Neon connection string
  - [ ] 7.3 Migrate local data to Neon
  - [ ] 7.4 Test web app with Neon database
