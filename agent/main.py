#!/usr/bin/env python3
"""
Loglumen Agent - Main Entry Point

This is the main agent daemon that:
1. Collects events from all sources
2. Sends events to the Loglumen server
3. Runs continuously on a configured interval

Usage:
    # Run once and exit
    python main.py --once

    # Run continuously (daemon mode)
    python main.py

    # Test mode (collect but don't send)
    python main.py --test

    # Dry run (show what would be collected)
    python main.py --dry-run
"""

import os
import sys
import time
import signal
import argparse
import platform
from datetime import datetime
from typing import List, Dict, Any

# Add collectors to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'collectors'))

# Import configuration and sender
from config_loader import load_config, ConfigurationError
from sender import EventSender, SenderError


class LoglumenAgent:
    """
    Main agent class.

    Coordinates event collection and transmission.
    """

    def __init__(self, config_path: str = None):
        """
        Initialize the agent.

        Args:
            config_path: Path to config file (optional)
        """
        # Load configuration
        self.config = load_config(config_path)

        # Get configuration sections
        self.server_config = self.config.get_server_config()
        self.collection_config = self.config.get_collection_config()

        # Create sender
        self.sender = EventSender(self.server_config)

        # Detect OS and load collectors
        self.os_type = self._detect_os()
        print(f"[INFO] Detected operating system: {self.os_type}")

        # Statistics
        self.total_collections = 0
        self.total_events_collected = 0
        self.total_events_sent = 0
        self.total_events_failed = 0

        # Running flag
        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\n[INFO] Shutdown signal received, stopping gracefully...")
        self.running = False

    def _detect_os(self) -> str:
        """
        Determine which operating system collectors to use.

        Returns:
            str: 'linux' or 'windows'
        """
        configured = self.config.get('agent', 'os', None)
        if configured:
            configured = configured.lower()
            if configured in ('linux', 'windows'):
                return configured
            else:
                print(f"[WARN] Unknown agent.os '{configured}' - falling back to auto-detect")

        system_name = platform.system().lower()
        if 'windows' in system_name:
            return 'windows'
        if 'linux' in system_name:
            return 'linux'

        raise ConfigurationError(f"Unsupported operating system: {platform.system()}")

    def _category_enabled(self, enabled: List[str], *names: str) -> bool:
        """Return True if any provided category alias is enabled."""
        normalized = [cat.lower() for cat in enabled]
        return any(name.lower() in normalized for name in names)

    def collect_all_events(self) -> List[Dict[str, Any]]:
        """
        Collect events from all enabled collectors.

        Returns:
            list: All collected events
        """
        enabled = self.collection_config['enabled_categories']
        max_lines = self.collection_config['max_lines_per_log']
        hours = self.collection_config['hours_lookback']

        if self.os_type == 'windows':
            return self._collect_windows_events(enabled, hours, max_lines)
        return self._collect_linux_events(enabled, hours, max_lines)

    def _collect_linux_events(self, enabled, hours, max_lines):
        """Collect events using Linux collectors."""
        from linux.auth_unified import collect_auth_events
        from linux.system import collect_system_events
        from linux.service import collect_service_events
        from linux.software import collect_software_events

        all_events = []

        print(f"[INFO] Collecting events from {len(enabled)} categories (Linux)...")

        # Auth-related categories (authentication, privilege_escalation, remote_access)
        # These all come from the same collector
        if self._category_enabled(enabled, 'authentication', 'privilege_escalation', 'remote_access', 'auth'):
            try:
                events = collect_auth_events(hours=hours, max_lines=max_lines)
                all_events.extend(events)
                # Count by category
                auth_count = len([e for e in events if e['category'] == 'authentication'])
                priv_count = len([e for e in events if e['category'] == 'privilege_escalation'])
                remote_count = len([e for e in events if e['category'] == 'remote_access'])
                print(f"  [OK] Authentication: {auth_count}, Privilege: {priv_count}, Remote: {remote_count}")
            except Exception as e:
                print(f"  [ERROR] Auth collector failed: {e}")

        # System crashes
        if 'system' in enabled:
            try:
                events = collect_system_events(max_lines=max_lines)
                all_events.extend(events)
                print(f"  [OK] System: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] System collector failed: {e}")

        # Service failures
        if 'service' in enabled:
            try:
                events = collect_service_events(hours=hours, max_lines=max_lines)
                all_events.extend(events)
                print(f"  [OK] Service: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Service collector failed: {e}")

        # Software changes
        if 'software' in enabled:
            try:
                events = collect_software_events(max_lines=max_lines)
                all_events.extend(events)
                print(f"  [OK] Software: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Software collector failed: {e}")

        return all_events

    def _collect_windows_events(self, enabled, hours, max_items):
        """Collect events using Windows collectors."""
        from windows.auth import collect_auth_events as win_collect_auth
        from windows.privilege import collect_privilege_events
        from windows.remote import collect_remote_events
        from windows.system import collect_system_events as win_collect_system
        from windows.service import collect_service_events as win_collect_service
        from windows.software import collect_software_events as win_collect_software

        all_events = []

        print(f"[INFO] Collecting events from {len(enabled)} categories (Windows)...")

        # Authentication
        if self._category_enabled(enabled, 'authentication', 'auth'):
            try:
                events = win_collect_auth(hours=hours, max_events=max_items)
                all_events.extend(events)
                print(f"  [OK] Authentication: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Windows auth collector failed: {e}")

        # Privilege escalation
        if self._category_enabled(enabled, 'privilege', 'privilege_escalation'):
            try:
                events = collect_privilege_events(hours=hours, max_events=max_items)
                all_events.extend(events)
                print(f"  [OK] Privilege: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Windows privilege collector failed: {e}")

        # Remote access
        if self._category_enabled(enabled, 'remote', 'remote_access'):
            try:
                events = collect_remote_events(hours=hours, max_events=max_items)
                all_events.extend(events)
                print(f"  [OK] Remote: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Windows remote collector failed: {e}")

        # System crashes
        if 'system' in enabled:
            try:
                events = win_collect_system(hours=hours, max_events=max_items)
                all_events.extend(events)
                print(f"  [OK] System: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Windows system collector failed: {e}")

        # Service failures
        if 'service' in enabled:
            try:
                events = win_collect_service(hours=hours, max_events=max_items)
                all_events.extend(events)
                print(f"  [OK] Service: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Windows service collector failed: {e}")

        # Software changes
        if 'software' in enabled:
            try:
                events = win_collect_software(hours=hours, max_events=max_items)
                all_events.extend(events)
                print(f"  [OK] Software: {len(events)} events")
            except Exception as e:
                print(f"  [ERROR] Windows software collector failed: {e}")

        return all_events

    def run_once(self, send_events: bool = True) -> bool:
        """
        Run one collection and send cycle.

        Args:
            send_events: Whether to send events (False for test mode)

        Returns:
            bool: True if successful
        """
        self.total_collections += 1

        print("\n" + "=" * 70)
        print(f"Collection #{self.total_collections} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Collect events
        events = self.collect_all_events()
        self.total_events_collected += len(events)

        if not events:
            print("[INFO] No events collected this cycle")
            return True

        print(f"\n[INFO] Total collected: {len(events)} events")

        # Apply batch size limit
        max_batch = self.collection_config['max_events_per_batch']
        if len(events) > max_batch:
            print(f"[WARN] Limiting to {max_batch} events (configured batch size)")
            events = events[:max_batch]

        if not send_events:
            print("[INFO] Test mode - not sending events")
            return True

        # Send events
        print(f"[INFO] Sending to {self.server_config['server_ip']}:{self.server_config['server_port']}")

        success = self.sender.send_events(events)

        if success:
            self.total_events_sent += len(events)
            print(f"[SUCCESS] All events sent successfully")
            return True
        else:
            self.total_events_failed += len(events)
            print(f"[ERROR] Failed to send events")
            return False

    def run_daemon(self):
        """
        Run in daemon mode (continuous collection).
        """
        interval = self.collection_config['collection_interval']

        print("=" * 70)
        print("Loglumen Agent - Daemon Mode")
        print("=" * 70)
        print(f"Server: {self.config.get_server_url()}")
        print(f"Collection interval: {interval} seconds")
        print(f"Enabled categories: {', '.join(self.collection_config['enabled_categories'])}")
        print("\nPress Ctrl+C to stop")
        print("=" * 70)

        # Test connection
        print("\n[INFO] Testing server connection...")
        if self.sender.test_connection():
            print("[OK] Server is reachable")
        else:
            print("[WARN] Server not reachable (will retry each cycle)")

        # Main loop
        while self.running:
            try:
                self.run_once(send_events=True)

                if self.running:
                    print(f"\n[INFO] Waiting {interval} seconds until next collection...")
                    print(f"[INFO] Press Ctrl+C to stop gracefully")

                    # Sleep in small increments to allow for quick shutdown
                    for _ in range(interval):
                        if not self.running:
                            break
                        time.sleep(1)

            except KeyboardInterrupt:
                print("\n[INFO] Keyboard interrupt received")
                self.running = False
                break
            except Exception as e:
                print(f"\n[ERROR] Unexpected error in main loop: {e}")
                import traceback
                traceback.print_exc()

                if self.running:
                    print(f"[INFO] Waiting {interval} seconds before retry...")
                    time.sleep(interval)

        # Shutdown
        print("\n" + "=" * 70)
        print("Agent Shutdown")
        print("=" * 70)
        print(f"Total collections: {self.total_collections}")
        print(f"Total events collected: {self.total_events_collected}")
        print(f"Total events sent: {self.total_events_sent}")
        print(f"Total events failed: {self.total_events_failed}")
        print("=" * 70)

    def dry_run(self):
        """
        Dry run mode - show what would be collected without sending.
        """
        print("=" * 70)
        print("Loglumen Agent - Dry Run Mode")
        print("=" * 70)

        events = self.collect_all_events()

        print(f"\n[INFO] Would collect {len(events)} events")

        if events:
            print("\nSample events (first 3):")
            for i, event in enumerate(events[:3], 1):
                print(f"\n  Event {i}:")
                print(f"    Category: {event['category']}")
                print(f"    Type: {event['event_type']}")
                print(f"    Severity: {event['severity']}")
                print(f"    Message: {event['message']}")

            # Summary by category
            by_category = {}
            for event in events:
                cat = event['category']
                by_category[cat] = by_category.get(cat, 0) + 1

            print("\nBy category:")
            for cat, count in sorted(by_category.items()):
                print(f"  {cat}: {count}")

        print("\n[INFO] Dry run complete - no events were sent")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Loglumen Security Event Collection Agent'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (default: run continuously)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: collect but do not send events'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run: show what would be collected'
    )
    args = parser.parse_args()

    # Load and initialize agent
    try:
        agent = LoglumenAgent(config_path=args.config)
    except ConfigurationError as e:
        print(f"[ERROR] Configuration error: {e}")
        return 1
    except SenderError as e:
        print(f"[ERROR] Sender error: {e}")
        return 1
    except Exception as e:
        print(f"[ERROR] Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Run in requested mode
    try:
        if args.dry_run:
            agent.dry_run()
        elif args.once:
            agent.run_once(send_events=not args.test)
        else:
            agent.run_daemon()

        return 0

    except Exception as e:
        print(f"\n[ERROR] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
