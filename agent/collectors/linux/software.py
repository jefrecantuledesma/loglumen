"""
Linux Software Changes Event Collector

Collects package management events:
- Package installations
- Package updates/upgrades
- Package removals
- System updates

Supported package managers:
- apt/dpkg (Ubuntu/Debian)
- yum/dnf (RHEL/CentOS/Fedora)
- pacman (Arch Linux)
- zypper (openSUSE)

Log locations:
- /var/log/dpkg.log (Debian/Ubuntu dpkg)
- /var/log/apt/history.log (Debian/Ubuntu apt)
- /var/log/yum.log (RHEL/CentOS yum)
- /var/log/dnf.log (Fedora dnf)
- /var/log/pacman.log (Arch pacman)

Author: Loglumen Team
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import create_event, get_hostname, get_local_ip


class LinuxSoftwareCollector:
    """
    Collects software installation/update/removal events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

        # Detect package manager and log files
        self.package_manager = self._detect_package_manager()
        self.log_files = self._get_log_files()

    def _detect_package_manager(self) -> str:
        """Detect which package manager is used on this system."""
        # Check for existence of package manager commands
        if os.path.exists('/usr/bin/apt') or os.path.exists('/usr/bin/dpkg'):
            return 'apt'
        elif os.path.exists('/usr/bin/dnf'):
            return 'dnf'
        elif os.path.exists('/usr/bin/yum'):
            return 'yum'
        elif os.path.exists('/usr/bin/pacman'):
            return 'pacman'
        elif os.path.exists('/usr/bin/zypper'):
            return 'zypper'
        return 'unknown'

    def _get_log_files(self) -> List[str]:
        """Get list of package manager log files to check."""
        log_files = []

        # APT/DPKG logs (Ubuntu/Debian)
        if self.package_manager == 'apt':
            for log in ['/var/log/apt/history.log', '/var/log/dpkg.log']:
                if os.path.exists(log):
                    log_files.append(log)

        # DNF logs (Fedora)
        elif self.package_manager == 'dnf':
            if os.path.exists('/var/log/dnf.log'):
                log_files.append('/var/log/dnf.log')
            if os.path.exists('/var/log/dnf.rpm.log'):
                log_files.append('/var/log/dnf.rpm.log')

        # YUM logs (RHEL/CentOS)
        elif self.package_manager == 'yum':
            if os.path.exists('/var/log/yum.log'):
                log_files.append('/var/log/yum.log')

        # Pacman logs (Arch)
        elif self.package_manager == 'pacman':
            if os.path.exists('/var/log/pacman.log'):
                log_files.append('/var/log/pacman.log')

        # Zypper logs (openSUSE)
        elif self.package_manager == 'zypper':
            if os.path.exists('/var/log/zypper.log'):
                log_files.append('/var/log/zypper.log')

        return log_files

    def collect_events(self, max_lines: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect software change events.

        Args:
            max_lines: Maximum lines to process per log file

        Returns:
            list: List of event dictionaries
        """
        events = []

        if not self.log_files:
            print(f"No package manager logs found (detected: {self.package_manager})")
            return events

        for log_file in self.log_files:
            if os.access(log_file, os.R_OK):
                file_events = self._collect_from_file(log_file, max_lines)
                events.extend(file_events)
            else:
                print(f"Warning: No permission to read {log_file}")

        return events

    def _collect_from_file(self, log_file: str, max_lines: int) -> List[Dict[str, Any]]:
        """Collect events from a specific log file."""
        events = []

        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

                for line in recent_lines:
                    event = self._parse_log_line(line, log_file)
                    if event:
                        events.append(event)

        except Exception as e:
            print(f"Error reading {log_file}: {e}")

        return events

    def _parse_log_line(self, line: str, log_file: str) -> Optional[Dict[str, Any]]:
        """Parse a log line based on package manager type."""
        if not line.strip():
            return None

        # Determine parser based on file name
        if 'dpkg.log' in log_file:
            return self._parse_dpkg_line(line)
        elif 'apt/history.log' in log_file:
            return self._parse_apt_history_line(line)
        elif 'yum.log' in log_file or 'dnf.log' in log_file or 'dnf.rpm.log' in log_file:
            return self._parse_yum_dnf_line(line)
        elif 'pacman.log' in log_file:
            return self._parse_pacman_line(line)
        elif 'zypper.log' in log_file:
            return self._parse_zypper_line(line)

        return None

    def _parse_dpkg_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse dpkg.log line.

        Format: 2025-11-16 10:30:00 install nginx:amd64 <none> 1.18.0-1ubuntu1
        """
        try:
            # Parse timestamp (first two fields)
            parts = line.split()
            if len(parts) < 5:
                return None

            timestamp_str = f"{parts[0]} {parts[1]}"
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

            action = parts[2]  # install, upgrade, remove, purge
            package = parts[3].split(':')[0]  # Remove architecture suffix

            # Determine event type and severity
            if action == 'install':
                event_type = 'software_installed'
                severity = 'info'
            elif action in ['upgrade', 'update']:
                event_type = 'software_updated'
                severity = 'info'
            elif action in ['remove', 'purge']:
                event_type = 'software_removed'
                severity = 'info'
            else:
                return None  # Skip configure, trigproc, etc.

            # Extract version if available
            version = parts[5] if len(parts) > 5 else "unknown"

            return create_event(
                category="software",
                event_type=event_type,
                severity=severity,
                message=f"Package {package} {action}: {version}",
                source="dpkg",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "package_name": package,
                    "action": action,
                    "version": version,
                    "package_manager": "dpkg"
                }
            )

        except Exception as e:
            print(f"Error parsing dpkg line: {e}")
            return None

    def _parse_apt_history_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse apt history.log line.

        Format:
        Start-Date: 2025-11-16  10:30:00
        Commandline: apt install nginx
        Install: nginx:amd64 (1.18.0-1ubuntu1)
        """
        # This file has multi-line entries, so we parse key-value pairs
        # For simplicity, we'll extract Install/Upgrade/Remove lines

        if line.startswith('Install:'):
            action = 'install'
            event_type = 'software_installed'
        elif line.startswith('Upgrade:'):
            action = 'upgrade'
            event_type = 'software_updated'
        elif line.startswith('Remove:'):
            action = 'remove'
            event_type = 'software_removed'
        else:
            return None

        try:
            # Extract package info
            # Format: "Install: nginx:amd64 (1.18.0-1ubuntu1), ..."
            packages_str = line.split(':', 1)[1].strip()

            # Just parse first package for simplicity
            pkg_match = re.search(r'([a-zA-Z0-9\-\.\_]+)(?:\:[\w]+)?\s*\(([^\)]+)\)', packages_str)
            if not pkg_match:
                return None

            package = pkg_match.group(1)
            version = pkg_match.group(2)

            return create_event(
                category="software",
                event_type=event_type,
                severity="info",
                message=f"Package {package} {action}: {version}",
                source="apt",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=datetime.utcnow(),  # APT history doesn't have inline timestamps
                data={
                    "package_name": package,
                    "action": action,
                    "version": version,
                    "package_manager": "apt"
                }
            )

        except Exception as e:
            print(f"Error parsing apt line: {e}")
            return None

    def _parse_yum_dnf_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse yum.log or dnf.log line.

        Format: Nov 16 10:30:00 Installed: nginx-1.18.0-1.el8.x86_64
        """
        try:
            # Extract action
            if 'Installed:' in line:
                action = 'install'
                event_type = 'software_installed'
            elif 'Updated:' in line or 'Upgrade:' in line:
                action = 'update'
                event_type = 'software_updated'
            elif 'Erased:' in line or 'Removed:' in line:
                action = 'remove'
                event_type = 'software_removed'
            else:
                return None

            # Parse timestamp (first 15 chars for syslog format)
            timestamp_str = line[:15]
            year = datetime.utcnow().year
            timestamp = datetime.strptime(f"{year} {timestamp_str}", "%Y %b %d %H:%M:%S")

            # Extract package name and version
            # Format: "Installed: nginx-1.18.0-1.el8.x86_64"
            pkg_match = re.search(r'(Installed|Updated|Erased|Removed):\s+([^\s]+)', line)
            if not pkg_match:
                return None

            full_package = pkg_match.group(2)

            # Split package name and version
            # Format: package-version-release.arch
            pkg_parts = full_package.rsplit('.', 1)[0]  # Remove arch
            name_version = pkg_parts.rsplit('-', 2)  # Split name from version-release

            package = name_version[0] if name_version else full_package
            version = '-'.join(name_version[1:]) if len(name_version) > 1 else "unknown"

            return create_event(
                category="software",
                event_type=event_type,
                severity="info",
                message=f"Package {package} {action}: {version}",
                source="yum/dnf",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "package_name": package,
                    "action": action,
                    "version": version,
                    "package_manager": "yum/dnf"
                }
            )

        except Exception as e:
            print(f"Error parsing yum/dnf line: {e}")
            return None

    def _parse_pacman_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse pacman.log line.

        Format: [2025-11-16T10:30:00+0000] [ALPM] installed nginx (1.18.0-1)
        """
        try:
            # Extract timestamp
            timestamp_match = re.search(r'\[([\d\-T\+:]+)\]', line)
            if not timestamp_match:
                return None

            timestamp_str = timestamp_match.group(1)
            timestamp = datetime.fromisoformat(timestamp_str.replace('+0000', ''))

            # Determine action
            if 'installed' in line.lower():
                action = 'install'
                event_type = 'software_installed'
            elif 'upgraded' in line.lower():
                action = 'upgrade'
                event_type = 'software_updated'
            elif 'removed' in line.lower():
                action = 'remove'
                event_type = 'software_removed'
            else:
                return None

            # Extract package name and version
            # Format: "installed nginx (1.18.0-1)"
            pkg_match = re.search(r'(?:installed|upgraded|removed)\s+([^\s]+)\s+\(([^\)]+)\)', line)
            if not pkg_match:
                return None

            package = pkg_match.group(1)
            version = pkg_match.group(2)

            return create_event(
                category="software",
                event_type=event_type,
                severity="info",
                message=f"Package {package} {action}: {version}",
                source="pacman",
                os="linux",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "package_name": package,
                    "action": action,
                    "version": version,
                    "package_manager": "pacman"
                }
            )

        except Exception as e:
            print(f"Error parsing pacman line: {e}")
            return None

    def _parse_zypper_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse zypper.log line (openSUSE)."""
        # Zypper log format varies, implement basic parsing
        try:
            if 'installed' in line.lower() or 'removed' in line.lower() or 'updated' in line.lower():
                # Basic parsing - you can enhance this
                return None  # Placeholder for now
        except Exception:
            pass
        return None


def collect_software_events(max_lines: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect software change events.

    Args:
        max_lines: Maximum lines to process per log file

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_software_events()
        print(f"Found {len(events)} software changes")
    """
    collector = LinuxSoftwareCollector()
    return collector.collect_events(max_lines)


if __name__ == "__main__":
    """Test the software collector."""
    import json

    print("=" * 70)
    print("Software Changes Event Collector - Test Mode")
    print("=" * 70)

    collector = LinuxSoftwareCollector()
    print(f"\nDetected package manager: {collector.package_manager}")
    print(f"Log files: {collector.log_files}")

    print("\nCollecting software change events...")
    events = collect_software_events(max_lines=100)

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

        # Most common packages
        print("\nMost frequently changed packages:")
        packages = {}
        for event in events:
            pkg = event.get('data', {}).get('package_name', 'unknown')
            packages[pkg] = packages.get(pkg, 0) + 1

        for pkg, count in sorted(packages.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {pkg}: {count} changes")

    else:
        print("No software change events found.")
        print(f"Package manager logs may be empty or inaccessible.")
        print("Try: sudo python collectors/linux/software.py")

    print("\n" + "=" * 70)
