"""
Configuration settings for NYC Events Scraper
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost:5432/nyc_events')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'nyc_events')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    # Browserbase Configuration
    BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
    BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')
    
    # Scraping Configuration
    SCRAPER_DELAY = int(os.getenv('SCRAPER_DELAY', '2'))  # seconds between requests
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'scraper.log')

    # Google Maps Configuration
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    GMAPS_REGION = os.getenv('GMAPS_REGION', 'US')
    GMAPS_LANGUAGE = os.getenv('GMAPS_LANGUAGE', 'en')
    HOME_COORDS = os.getenv('HOME_COORDS')  # expected format: "lat,lon"
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required_vars = ['BROWSERBASE_API_KEY']
        missing = [var for var in required_vars if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True
