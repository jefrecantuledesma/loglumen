"""
Windows Software Installation Event Collector

Collects software installation, update, and removal events:
- Software installations via MSI
- Software removals/uninstalls
- Windows Update installations
- Windows Update failures
- Patch installations

Uses PowerShell Get-WinEvent to query Application and Setup logs.

Author: Loglumen Team
"""

import os
import subprocess
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import create_event, get_hostname, get_local_ip


# Event IDs for software-related events
SOFTWARE_EVENT_IDS = {
    # MSI Installer events (Application log)
    1033: "software_installed",  # Product installed successfully
    1034: "software_removed",  # Product removed successfully
    11707: "software_install_success",  # Installation completed successfully
    11708: "software_install_failed",  # Installation failed
    11724: "software_removal_success",  # Removal completed successfully
    # Windows Update events
    19: "windows_update_installed",  # Update installation successful
    20: "windows_update_failed",  # Update installation failed
    43: "windows_update_download_started",  # Update download started
    44: "windows_update_download_completed",  # Update download completed
}


class WindowsSoftwareCollector:
    """
    Collects software installation and update events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 168, max_events: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect software installation events from Windows Application and Setup logs.

        Note: Default hours is 168 (7 days) because software events are less frequent.

        Args:
            hours: How many hours back to search (default 168 = 7 days)
            max_events: Maximum number of events to collect

        Returns:
            list: List of event dictionaries
        """
        events = []

        try:
            # Get MSI Installer events from Application log
            msi_events = self._query_msi_events(hours, max_events // 3)
            events.extend(msi_events)

            # Get Windows Update events
            update_events = self._query_windows_update_events(hours, max_events // 3)
            events.extend(update_events)

            # Get Setup events
            setup_events = self._query_setup_events(hours, max_events // 3)
            events.extend(setup_events)

        except Exception as e:
            print(f"Error collecting software events: {e}")

        return events

    def _query_msi_events(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for MSI Installer events from Application log."""
        parsed_events = []

        # MSI Installer event IDs
        msi_event_ids = [1033, 1034, 11707, 11708, 11724]
        event_id_filter = ",".join(str(eid) for eid in msi_event_ids)

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='Application'
            ProviderName='MsiInstaller'
            ID={event_id_filter}
            StartTime=$StartTime
        }} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
        Select-Object -Property TimeCreated, Id, LevelDisplayName, Message |
        ConvertTo-Json -Compress
        """

        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    output = result.stdout.strip()
                    if output.startswith('['):
                        win_events = json.loads(output)
                    else:
                        win_events = [json.loads(output)]

                    for win_event in win_events:
                        event = self._parse_msi_event(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for MSI events")
        except Exception as e:
            print(f"Error querying MSI events: {e}")

        return parsed_events

    def _query_windows_update_events(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for Windows Update events."""
        parsed_events = []

        # Try to get Windows Update events from the WindowsUpdateClient provider
        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='System'
            ProviderName='Microsoft-Windows-WindowsUpdateClient'
            StartTime=$StartTime
        }} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
        Where-Object {{ $_.Id -in @(19,20,43,44) }} |
        Select-Object -Property TimeCreated, Id, LevelDisplayName, Message |
        ConvertTo-Json -Compress
        """

        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    output = result.stdout.strip()
                    if output.startswith('['):
                        win_events = json.loads(output)
                    else:
                        win_events = [json.loads(output)]

                    for win_event in win_events:
                        event = self._parse_windows_update_event(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for Windows Update events")
        except Exception as e:
            print(f"Error querying Windows Update events: {e}")

        return parsed_events

    def _query_setup_events(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for Setup log events (major installations/updates)."""
        parsed_events = []

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='Setup'
            StartTime=$StartTime
        }} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
        Select-Object -Property TimeCreated, Id, LevelDisplayName, Message, ProviderName |
        ConvertTo-Json -Compress
        """

        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    output = result.stdout.strip()
                    if output.startswith('['):
                        win_events = json.loads(output)
                    else:
                        win_events = [json.loads(output)]

                    for win_event in win_events:
                        event = self._parse_setup_event(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for Setup events")
        except Exception as e:
            print(f"Error querying Setup events: {e}")

        return parsed_events

    def _parse_msi_event(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse an MSI Installer event."""
        try:
            event_id = win_event.get('Id', 0)
            event_type = SOFTWARE_EVENT_IDS.get(event_id, "software_change")
            message_text = win_event.get('Message', '')

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Extract product name from message
            # Common patterns:
            # "Windows Installer installed the product. Product Name: <name>. Product Version: <version>"
            # "Product: <name> -- Installation completed successfully."
            product_match = re.search(r'Product(?:\s+Name)?:\s*([^.]+?)(?:\.|--|\s+Product)', message_text, re.IGNORECASE)
            if not product_match:
                product_match = re.search(r'installed the product\.\s+([^.]+)', message_text, re.IGNORECASE)

            product_name = product_match.group(1).strip() if product_match else "unknown"

            # Extract version if present
            version_match = re.search(r'(?:Product\s+)?Version:\s*([^\s.]+)', message_text, re.IGNORECASE)
            version = version_match.group(1) if version_match else None

            # Determine action
            action_map = {
                1033: "installed",
                1034: "removed",
                11707: "installed",
                11708: "install_failed",
                11724: "removed",
            }
            action = action_map.get(event_id, "changed")

            # Determine severity
            severity = "error" if action == "install_failed" else "info"

            # Build message
            message = f"Software '{product_name}' was {action}"
            if version:
                message += f" (version {version})"

            return create_event(
                category="software",
                event_type=event_type,
                severity=severity,
                message=message,
                source="Application",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "software_name": product_name,
                    "version": version,
                    "action": action,
                    "installer_type": "msi",
                    "full_message": message_text[:300],
                }
            )

        except Exception as e:
            print(f"Error parsing MSI event: {e}")
            return None

    def _parse_windows_update_event(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a Windows Update event."""
        try:
            event_id = win_event.get('Id', 0)
            message_text = win_event.get('Message', '')

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Extract update information
            # Pattern: "Installation Successful: Windows successfully installed the following update: <name>"
            # Or: "Update <KB#> successfully installed"
            kb_match = re.search(r'KB\d+', message_text, re.IGNORECASE)
            kb_number = kb_match.group(0) if kb_match else None

            # Extract update title
            title_match = re.search(r'installed the following update:\s*(.+?)(?:\.|$)', message_text, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'Update\s+(.+?)\s+(?:successfully|failed)', message_text, re.IGNORECASE)

            update_title = title_match.group(1).strip() if title_match else (kb_number or "Windows Update")

            # Determine event type
            event_type_map = {
                19: "windows_update_installed",
                20: "windows_update_failed",
                43: "windows_update_started",
                44: "windows_update_completed",
            }
            event_type = event_type_map.get(event_id, "windows_update")

            # Determine severity
            severity = "error" if event_id == 20 else "info"

            # Build message
            message_map = {
                19: f"Windows Update installed: {update_title}",
                20: f"Windows Update failed: {update_title}",
                43: f"Windows Update download started: {update_title}",
                44: f"Windows Update download completed: {update_title}",
            }
            message = message_map.get(event_id, f"Windows Update: {update_title}")

            return create_event(
                category="software",
                event_type=event_type,
                severity=severity,
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "update_title": update_title,
                    "kb_number": kb_number,
                    "update_type": "windows_update",
                    "full_message": message_text[:300],
                }
            )

        except Exception as e:
            print(f"Error parsing Windows Update event: {e}")
            return None

    def _parse_setup_event(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a Setup log event."""
        try:
            event_id = win_event.get('Id', 0)
            provider = win_event.get('ProviderName', 'unknown')
            message_text = win_event.get('Message', '')
            level = win_event.get('LevelDisplayName', 'Information')

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Skip informational events that aren't useful
            if level == 'Information' and event_id in [2, 4]:
                return None

            # Build message
            first_line = message_text.split('\n')[0][:100]
            message = f"System setup/update event (Event {event_id}): {first_line}"

            # Determine severity
            severity_map = {
                'Error': 'error',
                'Warning': 'warning',
                'Information': 'info',
            }
            severity = severity_map.get(level, 'info')

            return create_event(
                category="software",
                event_type="system_update",
                severity=severity,
                message=message,
                source="Setup",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "provider": provider,
                    "level": level,
                    "full_message": message_text[:300],
                }
            )

        except Exception as e:
            print(f"Error parsing Setup event: {e}")
            return None

    def _parse_timestamp(self, time_created: str) -> datetime:
        """Parse timestamp from PowerShell datetime string."""
        if time_created:
            try:
                return datetime.fromisoformat(time_created.replace('Z', '+00:00'))
            except:
                pass
        return datetime.utcnow()


def collect_software_events(hours: int = 168, max_events: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect Windows software installation events.

    Args:
        hours: Hours to look back (default 168 = 7 days)
        max_events: Maximum number of events to collect

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_software_events(hours=168)
        print(f"Collected {len(events)} software events")
    """
    collector = WindowsSoftwareCollector()
    return collector.collect_events(hours, max_events)


if __name__ == "__main__":
    """Test the Windows software collector."""
    import json

    print("=" * 70)
    print("Windows Software Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting software events from last 7 days...")
    print("(Software events are less frequent, so we search 7 days by default)")

    events = collect_software_events(hours=168, max_events=100)

    print(f"\n[OK] Collected {len(events)} events\n")

    if events:
        print("Sample events (first 5):")
        for i, event in enumerate(events[:5], 1):
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

        # Recent software changes
        print("\nRecent software changes:")
        for event in events[:10]:
            software = event.get('data', {}).get('software_name') or event.get('data', {}).get('update_title', 'unknown')
            action = event.get('data', {}).get('action', event.get('event_type', ''))
            print(f"  {software}: {action}")

    else:
        print("No software installation events found in the last 7 days.")

    print("\n" + "=" * 70)
