"""
Linux Authentication Event Collector - Journald Version

This version works with systemd journal (journalctl) instead of log files.
Modern Linux systems (Ubuntu 16.04+, Fedora, Arch, etc.) use journald.

This is useful for systems that don't have /var/log/auth.log but use journald instead.

Usage:
    from collectors.linux.auth_journald import collect_auth_events
    events = collect_auth_events(hours=24)  # Get last 24 hours
"""

import subprocess
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Import our helper utilities
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import create_event, get_hostname, get_local_ip


class JournaldAuthCollector:
    """
    Collects authentication events from systemd journal.

    Uses journalctl command to query the journal for SSH, sudo, and login events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 24, max_lines: int = 10000) -> List[Dict[str, Any]]:
        """
        Collect authentication events from journald.

        Args:
            hours: How many hours back to search (default: 24)
            max_lines: Maximum number of journal entries to process

        Returns:
            list: List of event dictionaries

        Example:
            collector = JournaldAuthCollector()
            events = collector.collect_events(hours=1)  # Last hour
        """
        events = []

        # Check if journalctl is available
        if not self._check_journalctl():
            print("Error: journalctl not found. This system may not use systemd.")
            return events

        # Get journal entries
        journal_lines = self._get_journal_entries(hours, max_lines)

        if not journal_lines:
            print("No journal entries found. You may need sudo access.")
            return events

        # Parse each line
        for line in journal_lines:
            event = self._parse_journal_line(line)
            if event:
                events.append(event)

        return events

    def _check_journalctl(self) -> bool:
        """Check if journalctl command is available."""
        try:
            subprocess.run(['journalctl', '--version'],
                         capture_output=True,
                         check=True,
                         timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _get_journal_entries(self, hours: int, max_lines: int) -> List[str]:
        """
        Get authentication-related entries from journal.

        Args:
            hours: How many hours back to search
            max_lines: Maximum lines to retrieve

        Returns:
            list: List of journal entry strings
        """
        try:
            # Calculate time range
            since = f"{hours}h ago"

            # Query journal for authentication units
            # We look at: sshd, sudo, su, login, and authentication-related messages
            cmd = [
                'journalctl',
                '--since', since,
                '--no-pager',
                '-n', str(max_lines),
                '-o', 'short-iso',  # ISO timestamp format
                '--grep', r'(sshd|sudo|su\[|login|authentication|session opened|session closed|Accepted|Failed|COMMAND=)'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                # Try without grep (older journalctl versions)
                cmd = [
                    'journalctl',
                    '--since', since,
                    '--no-pager',
                    '-n', str(max_lines),
                    '-o', 'short-iso',
                    '_COMM=sshd'  # Filter for sshd
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.stdout:
                return result.stdout.strip().split('\n')

            return []

        except subprocess.TimeoutExpired:
            print("Warning: journalctl command timed out")
            return []
        except Exception as e:
            print(f"Error querying journal: {e}")
            return []

    def _parse_journal_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a journal entry line.

        Journal format: TIMESTAMP HOSTNAME PROCESS[PID]: MESSAGE
        Example: 2025-11-16T14:30:25+0000 hostname sshd[12345]: Accepted publickey for alice...

        Args:
            line: Journal entry line

        Returns:
            dict: Event dictionary or None
        """
        # Skip empty lines and journal hints
        if not line.strip() or line.startswith('--') or line.startswith('Hint:'):
            return None

        # Parse different event types
        if 'sshd' in line:
            if 'Accepted' in line:
                return self._parse_ssh_success(line)
            elif 'Failed' in line:
                return self._parse_ssh_failure(line)
        elif 'sudo' in line and 'COMMAND=' in line:
            return self._parse_sudo_command(line)
        elif ' su[' in line or ' su:' in line:
            return self._parse_su_command(line)

        return None

    def _parse_timestamp(self, line: str) -> datetime:
        """
        Parse ISO timestamp from journal line.

        Format: 2025-11-16T14:30:25+0000 or 2025-11-16T14:30:25.123456+0000
        """
        try:
            # Extract timestamp (first field before hostname)
            timestamp_str = line.split()[0]

            # Handle with or without microseconds
            if '.' in timestamp_str:
                # Has microseconds: 2025-11-16T14:30:25.123456+0000
                dt = datetime.fromisoformat(timestamp_str.replace('+0000', ''))
            else:
                # No microseconds: 2025-11-16T14:30:25+0000
                dt = datetime.fromisoformat(timestamp_str.replace('+0000', ''))

            return dt
        except Exception:
            return datetime.utcnow()

    def _parse_ssh_success(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse successful SSH login from journal."""
        try:
            timestamp = self._parse_timestamp(line)

            # Extract username
            username_match = re.search(r'Accepted \w+ for (\S+) from', line)
            if not username_match:
                return None
            username = username_match.group(1)

            # Extract remote IP
            ip_match = re.search(r'from ([\d\.]+)', line)
            remote_ip = ip_match.group(1) if ip_match else "unknown"

            # Extract auth method
            method_match = re.search(r'Accepted (\w+) for', line)
            auth_method = method_match.group(1) if method_match else "unknown"

            # Extract port
            port_match = re.search(r'port (\d+)', line)
            port = int(port_match.group(1)) if port_match else None

            return create_event(
                category="remote_access",
                event_type="ssh_login_success",
                severity="info",
                message=f"User {username} logged in via SSH from {remote_ip}",
                source="journald",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "username": username,
                    "remote_ip": remote_ip,
                    "auth_method": auth_method,
                    "port": port,
                    "protocol": "ssh"
                }
            )
        except Exception as e:
            print(f"Error parsing SSH success: {e}")
            return None

    def _parse_ssh_failure(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse failed SSH login from journal."""
        try:
            timestamp = self._parse_timestamp(line)

            # Check if invalid user
            is_invalid_user = 'invalid user' in line

            # Extract username
            if is_invalid_user:
                username_match = re.search(r'invalid user (\S+) from', line)
            else:
                username_match = re.search(r'for (\S+) from', line)

            if not username_match:
                return None
            username = username_match.group(1)

            # Extract remote IP
            ip_match = re.search(r'from ([\d\.]+)', line)
            remote_ip = ip_match.group(1) if ip_match else "unknown"

            # Extract port
            port_match = re.search(r'port (\d+)', line)
            port = int(port_match.group(1)) if port_match else None

            # Determine reason
            if is_invalid_user:
                reason = "Invalid user"
            elif 'Failed password' in line:
                reason = "Bad password"
            else:
                reason = "Authentication failed"

            return create_event(
                category="remote_access",
                event_type="ssh_login_failed",
                severity="warning",
                message=f"Failed SSH login for {username} from {remote_ip} - {reason}",
                source="journald",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "username": username,
                    "remote_ip": remote_ip,
                    "port": port,
                    "reason": reason,
                    "invalid_user": is_invalid_user,
                    "protocol": "ssh"
                }
            )
        except Exception as e:
            print(f"Error parsing SSH failure: {e}")
            return None

    def _parse_sudo_command(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse sudo command from journal."""
        try:
            timestamp = self._parse_timestamp(line)

            # Extract username
            username_match = re.search(r'sudo.*:\s+(\S+)\s+:', line)
            if not username_match:
                return None
            username = username_match.group(1)

            # Extract command
            command_match = re.search(r'COMMAND=(.+?)(?:\s*$|;)', line)
            command = command_match.group(1).strip() if command_match else "unknown"

            # Extract target user
            user_match = re.search(r'USER=(\S+)', line)
            target_user = user_match.group(1) if user_match else "root"

            # Extract TTY
            tty_match = re.search(r'TTY=(\S+)', line)
            tty = tty_match.group(1) if tty_match else "unknown"

            # Extract PWD
            pwd_match = re.search(r'PWD=(\S+)', line)
            pwd = pwd_match.group(1) if pwd_match else "unknown"

            return create_event(
                category="privilege_escalation",
                event_type="sudo_used",
                severity="info",
                message=f"User {username} used sudo to run: {command}",
                source="journald",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "username": username,
                    "command": command,
                    "target_user": target_user,
                    "tty": tty,
                    "pwd": pwd,
                    "success": True
                }
            )
        except Exception as e:
            print(f"Error parsing sudo: {e}")
            return None

    def _parse_su_command(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse su command from journal."""
        try:
            timestamp = self._parse_timestamp(line)

            # Check success/failure
            success = 'FAILED' not in line and 'authentication failure' not in line
            severity = "info" if success else "warning"

            # Extract target user
            target_match = re.search(r'\(to (\S+)\)', line)
            target_user = target_match.group(1) if target_match else "root"

            # Extract source user
            user_match = re.search(r'\)\s+(\S+)\s+on', line)
            username = user_match.group(1) if user_match else "unknown"

            # Extract TTY
            tty_match = re.search(r'on\s+(\S+)', line)
            tty = tty_match.group(1) if tty_match else "unknown"

            event_type = "su_success" if success else "su_failed"
            message = f"User {username} {'switched to' if success else 'failed to switch to'} {target_user}"

            return create_event(
                category="privilege_escalation",
                event_type=event_type,
                severity=severity,
                message=message,
                source="journald",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "username": username,
                    "target_user": target_user,
                    "tty": tty,
                    "success": success
                }
            )
        except Exception as e:
            print(f"Error parsing su: {e}")
            return None


def collect_auth_events(hours: int = 24, max_lines: int = 10000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect auth events from journald.

    Args:
        hours: How many hours back to search (default: 24)
        max_lines: Maximum journal entries to process

    Returns:
        list: List of event dictionaries

    Example:
        # Get events from last hour
        events = collect_auth_events(hours=1)

        # Get events from last week
        events = collect_auth_events(hours=24*7)
    """
    collector = JournaldAuthCollector()
    return collector.collect_events(hours, max_lines)


if __name__ == "__main__":
    """Test the journald collector."""
    import json

    print("=" * 70)
    print("Journald Authentication Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting events from last 24 hours...")
    events = collect_auth_events(hours=24, max_lines=100)

    print(f"\n✓ Collected {len(events)} events\n")

    if events:
        print("Sample events (first 3):")
        print("-" * 70)
        for i, event in enumerate(events[:3], 1):
            print(f"\nEvent {i}:")
            print(json.dumps(event, indent=2))

        # Summary
        print("\n" + "=" * 70)
        print("Summary:")
        event_types = {}
        for event in events:
            et = event['event_type']
            event_types[et] = event_types.get(et, 0) + 1

        for et, count in sorted(event_types.items()):
            print(f"  {et}: {count}")
    else:
        print("No events found. Possible reasons:")
        print("  1. No authentication events in the time range")
        print("  2. Need elevated privileges (try with sudo)")
        print("  3. journalctl not available on this system")

    print("\n" + "=" * 70)
