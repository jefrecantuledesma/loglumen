"""
Linux Service Failure Event Collector

Collects service/daemon failure events:
- Systemd service failures
- Service crashes and restarts
- Application errors
- Daemon failures
- Service state changes (stopped, failed, degraded)

Data sources:
- journalctl (systemd journal)
- /var/log/syslog
- /var/log/messages

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


class LinuxServiceCollector:
    """
    Collects service failure and daemon crash events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 24, max_lines: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect service failure events.

        Args:
            hours: How many hours back to search (for journald)
            max_lines: Maximum entries to process

        Returns:
            list: List of event dictionaries
        """
        events = []

        # Try journald first (best for systemd systems)
        journald_events = self._collect_from_journald(hours, max_lines)
        events.extend(journald_events)

        # If no journald or few events, try syslog
        if len(events) < 5:
            syslog_events = self._collect_from_syslog(max_lines)
            events.extend(syslog_events)

        return events

    def _collect_from_journald(self, hours: int, max_lines: int) -> List[Dict[str, Any]]:
        """
        Collect service events from systemd journal.

        Queries journald for:
        - Service failures
        - Service restarts
        - Application crashes
        """
        events = []

        # Check if journalctl is available
        try:
            subprocess.run(['journalctl', '--version'],
                         capture_output=True,
                         check=True,
                         timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return events  # journalctl not available

        # Query for service failures
        try:
            cmd = [
                'journalctl',
                '--since', f'{hours}h ago',
                '-n', str(max_lines),
                '--no-pager',
                '-o', 'short-iso',
                '-p', 'err',  # Priority: error and above
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split('\n'):
                    event = self._parse_journald_line(line)
                    if event:
                        events.append(event)

        except Exception as e:
            print(f"Error querying journald: {e}")

        # Also query specifically for systemd unit failures
        try:
            cmd = [
                'journalctl',
                '--since', f'{hours}h ago',
                '-n', str(max_lines),
                '--no-pager',
                '-o', 'short-iso',
                '-u', '*.service',  # All services
                '--grep', 'failed|crashed|stopped'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split('\n'):
                    event = self._parse_journald_line(line)
                    if event and not any(e.get('data', {}).get('service_name') ==
                                        event.get('data', {}).get('service_name') and
                                        e.get('time') == event.get('time')
                                        for e in events):
                        events.append(event)

        except Exception:
            pass  # Grep might not be supported on older journalctl

        return events

    def _collect_from_syslog(self, max_lines: int) -> List[Dict[str, Any]]:
        """Collect service events from syslog."""
        events = []

        syslog_paths = ['/var/log/syslog', '/var/log/messages']

        for log_path in syslog_paths:
            if os.path.exists(log_path) and os.access(log_path, os.R_OK):
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

                        for line in recent_lines:
                            event = self._parse_syslog_line(line)
                            if event:
                                events.append(event)

                except Exception as e:
                    print(f"Error reading {log_path}: {e}")

                break  # Use first available log

        return events

    def _parse_journald_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a journald entry for service failures."""
        if not line.strip() or line.startswith('--') or line.startswith('Hint:'):
            return None

        line_lower = line.lower()

        # Service failure patterns
        if 'failed' in line_lower and ('.service' in line_lower or 'unit' in line_lower):
            return self._parse_service_failure(line)

        elif 'crashed' in line_lower or 'core dump' in line_lower:
            return self._parse_service_crash(line)

        elif 'restart' in line_lower and ('limit' in line_lower or 'too' in line_lower):
            return self._parse_service_restart_limit(line)

        elif 'error' in line_lower and any(daemon in line_lower for daemon in ['systemd', 'init', 'service']):
            return self._parse_service_error(line)

        return None

    def _parse_syslog_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a syslog entry for service failures."""
        if not line.strip():
            return None

        line_lower = line.lower()

        # Look for service-related errors
        if ('error' in line_lower or 'failed' in line_lower or 'crash' in line_lower):
            # Filter for service names (common daemons)
            service_keywords = ['systemd', 'nginx', 'apache', 'mysql', 'postgresql',
                              'redis', 'docker', 'sshd', 'cron', 'rsyslog']

            if any(keyword in line_lower for keyword in service_keywords):
                return self._parse_service_error(line)

        return None

    def _parse_service_failure(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse systemd service failure.

        Example:
        2025-11-16T10:30:00+0000 hostname systemd[1]: nginx.service: Failed with result 'exit-code'.
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract service name
            service_match = re.search(r'([a-zA-Z0-9_\-\.]+)\.service', line)
            if not service_match:
                return None
            service_name = service_match.group(1)

            # Extract failure reason
            reason_match = re.search(r"result '([^']+)'", line)
            reason = reason_match.group(1) if reason_match else "unknown"

            # Extract exit code if present
            exit_code_match = re.search(r'code=(\w+)', line)
            exit_code = exit_code_match.group(1) if exit_code_match else None

            return create_event(
                category="service",
                event_type="service_failed",
                severity="error",
                message=f"Service {service_name} failed: {reason}",
                source="journald",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "service_name": service_name,
                    "failure_reason": reason,
                    "exit_code": exit_code,
                    "unit_type": "systemd"
                }
            )

        except Exception as e:
            print(f"Error parsing service failure: {e}")
            return None

    def _parse_service_crash(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse service crash.

        Example:
        2025-11-16T11:00:00+0000 hostname kernel: nginx[12345]: crashed with signal 11
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract service/process name
            service_match = re.search(r'\s([a-zA-Z0-9_\-\.]+)\[\d+\].*crash', line)
            service_name = service_match.group(1) if service_match else "unknown"

            # Extract PID
            pid_match = re.search(r'\[(\d+)\]', line)
            pid = int(pid_match.group(1)) if pid_match else None

            # Extract signal if present
            signal_match = re.search(r'signal (\d+)', line)
            signal = signal_match.group(1) if signal_match else None

            return create_event(
                category="service",
                event_type="service_crashed",
                severity="error",
                message=f"Service {service_name} crashed (PID {pid})",
                source=self._get_source(line),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "service_name": service_name,
                    "pid": pid,
                    "signal": signal,
                    "crash_type": "core_dump" if 'core' in line.lower() else "crash"
                }
            )

        except Exception as e:
            print(f"Error parsing service crash: {e}")
            return None

    def _parse_service_restart_limit(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse service restart limit exceeded.

        Example:
        2025-11-16T12:00:00+0000 hostname systemd[1]: mysql.service: Start request repeated too quickly.
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Extract service name
            service_match = re.search(r'([a-zA-Z0-9_\-\.]+)\.service', line)
            service_name = service_match.group(1) if service_match else "unknown"

            return create_event(
                category="service",
                event_type="service_restart_limit",
                severity="warning",
                message=f"Service {service_name} restart limit exceeded",
                source="journald",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "service_name": service_name,
                    "reason": "restart_limit_exceeded",
                    "unit_type": "systemd"
                }
            )

        except Exception as e:
            print(f"Error parsing restart limit: {e}")
            return None

    def _parse_service_error(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse general service error.

        Example:
        Nov 16 13:00:00 hostname nginx: Error: configuration file test failed
        """
        try:
            timestamp = self._extract_timestamp(line)

            # Try to extract service name from the log line
            # Format: "hostname service: message" or "hostname service[pid]: message"
            service_match = re.search(r'\s([a-zA-Z0-9_\-\.]+)(?:\[\d+\])?:\s+(.+)', line)

            if not service_match:
                return None

            service_name = service_match.group(1)
            error_msg = service_match.group(2).strip()

            # Filter out non-services (like kernel, systemd journald, etc.)
            if service_name in ['kernel', 'systemd-journald', 'systemd-logind']:
                return None

            return create_event(
                category="service",
                event_type="service_error",
                severity="warning",
                message=f"Service {service_name} error: {error_msg[:80]}",
                source=self._get_source(line),
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "service_name": service_name,
                    "error_message": error_msg,
                    "error_type": "application_error"
                }
            )

        except Exception as e:
            print(f"Error parsing service error: {e}")
            return None

    def _extract_timestamp(self, line: str) -> datetime:
        """Extract timestamp from log line."""
        try:
            # Journald format (ISO timestamp)
            if re.match(r'^\d{4}-\d{2}-\d{2}T', line):
                timestamp_str = line.split()[0]
                return datetime.fromisoformat(timestamp_str.replace('+0000', ''))
            else:
                # Syslog format
                return parse_syslog_timestamp(line)
        except Exception:
            return datetime.utcnow()

    def _get_source(self, line: str) -> str:
        """Determine log source."""
        if 'journald' in line or re.match(r'^\d{4}-\d{2}-\d{2}T', line):
            return "journald"
        return "syslog"


def collect_service_events(hours: int = 24, max_lines: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect service failure events.

    Args:
        hours: Hours to look back (for journald)
        max_lines: Maximum entries to process

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_service_events(hours=24)
        print(f"Found {len(events)} service failures")
    """
    collector = LinuxServiceCollector()
    return collector.collect_events(hours, max_lines)


if __name__ == "__main__":
    """Test the service collector."""
    import json

    print("=" * 70)
    print("Service Failure Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting service events from last 24 hours...")
    events = collect_service_events(hours=24, max_lines=100)

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

        # Summary by service
        print("\nTop services with issues:")
        services = {}
        for event in events:
            svc = event.get('data', {}).get('service_name', 'unknown')
            services[svc] = services.get(svc, 0) + 1

        for svc, count in sorted(services.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {svc}: {count} issues")

    else:
        print("No service failure events found (this is good!)")
        print("Try: sudo python collectors/linux/service.py")

    print("\n" + "=" * 70)
