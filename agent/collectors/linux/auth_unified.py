"""
Unified Linux Authentication Collector

This collector automatically detects the best method for collecting auth events:
1. Try traditional log files (/var/log/auth.log or /var/log/secure)
2. Fall back to journald (systemd journal) if log files unavailable

Works on any Linux distribution!

Usage:
    from collectors.linux.auth_unified import collect_auth_events
    events = collect_auth_events()
"""

import os
from typing import List, Dict, Any

# Import both collectors
from collectors.linux.auth import LinuxAuthCollector
from collectors.linux.auth_journald import JournaldAuthCollector


def collect_auth_events(
    log_file: str = None,
    hours: int = 24,
    max_lines: int = 1000,
    prefer_method: str = "auto"
) -> List[Dict[str, Any]]:
    """
    Collect authentication events using the best available method.

    Args:
        log_file: Specific log file to use (optional)
        hours: For journald, how many hours back to search
        max_lines: Maximum entries to process
        prefer_method: "auto", "logfile", or "journald"

    Returns:
        list: List of event dictionaries

    Example:
        # Auto-detect best method
        events = collect_auth_events()

        # Force use of journald
        events = collect_auth_events(prefer_method="journald", hours=1)

        # Use specific log file
        events = collect_auth_events(log_file="/var/log/auth.log")
    """

    # If specific log file requested, use log file collector
    if log_file:
        collector = LinuxAuthCollector(log_file)
        return collector.collect_events(max_lines)

    # If journald preferred, use it
    if prefer_method == "journald":
        collector = JournaldAuthCollector()
        return collector.collect_events(hours, max_lines)

    # If logfile preferred, use it
    if prefer_method == "logfile":
        collector = LinuxAuthCollector()
        return collector.collect_events(max_lines)

    # Auto-detect mode
    # Try log files first (faster and more reliable)
    auth_logs = [
        "/var/log/auth.log",
        "/var/log/secure"
    ]

    for log_path in auth_logs:
        if os.path.exists(log_path) and os.access(log_path, os.R_OK):
            print(f"Using log file: {log_path}")
            collector = LinuxAuthCollector(log_path)
            return collector.collect_events(max_lines)

    # No accessible log files, try journald
    print("No accessible log files found, trying journald...")
    collector = JournaldAuthCollector()
    return collector.collect_events(hours, max_lines)


if __name__ == "__main__":
    """Test the unified collector."""
    import json

    print("=" * 70)
    print("Unified Linux Authentication Collector")
    print("=" * 70)
    print("\nAuto-detecting best collection method...")

    events = collect_auth_events(max_lines=100)

    print(f"\n✓ Collected {len(events)} events\n")

    if events:
        print("First event:")
        print(json.dumps(events[0], indent=2))

        # Summary
        print("\nSummary by event type:")
        event_types = {}
        for event in events:
            et = event['event_type']
            event_types[et] = event_types.get(et, 0) + 1

        for et, count in sorted(event_types.items()):
            print(f"  {et}: {count}")
    else:
        print("No events collected.")

    print("\n" + "=" * 70)
