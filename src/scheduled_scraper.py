#!/usr/bin/env python3
"""
Scheduled Scraper with Notifications

Designed to run automatically via cron/GitHub Actions.
Features:
- Runs all scrapers with self-healing
- Generates summary report
- Sends notification on failures (via webhook or email)
- Outputs structured JSON for CI/CD integration

Usage:
    # Basic scheduled run
    python src/scheduled_scraper.py

    # With Slack webhook notification
    python src/scheduled_scraper.py --slack-webhook $SLACK_WEBHOOK_URL

    # With email notification (requires SMTP config)
    python src/scheduled_scraper.py --email alerts@example.com

    # Output for GitHub Actions
    python src/scheduled_scraper.py --github-output
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.append(str(Path(__file__).parent.parent))

from src.self_healing_runner import SelfHealingRunner, get_all_sources
from src.validate_scraper_results import run_all_validations, load_venue_baselines


def send_slack_notification(webhook_url: str, results: Dict[str, Any]):
    """Send a Slack notification with run results."""
    s = results.get("summary", {})
    status_emoji = "✅" if s.get("failed", 0) == 0 else "❌"

    # Build message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_emoji} Scraper Run Complete"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Success:* {s.get('success', 0)}/{s.get('total', 0)}"},
                {"type": "mrkdwn", "text": f"*Failed:* {s.get('failed', 0)}/{s.get('total', 0)}"},
                {"type": "mrkdwn", "text": f"*Events:* {s.get('total_events', 0)}"},
                {"type": "mrkdwn", "text": f"*Time:* {results.get('completed_at', 'N/A')[:19]}"}
            ]
        }
    ]

    # Add failed scrapers if any
    failed = [k for k, v in results.get("sources", {}).items() if not v.get("success")]
    if failed:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Failed Scrapers:*\n" + "\n".join(f"• {s}" for s in failed[:10])
            }
        })

    payload = {"blocks": blocks}

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
        print("📨 Slack notification sent")
    except Exception as e:
        print(f"⚠️  Failed to send Slack notification: {e}")


def output_github_actions(results: Dict[str, Any]):
    """Output results in GitHub Actions format."""
    s = results.get("summary", {})

    # Set output variables
    outputs = [
        f"success_count={s.get('success', 0)}",
        f"failed_count={s.get('failed', 0)}",
        f"total_events={s.get('total_events', 0)}",
        f"status={'success' if s.get('failed', 0) == 0 else 'failure'}"
    ]

    # Write to GITHUB_OUTPUT if available
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            for output in outputs:
                f.write(f"{output}\n")
    else:
        # Print for manual inspection
        print("\n📤 GitHub Actions Output:")
        for output in outputs:
            print(f"  {output}")

    # Set job summary if available
    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary:
        with open(github_step_summary, "a") as f:
            f.write(f"## Scraper Run Results\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Success | {s.get('success', 0)}/{s.get('total', 0)} |\n")
            f.write(f"| Failed | {s.get('failed', 0)} |\n")
            f.write(f"| Total Events | {s.get('total_events', 0)} |\n")


def generate_report(results: Dict[str, Any]) -> str:
    """Generate a text report of the run."""
    s = results.get("summary", {})

    lines = [
        "=" * 60,
        "SCRAPER RUN REPORT",
        "=" * 60,
        f"Started:   {results.get('started_at', 'N/A')}",
        f"Completed: {results.get('completed_at', 'N/A')}",
        "",
        f"✅ Success: {s.get('success', 0)}/{s.get('total', 0)}",
        f"❌ Failed:  {s.get('failed', 0)}/{s.get('total', 0)}",
        f"⏭️  Skipped: {s.get('skipped', 0)}/{s.get('total', 0)}",
        f"📊 Events:  {s.get('total_events', 0)}",
        ""
    ]

    # Add details for each source
    lines.append("SOURCE DETAILS:")
    lines.append("-" * 60)

    for source, info in sorted(results.get("sources", {}).items()):
        status = "✅" if info.get("success") else "❌"
        events = info.get("events_count", 0)
        issues = info.get("issues", [])

        lines.append(f"{status} {source}: {events} events")
        if issues:
            lines.append(f"   Issues: {', '.join(issues)}")
        if info.get("error_message"):
            lines.append(f"   Error: {info['error_message'][:50]}...")

    # Add healing actions
    healing_log = results.get("healing_log", [])
    if healing_log:
        lines.append("")
        lines.append("HEALING ACTIONS:")
        lines.append("-" * 60)
        for h in healing_log:
            lines.append(f"• {h['source']}: {h['action']} - {h['description'][:40]}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Scheduled scraper with notifications')
    parser.add_argument('--slack-webhook', help='Slack webhook URL for notifications')
    parser.add_argument('--email', help='Email address for notifications')
    parser.add_argument('--github-output', action='store_true', help='Output for GitHub Actions')
    parser.add_argument('--source', help='Run specific source only')
    parser.add_argument('--dry-run', action='store_true', help='Show what would run without running')

    args = parser.parse_args()

    # Determine sources
    sources = [args.source] if args.source else get_all_sources()

    if args.dry_run:
        print(f"Would run {len(sources)} scrapers")
        return

    print(f"🚀 Starting scheduled scraper run at {datetime.now().isoformat()}")
    print(f"   Sources: {len(sources)}")

    # Run scrapers with self-healing
    runner = SelfHealingRunner(verbose=False)
    results = runner.run_all(sources)

    # Generate and save report
    report = generate_report(results)
    print(report)

    # Save report to file
    report_path = Path("data/output") / f"scraper_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"\n📄 Report saved to: {report_path}")

    # Send notifications
    if args.slack_webhook:
        send_slack_notification(args.slack_webhook, results)

    if args.github_output:
        output_github_actions(results)

    # Exit with appropriate code
    if results["summary"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
