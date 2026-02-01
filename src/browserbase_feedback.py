#!/usr/bin/env python3
"""
Browserbase Feedback Module

Retrieves and analyzes session logs from Browserbase to provide
real-time feedback for the self-healing loop.

This module:
1. Calls the JavaScript diagnostics module to get session logs
2. Parses the results
3. Provides insights for diagnosis
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional


@dataclass
class SessionDiagnostics:
    """Diagnostics from a Browserbase session."""
    session_id: str
    total_events: int = 0
    has_scrolled: bool = False
    scroll_count: int = 0
    click_count: int = 0
    error_count: int = 0
    session_duration: float = 0.0
    navigations: List[str] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)
    insights: List[Dict] = field(default_factory=list)
    recommendations: List[Dict] = field(default_factory=list)


def get_session_diagnostics(session_id: str) -> Optional[SessionDiagnostics]:
    """
    Get diagnostics for a Browserbase session.

    Args:
        session_id: Browserbase session ID

    Returns:
        SessionDiagnostics object or None if failed
    """
    if not session_id:
        return None

    try:
        # Call the JavaScript diagnostics module
        result = subprocess.run(
            ["node", "src/lib/browserbase-diagnostics.js", session_id],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"[BB-FEEDBACK] Error getting diagnostics: {result.stderr}")
            return None

        # Parse the JSON output (it's after "=== FULL DIAGNOSTICS ===")
        output = result.stdout
        json_start = output.find("=== FULL DIAGNOSTICS ===")
        if json_start == -1:
            # Try to find JSON directly
            json_match = re.search(r'\{[\s\S]*\}', output)
            if json_match:
                json_str = json_match.group(0)
            else:
                print(f"[BB-FEEDBACK] Could not find JSON in output")
                return None
        else:
            json_str = output[json_start + len("=== FULL DIAGNOSTICS ==="):].strip()

        data = json.loads(json_str)

        # Build diagnostics object
        analysis = data.get("analysis", {})
        summary = analysis.get("summary", {})

        return SessionDiagnostics(
            session_id=session_id,
            total_events=analysis.get("totalEvents", 0),
            has_scrolled=summary.get("hasScrolled", False),
            scroll_count=summary.get("scrollCount", 0),
            click_count=summary.get("clickCount", 0),
            error_count=summary.get("errorCount", 0),
            session_duration=summary.get("sessionDuration", 0.0),
            navigations=[n.get("url", "") for n in analysis.get("navigations", [])],
            errors=analysis.get("errors", []),
            insights=data.get("insights", []),
            recommendations=data.get("recommendations", [])
        )

    except subprocess.TimeoutExpired:
        print(f"[BB-FEEDBACK] Timeout getting diagnostics for session {session_id}")
        return None
    except json.JSONDecodeError as e:
        print(f"[BB-FEEDBACK] Failed to parse diagnostics JSON: {e}")
        return None
    except Exception as e:
        print(f"[BB-FEEDBACK] Error: {e}")
        return None


def extract_session_id_from_output(output: str) -> Optional[str]:
    """
    Extract Browserbase session ID from scraper output.

    Args:
        output: Stdout from a scraper run

    Returns:
        Session ID or None
    """
    # Look for patterns like:
    # "https://browserbase.com/sessions/abc123"
    # "browserbaseSessionID: abc123"
    patterns = [
        r'browserbase\.com/sessions/([a-zA-Z0-9-]+)',
        r'browserbaseSessionID["\s:]+([a-zA-Z0-9-]+)',
        r'Session ID: ([a-zA-Z0-9-]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(1)

    return None


def analyze_session_for_healing(session_id: str) -> Dict[str, Any]:
    """
    Analyze a session and return healing recommendations.

    Args:
        session_id: Browserbase session ID

    Returns:
        Dict with issues and recommendations
    """
    diagnostics = get_session_diagnostics(session_id)

    if not diagnostics:
        return {
            "success": False,
            "error": "Could not retrieve session diagnostics",
            "issues": [],
            "recommendations": []
        }

    issues = []
    recommendations = []

    # Check for scroll issues
    if not diagnostics.has_scrolled:
        issues.append({
            "type": "NO_SCROLL",
            "severity": "high",
            "message": "No scroll events detected - page content may not have loaded"
        })
        recommendations.append({
            "action": "verify_scroll",
            "description": "Add scroll verification and logging",
            "priority": 1
        })
    elif diagnostics.scroll_count < 3:
        issues.append({
            "type": "INSUFFICIENT_SCROLL",
            "severity": "medium",
            "message": f"Only {diagnostics.scroll_count} scroll events - may need more scrolling"
        })

    # Check for click issues
    if diagnostics.click_count == 0:
        # This might be OK for scroll-based scrapers
        pass
    elif diagnostics.click_count < 3 and diagnostics.error_count > 0:
        issues.append({
            "type": "CLICK_FAILURE",
            "severity": "high",
            "message": f"Only {diagnostics.click_count} clicks with {diagnostics.error_count} errors"
        })

    # Check for session crash
    if diagnostics.session_duration < 5 and diagnostics.error_count > 0:
        issues.append({
            "type": "SESSION_CRASH",
            "severity": "critical",
            "message": f"Session crashed after {diagnostics.session_duration}s with {diagnostics.error_count} errors"
        })

    # Check for errors
    if diagnostics.error_count > 0:
        issues.append({
            "type": "SESSION_ERRORS",
            "severity": "medium",
            "message": f"{diagnostics.error_count} errors occurred during session"
        })

    # Add recommendations from diagnostics
    for rec in diagnostics.recommendations:
        recommendations.append({
            "action": rec.get("action", "unknown"),
            "description": rec.get("description", ""),
            "priority": rec.get("priority", 3)
        })

    return {
        "success": True,
        "session_id": session_id,
        "duration": diagnostics.session_duration,
        "scroll_count": diagnostics.scroll_count,
        "click_count": diagnostics.click_count,
        "error_count": diagnostics.error_count,
        "issues": issues,
        "recommendations": sorted(recommendations, key=lambda x: x.get("priority", 99)),
        "insights": diagnostics.insights
    }


def print_session_analysis(session_id: str):
    """Print a human-readable session analysis."""
    print(f"\n{'='*60}")
    print(f"BROWSERBASE SESSION ANALYSIS")
    print(f"{'='*60}")

    analysis = analyze_session_for_healing(session_id)

    if not analysis["success"]:
        print(f"Error: {analysis['error']}")
        return

    print(f"\nSession ID: {analysis['session_id']}")
    print(f"Duration: {analysis['duration']:.1f}s")
    print(f"Scroll events: {analysis['scroll_count']}")
    print(f"Click events: {analysis['click_count']}")
    print(f"Errors: {analysis['error_count']}")

    if analysis["issues"]:
        print(f"\n⚠️  ISSUES DETECTED:")
        for issue in analysis["issues"]:
            severity_icon = "🔴" if issue["severity"] == "critical" else "🟡" if issue["severity"] == "high" else "🟠"
            print(f"   {severity_icon} [{issue['type']}] {issue['message']}")

    if analysis["recommendations"]:
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(analysis["recommendations"], 1):
            print(f"   {i}. {rec['description']}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/browserbase_feedback.py <session_id>")
        print("")
        print("Or extract from scraper output:")
        print("  node src/scrapers/barclays_center.js 2>&1 | python src/browserbase_feedback.py --from-output")
        sys.exit(1)

    if sys.argv[1] == "--from-output":
        # Read from stdin
        output = sys.stdin.read()
        session_id = extract_session_id_from_output(output)
        if session_id:
            print(f"Found session ID: {session_id}")
            print_session_analysis(session_id)
        else:
            print("Could not extract session ID from output")
            sys.exit(1)
    else:
        session_id = sys.argv[1]
        print_session_analysis(session_id)
