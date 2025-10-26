#!/usr/bin/env python3
"""
Integration script for Kings Theatre scraper with time extraction.

This script demonstrates how to integrate the event time extractor
with the existing Kings Theatre scraper workflow.
"""

import json
import subprocess
import sys
import os
from pathlib import Path


def run_kings_scraper():
    """Run the Kings Theatre scraper to get events with URLs."""
    print("=== Step 1: Running Kings Theatre Scraper ===")
    
    try:
        # Run the Kings Theatre scraper
        cmd = ["node", "-e", """
        import('./src/scrapers/kings_theatre.js').then(module => {
          module.scrapeKingsTheatre().then(result => {
            console.log('=== SCRAPER OUTPUT ===');
            console.log('Events found:', result.events.length);
            
            // Save events to JSON file for time extraction
            const fs = require('fs');
            const filename = 'kings_events_for_time_extraction.json';
            fs.writeFileSync(filename, JSON.stringify(result.events, null, 2));
            console.log('Events saved to:', filename);
            
            if (result.events.length > 0) {
              console.log('\\nFirst 3 events:');
              result.events.slice(0, 3).forEach((event, i) => {
                console.log(\`\${i + 1}. \${event.eventName}\`);
                console.log(\`   Date: \${event.eventDate}\`);
                console.log(\`   Time: \${event.eventTime || 'No time'}\`);
                console.log(\`   URL: \${event.eventUrl}\`);
                console.log('');
              });
            }
          }).catch(err => {
            console.error('Scraper error:', err.message);
            process.exit(1);
          });
        });
        """]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        print("Scraper output:")
        print(result.stdout)
        
        if result.stderr:
            print("Scraper errors:")
            print(result.stderr)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error running Kings scraper: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def extract_times():
    """Extract times from the scraped events."""
    print("\n=== Step 2: Extracting Event Times ===")
    
    input_file = "kings_events_for_time_extraction.json"
    output_file = "kings_events_with_times.json"
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found. Run the scraper first.")
        return False
    
    try:
        cmd = [
            sys.executable, 
            "src/extract_event_times.py", 
            input_file, 
            output_file, 
            "--workers", "10"
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        print("Time extraction output:")
        print(result.stdout)
        
        if result.stderr:
            print("Time extraction errors:")
            print(result.stderr)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error running time extraction: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def import_to_database():
    """Import the enriched events to the database."""
    print("\n=== Step 3: Importing to Database ===")
    
    output_file = "kings_events_with_times.json"
    
    if not os.path.exists(output_file):
        print(f"Error: {output_file} not found. Run time extraction first.")
        return False
    
    try:
        cmd = [
            sys.executable, 
            "src/import_scraped_data.py", 
            "kings_theatre", 
            output_file
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        print("Import output:")
        print(result.stdout)
        
        if result.stderr:
            print("Import errors:")
            print(result.stderr)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error importing to database: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def show_results():
    """Show the final results."""
    print("\n=== Step 4: Final Results ===")
    
    output_file = "kings_events_with_times.json"
    
    if not os.path.exists(output_file):
        print(f"Error: {output_file} not found.")
        return
    
    with open(output_file, 'r') as f:
        events = json.load(f)
    
    events_with_times = [e for e in events if e.get('eventTime')]
    
    print(f"Total events: {len(events)}")
    print(f"Events with times: {len(events_with_times)}")
    print(f"Events without times: {len(events) - len(events_with_times)}")
    
    print(f"\nFirst 5 events with times:")
    for i, event in enumerate(events_with_times[:5]):
        print(f"{i+1}. {event['eventName']} - {event['eventTime']}")


def main():
    """Main integration workflow."""
    print("=== Kings Theatre Scraper with Time Extraction ===\n")
    
    # Step 1: Run scraper
    if not run_kings_scraper():
        print("Failed at step 1: Scraping")
        sys.exit(1)
    
    # Step 2: Extract times
    if not extract_times():
        print("Failed at step 2: Time extraction")
        sys.exit(1)
    
    # Step 3: Import to database
    if not import_to_database():
        print("Failed at step 3: Database import")
        sys.exit(1)
    
    # Step 4: Show results
    show_results()
    
    print("\n=== Integration Complete ===")
    print("All steps completed successfully!")


if __name__ == '__main__':
    main()
