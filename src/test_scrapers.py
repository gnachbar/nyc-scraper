#!/usr/bin/env python3
"""
Scraper Testing and Reporting Framework

This script compares current scrape runs against previous runs to detect:
- Added events (in current run, not in previous)
- Removed events (in previous run, not in current)
- Data quality issues
- Generates JSON reports and console summaries
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from models import ScrapeRun, RawEvent, SessionLocal
from logger import get_logger

logger = get_logger('test_scrapers')


@dataclass
class EventComparison:
    """Represents the comparison between two events"""
    event_id: int
    title: str
    start_time: datetime
    url: str
    source: str


@dataclass
class QualityIssue:
    """Represents a data quality issue found in an event"""
    event_id: int
    title: str
    issue_type: str
    description: str
    severity: str  # 'warning' or 'error'


def get_latest_two_runs(source: str) -> Tuple[Optional[ScrapeRun], Optional[ScrapeRun]]:
    """
    Get the two most recent completed runs for a given source.
    Returns (current_run, previous_run) or (None, None) if not enough runs exist.
    """
    session = SessionLocal()
    try:
        runs = session.query(ScrapeRun).filter(
            ScrapeRun.source == source,
            ScrapeRun.status == 'completed'
        ).order_by(ScrapeRun.completed_at.desc()).limit(2).all()
        
        if len(runs) < 2:
            logger.warning(f"Not enough completed runs for source '{source}'. Found {len(runs)} runs.")
            if len(runs) == 1:
                return runs[0], None
            else:
                return None, None
            
        return runs[0], runs[1]  # Most recent, second most recent
        
    except Exception as e:
        logger.error(f"Error getting latest runs for source '{source}': {e}")
        return None, None
    finally:
        session.close()


def get_events_for_run(scrape_run_id: int) -> List[RawEvent]:
    """Get all events for a specific scrape run."""
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


def compare_scrape_runs(current_run_id: int, previous_run_id: int) -> Dict[str, Any]:
    """
    Compare two scrape runs and return detailed comparison data.
    """
    logger.info(f"Comparing runs: current={current_run_id}, previous={previous_run_id}")
    
    current_events = get_events_for_run(current_run_id)
    previous_events = get_events_for_run(previous_run_id)
    
    logger.info(f"Current run has {len(current_events)} events, previous run has {len(previous_events)} events")
    
    # Create lookup dictionaries for efficient comparison
    # Use a more robust key that handles None values
    def create_event_key(event):
        return (
            event.title or "NO_TITLE",
            event.start_time,
            event.url or "NO_URL"
        )
    
    current_lookup = {create_event_key(event): event for event in current_events}
    previous_lookup = {create_event_key(event): event for event in previous_events}
    
    # Find added events (in current, not in previous)
    added_events = []
    for key, event in current_lookup.items():
        if key not in previous_lookup:
            added_events.append({
                'id': event.id,
                'title': event.title,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'url': event.url,
                'venue': event.venue,
                'location': event.location
            })
    
    # Find removed events (in previous, not in current)
    removed_events = []
    for key, event in previous_lookup.items():
        if key not in current_lookup:
            removed_events.append({
                'id': event.id,
                'title': event.title,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'url': event.url,
                'venue': event.venue,
                'location': event.location
            })
    
    # Find unchanged events (in both)
    unchanged_events = []
    for key, event in current_lookup.items():
        if key in previous_lookup:
            unchanged_events.append({
                'id': event.id,
                'title': event.title,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'url': event.url,
                'venue': event.venue,
                'location': event.location
            })
    
    # Validate the comparison makes sense
    total_events = len(added_events) + len(removed_events) + len(unchanged_events)
    if total_events != len(current_events):
        logger.warning(f"Comparison validation failed: {total_events} != {len(current_events)} current events")
    
    return {
        'total_current': len(current_events),
        'total_previous': len(previous_events),
        'added': len(added_events),
        'removed': len(removed_events),
        'unchanged': len(unchanged_events),
        'added_events': added_events,
        'removed_events': removed_events,
        'unchanged_events': unchanged_events,
        'comparison_valid': total_events == len(current_events)
    }


def validate_event_quality(event: RawEvent) -> List[QualityIssue]:
    """
    Validate an event for data quality issues.
    Returns a list of QualityIssue objects.
    """
    issues = []
    
    # Check for missing start_time (PRD requirement)
    if not event.start_time:
        issues.append(QualityIssue(
            event_id=event.id,
            title=event.title or "Unknown",
            issue_type="missing_start_time",
            description="Event is missing start_time (required by PRD)",
            severity="error"
        ))
    
    # Check for missing title
    if not event.title or event.title.strip() == "":
        issues.append(QualityIssue(
            event_id=event.id,
            title="Unknown",
            issue_type="missing_title",
            description="Event is missing title",
            severity="error"
        ))
    
    # Check for missing URL
    if not event.url or event.url.strip() == "":
        issues.append(QualityIssue(
            event_id=event.id,
            title=event.title or "Unknown",
            issue_type="missing_url",
            description="Event is missing URL",
            severity="warning"
        ))
    
    # Check for invalid URL format
    if event.url and not event.url.startswith(('http://', 'https://')):
        issues.append(QualityIssue(
            event_id=event.id,
            title=event.title or "Unknown",
            issue_type="invalid_url",
            description=f"URL format appears invalid: {event.url}",
            severity="warning"
        ))
    
    # Check for very short titles (might be incomplete)
    if event.title and len(event.title.strip()) < 5:
        issues.append(QualityIssue(
            event_id=event.id,
            title=event.title,
            issue_type="short_title",
            description=f"Title is very short (may be incomplete): '{event.title}'",
            severity="warning"
        ))
    
    return issues


def analyze_removed_events_patterns(removed_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze patterns in removed events to help identify potential issues.
    """
    if not removed_events:
        return {'pattern_detected': False, 'analysis': 'No removed events to analyze'}
    
    analysis = {
        'pattern_detected': True,
        'total_removed': len(removed_events),
        'venue_distribution': {},
        'date_patterns': {},
        'title_patterns': {},
        'potential_issues': []
    }
    
    # Analyze venue distribution
    venues = [event.get('venue', 'Unknown') for event in removed_events]
    venue_counts = {}
    for venue in venues:
        venue_counts[venue] = venue_counts.get(venue, 0) + 1
    analysis['venue_distribution'] = venue_counts
    
    # Check for patterns in titles (common words, formats)
    titles = [event.get('title', '') for event in removed_events]
    common_words = {}
    for title in titles:
        words = title.lower().split()
        for word in words:
            if len(word) > 3:  # Skip short words
                common_words[word] = common_words.get(word, 0) + 1
    
    # Get most common words
    sorted_words = sorted(common_words.items(), key=lambda x: x[1], reverse=True)
    analysis['title_patterns'] = {
        'most_common_words': sorted_words[:5],
        'total_unique_words': len(common_words)
    }
    
    # Check for potential issues
    if len(removed_events) > len(venues) * 0.8:  # Most events from same venue
        analysis['potential_issues'].append('Most removed events from same venue - possible venue-specific issue')
    
    if any(word in ' '.join(titles).lower() for word in ['cancelled', 'canceled', 'postponed']):
        analysis['potential_issues'].append('Some events may have been cancelled/postponed')
    
    if len(removed_events) > 10:
        analysis['potential_issues'].append('High number of removed events - investigate scraper changes')
    
    return analysis


def generate_scrape_report(comparison: Dict[str, Any], source: str, 
                          current_run: ScrapeRun, previous_run: ScrapeRun,
                          output_file: str) -> Dict[str, Any]:
    """
    Generate a comprehensive JSON report of the scrape comparison.
    Returns the quality issues for use in console summary.
    """
    # Get quality issues for current run events
    current_events = get_events_for_run(current_run.id)
    quality_issues = []
    
    for event in current_events:
        issues = validate_event_quality(event)
        for issue in issues:
            quality_issues.append({
                'event_id': issue.event_id,
                'title': issue.title,
                'issue_type': issue.issue_type,
                'description': issue.description,
                'severity': issue.severity
            })
    
    # Analyze removed events patterns
    removed_events_analysis = analyze_removed_events_patterns(comparison['removed_events'])
    
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'source': source,
        'current_run': {
            'id': current_run.id,
            'started_at': current_run.started_at.isoformat(),
            'completed_at': current_run.completed_at.isoformat() if current_run.completed_at else None,
            'events_scraped': current_run.events_scraped,
            'status': current_run.status
        },
        'previous_run': {
            'id': previous_run.id,
            'started_at': previous_run.started_at.isoformat(),
            'completed_at': previous_run.completed_at.isoformat() if previous_run.completed_at else None,
            'events_scraped': previous_run.events_scraped,
            'status': previous_run.status
        },
        'summary': {
            'total_current': comparison['total_current'],
            'total_previous': comparison['total_previous'],
            'added': comparison['added'],
            'removed': comparison['removed'],
            'unchanged': comparison['unchanged'],
            'quality_issues_count': len(quality_issues),
            'error_count': len([i for i in quality_issues if i['severity'] == 'error']),
            'warning_count': len([i for i in quality_issues if i['severity'] == 'warning']),
            'removed_events_percentage': round((comparison['removed'] / comparison['total_previous']) * 100, 2) if comparison['total_previous'] > 0 else 0,
            'added_events_percentage': round((comparison['added'] / comparison['total_current']) * 100, 2) if comparison['total_current'] > 0 else 0
        },
        'added_events': comparison['added_events'],
        'removed_events': comparison['removed_events'],
        'removed_events_analysis': removed_events_analysis,
        'quality_issues': quality_issues,
        'analysis': {
            'data_stability': 'stable' if comparison['removed'] == 0 else 'unstable',
            'growth_trend': 'growing' if comparison['added'] > comparison['removed'] else 'declining' if comparison['removed'] > comparison['added'] else 'stable',
            'change_magnitude': 'significant' if abs(comparison['added'] - comparison['removed']) > 5 else 'minor'
        }
    }
    
    # Write report to file
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Scrape report saved to: {output_file}")
    
    return quality_issues


def print_console_summary(comparison: Dict[str, Any], source: str, 
                         current_run: ScrapeRun, previous_run: ScrapeRun,
                         quality_issues: List[Dict[str, Any]]) -> None:
    """
    Print a summary of the scrape comparison to console.
    """
    print(f"\n=== Scrape Test Results for {source.upper()} ===")
    print(f"Current Run ID: {current_run.id} ({current_run.completed_at})")
    print(f"Previous Run ID: {previous_run.id} ({previous_run.completed_at})")
    print(f"\nEvent Count Changes:")
    print(f"  Current: {comparison['total_current']} events")
    print(f"  Previous: {comparison['total_previous']} events")
    print(f"  Added: {comparison['added']} events")
    print(f"  Removed: {comparison['removed']} events")
    print(f"  Unchanged: {comparison['unchanged']} events")
    
    # Highlight removed events prominently
    if comparison['removed'] > 0:
        print(f"\n⚠️  REMOVED EVENTS DETECTED ({comparison['removed']} events):")
        for event in comparison['removed_events'][:10]:  # Show first 10
            print(f"  ❌ {event['title']} ({event['start_time']})")
            if event.get('venue'):
                print(f"     Venue: {event['venue']}")
        if len(comparison['removed_events']) > 10:
            print(f"  ... and {len(comparison['removed_events']) - 10} more removed events")
        print(f"  📊 Total removed: {comparison['removed']} events")
    
    if comparison['added'] > 0:
        print(f"\n✅ New Events Added ({comparison['added']} events):")
        for event in comparison['added_events'][:5]:  # Show first 5
            print(f"  + {event['title']} ({event['start_time']})")
        if len(comparison['added_events']) > 5:
            print(f"  ... and {len(comparison['added_events']) - 5} more")
    
    # Show quality issues if any
    if quality_issues:
        error_count = len([i for i in quality_issues if i.get('severity') == 'error'])
        warning_count = len([i for i in quality_issues if i.get('severity') == 'warning'])
        
        if error_count > 0:
            print(f"\n🚨 DATA QUALITY ERRORS ({error_count} errors):")
            for issue in quality_issues[:5]:
                if issue.get('severity') == 'error':
                    print(f"  ❌ {issue['title']}: {issue['description']}")
        
        if warning_count > 0:
            print(f"\n⚠️  DATA QUALITY WARNINGS ({warning_count} warnings):")
            for issue in quality_issues[:3]:
                if issue.get('severity') == 'warning':
                    print(f"  ⚠️  {issue['title']}: {issue['description']}")
    
    print(f"\n=== Test Complete ===\n")


def test_scraper_run(source: str, scrape_run_id: Optional[int] = None) -> bool:
    """
    Test a scraper run by comparing it against the previous run.
    Returns True if test passed, False otherwise.
    """
    logger.info(f"Starting scraper test for source: {source}")
    
    # Get the latest two runs
    current_run, previous_run = get_latest_two_runs(source)
    
    if not current_run:
        logger.error(f"No completed runs found for source '{source}'")
        return False
    
    if not previous_run:
        logger.warning(f"Only one completed run found for source '{source}'. Cannot compare.")
        print(f"\n=== Scrape Test Results for {source.upper()} ===")
        print(f"Current Run ID: {current_run.id} ({current_run.completed_at})")
        print(f"Events: {current_run.events_scraped}")
        print("Note: This is the first run - no comparison available")
        print(f"=== Test Complete ===\n")
        return True
    
    # If specific run ID provided, use that as current
    if scrape_run_id and scrape_run_id != current_run.id:
        session = SessionLocal()
        try:
            specified_run = session.query(ScrapeRun).filter(
                ScrapeRun.id == scrape_run_id,
                ScrapeRun.source == source,
                ScrapeRun.status == 'completed'
            ).first()
            if specified_run:
                current_run = specified_run
            else:
                logger.error(f"Run {scrape_run_id} not found or not completed for source '{source}'")
                return False
        finally:
            session.close()
    
    # Compare the runs
    comparison = compare_scrape_runs(current_run.id, previous_run.id)
    
    # Generate report file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"data/output/scrape_test_report_{source}_{timestamp}.json"
    Path("data/output").mkdir(parents=True, exist_ok=True)
    
    quality_issues = generate_scrape_report(comparison, source, current_run, previous_run, output_file)
    
    # Print console summary
    print_console_summary(comparison, source, current_run, previous_run, quality_issues)
    
    # Determine if test passed (no critical errors)
    error_count = len([i for i in quality_issues if i.get('severity') == 'error'])
    test_passed = error_count == 0
    
    if not test_passed:
        logger.warning(f"Scraper test failed for {source}: {error_count} critical errors found")
    else:
        logger.info(f"Scraper test passed for {source}")
    
    return test_passed


def main():
    """Main CLI interface for the scraper testing framework."""
    parser = argparse.ArgumentParser(description='Test and report on scraper runs')
    parser.add_argument('--source', required=True, 
                       choices=['kings_theatre', 'msg_calendar', 'prospect_park'],
                       help='Source to test')
    parser.add_argument('--run-id', type=int, 
                       help='Specific scrape run ID to test (defaults to latest)')
    parser.add_argument('--all', action='store_true',
                       help='Test all sources')
    
    args = parser.parse_args()
    
    if args.all:
        sources = ['kings_theatre', 'msg_calendar', 'prospect_park']
        all_passed = True
        
        for source in sources:
            print(f"\n{'='*60}")
            print(f"Testing {source.upper()}")
            print(f"{'='*60}")
            
            passed = test_scraper_run(source)
            if not passed:
                all_passed = False
        
        if all_passed:
            print(f"\n✅ All scraper tests passed!")
            sys.exit(0)
        else:
            print(f"\n❌ Some scraper tests failed!")
            sys.exit(1)
    else:
        passed = test_scraper_run(args.source, args.run_id)
        sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
