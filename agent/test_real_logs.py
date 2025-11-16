#!/usr/bin/env python3
"""
Production Test Script for Real Log Collection

This script demonstrates how to collect authentication events from
REAL system logs (not sample data).

Usage:
    # Auto-detect best method (log files or journald)
    python test_real_logs.py

    # With sudo for full access
    sudo python test_real_logs.py

    # Save to JSON file
    python test_real_logs.py --output real_events.json

    # Specify time range for journald
    python test_real_logs.py --hours 48

    # Force specific method
    python test_real_logs.py --method journald
    python test_real_logs.py --method logfile
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Add collectors to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'collectors'))

# Try to import the unified collector
try:
    from linux.auth_unified import collect_auth_events
    UNIFIED_AVAILABLE = True
except ImportError:
    UNIFIED_AVAILABLE = False
    print("Warning: Unified collector not available, using basic collector")
    from linux.auth import collect_auth_events


def print_header(text):
    """Print a nice header."""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def check_permissions():
    """Check if we have necessary permissions."""
    uid = os.getuid()
    if uid == 0:
        print("✓ Running as root - full access to all logs")
        return True
    else:
        print("⚠ Running as regular user - may have limited log access")
        print("  Tip: Run with 'sudo' for full access to all logs")
        return False


def print_event_summary(events):
    """Print summary of events."""
    if not events:
        print("\n📊 No events collected")
        return

    # Count by type and severity
    type_counts = {}
    severity_counts = {}
    users = set()
    remote_ips = set()

    for event in events:
        # Count by type
        event_type = event.get('event_type', 'unknown')
        type_counts[event_type] = type_counts.get(event_type, 0) + 1

        # Count by severity
        severity = event.get('severity', 'unknown')
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Track users
        if 'data' in event and 'username' in event['data']:
            users.add(event['data']['username'])

        # Track remote IPs
        if 'data' in event and 'remote_ip' in event['data']:
            remote_ips.add(event['data']['remote_ip'])

    # Print summary
    print(f"\n📊 Event Summary")
    print(f"   Total events: {len(events)}")
    print(f"   Unique users: {len(users)}")
    if remote_ips:
        print(f"   Remote IPs: {len(remote_ips)}")

    print(f"\n📋 By Event Type:")
    for event_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {event_type}: {count}")

    print(f"\n⚠️  By Severity:")
    severity_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
    for severity in ['info', 'warning', 'error', 'critical']:
        if severity in severity_counts:
            emoji = severity_emoji.get(severity, '•')
            print(f"   {emoji} {severity}: {severity_counts[severity]}")


def analyze_security(events):
    """Analyze events for security concerns."""
    if not events:
        return

    print("\n🔒 Security Analysis")
    print("-" * 70)

    # Failed logins
    failed = [e for e in events if 'failed' in e.get('event_type', '').lower()]
    if failed:
        print(f"\n⚠️  {len(failed)} failed authentication attempts")

        # Group by IP
        by_ip = {}
        for event in failed:
            ip = event.get('data', {}).get('remote_ip', 'unknown')
            by_ip[ip] = by_ip.get(ip, 0) + 1

        # Potential brute force (3+ failures)
        brute_force = {ip: count for ip, count in by_ip.items() if count >= 3}
        if brute_force:
            print("   🚨 Potential brute force attacks:")
            for ip, count in sorted(brute_force.items(), key=lambda x: x[1], reverse=True):
                print(f"      {ip}: {count} attempts")

    # Invalid users
    invalid = [e for e in events if e.get('data', {}).get('invalid_user', False)]
    if invalid:
        usernames = set(e['data']['username'] for e in invalid)
        print(f"\n⚠️  {len(invalid)} attempts with invalid usernames")
        print(f"   Attempted: {', '.join(sorted(usernames)[:10])}")

    # Root activity
    root_events = [e for e in events if e.get('data', {}).get('username') == 'root']
    if root_events:
        print(f"\n⚠️  {len(root_events)} root user events")

    # Sudo usage
    sudo_events = [e for e in events if e.get('event_type') == 'sudo_used']
    if sudo_events:
        users = set(e['data']['username'] for e in sudo_events)
        print(f"\nℹ️  {len(sudo_events)} sudo commands by {len(users)} users")


def save_to_file(events, filename):
    """Save events to JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(events, f, indent=2)
        size = os.path.getsize(filename)
        print(f"\n✅ Saved {len(events)} events to: {filename}")
        print(f"   File size: {size:,} bytes")
    except Exception as e:
        print(f"\n❌ Error saving file: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Collect authentication events from real system logs'
    )
    parser.add_argument(
        '--method',
        choices=['auto', 'logfile', 'journald'],
        default='auto',
        help='Collection method (default: auto-detect)'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Hours to look back for journald (default: 24)'
    )
    parser.add_argument(
        '--max-lines',
        type=int,
        default=1000,
        help='Maximum log lines to process (default: 1000)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Save events to JSON file'
    )
    parser.add_argument(
        '--show-all',
        action='store_true',
        help='Show all events in detail'
    )
    args = parser.parse_args()

    print_header("🔍 Real Log Collection - Production Test")

    # Check permissions
    has_root = check_permissions()

    # Info about what we're doing
    print(f"\n📂 Collection Method: {args.method}")
    if args.method in ['auto', 'journald']:
        print(f"   Time range: Last {args.hours} hours")
    print(f"   Max entries: {args.max_lines}")

    # Collect events
    print(f"\n⏳ Collecting authentication events...")

    try:
        if UNIFIED_AVAILABLE:
            events = collect_auth_events(
                prefer_method=args.method,
                hours=args.hours,
                max_lines=args.max_lines
            )
        else:
            events = collect_auth_events(max_lines=args.max_lines)

    except PermissionError:
        print("\n❌ Permission denied!")
        print("   Auth logs require root access.")
        print("   Try: sudo python test_real_logs.py")
        return 1
    except Exception as e:
        print(f"\n❌ Error collecting events: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Print results
    print_header(f"✅ Collection Complete - {len(events)} Events Found")

    # Summary
    print_event_summary(events)

    # Security analysis
    if events:
        analyze_security(events)

    # Show sample events
    if events:
        max_show = len(events) if args.show_all else 3
        print(f"\n📝 Sample Events (showing first {min(max_show, len(events))}):")
        print("-" * 70)

        for i, event in enumerate(events[:max_show], 1):
            print(f"\n🔹 Event {i}: {event['event_type']}")
            print(f"   Time: {event['time']}")
            print(f"   Message: {event['message']}")
            if event.get('data'):
                print(f"   Details: {json.dumps(event['data'], indent=6)}")

    # Save to file
    if args.output:
        save_to_file(events, args.output)

    # Final tips
    if events:
        print("\n" + "=" * 70)
        print("💡 Tips:")
        print("   • These events are ready to send to the Loglumen server")
        print("   • All events follow the standard Loglumen JSON schema")
        if not has_root and len(events) < 5:
            print("   • Try running with sudo for access to more logs")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
