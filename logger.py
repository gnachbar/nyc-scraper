"""
Logging configuration for NYC Events Scraper
"""
import logging
import sys
from datetime import datetime
from config import Config

def setup_logging():
    """Set up logging configuration"""
    
    # Create logger
    logger = logging.getLogger('nyc_scraper')
    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger

def get_logger(name=None):
    """Get a logger instance"""
    if name:
        return logging.getLogger(f'nyc_scraper.{name}')
    return logging.getLogger('nyc_scraper')

# Set up default logger
logger = setup_logging()
