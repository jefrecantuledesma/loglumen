#!/usr/bin/env python3
"""
Test All Collectors - Complete Event Collection

This script runs ALL six event collectors and shows a comprehensive
summary of all security events on the system.

Categories:
1. Authentication (SSH, local logins, login failures)
2. Privilege Escalation (sudo, su commands)
3. Remote Access (SSH - covered by auth)
4. System Crashes (kernel panics, OOM kills, segfaults)
5. Service Issues (service failures, crashes, restarts)
6. Software Changes (package installs, updates, removals)

Usage:
    # Run all collectors
    sudo python test_all_collectors.py

    # Save all events to JSON
    sudo python test_all_collectors.py --output all_events.json

    # Show detailed output
    sudo python test_all_collectors.py --verbose
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Add collectors to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'collectors'))

# Import all collectors
try:
    from linux.auth_unified import collect_auth_events
    from linux.system import collect_system_events
    from linux.service import collect_service_events
    from linux.software import collect_software_events
    COLLECTORS_AVAILABLE = True
except ImportError as e:
    print(f"Error importing collectors: {e}")
    COLLECTORS_AVAILABLE = False


def print_header(text, char="="):
    """Print a formatted header."""
    print("\n" + char * 70)
    print(text)
    print(char * 70)


def collect_all_events(hours=24, max_lines=1000):
    """
    Collect events from all collectors.

    Returns:
        dict: Dictionary with category as key, events list as value
    """
    all_events = {}

    print("\n📊 Collecting from all event sources...")

    # 1. Authentication & Privilege Escalation & Remote Access
    print("  ├─ Authentication, Privilege, Remote Access...", end="", flush=True)
    try:
        auth_events = collect_auth_events(hours=hours, max_lines=max_lines)
        all_events['auth'] = auth_events
        print(f" ✓ ({len(auth_events)} events)")
    except Exception as e:
        print(f" ✗ Error: {e}")
        all_events['auth'] = []

    # 2. System Crashes
    print("  ├─ System Crashes...", end="", flush=True)
    try:
        system_events = collect_system_events(max_lines=max_lines)
        all_events['system'] = system_events
        print(f" ✓ ({len(system_events)} events)")
    except Exception as e:
        print(f" ✗ Error: {e}")
        all_events['system'] = []

    # 3. Service Issues
    print("  ├─ Service Issues...", end="", flush=True)
    try:
        service_events = collect_service_events(hours=hours, max_lines=max_lines)
        all_events['service'] = service_events
        print(f" ✓ ({len(service_events)} events)")
    except Exception as e:
        print(f" ✗ Error: {e}")
        all_events['service'] = []

    # 4. Software Changes
    print("  └─ Software Changes...", end="", flush=True)
    try:
        software_events = collect_software_events(max_lines=max_lines)
        all_events['software'] = software_events
        print(f" ✓ ({len(software_events)} events)")
    except Exception as e:
        print(f" ✗ Error: {e}")
        all_events['software'] = []

    return all_events


def print_summary(all_events):
    """Print comprehensive summary of all events."""
    # Flatten all events
    events = []
    for category_events in all_events.values():
        events.extend(category_events)

    total = len(events)

    print_header("📈 Event Summary", "=")

    if total == 0:
        print("\n✓ No security events found!")
        print("  This is generally good - it means no failures, crashes, or issues.")
        print("  Note: You may need sudo for full access to all logs.")
        return

    print(f"\n🔢 Total Events: {total}")

    # By category
    print("\n📋 By Category:")
    for category, category_events in all_events.items():
        if category_events:
            emoji = {
                'auth': '🔐',
                'system': '💻',
                'service': '⚙️',
                'software': '📦'
            }.get(category, '•')
            print(f"  {emoji} {category.capitalize()}: {len(category_events)}")

    # By event type
    print("\n📊 By Event Type:")
    event_types = {}
    for event in events:
        et = event.get('event_type', 'unknown')
        event_types[et] = event_types.get(et, 0) + 1

    for et, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {et}: {count}")

    # By severity
    print("\n⚠️  By Severity:")
    severity_counts = {}
    for event in events:
        sev = event.get('severity', 'unknown')
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    severity_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
    for sev in ['info', 'warning', 'error', 'critical']:
        if sev in severity_counts:
            emoji = severity_emoji.get(sev, '•')
            print(f"  {emoji} {sev}: {severity_counts[sev]}")


def analyze_security(all_events):
    """Perform security analysis across all event types."""
    events = []
    for category_events in all_events.values():
        events.extend(category_events)

    if not events:
        return

    print_header("🔒 Security Analysis", "=")

    # Critical and error events
    critical = [e for e in events if e.get('severity') in ['critical', 'error']]
    if critical:
        print(f"\n🚨 {len(critical)} critical/error events require attention:")
        for event in critical[:5]:  # Show first 5
            print(f"  • {event['time']}: {event['message'][:60]}")
        if len(critical) > 5:
            print(f"  ... and {len(critical) - 5} more")

    # Failed authentication
    failed_auth = [e for e in events if 'failed' in e.get('event_type', '').lower()
                   and e.get('category') == 'auth']
    if failed_auth:
        print(f"\n⚠️  {len(failed_auth)} failed authentication attempts")

        # Group by IP
        by_ip = {}
        for event in failed_auth:
            ip = event.get('data', {}).get('remote_ip', 'unknown')
            by_ip[ip] = by_ip.get(ip, 0) + 1

        suspicious = {ip: count for ip, count in by_ip.items() if count >= 3}
        if suspicious:
            print("   Potential brute force attacks:")
            for ip, count in sorted(suspicious.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"     {ip}: {count} failed attempts")

    # Service failures
    service_failures = [e for e in events if e.get('category') == 'service']
    if service_failures:
        print(f"\n⚙️  {len(service_failures)} service issues detected")
        services = {}
        for event in service_failures:
            svc = event.get('data', {}).get('service_name', 'unknown')
            services[svc] = services.get(svc, 0) + 1

        print("   Top affected services:")
        for svc, count in sorted(services.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     {svc}: {count} issues")

    # System crashes
    crashes = [e for e in events if e.get('category') == 'system']
    if crashes:
        print(f"\n💻 {len(crashes)} system-level events")
        crash_types = {}
        for event in crashes:
            ct = event.get('event_type', 'unknown')
            crash_types[ct] = crash_types.get(ct, 0) + 1

        for ct, count in sorted(crash_types.items()):
            print(f"     {ct}: {count}")

    # Recent software changes
    software = [e for e in events if e.get('category') == 'software']
    if software:
        print(f"\n📦 {len(software)} software changes")

        installs = len([e for e in software if e.get('event_type') == 'software_installed'])
        updates = len([e for e in software if e.get('event_type') == 'software_updated'])
        removes = len([e for e in software if e.get('event_type') == 'software_removed'])

        if installs:
            print(f"     Installed: {installs}")
        if updates:
            print(f"     Updated: {updates}")
        if removes:
            print(f"     Removed: {removes}")


def print_sample_events(all_events, max_per_category=2):
    """Print sample events from each category."""
    print_header("📝 Sample Events", "=")

    for category, events in all_events.items():
        if not events:
            continue

        print(f"\n{category.upper()}:")
        for i, event in enumerate(events[:max_per_category], 1):
            print(f"\n  Event {i}:")
            print(f"    Type: {event['event_type']}")
            print(f"    Time: {event['time']}")
            print(f"    Severity: {event['severity']}")
            print(f"    Message: {event['message']}")


def save_events(all_events, filename):
    """Save all events to JSON file."""
    # Flatten events
    events = []
    for category_events in all_events.values():
        events.extend(category_events)

    try:
        with open(filename, 'w') as f:
            json.dump(events, f, indent=2)

        size = os.path.getsize(filename)
        print(f"\n✅ Saved {len(events)} events to: {filename}")
        print(f"   File size: {size:,} bytes")
        print(f"\n💡 This JSON file is ready to send to the Loglumen server!")

    except Exception as e:
        print(f"\n❌ Error saving file: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Test all Loglumen collectors'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Hours to look back (default: 24)'
    )
    parser.add_argument(
        '--max-lines',
        type=int,
        default=1000,
        help='Max lines per log file (default: 1000)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Save all events to JSON file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show sample events from each category'
    )
    args = parser.parse_args()

    if not COLLECTORS_AVAILABLE:
        print("❌ Collectors not available. Please check installation.")
        return 1

    print_header("🔍 Loglumen - Complete Event Collection Test", "=")

    # Check permissions
    uid = os.getuid()
    if uid == 0:
        print("✓ Running as root - full access")
    else:
        print("⚠  Running as regular user - may have limited access")
        print("   Tip: Run with sudo for complete results")

    print(f"\n⚙️  Collection Parameters:")
    print(f"   Time range: Last {args.hours} hours")
    print(f"   Max lines: {args.max_lines} per log")

    # Collect all events
    all_events = collect_all_events(hours=args.hours, max_lines=args.max_lines)

    # Print summary
    print_summary(all_events)

    # Security analysis
    analyze_security(all_events)

    # Sample events if verbose
    if args.verbose:
        print_sample_events(all_events)

    # Save to file if requested
    if args.output:
        save_events(all_events, args.output)

    # Final status
    total = sum(len(events) for events in all_events.values())
    print_header(f"✨ Collection Complete - {total} Total Events", "=")

    print("\n📊 Coverage:")
    print("   ✓ Authentication events (SSH, local, failures)")
    print("   ✓ Privilege escalation (sudo, su)")
    print("   ✓ Remote access (SSH logins)")
    print("   ✓ System crashes (panics, OOM, segfaults)")
    print("   ✓ Service issues (failures, crashes, restarts)")
    print("   ✓ Software changes (installs, updates, removals)")

    print("\n🎯 Next Step:")
    print("   These events are now ready to be sent to the Loglumen server!")
    print("   Next: Implement the sender module to transmit events.")

    print("\n" + "=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
