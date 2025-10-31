#!/usr/bin/env python3
"""
Data Cleaning Pipeline (Within Source)

ARCHITECTURE:
- READ ONLY from raw_events table (scraper outputs)
- WRITE ONLY to clean_events table (cleaned data)
- NEVER modify raw_events table

This script processes raw events from the raw_events table and creates cleaned,
deduplicated events in the clean_events table. It handles:

1. Data standardization (title case, date/time formatting)
2. Within-source deduplication using fuzzy title matching
3. Quality control validation
4. Latest run detection per source

The raw_events table is treated as immutable - it contains the original
scraper outputs and should never be modified by this cleaning script.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, CleanEvent, SessionLocal, Venue
from src.logger import get_logger
from src.lib.google_maps import geocode_place, GoogleMapsError

# Import fuzzy matching
try:
    from Levenshtein import ratio
except ImportError:
    logger = get_logger('clean_events')
    logger.error("python-Levenshtein not installed. Run: pip install python-Levenshtein")
    sys.exit(1)

logger = get_logger('clean_events')


@dataclass
class CleaningStats:
    """Statistics for cleaning process"""
    source: str
    raw_events_processed: int
    duplicates_found: int
    clean_events_created: int
    quality_issues: int
    processing_time: float


def get_latest_run_per_source() -> Dict[str, ScrapeRun]:
    """
    Get the latest completed run for each source.
    Returns a dictionary mapping source -> ScrapeRun
    """
    session = SessionLocal()
    try:
        latest_runs = {}
        
        # Get all sources
        sources = session.query(ScrapeRun.source).distinct().all()
        
        for source_tuple in sources:
            source = source_tuple[0]
            latest_run = session.query(ScrapeRun).filter(
                ScrapeRun.source == source,
                ScrapeRun.status == 'completed'
            ).order_by(ScrapeRun.completed_at.desc()).first()
            
            if latest_run:
                latest_runs[source] = latest_run
                logger.info(f"Latest run for {source}: Run {latest_run.id} with {latest_run.events_scraped} events")
            else:
                logger.warning(f"No completed runs found for source '{source}'")
        
        return latest_runs
        
    except Exception as e:
        logger.error(f"Error getting latest runs: {e}")
        return {}
    finally:
        session.close()


def get_raw_events_for_run(scrape_run_id: int) -> List[RawEvent]:
    """Get all raw events for a specific scrape run."""
    session = SessionLocal()
    try:
        events = session.query(RawEvent).filter(
            RawEvent.scrape_run_id == scrape_run_id
        ).all()
        return events
    except Exception as e:
        logger.error(f"Error getting events for run {scrape_run_id}: {e}")
        return []
    finally:
        session.close()


def clear_existing_clean_events(source: str, session) -> int:
    """
    Clear existing clean events for a source before processing latest run.
    This ensures we don't have stale data from previous runs.
    Returns the number of events cleared.
    """
    try:
        existing_events = session.query(CleanEvent).filter(
            CleanEvent.source == source
        ).all()
        
        count = len(existing_events)
        if count > 0:
            logger.info(f"Clearing {count} existing clean events for {source}")
            for event in existing_events:
                session.delete(event)
        else:
            logger.info(f"No existing clean events found for {source}")
        
        return count
    except Exception as e:
        logger.error(f"Error clearing existing clean events for {source}: {e}")
        return 0


def standardize_title(title: str) -> str:
    """
    Standardize event title to title case with proper handling of special cases.
    """
    if not title:
        return ""
    
    # Clean up the title
    title = title.strip()
    
    # Abbreviations that should be uppercase
    uppercase_abbrevs = {
        'nyc': 'NYC',
        'ny': 'NY',
        'usa': 'USA',
        'uk': 'UK',
        'tv': 'TV',
        'dj': 'DJ',
        'ceo': 'CEO',
        'cto': 'CTO',
        'ai': 'AI',
        'ml': 'ML',
        'api': 'API',
        'html': 'HTML',
        'css': 'CSS',
        'js': 'JS',
        'sql': 'SQL',
        'json': 'JSON',
        'xml': 'XML',
        'http': 'HTTP',
        'https': 'HTTPS',
        'www': 'WWW',
        'com': 'COM',
        'org': 'ORG',
        'net': 'NET',
        'edu': 'EDU',
        'gov': 'GOV',
        'pm': 'PM',
        'am': 'AM',
        'est': 'EST',
        'pst': 'PST',
        'cst': 'CST',
        'mst': 'MST',
        'gmt': 'GMT',
        'utc': 'UTC',
        'rsvp': 'RSVP',
        'q&a': 'Q&A',
        'faq': 'FAQ',
        'etc': 'ETC',
        'ft': 'FT',
        'nd': 'ND',
        'rd': 'RD',
        'th': 'TH',
        'jr': 'JR',
        'sr': 'SR',
        'ii': 'II',
        'iii': 'III',
        'iv': 'IV',
        'v': 'V',
        'vi': 'VI',
        'vii': 'VII',
        'viii': 'VIII',
        'ix': 'IX',
        'x': 'X'
    }
    
    # Words that should always be lowercase (except at start of title)
    lowercase_words = {'vs', 'vs.', 'versus', 'of', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from'}
    
    # Apply special cases
    words = title.split()
    result_words = []
    
    for i, word in enumerate(words):
        # Handle apostrophes - lowercase the letter after apostrophe
        # Detect and handle both straight apostrophe (') and Unicode right single quotation mark (')
        apostrophe_char = None
        for char in ["'", "'", '"', '"']:
            if char in word:
                apostrophe_char = char
                break
        
        if apostrophe_char:
            parts = word.split(apostrophe_char)
            if len(parts) == 2:
                # e.g., "John'S" -> "John's"
                parts[1] = parts[1].lower()
                word = apostrophe_char.join(parts)
        
        # Check if word should be uppercase abbrev
        clean_word = re.sub(r'[^\w]', '', word.lower())
        if clean_word in uppercase_abbrevs:
            word = uppercase_abbrevs[clean_word]
        elif clean_word in lowercase_words and i > 0:  # Keep lowercase unless first word
            word = word.lower()
        else:
            # Apply title case
            word = word.title()
            # Fix apostrophes again after title case (handle Unicode apostrophes)
            apostrophe_char = None
            for char in ["'", "'", '"', '"']:
                if char in word:
                    apostrophe_char = char
                    break
            
            if apostrophe_char:
                parts = word.split(apostrophe_char)
                if len(parts) == 2:
                    parts[1] = parts[1].lower()
                    word = apostrophe_char.join(parts)
        
        result_words.append(word)
    
    return ' '.join(result_words)


def standardize_venue(venue: str) -> str:
    """
    Standardize venue names for consistency.
    """
    if not venue:
        return ""
    
    venue = venue.strip()
    
    # Common venue standardizations
    venue_mappings = {
        'kings theatre brooklyn': 'Kings Theatre',
        'kings theatre': 'Kings Theatre',
        'madison square garden': 'Madison Square Garden',
        'msg': 'Madison Square Garden',
        'prospect park': 'Prospect Park',
        'prospect park bandshell': 'Prospect Park Bandshell',
        'barclays center': 'Barclays Center',
        'brooklyn academy of music': 'Brooklyn Academy of Music',
        'bam': 'Brooklyn Academy of Music',
        'carnegie hall': 'Carnegie Hall',
        'lincoln center': 'Lincoln Center',
        'radio city music hall': 'Radio City Music Hall',
        'beacon theatre': 'Beacon Theatre',
        'beacon theater': 'Beacon Theatre',
        'hammerstein ballroom': 'Hammerstein Ballroom',
        'terminal 5': 'Terminal 5',
        'webster hall': 'Webster Hall',
        'bowery ballroom': 'Bowery Ballroom',
        'mercury lounge': 'Mercury Lounge',
        'irving plaza': 'Irving Plaza',
        'gramercy theatre': 'Gramercy Theatre',
        'gramercy theater': 'Gramercy Theatre',
        'playstation theater': 'PlayStation Theater',
        'playstation theatre': 'PlayStation Theater',
        'theatre at madison square garden': 'Theatre at Madison Square Garden',
        'theater at madison square garden': 'Theatre at Madison Square Garden'
    }
    
    # Check for exact matches first
    venue_lower = venue.lower().strip()
    if venue_lower in venue_mappings:
        return venue_mappings[venue_lower]
    
    # Apply title case for unmatched venues
    return standardize_title(venue)


def standardize_datetime(dt: datetime) -> datetime:
    """
    Standardize datetime by removing microseconds and normalizing timezone.
    """
    if not dt:
        return None
    
    # Remove microseconds and normalize to UTC
    return dt.replace(microsecond=0)


def normalize_title_for_matching(title: str) -> str:
    """
    Normalize title for fuzzy matching by removing common words, punctuation, and time indicators.
    """
    if not title:
        return ""
    
    # Convert to lowercase
    title = title.lower()
    
    # Remove time indicators that might be in titles (7pm, 9:30pm, 1pm show, etc.)
    time_patterns = [
        r'\b\d{1,2}:\d{2}\s*(am|pm)\b',  # 7:30pm, 9:30am
        r'\b\d{1,2}\s*(am|pm)\b',        # 7pm, 9am
        r'\b\d{1,2}pm\s*show\b',         # 1pm show
        r'\b\d{1,2}am\s*show\b',         # 1am show
        r'\(\d{1,2}:\d{2}\s*(am|pm)\)',  # (7:30pm)
        r'\(\d{1,2}\s*(am|pm)\)',        # (7pm)
        r'\(\d{1,2}pm\s*show\)',         # (1pm show)
        r'\(\d{1,2}am\s*show\)',         # (1am show)
    ]
    
    for pattern in time_patterns:
        title = re.sub(pattern, '', title)
    
    # Remove common words that don't add meaning
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'among', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
        'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
        'can', 'shall', 'live', 'concert', 'show', 'event', 'performance', 'presentation',
        'workshop', 'seminar', 'conference', 'festival', 'tour', 'tour', 'touring', 'tickets',
        'ticket', 'sale', 'sales', 'special', 'special', 'presented', 'by', 'featuring',
        'feat', 'ft', 'with', 'starring', 'starring', 'hosted', 'hosting', 'host'
    }
    
    # Remove punctuation and split into words
    words = re.findall(r'\b\w+\b', title)
    
    # Filter out stop words and short words
    filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
    
    return ' '.join(filtered_words)


def has_time_indicator_in_title(title: str) -> bool:
    """
    Check if a title contains time indicators that suggest different show times.
    """
    if not title:
        return False
    
    title_lower = title.lower()
    time_patterns = [
        r'\b\d{1,2}:\d{2}\s*(am|pm)\b',  # 7:30pm, 9:30am
        r'\b\d{1,2}\s*(am|pm)\b',        # 7pm, 9am
        r'\b\d{1,2}pm\s*show\b',         # 1pm show
        r'\b\d{1,2}am\s*show\b',         # 1am show
        r'\(\d{1,2}:\d{2}\s*(am|pm)\)',  # (7:30pm)
        r'\(\d{1,2}\s*(am|pm)\)',        # (7pm)
        r'\(\d{1,2}pm\s*show\)',         # (1pm show)
        r'\(\d{1,2}am\s*show\)',         # (1am show)
    ]
    
    for pattern in time_patterns:
        if re.search(pattern, title_lower):
            return True
    
    return False


def find_duplicates_within_source(events: List[RawEvent], similarity_threshold: float = 0.85) -> List[List[RawEvent]]:
    """
    Find duplicate events within a source using fuzzy title matching and EXACT same date/time.
    Only considers events as duplicates if they don't have time indicators in their titles.
    Returns a list of duplicate groups.
    """
    if len(events) < 2:
        return []
    
    duplicates = []
    processed = set()
    
    for i, event1 in enumerate(events):
        if event1.id in processed:
            continue
            
        # Skip events with time indicators - these are different show times, not duplicates
        if has_time_indicator_in_title(event1.title or ""):
            continue
            
        duplicate_group = [event1]
        processed.add(event1.id)
        
        for j, event2 in enumerate(events[i+1:], i+1):
            if event2.id in processed:
                continue
            
            # Skip events with time indicators
            if has_time_indicator_in_title(event2.title or ""):
                continue
            
            # Check if events have EXACT same date and time
            same_datetime = False
            if event1.start_time and event2.start_time:
                # Must be exactly the same time (no tolerance)
                same_datetime = event1.start_time == event2.start_time
            elif event1.start_time is None and event2.start_time is None:
                same_datetime = True
            
            if same_datetime:
                # Check title similarity
                title1 = normalize_title_for_matching(event1.title or "")
                title2 = normalize_title_for_matching(event2.title or "")
                
                if title1 and title2:
                    similarity = ratio(title1, title2)
                    if similarity >= similarity_threshold:
                        duplicate_group.append(event2)
                        processed.add(event2.id)
                        logger.debug(f"Found duplicate: '{event1.title}' ~ '{event2.title}' (similarity: {similarity:.2f})")
        
        if len(duplicate_group) > 1:
            duplicates.append(duplicate_group)
    
    return duplicates


def merge_duplicate_events(duplicate_group: List[RawEvent]) -> RawEvent:
    """
    Merge a group of duplicate events into a single event.
    Uses the event with the most complete data as the base.
    """
    if not duplicate_group:
        return None
    
    if len(duplicate_group) == 1:
        return duplicate_group[0]
    
    # Score events by completeness
    def score_event(event):
        score = 0
        if event.title:
            score += 1
        if event.description:
            score += 1
        if event.start_time:
            score += 1
        if event.end_time:
            score += 1
        if event.location:
            score += 1
        if event.venue:
            score += 1
        if event.url:
            score += 1
        if event.image_url:
            score += 1
        return score
    
    # Find the most complete event
    best_event = max(duplicate_group, key=score_event)
    
    # Merge data from other events
    merged_event = RawEvent(
        id=best_event.id,
        source=best_event.source,
        source_id=best_event.source_id,
        title=best_event.title,
        description=best_event.description,
        start_time=best_event.start_time,
        end_time=best_event.end_time,
        location=best_event.location,
        venue=best_event.venue,
        price_info=best_event.price_info,
        category=best_event.category,
        url=best_event.url,
        image_url=best_event.image_url,
        raw_data=best_event.raw_data,
        scraped_at=best_event.scraped_at,
        processed=best_event.processed,
        scrape_run_id=best_event.scrape_run_id
    )
    
    # Fill in missing data from other events
    for event in duplicate_group:
        if event.id == best_event.id:
            continue
            
        if not merged_event.description and event.description:
            merged_event.description = event.description
        if not merged_event.end_time and event.end_time:
            merged_event.end_time = event.end_time
        if not merged_event.location and event.location:
            merged_event.location = event.location
        if not merged_event.venue and event.venue:
            merged_event.venue = event.venue
        if not merged_event.price_info and event.price_info:
            merged_event.price_info = event.price_info
        if not merged_event.category and event.category:
            merged_event.category = event.category
        if not merged_event.image_url and event.image_url:
            merged_event.image_url = event.image_url
    
    return merged_event


def validate_event_quality(event: RawEvent) -> List[str]:
    """
    Validate event data quality and return list of issues.
    """
    issues = []
    
    if not event.title or event.title.strip() == "":
        issues.append("Missing title")
    
    if not event.start_time:
        issues.append("Missing start_time (required by PRD)")
    
    if not event.url or not event.url.startswith(('http://', 'https://')):
        issues.append("Missing or invalid URL")
    
    if event.title and len(event.title.strip()) < 3:
        issues.append("Title too short")
    
    return issues


def clean_events_for_source(source: str, scrape_run: ScrapeRun) -> CleaningStats:
    """
    Clean events for a specific source and scrape run.
    
    ARCHITECTURE:
    - READ ONLY from raw_events table (scraper outputs)
    - WRITE ONLY to clean_events table (cleaned data)
    - NEVER modify raw_events table
    - ONLY process LATEST run to avoid duplicate clean events
    """
    start_time = datetime.now()
    
    logger.info(f"Starting cleaning for source '{source}' (Run {scrape_run.id})")
    
    # STEP 1: Verify this is the latest run for this source
    latest_runs = get_latest_run_per_source()
    if source not in latest_runs or latest_runs[source].id != scrape_run.id:
        logger.warning(f"Run {scrape_run.id} is not the latest run for {source}. Skipping to avoid duplicate clean events.")
        return CleaningStats(source, 0, 0, 0, 0, 0.0)
    
    logger.info(f"Confirmed: Run {scrape_run.id} is the latest run for {source}")
    
    # STEP 2: Get raw events for this run (READ ONLY)
    raw_events = get_raw_events_for_run(scrape_run.id)
    logger.info(f"Found {len(raw_events)} raw events for {source}")
    
    if not raw_events:
        logger.warning(f"No raw events found for {source}")
        return CleaningStats(source, 0, 0, 0, 0, 0.0)
    
    # Find duplicates (READ ONLY from raw_events)
    duplicates = find_duplicates_within_source(raw_events)
    logger.info(f"Found {len(duplicates)} duplicate groups in {source}")
    
    # Process duplicates and create clean events (WRITE ONLY to clean_events)
    session = SessionLocal()
    try:
        clean_events_created = 0
        quality_issues = 0
        
        # STEP 3: Clear existing clean events for this source (to avoid stale data)
        cleared_count = clear_existing_clean_events(source, session)
        
        # ARCHITECTURE ENFORCEMENT: We NEVER modify raw_events table - only read from it
        # All writes go to clean_events table only
        
        # Process non-duplicate events
        processed_ids = set()
        for duplicate_group in duplicates:
            for event in duplicate_group:
                processed_ids.add(event.id)
        
        for event in raw_events:
            if event.id not in processed_ids:
                # Create clean event from single event
                clean_event = create_clean_event(event, session)
                if clean_event:
                    clean_events_created += 1
                    quality_issues += len(validate_event_quality(event))
        
        # Process duplicate groups
        for duplicate_group in duplicates:
            merged_event = merge_duplicate_events(duplicate_group)
            if merged_event:
                clean_event = create_clean_event(merged_event, session)
                if clean_event:
                    clean_events_created += 1
                    quality_issues += len(validate_event_quality(merged_event))
        
        session.commit()
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        stats = CleaningStats(
            source=source,
            raw_events_processed=len(raw_events),
            duplicates_found=sum(len(group) - 1 for group in duplicates),
            clean_events_created=clean_events_created,
            quality_issues=quality_issues,
            processing_time=processing_time
        )
        
        logger.info(f"Cleaning completed for {source}: {cleared_count} existing events cleared, {clean_events_created} new clean events created")
        
        logger.info(f"Cleaning completed for {source}: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error cleaning events for {source}: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def get_or_create_venue(session, name: str, location_text: str) -> Venue:
    name = (name or '').strip()
    location_text = (location_text or '').strip()
    # find existing
    venue = session.query(Venue).filter(
        Venue.name == name,
        Venue.location_text == (location_text or None)
    ).first()
    if venue:
        return venue
    # create new (geocode once)
    venue = Venue(name=name, location_text=location_text or None)
    try:
        query = ' '.join([p for p in [name, location_text] if p])
        if query:
            geo = geocode_place(query)
            if geo:
                venue.latitude = float(geo.get('lat')) if geo.get('lat') is not None else None
                venue.longitude = float(geo.get('lng')) if geo.get('lng') is not None else None
    except GoogleMapsError as e:
        logger.warning(f"Venue geocoding failed for '{name}': {e}")
    except Exception as e:
        logger.warning(f"Unexpected venue geocoding error for '{name}': {e}")
    session.add(venue)
    session.flush()
    return venue


def create_clean_event(raw_event: RawEvent, session) -> Optional[CleanEvent]:
    """
    Create a clean event from a raw event.
    
    ARCHITECTURE ENFORCEMENT: This function ONLY creates CleanEvent objects.
    It NEVER modifies RawEvent objects or writes to raw_events table.
    """
    try:
        # Validate required fields
        if not raw_event.title or not raw_event.start_time:
            logger.warning(f"Skipping event {raw_event.id}: missing required fields")
            return None
        
        # Set display_venue based on source
        venue_name = standardize_venue(raw_event.venue)
        if raw_event.source == 'prospect_park':
            display_venue = "Prospect Park"
        else:
            display_venue = venue_name
        
        # Resolve normalized venue once; do not compute per-event distances/times
        venue_obj = get_or_create_venue(session, display_venue, raw_event.location or '')

        # Create clean event (WRITE ONLY to clean_events table)
        clean_event = CleanEvent(
            title=standardize_title(raw_event.title),
            description=raw_event.description,
            start_time=standardize_datetime(raw_event.start_time),
            end_time=standardize_datetime(raw_event.end_time),
            location=raw_event.location,
            venue=venue_name,  # Detailed venue preserved
            display_venue=display_venue,  # Simplified venue for UI
            price_range=raw_event.price_info,
            category=raw_event.category,
            url=raw_event.url,
            image_url=raw_event.image_url,
            source=raw_event.source,
            source_urls=[raw_event.url] if raw_event.url else [],
            venue_id=venue_obj.id
        )
        
        # Add to session (clean_events table only)
        session.add(clean_event)
        return clean_event
        
    except Exception as e:
        logger.error(f"Error creating clean event from raw event {raw_event.id}: {e}")
        return None


def clean_all_sources() -> List[CleaningStats]:
    """
    Clean events for all sources using their latest runs.
    """
    logger.info("Starting cleaning for all sources")
    
    # Get latest runs for all sources
    latest_runs = get_latest_run_per_source()
    
    if not latest_runs:
        logger.error("No completed runs found for any source")
        return []
    
    all_stats = []
    
    for source, scrape_run in latest_runs.items():
        try:
            stats = clean_events_for_source(source, scrape_run)
            all_stats.append(stats)
        except Exception as e:
            logger.error(f"Failed to clean events for {source}: {e}")
            continue
    
    return all_stats


def print_cleaning_summary(stats_list: List[CleaningStats]):
    """
    Print a summary of the cleaning process.
    """
    if not stats_list:
        print("No cleaning performed.")
        return
    
    print("\n" + "="*60)
    print("DATA CLEANING SUMMARY")
    print("="*60)
    
    total_raw = sum(s.raw_events_processed for s in stats_list)
    total_duplicates = sum(s.duplicates_found for s in stats_list)
    total_clean = sum(s.clean_events_created for s in stats_list)
    total_issues = sum(s.quality_issues for s in stats_list)
    total_time = sum(s.processing_time for s in stats_list)
    
    print(f"Total Sources Processed: {len(stats_list)}")
    print(f"Total Raw Events: {total_raw}")
    print(f"Total Duplicates Found: {total_duplicates}")
    print(f"Total Clean Events Created: {total_clean}")
    print(f"Total Quality Issues: {total_issues}")
    print(f"Total Processing Time: {total_time:.2f} seconds")
    
    print(f"\nPer-Source Breakdown:")
    for stats in stats_list:
        print(f"  {stats.source}:")
        print(f"    Raw Events: {stats.raw_events_processed}")
        print(f"    Duplicates: {stats.duplicates_found}")
        print(f"    Clean Events: {stats.clean_events_created}")
        print(f"    Quality Issues: {stats.quality_issues}")
        print(f"    Processing Time: {stats.processing_time:.2f}s")
    
    print("="*60)


def main():
    """Main CLI interface for the data cleaning pipeline."""
    parser = argparse.ArgumentParser(description='Clean and deduplicate event data')
    parser.add_argument('--source', 
                       choices=['kings_theatre', 'msg_calendar', 'prospect_park', 'brooklyn_museum', 'public_theater', 'brooklyn_paramount', 'bric_house', 'barclays_center', 'lepistol', 'roulette', 'crown_hill_theatre', 'soapbox_gallery', 'farm_one', 'union_hall', 'bell_house', 'littlefield', 'shapeshifter_plus', 'concerts_on_the_slope', 'public_records'],
                       help='Clean events for specific source (default: all sources)')
    parser.add_argument('--run-id', type=int,
                       help='Clean events for specific scrape run ID')
    parser.add_argument('--similarity-threshold', type=float, default=0.85,
                       help='Title similarity threshold for duplicate detection (default: 0.85)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be cleaned without making changes')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        # TODO: Implement dry run functionality
        print("Dry run mode not yet implemented")
        return
    
    try:
        if args.source and args.run_id:
            # Clean specific source and run
            session = SessionLocal()
            try:
                scrape_run = session.query(ScrapeRun).filter(
                    ScrapeRun.id == args.run_id,
                    ScrapeRun.source == args.source,
                    ScrapeRun.status == 'completed'
                ).first()
                
                if not scrape_run:
                    logger.error(f"Run {args.run_id} not found for source '{args.source}'")
                    return
                
                stats = clean_events_for_source(args.source, scrape_run)
                print_cleaning_summary([stats])
                
            finally:
                session.close()
                
        elif args.source:
            # Clean specific source (latest run)
            latest_runs = get_latest_run_per_source()
            if args.source not in latest_runs:
                logger.error(f"No completed runs found for source '{args.source}'")
                return
            
            stats = clean_events_for_source(args.source, latest_runs[args.source])
            print_cleaning_summary([stats])
            
        else:
            # Clean all sources
            stats_list = clean_all_sources()
            print_cleaning_summary(stats_list)
    
    except Exception as e:
        logger.error(f"Cleaning failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
