#!/usr/bin/env python3
"""
Auto-Fix Rules for Self-Healing Scrapers

Contains rules and code modifications that can be automatically applied
to fix common scraper issues.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


def fix_year_in_instruction(scraper_path: str) -> bool:
    """
    Fix hardcoded year in extraction instructions.

    Replaces patterns like:
    - "2025" -> dynamic year using new Date().getFullYear()
    - "add the year 2025" -> "add the year ${currentYear}"
    """
    path = Path(scraper_path)
    if not path.exists():
        return False

    content = path.read_text()
    original = content
    current_year = datetime.now().year

    # Check if already using dynamic year
    if "getFullYear()" in content:
        return False  # Already fixed

    # Pattern: hardcoded year in string like "2025"
    # Only replace in extraction instruction strings
    old_year = str(current_year - 1)  # Last year is typically the stale one

    # Look for instruction strings with hardcoded years
    patterns = [
        (f"'Wednesday, October 29, {old_year}'", f"'Wednesday, October 29, ${{{current_year}}}'"),
        (f"the current year {old_year}", f"the current year ${{currentYear}}"),
        (f"add the year {old_year}", f"add the year ${{currentYear}}"),
        (f"adding the current year {old_year}", f"adding the current year ${{currentYear}}"),
    ]

    for old, new in patterns:
        if old in content:
            # Need to add currentYear variable before the extract call
            content = content.replace(old, new)

    # If we made changes, add the currentYear variable
    if content != original and "const currentYear = new Date().getFullYear();" not in content:
        # Find the extractEventsFromPage call and add variable before it
        extract_pattern = r"(const result = await extractEventsFromPage\()"
        if re.search(extract_pattern, content):
            content = re.sub(
                extract_pattern,
                "const currentYear = new Date().getFullYear();\n    \\1",
                content
            )

    if content != original:
        path.write_text(content)
        return True

    return False


def add_url_fallback(scraper_path: str, base_url: str) -> bool:
    """
    Add URL fallback for events without URLs.

    Modifies the event mapping to add a fallback URL when eventUrl is empty.
    """
    path = Path(scraper_path)
    if not path.exists():
        return False

    content = path.read_text()

    # Check if already has URL fallback
    if "eventUrl ||" in content or '!eventUrl' in content:
        return False  # Already has fallback

    # Look for the eventsWithLocation mapping
    pattern = r"const eventsWithLocation = result\.events\.map\(event => \(\{"
    if not re.search(pattern, content):
        return False

    # This is complex - would need AST manipulation for reliability
    # For now, return False to escalate to manual fix
    return False


def mark_times_unavailable(source: str) -> bool:
    """
    Mark a venue as having times_available: false in baselines.
    """
    baseline_path = Path("src/config/venue_baselines.yaml")
    if not baseline_path.exists():
        return False

    content = baseline_path.read_text()

    # Check if venue exists and doesn't already have times_available
    venue_pattern = rf"(\s+{source}:.*?)(\n\s+[a-z])"
    match = re.search(venue_pattern, content, re.DOTALL)

    if not match:
        return False

    venue_block = match.group(1)
    if "times_available:" in venue_block:
        return False  # Already set

    # Add times_available: false before the notes line or at end
    if "notes:" in venue_block:
        new_block = venue_block.replace(
            "    notes:",
            "    times_available: false  # Auto-added by self-healing\n    notes:"
        )
    else:
        new_block = venue_block.rstrip() + "\n    times_available: false  # Auto-added by self-healing"

    content = content.replace(venue_block, new_block)
    baseline_path.write_text(content)
    return True


def increase_pagination_clicks(scraper_path: str) -> bool:
    """
    Increase the max pagination clicks for a scraper.
    """
    path = Path(scraper_path)
    if not path.exists():
        return False

    content = path.read_text()
    modified = False

    # Look for maxClicks or maxPages patterns and increase them
    patterns = [
        (r"maxClicks\s*[:=]\s*(\d+)", "maxClicks"),
        (r"maxPages\s*[:=]\s*(\d+)", "maxPages"),
        (r"clickButtonUntilGone\(page,\s*['\"][^'\"]+['\"],\s*(\d+)", "clickButtonUntilGone"),
    ]

    for pattern, name in patterns:
        match = re.search(pattern, content)
        if match:
            old_num = int(match.group(1))
            new_num = old_num + 5
            # Replace just the number in the match
            old_text = match.group(0)
            new_text = old_text.replace(str(old_num), str(new_num))
            content = content.replace(old_text, new_text, 1)
            modified = True

    if modified:
        path.write_text(content)
        return True

    return False


def apply_auto_fix(source: str, issue_type: str) -> Dict[str, Any]:
    """
    Apply an automatic fix for a detected issue.

    Returns:
        {"applied": bool, "description": str}
    """
    scraper_path = f"src/scrapers/{source}.js"

    if issue_type == "wrong_year":
        if fix_year_in_instruction(scraper_path):
            return {
                "applied": True,
                "description": f"Fixed hardcoded year in {scraper_path}"
            }
        return {
            "applied": False,
            "description": "Could not auto-fix year - manual intervention needed"
        }

    elif issue_type == "time_extraction_failed":
        if mark_times_unavailable(source):
            return {
                "applied": True,
                "description": f"Marked {source} as times_available: false in baselines"
            }
        return {
            "applied": False,
            "description": "Could not update baselines"
        }

    elif issue_type == "pagination_incomplete":
        if increase_pagination_clicks(scraper_path):
            return {
                "applied": True,
                "description": f"Increased pagination clicks in {scraper_path}"
            }
        return {
            "applied": False,
            "description": "Could not find pagination settings to modify"
        }

    elif issue_type == "url_extraction_failed":
        # This is complex - need to add URL normalization code
        # For now, escalate
        return {
            "applied": False,
            "description": "URL extraction fixes require manual code changes"
        }

    return {
        "applied": False,
        "description": f"No auto-fix rule for issue type: {issue_type}"
    }


if __name__ == "__main__":
    # Test the fixes
    import sys

    if len(sys.argv) < 3:
        print("Usage: python auto_fix_rules.py <source> <issue_type>")
        print("Issue types: wrong_year, time_extraction_failed, pagination_incomplete, url_extraction_failed")
        sys.exit(1)

    source = sys.argv[1]
    issue_type = sys.argv[2]

    result = apply_auto_fix(source, issue_type)
    print(f"Applied: {result['applied']}")
    print(f"Description: {result['description']}")
