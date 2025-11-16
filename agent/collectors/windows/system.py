"""
Windows System Crash Event Collector

Collects critical system events:
- Blue Screen of Death (BSOD) / BugCheck (Event ID 1001)
- Unexpected shutdowns (Event ID 6008, 41)
- System crashes and critical errors
- Kernel errors
- Hardware errors

Uses PowerShell Get-WinEvent to query the System event log.

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


# Event IDs for system crash events
SYSTEM_EVENT_IDS = {
    1001: "bugcheck",  # BugCheck / BSOD
    41: "unexpected_shutdown",  # Kernel-Power unexpected shutdown
    6008: "unexpected_shutdown",  # EventLog service started after improper shutdown
    1074: "system_shutdown",  # System shutdown initiated
    6005: "event_log_started",  # Event Log service was started
    6006: "event_log_stopped",  # Event Log service was stopped
    6009: "os_version_at_boot",  # OS version info at startup
}


class WindowsSystemCollector:
    """
    Collects system crash and critical failure events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect system crash events from Windows System log.

        Args:
            hours: How many hours back to search
            max_events: Maximum number of events to collect

        Returns:
            list: List of event dictionaries
        """
        events = []

        try:
            # Get specific system events
            specific_events = self._query_specific_events(hours, max_events)
            events.extend(specific_events)

            # Get critical errors
            critical_events = self._query_critical_errors(hours, max_events // 2)
            events.extend(critical_events)

        except Exception as e:
            print(f"Error collecting system events: {e}")

        return events

    def _query_specific_events(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for specific system event IDs."""
        parsed_events = []

        # Query for specific event IDs
        event_ids = list(SYSTEM_EVENT_IDS.keys())
        event_id_filter = ",".join(str(eid) for eid in event_ids)

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='System'
            ID={event_id_filter}
            StartTime=$StartTime
        }} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
        Select-Object -Property TimeCreated, Id, LevelDisplayName, Message, @{{Name='EventData';Expression={{
            $xml = [xml]$_.ToXml()
            $data = @{{}}
            foreach ($item in $xml.Event.EventData.Data) {{
                if ($item.Name) {{
                    $data[$item.Name] = $item.'#text'
                }}
            }}
            $data | ConvertTo-Json -Compress
        }}}} |
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
                        event = self._parse_event(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for System log")
        except Exception as e:
            print(f"Error querying specific system events: {e}")

        return parsed_events

    def _query_critical_errors(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for critical level errors in System log."""
        parsed_events = []

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='System'
            Level=1
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
                        event = self._parse_critical_error(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for critical errors")
        except Exception as e:
            print(f"Error querying critical errors: {e}")

        return parsed_events

    def _parse_event(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a Windows system event into our standardized format.

        Args:
            win_event: Event dictionary from PowerShell

        Returns:
            dict: Standardized event dictionary or None
        """
        try:
            event_id = win_event.get('Id', 0)
            event_type = SYSTEM_EVENT_IDS.get(event_id, "unknown")

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Parse event data
            event_data = {}
            if 'EventData' in win_event and win_event['EventData']:
                try:
                    event_data = json.loads(win_event['EventData'])
                except:
                    pass

            # Parse based on event ID
            if event_id == 1001:  # BugCheck/BSOD
                return self._parse_bugcheck(win_event, event_data, timestamp)
            elif event_id == 41:  # Kernel-Power unexpected shutdown
                return self._parse_kernel_power_shutdown(win_event, event_data, timestamp)
            elif event_id == 6008:  # Unexpected shutdown
                return self._parse_unexpected_shutdown(win_event, timestamp)
            elif event_id == 1074:  # System shutdown
                return self._parse_system_shutdown(win_event, event_data, timestamp)
            elif event_id in [6005, 6006]:  # Event log service started/stopped
                return self._parse_event_log_service(event_id, win_event, timestamp)

        except Exception as e:
            print(f"Error parsing system event: {e}")

        return None

    def _parse_bugcheck(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse BugCheck (Blue Screen of Death) event."""
        try:
            message_text = win_event.get('Message', '')

            # Extract bugcheck code from message
            bugcheck_match = re.search(r'0x([0-9a-fA-F]+)', message_text)
            bugcheck_code = bugcheck_match.group(0) if bugcheck_match else "unknown"

            # Try to extract bugcheck parameters
            params = re.findall(r'0x[0-9a-fA-F]+', message_text)

            message = f"System experienced Blue Screen (BugCheck: {bugcheck_code})"

            return create_event(
                category="system",
                event_type="bugcheck",
                severity="critical",
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 1001,
                    "bugcheck_code": bugcheck_code,
                    "parameters": params[:4] if len(params) > 1 else [],
                    "full_message": message_text[:200],
                }
            )

        except Exception as e:
            print(f"Error parsing bugcheck: {e}")
            return None

    def _parse_kernel_power_shutdown(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse Kernel-Power unexpected shutdown event."""
        try:
            message_text = win_event.get('Message', '')

            message = "System rebooted without cleanly shutting down first (unexpected shutdown)"

            return create_event(
                category="system",
                event_type="unexpected_shutdown",
                severity="error",
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 41,
                    "provider": "Kernel-Power",
                    "reason": "unexpected_power_loss",
                    "full_message": message_text[:200],
                }
            )

        except Exception as e:
            print(f"Error parsing kernel power shutdown: {e}")
            return None

    def _parse_unexpected_shutdown(
        self,
        win_event: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse unexpected shutdown event (6008)."""
        try:
            message_text = win_event.get('Message', '')

            # Extract time information from message if available
            time_match = re.search(r'(\d{1,2}:\d{2}:\d{2}\s*[AP]M)', message_text)
            shutdown_time = time_match.group(1) if time_match else ""

            message = "System was not shut down properly"
            if shutdown_time:
                message += f" (last known good time: {shutdown_time})"

            return create_event(
                category="system",
                event_type="unexpected_shutdown",
                severity="warning",
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 6008,
                    "provider": "EventLog",
                    "shutdown_time": shutdown_time,
                    "full_message": message_text[:200],
                }
            )

        except Exception as e:
            print(f"Error parsing unexpected shutdown: {e}")
            return None

    def _parse_system_shutdown(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse system shutdown event (1074)."""
        try:
            message_text = win_event.get('Message', '')

            # Extract user, process, and reason from message
            user_match = re.search(r'user\s+([^\s]+)', message_text, re.IGNORECASE)
            user = user_match.group(1) if user_match else "unknown"

            process_match = re.search(r'process\s+([^\s]+)', message_text, re.IGNORECASE)
            process = process_match.group(1) if process_match else "unknown"

            # Determine if planned or unplanned
            reason_match = re.search(r'reason:\s+(.+?)(?:\.|$)', message_text, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else "unknown"

            # Only report unplanned shutdowns or specific shutdown types
            if "planned" in reason.lower() and "un" not in reason.lower():
                return None  # Skip planned shutdowns

            message = f"System shutdown initiated by {user} ({process})"
            if reason:
                message += f": {reason}"

            return create_event(
                category="system",
                event_type="system_shutdown",
                severity="info",
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 1074,
                    "user": user,
                    "process": process,
                    "reason": reason,
                    "full_message": message_text[:200],
                }
            )

        except Exception as e:
            print(f"Error parsing system shutdown: {e}")
            return None

    def _parse_event_log_service(
        self,
        event_id: int,
        win_event: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse Event Log service start/stop events."""
        try:
            if event_id == 6005:
                message = "Event Log service started (system boot detected)"
                event_type = "system_boot"
            else:  # 6006
                message = "Event Log service stopped (system shutdown)"
                event_type = "system_shutdown"

            return create_event(
                category="system",
                event_type=event_type,
                severity="info",
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "service": "EventLog",
                }
            )

        except Exception as e:
            print(f"Error parsing event log service: {e}")
            return None

    def _parse_critical_error(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse critical level error event."""
        try:
            event_id = win_event.get('Id', 0)
            provider = win_event.get('ProviderName', 'unknown')
            message_text = win_event.get('Message', '')

            # Skip if we already handled this event ID
            if event_id in SYSTEM_EVENT_IDS:
                return None

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Truncate message for summary
            message = f"Critical system error from {provider} (Event {event_id})"
            if message_text:
                # Get first line or first 100 chars of message
                first_line = message_text.split('\n')[0][:100]
                message += f": {first_line}"

            return create_event(
                category="system",
                event_type="critical_error",
                severity="critical",
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "provider": provider,
                    "full_message": message_text[:500],
                }
            )

        except Exception as e:
            print(f"Error parsing critical error: {e}")
            return None

    def _parse_timestamp(self, time_created: str) -> datetime:
        """Parse timestamp from PowerShell datetime string."""
        if time_created:
            try:
                return datetime.fromisoformat(time_created.replace('Z', '+00:00'))
            except:
                pass
        return datetime.utcnow()


def collect_system_events(hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect Windows system crash events.

    Args:
        hours: Hours to look back
        max_events: Maximum number of events to collect

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_system_events(hours=24)
        print(f"Collected {len(events)} system events")
    """
    collector = WindowsSystemCollector()
    return collector.collect_events(hours, max_events)


if __name__ == "__main__":
    """Test the Windows system collector."""
    import json

    print("=" * 70)
    print("Windows System Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting system events from last 24 hours...")

    events = collect_system_events(hours=24, max_events=100)

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

        # Summary by severity
        print("\nSummary by severity:")
        severities = {}
        for event in events:
            sev = event['severity']
            severities[sev] = severities.get(sev, 0) + 1

        for sev, count in sorted(severities.items()):
            print(f"  {sev}: {count}")

    else:
        print("No system events found (this is good - means no crashes!).")

    print("\n" + "=" * 70)
