"""
Linux System Crash Event Collector

Collects critical system events:
- Kernel panics
- Out of Memory (OOM) kills
- Segmentation faults
- Hardware errors
- Unexpected reboots
- System freezes

Log locations:
- /var/log/kern.log (Ubuntu/Debian)
- /var/log/messages (RHEL/CentOS)
- journalctl -k (systemd kernel logs)

Author: Loglumen Team
"""

import os
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import create_event, get_hostname, get_local_ip, parse_syslog_timestamp


# Log file locations
SYSTEM_LOG_LOCATIONS = [
    "/var/log/kern.log",     # Ubuntu/Debian kernel log
    "/var/log/messages",     # RHEL/CentOS system log
    "/var/log/syslog",       # General system log
]


class LinuxSystemCollector:
    """
    Collects system crash and critical failure events.
    """

    def __init__(self, log_file: str = None):
        """
        Initialize the collector.

        Args:
            log_file: Specific log file to use (optional, will auto-detect)
        """
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

        # Find log file
        if log_file:
            self.log_file = log_file
        else:
            self.log_file = self._find_system_log()

    def _find_system_log(self) -> Optional[str]:
        """Find the system/kernel log file."""
        for log_path in SYSTEM_LOG_LOCATIONS:
            if os.path.exists(log_path):
                return log_path
        return None

    def collect_events(self, max_lines: int = 1000, use_journald: bool = True) -> List[Dict[str, Any]]:
        """
        Collect system crash events.

        Args:
            max_lines: Maximum lines to process
            use_journald: If True and log file unavailable, try journald

        Returns:
            list: List of event dictionaries
        """
        events = []

        # Try log file first
        if self.log_file and os.path.exists(self.log_file):
            if os.access(self.log_file, os.R_OK):
                events = self._collect_from_file(max_lines)
            else:
                print(f"Warning: No permission to read {self.log_file}")

        # Try journald if no log file or no events
        if use_journald and (not self.log_file or len(events) == 0):
            journald_events = self._collect_from_journald(max_lines)
            events.extend(journald_events)

        return events

    def _collect_from_file(self, max_lines: int) -> List[Dict[str, Any]]:
        """Collect events from log file."""
        events = []

        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

                for line in recent_lines:
                    event = self._parse_log_line(line)
                    if event:
                        events.append(event)

        except Exception as e:
            print(f"Error reading {self.log_file}: {e}")

        return events

    def _collect_from_journald(self, max_lines: int) -> List[Dict[str, Any]]:
        """Collect events from journald kernel log."""
        events = []

        try:
            # Query kernel messages
            cmd = [
                'journalctl',
                '-k',  # Kernel messages
                '-n', str(max_lines),
                '--no-pager',
                '-o', 'short-iso'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split('\n'):
                    event = self._parse_log_line(line)
                    if event:
                        events.append(event)

        except Exception as e:
            print(f"Error querying journald: {e}")

        return events

    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a log line for system events.

        Args:
            line: Log line to parse

        Returns:
            dict: Event dictionary or None
        """
        if not line.strip():
            return None

        # Skip journal hints
        if line.startswith('--') or line.startswith('Hint:'):
            return None

        line_lower = line.lower()

        # Check for different event types
        if 'kernel panic' in line_lower or 'panic:' in line_lower:
            return self._parse_kernel_panic(line)

        elif 'oom' in line_lower and 'kill' in line_lower:
            return self._parse_oom_kill(line)

        elif 'segfault' in line_lower or 'segmentation fault' in line_lower:
            return self._parse_segfault(line)

        elif 'hardware error' in line_lower or 'mce:' in line_lower:
            return self._parse_hardware_error(line)

        elif 'oops:' in line_lower or 'bug:' in line_lower:
            return self._parse_kernel_oops(line)

        elif 'reboot' in line_lower and 'unexpected' in line_lower:
            return self._parse_unexpected_reboot(line)

        return None

    def _parse_kernel_panic(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse kernel panic.

        Example:
        Nov 16 03:22:15 hostname kernel: Kernel panic - not syncing: VFS: Unable to mount root fs
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract panic message
            panic_match = re.search(r'[Pp]anic[:\-]\s*(.+?)(?:\s*$|CPU:)', line)
            panic_msg = panic_match.group(1).strip() if panic_match else line

            return create_event(
                category="system",
                event_type="kernel_panic",
                severity="critical",
                message=f"Kernel panic: {panic_msg[:100]}",
                source=self._get_source_name(),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "panic_message": panic_msg,
                    "full_log": line.strip()
                }
            )

        except Exception as e:
            print(f"Error parsing kernel panic: {e}")
            return None

    def _parse_oom_kill(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse Out of Memory kill.

        Example:
        Nov 16 10:30:00 hostname kernel: Out of memory: Killed process 12345 (nginx) total-vm:1234kB
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract process name
            process_match = re.search(r'Killed process \d+ \(([^)]+)\)', line)
            process = process_match.group(1) if process_match else "unknown"

            # Extract PID
            pid_match = re.search(r'Killed process (\d+)', line)
            pid = int(pid_match.group(1)) if pid_match else None

            # Extract memory info
            mem_match = re.search(r'total-vm:(\d+)kB', line)
            memory = mem_match.group(1) if mem_match else "unknown"

            return create_event(
                category="system",
                event_type="oom_kill",
                severity="error",
                message=f"Out of memory: Killed process {process} (PID {pid})",
                source=self._get_source_name(),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "process_name": process,
                    "pid": pid,
                    "memory_kb": memory,
                    "reason": "out_of_memory"
                }
            )

        except Exception as e:
            print(f"Error parsing OOM kill: {e}")
            return None

    def _parse_segfault(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse segmentation fault.

        Example:
        Nov 16 12:00:00 hostname kernel: program[12345]: segfault at 7f1234567890 ip 00007f9876543210
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract program name
            prog_match = re.search(r'\s([a-zA-Z0-9_\-\.]+)\[\d+\].*segfault', line)
            program = prog_match.group(1) if prog_match else "unknown"

            # Extract PID
            pid_match = re.search(r'\[(\d+)\]', line)
            pid = int(pid_match.group(1)) if pid_match else None

            # Extract address
            addr_match = re.search(r'segfault at ([0-9a-fA-F]+)', line)
            address = addr_match.group(1) if addr_match else "unknown"

            return create_event(
                category="system",
                event_type="segmentation_fault",
                severity="warning",
                message=f"Segmentation fault in {program} (PID {pid})",
                source=self._get_source_name(),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "program": program,
                    "pid": pid,
                    "fault_address": address,
                    "fault_type": "segfault"
                }
            )

        except Exception as e:
            print(f"Error parsing segfault: {e}")
            return None

    def _parse_hardware_error(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse hardware error.

        Example:
        Nov 16 15:00:00 hostname kernel: mce: CPU0: Machine Check Exception: 4 Bank 5
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract error details
            error_msg = line.split('kernel:')[-1].strip() if 'kernel:' in line else line

            # Extract CPU if present
            cpu_match = re.search(r'CPU(\d+)', line)
            cpu = cpu_match.group(1) if cpu_match else None

            return create_event(
                category="system",
                event_type="hardware_error",
                severity="error",
                message=f"Hardware error detected: {error_msg[:80]}",
                source=self._get_source_name(),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "error_message": error_msg,
                    "cpu": cpu,
                    "error_type": "machine_check_exception"
                }
            )

        except Exception as e:
            print(f"Error parsing hardware error: {e}")
            return None

    def _parse_kernel_oops(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse kernel oops (non-fatal kernel error).

        Example:
        Nov 16 16:00:00 hostname kernel: BUG: unable to handle kernel paging request
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract oops/bug message
            msg = line.split('kernel:')[-1].strip() if 'kernel:' in line else line

            # Determine if BUG or Oops
            error_type = "kernel_bug" if 'BUG:' in line else "kernel_oops"

            return create_event(
                category="system",
                event_type=error_type,
                severity="error",
                message=f"Kernel error: {msg[:80]}",
                source=self._get_source_name(),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "error_message": msg,
                    "error_type": error_type
                }
            )

        except Exception as e:
            print(f"Error parsing kernel oops: {e}")
            return None

    def _parse_unexpected_reboot(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse unexpected reboot event."""
        try:
            timestamp = self._extract_timestamp(line)

            return create_event(
                category="system",
                event_type="unexpected_reboot",
                severity="warning",
                message="System experienced unexpected reboot",
                source=self._get_source_name(),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "reboot_type": "unexpected",
                    "log_message": line.strip()
                }
            )

        except Exception as e:
            print(f"Error parsing reboot: {e}")
            return None

    def _extract_timestamp(self, line: str) -> datetime:
        """Extract timestamp from log line."""
        try:
            # Check if journald format (ISO timestamp at start)
            if re.match(r'^\d{4}-\d{2}-\d{2}T', line):
                timestamp_str = line.split()[0]
                return datetime.fromisoformat(timestamp_str.replace('+0000', ''))
            else:
                # Syslog format
                return parse_syslog_timestamp(line)
        except Exception:
            return datetime.utcnow()

    def _get_source_name(self) -> str:
        """Get the log source name."""
        if self.log_file:
            return os.path.basename(self.log_file)
        return "journald"


def collect_system_events(log_file: str = None, max_lines: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect system crash events.

    Args:
        log_file: Specific log file to use
        max_lines: Maximum lines to process

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_system_events()
        print(f"Found {len(events)} system events")
    """
    collector = LinuxSystemCollector(log_file)
    return collector.collect_events(max_lines)


if __name__ == "__main__":
    """Test the system collector."""
    import json

    print("=" * 70)
    print("System Crash Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting system events...")
    events = collect_system_events(max_lines=500)

    print(f"\n✓ Collected {len(events)} events\n")

    if events:
        print("Sample events:")
        for i, event in enumerate(events[:3], 1):
            print(f"\nEvent {i}:")
            print(json.dumps(event, indent=2))

        # Summary
        print("\n" + "=" * 70)
        print("Summary by event type:")
        event_types = {}
        for event in events:
            et = event['event_type']
            event_types[et] = event_types.get(et, 0) + 1

        for et, count in sorted(event_types.items()):
            print(f"  {et}: {count}")
    else:
        print("No system crash events found (this is good!)")
        print("If you want to test, you can check historical logs with:")
        print("  sudo python collectors/linux/system.py")

    print("\n" + "=" * 70)
