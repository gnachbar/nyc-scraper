#!/usr/bin/env python3
"""
Data Pipeline Orchestration Script

Runs all scrapers sequentially with automatic cleaning and validation.
Generates comprehensive reports for monitoring and debugging.
"""

import subprocess
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, CleanEvent, SessionLocal
from src.logger import get_logger

logger = get_logger('run_pipeline')


@dataclass
class ScraperResult:
    """Results from running a single scraper"""
    source: str
    success: bool
    events_scraped: int
    events_cleaned: int
    test_passed: bool
    error_message: Optional[str]
    duration_seconds: float


@dataclass
class PipelineReport:
    """Complete pipeline execution report"""
    timestamp: str
    overall_success: bool
    total_duration: float
    scrapers: List[ScraperResult]
    summary: Dict[str, Any]


def run_scraper(source: str) -> ScraperResult:
    """
    Run a single Node.js scraper.
    
    Args:
        source: Source name (kings_theatre, msg_calendar, prospect_park)
    
    Returns:
        ScraperResult with execution details
    """
    start_time = datetime.now()
    logger.info(f"Starting scraper: {source}")
    
    try:
        # Run the Node.js scraper
        result = subprocess.run(
            ['node', f'src/scrapers/{source}.js'],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if result.returncode != 0:
            logger.error(f"Scraper {source} failed with return code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return ScraperResult(
                source=source,
                success=False,
                events_scraped=0,
                events_cleaned=0,
                test_passed=False,
                error_message=result.stderr[:500] if result.stderr else "Unknown error",
                duration_seconds=duration
            )
        
        # Parse events scraped from output
        events_scraped = parse_events_scraped(source, result.stdout)
        
        logger.info(f"Scraper {source} completed successfully: {events_scraped} events")
        
        return ScraperResult(
            source=source,
            success=True,
            events_scraped=events_scraped,
            events_cleaned=0,  # Will be updated after cleaning
            test_passed=False,  # Will be updated after testing
            error_message=None,
            duration_seconds=duration
        )
        
    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Scraper {source} timed out after {duration} seconds")
        return ScraperResult(
            source=source,
            success=False,
            events_scraped=0,
            events_cleaned=0,
            test_passed=False,
            error_message=f"Timeout after {duration} seconds",
            duration_seconds=duration
        )
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Scraper {source} encountered exception: {e}")
        return ScraperResult(
            source=source,
            success=False,
            events_scraped=0,
            events_cleaned=0,
            test_passed=False,
            error_message=str(e),
            duration_seconds=duration
        )


def parse_events_scraped(source: str, output: str) -> int:
    """
    Parse the number of events scraped from scraper output.
    
    Args:
        source: Source name
        output: Console output from scraper
    
    Returns:
        Number of events scraped
    """
    # Try to parse from output (looking for "Total events found: X")
    for line in output.split('\n'):
        if 'Total events found:' in line or 'Events Imported:' in line:
            try:
                # Extract number from line
                parts = line.split(':')
                if len(parts) >= 2:
                    number_str = parts[1].strip().split()[0]
                    return int(number_str)
            except (ValueError, IndexError):
                pass
    
    # Fallback: query database for latest run
    try:
        session = SessionLocal()
        latest_run = session.query(ScrapeRun).filter(
            ScrapeRun.source == source
        ).order_by(ScrapeRun.id.desc()).first()
        
        if latest_run:
            count = latest_run.events_scraped or 0
            session.close()
            return count
        session.close()
    except Exception as e:
        logger.warning(f"Could not query database for events count: {e}")
    
    return 0


def run_cleaning(source: str) -> tuple[bool, int]:
    """
    Run cleaning script for a source.
    
    Args:
        source: Source name
    
    Returns:
        Tuple of (success, events_cleaned)
    """
    logger.info(f"Running cleaning for {source}")
    
    try:
        result = subprocess.run(
            ['python3', 'src/clean_events.py', '--source', source],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Cleaning failed for {source}: {result.stderr}")
            return False, 0
        
        # Parse events cleaned from output
        events_cleaned = parse_events_cleaned(result.stdout)
        
        logger.info(f"Cleaning completed for {source}: {events_cleaned} events")
        return True, events_cleaned
        
    except Exception as e:
        logger.error(f"Cleaning encountered exception for {source}: {e}")
        return False, 0


def parse_events_cleaned(output: str) -> int:
    """
    Parse the number of events cleaned from cleaning output.
    
    Args:
        output: Console output from cleaning script
    
    Returns:
        Number of events cleaned
    """
    for line in output.split('\n'):
        if 'Clean Events Created:' in line:
            try:
                parts = line.split(':')
                if len(parts) >= 2:
                    number_str = parts[1].strip()
                    return int(number_str)
            except (ValueError, IndexError):
                pass
    
    return 0


def run_tests(source: str) -> bool:
    """
    Run test script for a source.
    
    Args:
        source: Source name
    
    Returns:
        True if tests passed, False otherwise
    """
    logger.info(f"Running tests for {source}")
    
    try:
        result = subprocess.run(
            ['python3', 'src/test_scrapers.py', '--source', source],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            logger.warning(f"Tests failed for {source}: {result.stderr}")
            return False
        
        logger.info(f"Tests passed for {source}")
        return True
        
    except Exception as e:
        logger.error(f"Tests encountered exception for {source}: {e}")
        return False


def generate_reports(report: PipelineReport, output_dir: Path):
    """
    Generate JSON and console reports.
    
    Args:
        report: Pipeline report data
        output_dir: Directory to save reports
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Generate JSON report
    json_file = output_dir / f'pipeline_report_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(asdict(report), f, indent=2, default=str)
    
    logger.info(f"JSON report saved to: {json_file}")
    
    # Generate console summary
    print("\n" + "="*70)
    print("PIPELINE EXECUTION SUMMARY")
    print("="*70)
    print(f"Timestamp: {report.timestamp}")
    print(f"Overall Success: {'✓' if report.overall_success else '✗'}")
    print(f"Total Duration: {report.total_duration:.1f} seconds")
    print()
    
    print("Scraper Results:")
    for scraper in report.scrapers:
        status = "✓" if scraper.success else "✗"
        print(f"  {status} {scraper.source}:")
        print(f"    Events Scraped: {scraper.events_scraped}")
        print(f"    Events Cleaned: {scraper.events_cleaned}")
        print(f"    Tests Passed: {'Yes' if scraper.test_passed else 'No'}")
        print(f"    Duration: {scraper.duration_seconds:.1f}s")
        if scraper.error_message:
            print(f"    Error: {scraper.error_message[:100]}")
        print()
    
    print("Summary:")
    print(f"  Total Events Scraped: {report.summary['total_events_scraped']}")
    print(f"  Total Events Cleaned: {report.summary['total_events_cleaned']}")
    print(f"  Successful Scrapers: {report.summary['successful_scrapers']}/{report.summary['total_scrapers']}")
    print(f"  Failed Scrapers: {report.summary['failed_scrapers']}")
    print("="*70)
    print()


def main():
    """Main orchestration logic"""
    parser = argparse.ArgumentParser(description='Run data pipeline for all scrapers')
    parser.add_argument('--source', 
                       choices=['kings_theatre', 'msg_calendar', 'prospect_park', 'brooklyn_museum'],
                       help='Run specific scraper only (default: all)')
    parser.add_argument('--skip-cleaning', action='store_true',
                       help='Skip cleaning step')
    parser.add_argument('--skip-tests', action='store_true',
                       help='Skip testing step')
    parser.add_argument('--output-dir', default='data/output',
                       help='Directory for output reports')
    
    args = parser.parse_args()
    
    # Determine which scrapers to run
    if args.source:
        sources = [args.source]
    else:
        sources = ['kings_theatre', 'msg_calendar', 'prospect_park', 'brooklyn_museum']
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Start pipeline
    pipeline_start = datetime.now()
    logger.info(f"Starting data pipeline for sources: {', '.join(sources)}")
    
    scraper_results = []
    
    # Run each scraper
    for source in sources:
        logger.info(f"\n{'='*70}")
        logger.info(f"Processing: {source}")
        logger.info(f"{'='*70}")
        
        # Run scraper
        result = run_scraper(source)
        
        # Run cleaning if scraper succeeded and not skipped
        if result.success and not args.skip_cleaning:
            cleaning_success, events_cleaned = run_cleaning(source)
            result.events_cleaned = events_cleaned
        elif result.success:
            # Query database for cleaned events count
            try:
                session = SessionLocal()
                count = session.query(CleanEvent).filter(
                    CleanEvent.source == source
                ).count()
                session.close()
                result.events_cleaned = count
            except Exception:
                result.events_cleaned = 0
        
        # Run tests if not skipped
        if not args.skip_tests:
            result.test_passed = run_tests(source)
        
        scraper_results.append(result)
    
    # Calculate summary
    total_duration = (datetime.now() - pipeline_start).total_seconds()
    total_events_scraped = sum(r.events_scraped for r in scraper_results)
    total_events_cleaned = sum(r.events_cleaned for r in scraper_results)
    successful_scrapers = sum(1 for r in scraper_results if r.success)
    failed_scrapers = len(scraper_results) - successful_scrapers
    overall_success = failed_scrapers == 0
    
    # Create report
    report = PipelineReport(
        timestamp=datetime.now().isoformat(),
        overall_success=overall_success,
        total_duration=total_duration,
        scrapers=scraper_results,
        summary={
            'total_events_scraped': total_events_scraped,
            'total_events_cleaned': total_events_cleaned,
            'successful_scrapers': successful_scrapers,
            'failed_scrapers': failed_scrapers,
            'total_scrapers': len(scraper_results)
        }
    )
    
    # Generate reports
    generate_reports(report, output_dir)
    
    # Exit with appropriate code
    sys.exit(0 if overall_success else 1)


if __name__ == '__main__':
    main()

