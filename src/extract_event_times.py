#!/usr/bin/env python3
"""
Generic Event Time Extractor

This script extracts event times from individual event pages by parsing JSON data
embedded in script tags. It's designed to be reusable across different venues
and event websites.

Usage:
    python src/extract_event_times.py input.json output.json

The input JSON should contain an array of events with 'eventUrl' fields.
The output JSON will contain the same events with 'eventTime' fields added.
"""

import json
import re
import sys
import argparse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
import time
from urllib.parse import urljoin, urlparse
from threading import Semaphore


class RateLimiter:
    """
    Rate limiter to control request frequency and be respectful to servers.
    """
    def __init__(self, max_requests_per_second: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_requests_per_second: Maximum requests per second (default: 1.0)
        """
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0
        self.semaphore = Semaphore(1)
    
    def wait_if_needed(self):
        """
        Wait if necessary to respect rate limits.
        """
        with self.semaphore:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()


def extract_time_from_page(url: str, timeout: int = 10, rate_limiter: RateLimiter = None) -> Optional[str]:
    """
    Extract event time from a single event page URL.
    
    Args:
        url: The event page URL
        timeout: Request timeout in seconds
        rate_limiter: Rate limiter instance to control request frequency
        
    Returns:
        The extracted time string, or None if not found
    """
    try:
        # Apply rate limiting if provided
        if rate_limiter:
            rate_limiter.wait_if_needed()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for JSON data in script tags
        for script in soup.find_all('script'):
            if not script.string:
                continue
                
            script_content = script.string
            
            # Try to extract startTime from JSON
            time_patterns = [
                r'"startTime":\s*"([^"]+)"',           # "startTime": "8:00 PM"
                r'"doorsOpen":\s*"([^"]+)"',           # "doorsOpen": "7:00 PM" 
                r'"eventTime":\s*"([^"]+)"',           # "eventTime": "8:00 PM"
                r'"showTime":\s*"([^"]+)"',            # "showTime": "8:00 PM"
                r'"performanceTime":\s*"([^"]+)"',     # "performanceTime": "8:00 PM"
                r'"time":\s*"([^"]+)"',                # "time": "8:00 PM"
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, script_content)
                if match:
                    time_str = match.group(1)
                    # Clean up the time string
                    time_str = time_str.strip()
                    if time_str and time_str != 'null' and time_str != 'undefined':
                        return time_str
        
        # If no JSON time found, try to extract from HTML content
        time_elements = soup.find_all(text=re.compile(r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)', re.I))
        for element in time_elements:
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))', element, re.I)
            if time_match:
                return time_match.group(1).upper()
        
        return None
        
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return None


def extract_times_for_event(event: Dict, rate_limiter: RateLimiter = None) -> Dict:
    """
    Extract time for a single event and return the updated event dict.
    
    Args:
        event: Event dictionary with 'eventUrl' field
        rate_limiter: Rate limiter instance to control request frequency
        
    Returns:
        Updated event dictionary with 'eventTime' field added
    """
    event_url = event.get('eventUrl')
    if not event_url:
        print(f"No URL found for event: {event.get('eventName', 'Unknown')}")
        return event
    
    # Ensure URL is absolute
    if not event_url.startswith(('http://', 'https://')):
        # Try to construct absolute URL (this is venue-specific)
        if 'kingstheatre.com' in event_url or 'kingstheatre.com' in event.get('eventUrl', ''):
            event_url = f"https://www.kingstheatre.com{event_url}" if event_url.startswith('/') else f"https://www.kingstheatre.com/{event_url}"
        else:
            print(f"Cannot resolve relative URL: {event_url}")
            return event
    
    print(f"Extracting time for: {event.get('eventName', 'Unknown')} - {event_url}")
    
    extracted_time = extract_time_from_page(event_url, rate_limiter=rate_limiter)
    
    if extracted_time:
        print(f"  ✓ Found time: {extracted_time}")
        event['eventTime'] = extracted_time
    else:
        print(f"  ✗ No time found")
        event['eventTime'] = None
    
    return event


def extract_event_times(events: List[Dict], max_workers: int = 10, requests_per_second: float = 1.0) -> List[Dict]:
    """
    Extract times for multiple events in parallel with rate limiting.
    
    Args:
        events: List of event dictionaries
        max_workers: Maximum number of parallel workers
        requests_per_second: Maximum requests per second (default: 1.0)
        
    Returns:
        List of updated event dictionaries
    """
    print(f"Extracting times for {len(events)} events using {max_workers} workers...")
    print(f"Rate limiting: {requests_per_second} requests per second")
    
    # Create a shared rate limiter
    rate_limiter = RateLimiter(max_requests_per_second=requests_per_second)
    
    enriched_events = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks with rate limiter
        future_to_event = {
            executor.submit(extract_times_for_event, event, rate_limiter): event 
            for event in events
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_event):
            try:
                enriched_event = future.result()
                enriched_events.append(enriched_event)
            except Exception as e:
                original_event = future_to_event[future]
                print(f"Error processing {original_event.get('eventName', 'Unknown')}: {e}")
                enriched_events.append(original_event)
    
    return enriched_events


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description='Extract event times from individual event pages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract times for Kings Theatre events
  python src/extract_event_times.py kings_events.json kings_events_with_times.json
  
  # Use more workers with rate limiting
  python src/extract_event_times.py --workers 20 --rate-limit 2.0 input.json output.json
        """
    )
    
    parser.add_argument('input_file', help='Input JSON file containing events with eventUrl fields')
    parser.add_argument('output_file', help='Output JSON file for events with extracted times')
    parser.add_argument('--workers', '-w', type=int, default=10, 
                       help='Number of parallel workers (default: 10)')
    parser.add_argument('--timeout', '-t', type=int, default=10,
                       help='Request timeout in seconds (default: 10)')
    parser.add_argument('--rate-limit', '-r', type=float, default=1.0,
                       help='Maximum requests per second (default: 1.0)')
    
    args = parser.parse_args()
    
    try:
        # Load input events
        print(f"Loading events from {args.input_file}...")
        with open(args.input_file, 'r', encoding='utf-8') as f:
            events = json.load(f)
        
        if not isinstance(events, list):
            print("Error: Input file must contain a JSON array of events")
            sys.exit(1)
        
        print(f"Found {len(events)} events to process")
        
        # Extract times
        start_time = time.time()
        enriched_events = extract_event_times(events, max_workers=args.workers, requests_per_second=args.rate_limit)
        end_time = time.time()
        
        # Save results
        print(f"Saving results to {args.output_file}...")
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_events, f, indent=2, ensure_ascii=False)
        
        # Print summary
        events_with_times = sum(1 for event in enriched_events if event.get('eventTime'))
        print(f"\n=== EXTRACTION COMPLETE ===")
        print(f"Total events processed: {len(enriched_events)}")
        print(f"Events with times found: {events_with_times}")
        print(f"Events without times: {len(enriched_events) - events_with_times}")
        print(f"Processing time: {end_time - start_time:.2f} seconds")
        print(f"Average time per event: {(end_time - start_time) / len(enriched_events):.2f} seconds")
        
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
