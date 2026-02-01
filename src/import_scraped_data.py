#!/usr/bin/env python3
"""
Data import script for NYC Events Scraper

This script imports JSON/CSV files from scrapers into the raw_events table,
tracking each import with a ScrapeRun record.
"""

import json
import argparse
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal
from src.logger import get_logger

logger = get_logger('import_scraped_data')


def parse_event_datetime(date_str: str, time_str: Optional[str] = None) -> Optional[datetime]:
    """
    Parse event date and time strings into a datetime object.
    Handles various formats from different scrapers.
    """
    if not date_str:
        return None
    
    try:
        # Handle special cases first
        if ' - ' in date_str and ('am' in date_str.lower() or 'pm' in date_str.lower()):
            # Format: "October 25, 8:00 am - 4:00 pm" - extract just the date part
            parts = date_str.split(',')
            if len(parts) >= 2:
                date_str = parts[0].strip()  # "October 25"
        elif ' - ' in date_str and len(date_str.split(' - ')) == 2:
            # Format: "April 22, 2025 - May 1, 2026" - take start date
            date_str = date_str.split(' - ')[0].strip()
        
        # Common date formats from scrapers
        date_formats = [
            '%B %d, %Y',           # October 25, 2025
            '%b %d, %Y',           # Nov 9, 2025 (abbreviated month)
            '%Y-%m-%d',           # 2025-10-25
            '%m/%d/%Y',           # 10/25/2025
            '%d/%m/%Y',           # 25/10/2025
            '%B %d',              # October 25 (current year)
            '%b %d',              # Nov 9 (current year, abbreviated month)
            '%a, %B %d',          # Sun, October 26
            '%a, %b %d, %Y',     # Mon, Nov 3, 2025 (abbreviated day and month, with year)
            '%A, %B %d',         # SATURDAY, OCTOBER 25
            '%A, %B %d, %Y',     # SATURDAY, OCTOBER 25, 2025
        ]
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt)
                break
            except ValueError:
                continue
        
        if not parsed_date:
            logger.warning(f"Could not parse date: {date_str}")
            return None
        
        # If no year specified, assume current year
        if parsed_date.year == 1900:
            parsed_date = parsed_date.replace(year=datetime.now().year)
        
        # Add time if provided
        if time_str:
            try:
                # Clean up complex time strings (e.g., "8:00 PM | Doors open 7:00 PM")
                clean_time_str = time_str.strip()
                if ' | ' in clean_time_str:
                    # Extract just the main event time before the pipe
                    clean_time_str = clean_time_str.split(' | ')[0].strip()
                
                # Remove timezone suffix (e.g., "ET", "PT", "EST")
                clean_time_str = re.sub(r'\s+(ET|PT|EST|PST|CST|MST)$', '', clean_time_str, flags=re.IGNORECASE)
                clean_time_str = clean_time_str.strip()  # Remove any extra whitespace
                
                # Handle time ranges (em dash, regular dash, or spaced dash)
                # Common patterns: "2–4 pm", "10:30 am–5:30 pm", "11 am–12:30 pm"
                if any(char in clean_time_str for char in ['–', '-']) and ('am' in clean_time_str.lower() or 'pm' in clean_time_str.lower()):
                    # Extract start time from range
                    for dash_char in ['–', '-']:
                        if dash_char in clean_time_str:
                            parts = clean_time_str.split(dash_char)
                            start_time_str = parts[0].strip()
                            # Extract am/pm from the range end
                            end_part = parts[1].strip() if len(parts) > 1 else ''
                            am_pm_match = re.search(r'\b(am|pm)\b', end_part, re.IGNORECASE)
                            if am_pm_match and 'am' not in start_time_str.lower() and 'pm' not in start_time_str.lower():
                                # Append am/pm to start time if not already present
                                start_time_str = f"{start_time_str} {am_pm_match.group(1)}"
                            break
                    else:
                        start_time_str = clean_time_str
                else:
                    start_time_str = clean_time_str
                
                # Common time formats
                time_formats = [
                    '%I:%M %p',        # 8:00 AM
                    '%I %p',            # 8 AM
                    '%I:%M%p',         # 7:00PM (no space)
                    '%H:%M',           # 08:00
                ]
                
                for fmt in time_formats:
                    try:
                        time_obj = datetime.strptime(start_time_str, fmt)
                        
                        parsed_date = parsed_date.replace(
                            hour=time_obj.hour,
                            minute=time_obj.minute,
                            second=0,
                            microsecond=0
                        )
                        break
                    except ValueError:
                        continue
            except Exception as e:
                logger.warning(f"Could not parse time '{time_str}' for date '{date_str}': {e}")
        
        return parsed_date
        
    except Exception as e:
        logger.warning(f"Error parsing datetime '{date_str}' + '{time_str}': {e}")
        return None


def extract_source_id(url: str) -> str:
    """
    Extract unique identifier from event URL.
    Handle different URL patterns per source.
    """
    if not url:
        return ""
    
    try:
        # Extract ID from URL patterns
        if '/event/' in url:
            # Pattern: https://site.com/event/event-name/2025-10-25/
            parts = url.split('/event/')
            if len(parts) > 1:
                event_part = parts[1].split('/')[0]
                return event_part
        
        # Fallback: use full URL as ID
        return url
        
    except Exception as e:
        logger.warning(f"Error extracting source ID from URL '{url}': {e}")
        return url


def create_scrape_run(session, source: str) -> int:
    """
    Create new ScrapeRun record with status='running'.
    Return scrape_run_id for linking events.
    """
    try:
        scrape_run = ScrapeRun(
            source=source,
            status='running',
            started_at=datetime.utcnow()
        )
        session.add(scrape_run)
        session.commit()
        
        logger.info(f"Created ScrapeRun {scrape_run.id} for source '{source}'")
        return scrape_run.id
        
    except Exception as e:
        logger.error(f"Error creating scrape run: {e}")
        session.rollback()
        raise


def complete_scrape_run(session, scrape_run_id: int, events_count: int, error: Optional[str] = None):
    """
    Update ScrapeRun with completion status.
    """
    try:
        scrape_run = session.query(ScrapeRun).filter(ScrapeRun.id == scrape_run_id).first()
        if scrape_run:
            scrape_run.completed_at = datetime.utcnow()
            scrape_run.events_scraped = events_count
            scrape_run.status = 'failed' if error else 'completed'
            if error:
                scrape_run.error_message = error
            
            session.commit()
            logger.info(f"Updated ScrapeRun {scrape_run_id}: {scrape_run.status}, {events_count} events")
        else:
            logger.error(f"ScrapeRun {scrape_run_id} not found")
            
    except Exception as e:
        logger.error(f"Error updating scrape run {scrape_run_id}: {e}")
        session.rollback()
        raise


def import_events(session, source: str, file_path: str, scrape_run_id: int) -> int:
    """
    Read JSON file from scraper output and import events.
    """
    try:
        # Read JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict) and 'events' in data:
            events = data['events']
        else:
            logger.error(f"Unexpected JSON structure in {file_path}")
            return 0
        
        imported_count = 0
        
        for event_data in events:
            try:
                # Map scraper fields to RawEvent fields
                title = event_data.get('eventName', '')
                event_date = event_data.get('eventDate', '')
                event_time = event_data.get('eventTime', '')
                event_description = event_data.get('eventDescription', '')
                venue = event_data.get('eventLocation', '')
                url = event_data.get('eventUrl', '')
                
                # Convert empty string to None for event_time and event_description (NULL in database)
                if event_time == '':
                    event_time = None
                if event_description == '':
                    event_description = None
                
                # Parse datetime
                start_time = parse_event_datetime(event_date, event_time)
                
                # Extract source ID
                source_id = extract_source_id(url)
                
                # Create RawEvent
                raw_event = RawEvent(
                    source=source,
                    source_id=source_id,
                    title=title,
                    description=event_description,
                    start_time=start_time,
                    venue=venue,
                    url=url,
                    raw_data=event_data,
                    scrape_run_id=scrape_run_id,
                    scraped_at=datetime.utcnow()
                )
                
                session.add(raw_event)
                imported_count += 1
                
            except Exception as e:
                logger.warning(f"Error importing event {event_data}: {e}")
                continue
        
        session.commit()
        logger.info(f"Imported {imported_count} events from {file_path}")
        return imported_count
        
    except Exception as e:
        logger.error(f"Error importing events from {file_path}: {e}")
        session.rollback()
        raise


def main():
    """Main script logic"""
    parser = argparse.ArgumentParser(description='Import scraped data into raw_events table')
    parser.add_argument('--source', required=True, help='Source name (kings_theatre, prospect_park, msg_calendar, brooklyn_museum, public_theater), brooklyn_paramount')
    parser.add_argument('--file', required=True, help='Path to JSON file to import')
    
    args = parser.parse_args()
    
    # Validate source
    valid_sources = ['kings_theatre', 'prospect_park', 'msg_calendar', 'brooklyn_museum', 'public_theater', 'brooklyn_paramount', 'bric_house', 'barclays_center', 'bam', 'lepistol', 'roulette', 'crown_hill_theatre', 'soapbox_gallery', 'farm_one', 'union_hall', 'bell_house', 'littlefield', 'shapeshifter_plus', 'concerts_on_the_slope', 'public_records', 'brooklyn_library', 'brooklyn_bowl', 'caveat', 'beacon_theatre', 'bowery_ballroom', 'the_shed', 'carnegie_hall', '92nd_street_y', 'brooklyn_bridge_park', 'soho_playhouse', 'connolly_theatre', 'apollo_theater', 'cherry_lane_theatre', 'greenwich_house', 'village_east', 'lincoln_center', 'radio_city', 'jazz_lincoln_center', 'town_hall', 'webster_hall', 'irving_plaza', 'blue_note', 'village_vanguard', 'joes_pub', 'city_winery', 'national_sawdust']
    if args.source not in valid_sources:
        logger.error(f"Invalid source '{args.source}'. Must be one of: {valid_sources}")
        sys.exit(1)
    
    # Validate file exists
    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"File not found: {args.file}")
        sys.exit(1)
    
    # Create database session
    session = SessionLocal()
    
    try:
        logger.info(f"Starting import for source '{args.source}' from file '{args.file}'")
        
        # Create scrape run
        scrape_run_id = create_scrape_run(session, args.source)
        
        # Import events
        events_count = import_events(session, args.source, args.file, scrape_run_id)
        
        # Complete scrape run
        complete_scrape_run(session, scrape_run_id, events_count)
        
        # Print summary
        print(f"\n=== Import Summary ===")
        print(f"Source: {args.source}")
        print(f"File: {args.file}")
        print(f"Scrape Run ID: {scrape_run_id}")
        print(f"Events Imported: {events_count}")
        print(f"Status: Completed successfully")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        # Try to update scrape run with error
        try:
            complete_scrape_run(session, scrape_run_id, 0, str(e))
        except:
            pass
        sys.exit(1)
        
    finally:
        session.close()


if __name__ == "__main__":
    main()
