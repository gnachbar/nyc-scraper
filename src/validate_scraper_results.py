#!/usr/bin/env python3
"""
Scraper Results Validation Framework

Analyzes scraped data to determine quality and completeness:
1. Field completeness - how many fields are properly filled
2. Date coverage - how far into the future, any gaps or cutoffs
3. Historical comparison - compare to previous runs
4. Baseline comparison - compare to venue's expected behavior
5. Identifies potential scraper issues vs. venue limitations
"""

import argparse
import json
import sys
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from statistics import mean, stdev

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.web.models import ScrapeRun, RawEvent, SessionLocal


def load_venue_baselines() -> Dict[str, Any]:
    """Load venue baselines from YAML config."""
    baseline_path = Path(__file__).parent / "config" / "venue_baselines.yaml"
    if baseline_path.exists():
        with open(baseline_path) as f:
            data = yaml.safe_load(f)
            return data.get("venues", {})
    return {}


def get_historical_runs(session, source: str, limit: int = 10) -> List[ScrapeRun]:
    """Get historical successful runs for comparison."""
    return session.query(ScrapeRun).filter(
        ScrapeRun.source == source,
        ScrapeRun.status == 'completed',
        ScrapeRun.events_scraped > 0
    ).order_by(ScrapeRun.id.desc()).limit(limit).all()


def analyze_field_completeness(events: List[RawEvent], baseline_config: Dict = None) -> Dict[str, Any]:
    """Analyze how complete each field is across all events."""
    if not events:
        return {"error": "No events to analyze"}

    total = len(events)

    # Track completeness for each field
    fields = {
        "title": {"filled": 0, "empty": 0, "examples_empty": []},
        "start_time": {"filled": 0, "empty": 0, "examples_empty": []},
        "venue": {"filled": 0, "empty": 0, "examples_empty": []},
        "url": {"filled": 0, "empty": 0, "examples_empty": []},
        "description": {"filled": 0, "empty": 0, "examples_empty": []},
    }

    # Track time-specific issues
    midnight_count = 0
    times_seen = set()

    for event in events:
        # Title
        if event.title and event.title.strip():
            fields["title"]["filled"] += 1
        else:
            fields["title"]["empty"] += 1
            if len(fields["title"]["examples_empty"]) < 3:
                fields["title"]["examples_empty"].append(f"ID {event.id}")

        # Start time
        if event.start_time:
            fields["start_time"]["filled"] += 1
            times_seen.add(event.start_time.strftime("%H:%M"))
            if event.start_time.hour == 0 and event.start_time.minute == 0:
                midnight_count += 1
        else:
            fields["start_time"]["empty"] += 1
            if len(fields["start_time"]["examples_empty"]) < 3:
                fields["start_time"]["examples_empty"].append(event.title[:50] if event.title else f"ID {event.id}")

        # Venue
        if event.venue and event.venue.strip():
            fields["venue"]["filled"] += 1
        else:
            fields["venue"]["empty"] += 1
            if len(fields["venue"]["examples_empty"]) < 3:
                fields["venue"]["examples_empty"].append(event.title[:50] if event.title else f"ID {event.id}")

        # URL
        if event.url and event.url.strip() and event.url.startswith("http"):
            fields["url"]["filled"] += 1
        else:
            fields["url"]["empty"] += 1
            if len(fields["url"]["examples_empty"]) < 3:
                fields["url"]["examples_empty"].append(event.title[:50] if event.title else f"ID {event.id}")

        # Description
        if event.description and event.description.strip() and len(event.description.strip()) > 10:
            fields["description"]["filled"] += 1
        else:
            fields["description"]["empty"] += 1

    # Calculate percentages and determine issues
    results = {
        "total_events": total,
        "fields": {},
        "issues": [],
        "warnings": []
    }

    for field_name, data in fields.items():
        pct = (data["filled"] / total * 100) if total > 0 else 0
        results["fields"][field_name] = {
            "filled": data["filled"],
            "empty": data["empty"],
            "percent_filled": round(pct, 1),
            "examples_empty": data["examples_empty"]
        }

        # Flag critical issues
        if field_name in ["title", "url"] and pct < 90:
            results["issues"].append(f"CRITICAL: {field_name} only {pct:.1f}% filled")
        elif field_name == "start_time" and pct < 90:
            results["warnings"].append(f"WARNING: {field_name} only {pct:.1f}% filled")
        elif field_name == "venue" and pct < 80:
            results["warnings"].append(f"WARNING: {field_name} only {pct:.1f}% filled")

    # Check for time issues
    results["time_analysis"] = {
        "unique_times": len(times_seen),
        "midnight_count": midnight_count,
        "midnight_percentage": round(midnight_count / total * 100, 1) if total > 0 else 0,
        "times_list": sorted(list(times_seen))[:10]  # First 10 unique times
    }

    # Check if venue is known to not have times available
    times_available = baseline_config.get("times_available", True) if baseline_config else True

    if midnight_count == total and total > 1:
        if not times_available:
            # Known venue limitation - not a scraper bug
            results["warnings"].append(f"INFO: All {total} events have midnight times - times not available for this venue (known limitation)")
        else:
            results["issues"].append(f"CRITICAL: ALL {total} events have midnight times - scraper not extracting times")
    elif midnight_count > total * 0.5:
        if not times_available:
            results["warnings"].append(f"INFO: {midnight_count}/{total} events have midnight times - times not available for this venue")
        else:
            results["warnings"].append(f"WARNING: {midnight_count}/{total} events have midnight times")

    if len(times_seen) == 1 and total > 5:
        the_time = list(times_seen)[0]
        # Only warn if it's midnight (indicating no extraction) and times should be available
        if the_time == "00:00" and times_available:
            results["warnings"].append(f"WARNING: All events have midnight time - likely not extracting times")
        # Otherwise it might be legitimate (venue has set show time) or known limitation

    return results


def analyze_date_coverage(events: List[RawEvent], baseline: Dict = None) -> Dict[str, Any]:
    """Analyze the date range and coverage of events."""
    if not events:
        return {"error": "No events to analyze"}

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get all dates
    dates = [e.start_time.date() for e in events if e.start_time]

    if not dates:
        return {
            "error": "No events have dates",
            "issues": ["CRITICAL: No events have start_time populated"]
        }

    dates.sort()

    earliest = min(dates)
    latest = max(dates)

    # Calculate months ahead
    months_ahead = (latest.year - today.year) * 12 + (latest.month - today.month)

    # Count events by month
    events_by_month = defaultdict(int)
    for d in dates:
        month_key = d.strftime("%Y-%m")
        events_by_month[month_key] += 1

    # Check for gaps (months with no events)
    gaps = []
    if earliest < latest:
        current = earliest.replace(day=1)
        end = latest.replace(day=1)
        while current <= end:
            month_key = current.strftime("%Y-%m")
            if month_key not in events_by_month:
                gaps.append(month_key)
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

    # Analyze distribution - check if events drop off suddenly
    monthly_counts = [(k, v) for k, v in sorted(events_by_month.items())]

    # Detect potential cutoff (sudden drop to very few events)
    potential_cutoff = None
    if len(monthly_counts) >= 3:
        for i in range(1, len(monthly_counts) - 1):
            prev_count = monthly_counts[i-1][1]
            curr_count = monthly_counts[i][1]
            if prev_count > 5 and curr_count <= 1:
                potential_cutoff = monthly_counts[i][0]
                break

    results = {
        "total_with_dates": len(dates),
        "earliest_event": earliest.isoformat(),
        "latest_event": latest.isoformat(),
        "months_ahead": months_ahead,
        "total_days_covered": (latest - earliest).days,
        "events_by_month": dict(events_by_month),
        "gaps_in_coverage": gaps,
        "potential_cutoff_month": potential_cutoff,
        "issues": [],
        "warnings": []
    }

    # Compare to baseline if available
    if baseline:
        expected_months = baseline.get("typical_horizon_months", 3)
        results["baseline_horizon_months"] = expected_months
        results["reaches_baseline"] = months_ahead >= expected_months - 1  # Allow 1 month tolerance

        if not results["reaches_baseline"]:
            shortfall = expected_months - months_ahead
            results["warnings"].append(
                f"WARNING: Events go {months_ahead} months ahead, baseline expects {expected_months} months ({shortfall} months short)"
            )
    else:
        results["baseline_horizon_months"] = None
        results["reaches_baseline"] = None

    if potential_cutoff:
        results["warnings"].append(f"WARNING: Possible pagination cutoff at {potential_cutoff} - events drop off suddenly")

    if len(gaps) > 2:
        results["warnings"].append(f"WARNING: {len(gaps)} gaps in monthly coverage")

    # Check if events are mostly in the past
    past_events = sum(1 for d in dates if d < today.date())
    if past_events > len(dates) * 0.5:
        results["warnings"].append(f"WARNING: {past_events}/{len(dates)} events are in the past")

    return results


def analyze_historical_comparison(current_count: int, historical_runs: List[ScrapeRun]) -> Dict[str, Any]:
    """Compare current run to historical runs."""
    if not historical_runs:
        return {
            "has_history": False,
            "issues": [],
            "warnings": []
        }

    counts = [r.events_scraped for r in historical_runs if r.events_scraped]
    if not counts:
        return {
            "has_history": False,
            "issues": [],
            "warnings": []
        }

    avg_count = mean(counts)
    min_count = min(counts)
    max_count = max(counts)

    results = {
        "has_history": True,
        "historical_runs": len(counts),
        "historical_average": round(avg_count, 1),
        "historical_min": min_count,
        "historical_max": max_count,
        "current_count": current_count,
        "vs_average_pct": round((current_count / avg_count * 100) - 100, 1) if avg_count > 0 else 0,
        "issues": [],
        "warnings": []
    }

    # Check for anomalies
    if current_count < avg_count * 0.5:
        results["issues"].append(
            f"CRITICAL: Event count ({current_count}) is {100 - results['vs_average_pct']:.0f}% below historical average ({avg_count:.0f})"
        )
    elif current_count < avg_count * 0.7:
        results["warnings"].append(
            f"WARNING: Event count ({current_count}) is {100 - results['vs_average_pct']:.0f}% below historical average ({avg_count:.0f})"
        )
    elif current_count > max_count * 1.5:
        results["warnings"].append(
            f"INFO: Event count ({current_count}) is unusually high (historical max: {max_count})"
        )

    return results


def analyze_baseline_comparison(current_count: int, baseline: Dict) -> Dict[str, Any]:
    """Compare current run to venue baseline expectations."""
    if not baseline:
        return {
            "has_baseline": False,
            "issues": [],
            "warnings": []
        }

    min_expected = baseline.get("typical_event_count_min", 1)
    max_expected = baseline.get("typical_event_count_max", 1000)

    results = {
        "has_baseline": True,
        "expected_min": min_expected,
        "expected_max": max_expected,
        "current_count": current_count,
        "within_range": min_expected <= current_count <= max_expected,
        "issues": [],
        "warnings": []
    }

    if current_count < min_expected:
        pct_of_min = (current_count / min_expected * 100) if min_expected > 0 else 0
        if pct_of_min < 50:
            results["issues"].append(
                f"CRITICAL: Event count ({current_count}) is far below expected minimum ({min_expected})"
            )
        else:
            results["warnings"].append(
                f"WARNING: Event count ({current_count}) is below expected minimum ({min_expected})"
            )

    return results


def determine_failure_reason(
    field_analysis: Dict,
    date_analysis: Dict,
    historical: Dict,
    baseline: Dict,
    baseline_config: Dict
) -> Dict[str, Any]:
    """
    Determine whether issues are due to scraper failure or venue limitations.

    Returns diagnosis with confidence level.
    """
    diagnosis = {
        "likely_cause": "unknown",
        "confidence": "low",
        "evidence": [],
        "recommendation": ""
    }

    issues_found = []

    # Check for clear scraper failures
    time_analysis = field_analysis.get("time_analysis", {})
    times_available = baseline_config.get("times_available", True) if baseline_config else True
    if time_analysis.get("midnight_percentage", 0) == 100 and times_available:
        issues_found.append("time_extraction_broken")
        diagnosis["evidence"].append("All events have midnight times - time extraction is broken")

    url_pct = field_analysis.get("fields", {}).get("url", {}).get("percent_filled", 100)
    if url_pct < 50:
        issues_found.append("url_extraction_broken")
        diagnosis["evidence"].append(f"URL field only {url_pct}% filled - extraction is broken")

    # Check for pagination issues
    if historical.get("has_history"):
        vs_avg = historical.get("vs_average_pct", 0)
        if vs_avg < -40:  # 40%+ fewer events than usual
            issues_found.append("possible_pagination_failure")
            diagnosis["evidence"].append(f"Event count is {abs(vs_avg):.0f}% below historical average")

    # Check date coverage vs baseline
    if baseline_config and not date_analysis.get("reaches_baseline", True):
        months_ahead = date_analysis.get("months_ahead", 0)
        expected = baseline_config.get("typical_horizon_months", 3)
        if months_ahead < expected - 1:
            # Could be scraper issue OR venue just hasn't posted
            if baseline_config.get("has_pagination", True):
                issues_found.append("possible_pagination_incomplete")
                diagnosis["evidence"].append(f"Events only go {months_ahead} months ahead (expected {expected}), venue has pagination")
            else:
                diagnosis["evidence"].append(f"Events only go {months_ahead} months ahead - venue may not have posted further")

    # Determine diagnosis
    if "url_extraction_broken" in issues_found or "time_extraction_broken" in issues_found:
        diagnosis["likely_cause"] = "scraper_bug"
        diagnosis["confidence"] = "high"
        diagnosis["recommendation"] = "Fix the scraper extraction logic"
    elif "possible_pagination_failure" in issues_found and "possible_pagination_incomplete" in issues_found:
        diagnosis["likely_cause"] = "pagination_failure"
        diagnosis["confidence"] = "medium"
        diagnosis["recommendation"] = "Check if pagination is working correctly"
    elif "possible_pagination_incomplete" in issues_found:
        diagnosis["likely_cause"] = "pagination_or_venue_limit"
        diagnosis["confidence"] = "low"
        diagnosis["recommendation"] = "Manually verify if venue has more events posted"
    elif not issues_found:
        diagnosis["likely_cause"] = "within_normal_range"
        diagnosis["confidence"] = "high"
        diagnosis["recommendation"] = "No action needed"
    else:
        diagnosis["likely_cause"] = "needs_investigation"
        diagnosis["confidence"] = "low"
        diagnosis["recommendation"] = "Manual investigation required"

    return diagnosis


def validate_source(source: str, session, baselines: Dict) -> Dict[str, Any]:
    """Run full validation for a single source."""
    baseline_config = baselines.get(source, {})

    # Get latest scrape run
    latest_run = session.query(ScrapeRun).filter(
        ScrapeRun.source == source
    ).order_by(ScrapeRun.id.desc()).first()

    if not latest_run:
        return {
            "source": source,
            "error": "No scrape runs found",
            "status": "NO_DATA"
        }

    # Get events from this run
    events = session.query(RawEvent).filter(
        RawEvent.scrape_run_id == latest_run.id
    ).all()

    if not events:
        return {
            "source": source,
            "scrape_run_id": latest_run.id,
            "scrape_time": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
            "error": "No events in latest run",
            "status": "FAILED"
        }

    # Get historical runs
    historical_runs = get_historical_runs(session, source)

    # Run analyses
    field_analysis = analyze_field_completeness(events, baseline_config)
    date_analysis = analyze_date_coverage(events, baseline_config)
    historical_analysis = analyze_historical_comparison(len(events), historical_runs)
    baseline_analysis = analyze_baseline_comparison(len(events), baseline_config)

    # Determine root cause
    diagnosis = determine_failure_reason(
        field_analysis, date_analysis, historical_analysis, baseline_analysis, baseline_config
    )

    # Combine issues
    all_issues = (
        field_analysis.get("issues", []) +
        date_analysis.get("issues", []) +
        historical_analysis.get("issues", []) +
        baseline_analysis.get("issues", [])
    )
    all_warnings = (
        field_analysis.get("warnings", []) +
        date_analysis.get("warnings", []) +
        historical_analysis.get("warnings", []) +
        baseline_analysis.get("warnings", [])
    )

    # Determine overall status
    if all_issues:
        status = "FAILED"
    elif all_warnings:
        status = "WARNING"
    else:
        status = "PASSED"

    # Calculate overall completeness score
    required_fields = ["title", "start_time", "url"]
    completeness_scores = [field_analysis["fields"].get(f, {}).get("percent_filled", 0) for f in required_fields]
    overall_completeness = sum(completeness_scores) / len(completeness_scores)

    return {
        "source": source,
        "status": status,
        "scrape_run_id": latest_run.id,
        "scrape_time": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
        "total_events": len(events),
        "overall_completeness": round(overall_completeness, 1),
        "field_analysis": field_analysis,
        "date_analysis": date_analysis,
        "historical_analysis": historical_analysis,
        "baseline_analysis": baseline_analysis,
        "diagnosis": diagnosis,
        "issues": all_issues,
        "warnings": all_warnings
    }


def print_validation_report(result: Dict[str, Any], verbose: bool = False):
    """Print a formatted validation report for a source."""
    source = result["source"]
    status = result["status"]

    # Status emoji
    status_emoji = {"PASSED": "✅", "WARNING": "⚠️", "FAILED": "❌", "NO_DATA": "❓"}.get(status, "❓")

    print(f"\n{'='*70}")
    print(f"{status_emoji} {source.upper()} - {status}")
    print(f"{'='*70}")

    if "error" in result:
        print(f"  Error: {result['error']}")
        return

    print(f"  Scrape Run: #{result['scrape_run_id']} at {result['scrape_time']}")
    print(f"  Total Events: {result['total_events']}")
    print(f"  Overall Completeness: {result['overall_completeness']}%")

    # Field completeness summary
    print(f"\n  📊 Field Completeness:")
    fields = result["field_analysis"]["fields"]
    for field, data in fields.items():
        pct = data["percent_filled"]
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        status_mark = "✓" if pct >= 90 else ("⚠" if pct >= 50 else "✗")
        print(f"     {field:<12} {bar} {pct:>5.1f}% ({data['filled']}/{data['filled'] + data['empty']}) {status_mark}")

    # Time analysis
    time_info = result["field_analysis"].get("time_analysis", {})
    if time_info:
        print(f"\n  ⏰ Time Analysis:")
        print(f"     Unique times: {time_info.get('unique_times', 'N/A')}")
        midnight_pct = time_info.get('midnight_percentage', 0)
        if midnight_pct > 0:
            print(f"     Midnight times: {time_info.get('midnight_count', 0)} ({midnight_pct}%)")

    # Date coverage
    date_info = result["date_analysis"]
    if "error" not in date_info:
        print(f"\n  📅 Date Coverage:")
        print(f"     Range: {date_info['earliest_event']} to {date_info['latest_event']}")
        print(f"     Months ahead: {date_info['months_ahead']}")
        if date_info.get("baseline_horizon_months"):
            reaches = "✓" if date_info['reaches_baseline'] else "✗"
            print(f"     Baseline expects: {date_info['baseline_horizon_months']} months {reaches}")

    # Historical comparison
    hist_info = result.get("historical_analysis", {})
    if hist_info.get("has_history"):
        print(f"\n  📈 Historical Comparison:")
        print(f"     Average: {hist_info['historical_average']} events")
        print(f"     Range: {hist_info['historical_min']} - {hist_info['historical_max']}")
        vs_avg = hist_info['vs_average_pct']
        indicator = "↑" if vs_avg > 0 else "↓" if vs_avg < 0 else "="
        print(f"     Current vs avg: {vs_avg:+.1f}% {indicator}")

    # Diagnosis
    diagnosis = result.get("diagnosis", {})
    if diagnosis.get("likely_cause") and diagnosis["likely_cause"] != "within_normal_range":
        print(f"\n  🔍 Diagnosis:")
        print(f"     Likely cause: {diagnosis['likely_cause'].replace('_', ' ').title()}")
        print(f"     Confidence: {diagnosis['confidence']}")
        if diagnosis.get("evidence"):
            print(f"     Evidence:")
            for e in diagnosis["evidence"]:
                print(f"       • {e}")
        if diagnosis.get("recommendation"):
            print(f"     Recommendation: {diagnosis['recommendation']}")

    # Issues and warnings
    if result["issues"]:
        print(f"\n  🚨 ISSUES:")
        for issue in result["issues"]:
            print(f"     • {issue}")

    if result["warnings"] and verbose:
        print(f"\n  ⚠️  WARNINGS:")
        for warning in result["warnings"]:
            print(f"     • {warning}")


def run_all_validations(sources: List[str], verbose: bool = False) -> Dict[str, Any]:
    """Run validation for all specified sources."""
    session = SessionLocal()
    baselines = load_venue_baselines()

    results = {
        "validation_time": datetime.now().isoformat(),
        "sources": {},
        "summary": {
            "total": len(sources),
            "passed": 0,
            "warnings": 0,
            "failed": 0,
            "no_data": 0,
            "total_events": 0
        },
        "issues_by_type": defaultdict(list)
    }

    for source in sources:
        result = validate_source(source, session, baselines)
        results["sources"][source] = result

        # Update summary
        status = result.get("status", "FAILED")
        if status == "PASSED":
            results["summary"]["passed"] += 1
        elif status == "WARNING":
            results["summary"]["warnings"] += 1
        elif status == "NO_DATA":
            results["summary"]["no_data"] += 1
        else:
            results["summary"]["failed"] += 1

        results["summary"]["total_events"] += result.get("total_events", 0)

        # Categorize issues
        diagnosis = result.get("diagnosis", {})
        cause = diagnosis.get("likely_cause", "unknown")
        if cause not in ["within_normal_range", "unknown"]:
            results["issues_by_type"][cause].append(source)

        # Print report
        print_validation_report(result, verbose)

    session.close()

    # Print overall summary
    print(f"\n{'='*70}")
    print("OVERALL SUMMARY")
    print(f"{'='*70}")
    s = results["summary"]
    print(f"  Total Sources: {s['total']}")
    print(f"  ✅ Passed:   {s['passed']}")
    print(f"  ⚠️  Warnings: {s['warnings']}")
    print(f"  ❌ Failed:   {s['failed']}")
    if s['no_data'] > 0:
        print(f"  ❓ No Data:  {s['no_data']}")
    print(f"  📊 Total Events: {s['total_events']}")

    # Issues breakdown
    if results["issues_by_type"]:
        print(f"\n  Issues by Category:")
        for issue_type, sources_affected in results["issues_by_type"].items():
            print(f"    • {issue_type.replace('_', ' ').title()}: {', '.join(sources_affected)}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Validate scraper results for quality and completeness')
    parser.add_argument('--source', help='Specific source to validate (default: all)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output including warnings')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')

    args = parser.parse_args()

    # Get sources to validate
    if args.source:
        sources = [args.source]
    else:
        # All known sources
        sources = [
            'crown_hill_theatre', 'bric_house', 'public_records', 'farm_one',
            'lepistol', 'brooklyn_paramount', 'barclays_center', 'public_theater',
            'soapbox_gallery', 'kings_theatre', 'brooklyn_museum', 'brooklyn_library',
            'bell_house', 'littlefield', 'concerts_on_the_slope', 'msg_calendar',
            'shapeshifter_plus', 'prospect_park', 'roulette', 'brooklyn_bowl', 'bam'
        ]

    # Run validations
    results = run_all_validations(sources, args.verbose)

    # Output JSON if requested
    if args.json:
        # Convert defaultdict to regular dict for JSON serialization
        results["issues_by_type"] = dict(results["issues_by_type"])
        print("\n" + json.dumps(results, indent=2, default=str))

    # Exit with appropriate code
    if results["summary"]["failed"] > 0:
        sys.exit(1)
    elif results["summary"]["warnings"] > 0:
        sys.exit(0)  # Warnings don't fail
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
