"""
Linux Authentication Event Collector

This collector reads Linux authentication logs and extracts security-relevant events:
- SSH login attempts (successful and failed)
- Local login attempts (console, TTY)
- Sudo usage
- Su (switch user) commands

Log locations:
- Ubuntu/Debian: /var/log/auth.log
- RHEL/CentOS: /var/log/secure

Author: Loglumen Team
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import our helper utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import create_event, get_hostname, get_local_ip, parse_syslog_timestamp


# Constants for log file locations
AUTH_LOG_LOCATIONS = [
    "/var/log/auth.log",      # Ubuntu/Debian
    "/var/log/secure",         # RHEL/CentOS
]


class LinuxAuthCollector:
    """
    Collects authentication events from Linux system logs.

    This class handles parsing auth logs and converting them into
    standardized Loglumen events.
    """

    def __init__(self, log_file: str = None):
        """
        Initialize the collector.

        Args:
            log_file: Path to auth log file. If None, will auto-detect.
        """
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

        # Find the auth log file
        if log_file:
            self.log_file = log_file
        else:
            self.log_file = self._find_auth_log()

        # Track which lines we've already processed (for future use)
        self.last_position = 0

    def _find_auth_log(self) -> Optional[str]:
        """
        Find the authentication log file on this system.

        Returns:
            str: Path to the auth log file, or None if not found
        """
        for log_path in AUTH_LOG_LOCATIONS:
            if os.path.exists(log_path):
                return log_path
        return None

    def collect_events(self, max_lines: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect authentication events from the log file.

        Args:
            max_lines: Maximum number of log lines to read (most recent)

        Returns:
            list: List of event dictionaries in Loglumen JSON format

        Example:
            collector = LinuxAuthCollector()
            events = collector.collect_events()
            print(f"Collected {len(events)} events")
        """
        events = []

        # Check if log file exists
        if not self.log_file or not os.path.exists(self.log_file):
            print(f"Warning: Auth log file not found. Tried: {AUTH_LOG_LOCATIONS}")
            return events

        # Check if we have permission to read it
        if not os.access(self.log_file, os.R_OK):
            print(f"Error: No permission to read {self.log_file}")
            print("Tip: Try running with sudo")
            return events

        try:
            # Read the log file
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Read all lines (in production, you'd read only new lines)
                lines = f.readlines()

                # Process only the most recent lines
                recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

                # Parse each line
                for line in recent_lines:
                    # Try to parse this line as an authentication event
                    event = self._parse_log_line(line)
                    if event:
                        events.append(event)

        except PermissionError:
            print(f"Error: Permission denied reading {self.log_file}")
            print("Tip: Run with sudo to access system logs")
        except Exception as e:
            print(f"Error reading log file: {e}")

        return events

    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line and create an event if it's relevant.

        Args:
            line: A single line from the auth log

        Returns:
            dict: Event dictionary, or None if line isn't relevant

        This method checks for different types of authentication events
        and calls the appropriate parser method.
        """
        # Skip empty lines
        if not line.strip():
            return None

        # Try to parse different event types
        # Each parser returns an event dict or None

        # SSH events
        if 'sshd' in line:
            if 'Accepted' in line:
                return self._parse_ssh_success(line)
            elif 'Failed password' in line or 'authentication failure' in line:
                return self._parse_ssh_failure(line)

        # Sudo events
        elif 'sudo' in line and 'COMMAND=' in line:
            return self._parse_sudo_command(line)

        # Su (switch user) events
        elif ' su[' in line or ' su:' in line:
            return self._parse_su_command(line)

        # Local login events
        elif 'login' in line.lower():
            return self._parse_local_login(line)

        # Not a relevant event
        return None

    def _parse_ssh_success(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a successful SSH login.

        Example log line:
        Nov 16 14:30:25 hostname sshd[12345]: Accepted publickey for alice from 192.168.1.50 port 54321 ssh2

        Args:
            line: Log line containing successful SSH login

        Returns:
            dict: Event dictionary
        """
        try:
            # Extract timestamp
            timestamp = parse_syslog_timestamp(line)

            # Extract username
            # Pattern: "Accepted <method> for <username> from"
            username_match = re.search(r'Accepted \w+ for (\S+) from', line)
            if not username_match:
                return None
            username = username_match.group(1)

            # Extract remote IP
            # Pattern: "from <ip> port"
            ip_match = re.search(r'from ([\d\.]+) port', line)
            remote_ip = ip_match.group(1) if ip_match else "unknown"

            # Extract authentication method (password, publickey, etc.)
            method_match = re.search(r'Accepted (\w+) for', line)
            auth_method = method_match.group(1) if method_match else "unknown"

            # Extract port
            port_match = re.search(r'port (\d+)', line)
            port = int(port_match.group(1)) if port_match else None

            # Create the event
            return create_event(
                category="auth",
                event_type="ssh_login_success",
                severity="info",
                message=f"User {username} logged in via SSH from {remote_ip}",
                source=os.path.basename(self.log_file),
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
        """
        Parse a failed SSH login attempt.

        Example log lines:
        Nov 16 14:35:12 hostname sshd[12346]: Failed password for bob from 192.168.1.51 port 54322 ssh2
        Nov 16 14:36:00 hostname sshd[12347]: Failed password for invalid user admin from 10.0.0.5 port 12345 ssh2

        Args:
            line: Log line containing failed SSH login

        Returns:
            dict: Event dictionary
        """
        try:
            # Extract timestamp
            timestamp = parse_syslog_timestamp(line)

            # Check if it's an invalid user
            is_invalid_user = 'invalid user' in line

            # Extract username
            if is_invalid_user:
                # Pattern: "invalid user <username> from"
                username_match = re.search(r'invalid user (\S+) from', line)
            else:
                # Pattern: "for <username> from"
                username_match = re.search(r'for (\S+) from', line)

            if not username_match:
                return None
            username = username_match.group(1)

            # Extract remote IP
            ip_match = re.search(r'from ([\d\.]+) port', line)
            remote_ip = ip_match.group(1) if ip_match else "unknown"

            # Extract port
            port_match = re.search(r'port (\d+)', line)
            port = int(port_match.group(1)) if port_match else None

            # Determine failure reason
            if is_invalid_user:
                reason = "Invalid user"
            elif 'Failed password' in line:
                reason = "Bad password"
            else:
                reason = "Authentication failed"

            # Create the event
            return create_event(
                category="auth",
                event_type="ssh_login_failed",
                severity="warning",
                message=f"Failed SSH login for {username} from {remote_ip} - {reason}",
                source=os.path.basename(self.log_file),
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
        """
        Parse a sudo command execution.

        Example log line:
        Nov 16 14:40:00 hostname sudo: alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/usr/bin/apt update

        Args:
            line: Log line containing sudo command

        Returns:
            dict: Event dictionary
        """
        try:
            # Extract timestamp
            timestamp = parse_syslog_timestamp(line)

            # Extract username (who ran sudo)
            # Pattern: "sudo: <username> :"
            username_match = re.search(r'sudo:\s+(\S+)\s+:', line)
            if not username_match:
                return None
            username = username_match.group(1)

            # Extract command
            # Pattern: "COMMAND=<command>"
            command_match = re.search(r'COMMAND=(.+)$', line)
            command = command_match.group(1).strip() if command_match else "unknown"

            # Extract target user (who they became, usually root)
            user_match = re.search(r'USER=(\S+)', line)
            target_user = user_match.group(1) if user_match else "root"

            # Extract TTY
            tty_match = re.search(r'TTY=(\S+)', line)
            tty = tty_match.group(1) if tty_match else "unknown"

            # Extract working directory
            pwd_match = re.search(r'PWD=(\S+)', line)
            pwd = pwd_match.group(1) if pwd_match else "unknown"

            # Create the event
            return create_event(
                category="privilege",
                event_type="sudo_used",
                severity="info",
                message=f"User {username} used sudo to run: {command}",
                source=os.path.basename(self.log_file),
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
                    "success": True  # If it's in the log, sudo succeeded
                }
            )

        except Exception as e:
            print(f"Error parsing sudo command: {e}")
            return None

    def _parse_su_command(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a su (switch user) command.

        Example log line:
        Nov 16 15:00:00 hostname su: (to root) alice on pts/0

        Args:
            line: Log line containing su command

        Returns:
            dict: Event dictionary
        """
        try:
            # Extract timestamp
            timestamp = parse_syslog_timestamp(line)

            # Check if successful or failed
            if 'FAILED' in line or 'authentication failure' in line:
                success = False
                severity = "warning"
            else:
                success = True
                severity = "info"

            # Extract target user
            # Pattern: "(to <user>)"
            target_match = re.search(r'\(to (\S+)\)', line)
            target_user = target_match.group(1) if target_match else "root"

            # Extract source user
            # Pattern: ") <user> on"
            user_match = re.search(r'\)\s+(\S+)\s+on', line)
            username = user_match.group(1) if user_match else "unknown"

            # Extract TTY
            tty_match = re.search(r'on\s+(\S+)', line)
            tty = tty_match.group(1) if tty_match else "unknown"

            # Create the event
            event_type = "su_success" if success else "su_failed"
            message = f"User {username} {'switched to' if success else 'failed to switch to'} {target_user}"

            return create_event(
                category="privilege",
                event_type=event_type,
                severity=severity,
                message=message,
                source=os.path.basename(self.log_file),
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
            print(f"Error parsing su command: {e}")
            return None

    def _parse_local_login(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a local console/TTY login.

        Example log line:
        Nov 16 16:00:00 hostname login[1234]: pam_unix(login:session): session opened for user bob by LOGIN(uid=0)

        Args:
            line: Log line containing local login

        Returns:
            dict: Event dictionary
        """
        try:
            # Extract timestamp
            timestamp = parse_syslog_timestamp(line)

            # Determine if successful
            if 'session opened' in line:
                success = True
                severity = "info"
            elif 'FAILED' in line or 'authentication failure' in line:
                success = False
                severity = "warning"
            else:
                return None  # Not a login event we care about

            # Extract username
            username_match = re.search(r'for user (\S+)', line)
            if not username_match:
                username_match = re.search(r'user=(\S+)', line)
            if not username_match:
                return None
            username = username_match.group(1)

            # Create the event
            event_type = "local_login_success" if success else "local_login_failed"
            message = f"Local {'login' if success else 'login failed'} for user {username}"

            return create_event(
                category="auth",
                event_type=event_type,
                severity=severity,
                message=message,
                source=os.path.basename(self.log_file),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "username": username,
                    "login_type": "local",
                    "success": success
                }
            )

        except Exception as e:
            print(f"Error parsing local login: {e}")
            return None


# ============================================================================
# Main function - for easy testing
# ============================================================================

def collect_auth_events(log_file: str = None, max_lines: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect authentication events.

    This is the main entry point that other parts of Loglumen will call.

    Args:
        log_file: Path to auth log (optional, will auto-detect)
        max_lines: Maximum number of recent log lines to process

    Returns:
        list: List of event dictionaries

    Example:
        from collectors.linux.auth import collect_auth_events
        events = collect_auth_events()
        print(f"Found {len(events)} authentication events")
    """
    collector = LinuxAuthCollector(log_file)
    return collector.collect_events(max_lines)


# ============================================================================
# Run as standalone script for testing
# ============================================================================

if __name__ == "__main__":
    """
    If you run this file directly, it will collect events and print them.

    Usage:
        python auth.py
        sudo python auth.py  # If you need elevated permissions
    """
    import json

    print("=" * 70)
    print("Linux Authentication Event Collector - Test Mode")
    print("=" * 70)

    # Collect events
    print("\nCollecting authentication events...")
    events = collect_auth_events(max_lines=100)

    # Print results
    print(f"\n✓ Collected {len(events)} events\n")

    if events:
        print("Sample events (showing first 3):")
        print("-" * 70)
        for i, event in enumerate(events[:3], 1):
            print(f"\nEvent {i}:")
            print(json.dumps(event, indent=2))

        # Print summary by event type
        print("\n" + "=" * 70)
        print("Summary by event type:")
        print("-" * 70)
        event_types = {}
        for event in events:
            event_type = event['event_type']
            event_types[event_type] = event_types.get(event_type, 0) + 1

        for event_type, count in sorted(event_types.items()):
            print(f"  {event_type}: {count}")

    else:
        print("No events collected. This could mean:")
        print("  1. No authentication events in the log file")
        print("  2. Permission denied (try: sudo python auth.py)")
        print("  3. Log file not found")

    print("\n" + "=" * 70)
