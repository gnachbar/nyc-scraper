"""
SQLAlchemy models for NYC Events Scraper
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config

Base = declarative_base()


class RawEvent(Base):
    """Raw scraped event data before processing"""
    __tablename__ = 'raw_events'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(100), nullable=False)  # kings_theatre, prospect_park, brooklyn_paper
    source_id = Column(String(200))  # Original ID from source website
    title = Column(Text)
    description = Column(Text)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    location = Column(Text)
    venue = Column(String(200))
    price_info = Column(String(100))
    category = Column(String(100))
    url = Column(Text)
    image_url = Column(Text)
    raw_data = Column(JSON)  # Store original scraped data as JSON
    scraped_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<RawEvent(id={self.id}, source='{self.source}', title='{self.title}')>"


class CleanEvent(Base):
    """Cleaned and deduplicated event data"""
    __tablename__ = 'clean_events'
    
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    start_time = Column(DateTime, nullable=False)  # Required field per PRD
    end_time = Column(DateTime)
    location = Column(Text)
    venue = Column(String(200))
    price_range = Column(String(100))  # Standardized price info
    category = Column(String(100))
    url = Column(Text)
    image_url = Column(Text)
    source = Column(String(100))  # Primary source
    source_urls = Column(JSON)  # All source URLs for this event
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<CleanEvent(id={self.id}, title='{self.title}', start_time='{self.start_time}')>"


# Database engine and session setup
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables"""
    Base.metadata.drop_all(bind=engine)
