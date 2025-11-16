"""
Windows Service Failure Event Collector

Collects service and application failure events:
- Service failures and crashes
- Service start failures
- Service control manager errors
- Application crashes
- Application hangs

Uses PowerShell Get-WinEvent to query System and Application logs.

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


# Event IDs for service-related events
SERVICE_EVENT_IDS = {
    # Service Control Manager events (System log)
    7000: "service_start_failed",  # Service failed to start
    7001: "service_start_failed_dependency",  # Service failed due to dependency
    7009: "service_timeout",  # Timeout starting service
    7022: "service_hung",  # Service hung on starting
    7023: "service_terminated_with_error",  # Service terminated with error
    7024: "service_terminated_with_error",  # Service terminated with service-specific error
    7026: "service_boot_failed",  # Boot-start or system-start driver failed
    7031: "service_terminated_unexpected",  # Service terminated unexpectedly
    7032: "service_recovery_action",  # Service recovery action taken
    7034: "service_terminated_unexpected",  # Service crashed
    # Application crashes (Application log)
    1000: "application_error",  # Application error
    1001: "application_fault",  # Windows Error Reporting fault
    1002: "application_hang",  # Application hang
}


class WindowsServiceCollector:
    """
    Collects service failure and application crash events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect service failure events from Windows System and Application logs.

        Args:
            hours: How many hours back to search
            max_events: Maximum number of events to collect

        Returns:
            list: List of event dictionaries
        """
        events = []

        try:
            # Get service events from System log
            system_events = self._query_service_events(hours, max_events // 2)
            events.extend(system_events)

            # Get application crashes from Application log
            app_events = self._query_application_crashes(hours, max_events // 2)
            events.extend(app_events)

            # Get error-level events from System log
            error_events = self._query_system_errors(hours, max_events // 4)
            events.extend(error_events)

        except Exception as e:
            print(f"Error collecting service events: {e}")

        return events

    def _query_service_events(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for service-related events from System log."""
        parsed_events = []

        # Service Control Manager event IDs
        scm_event_ids = [7000, 7001, 7009, 7022, 7023, 7024, 7026, 7031, 7032, 7034]
        event_id_filter = ",".join(str(eid) for eid in scm_event_ids)

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='System'
            ProviderName='Service Control Manager'
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
                        event = self._parse_service_event(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for service events")
        except Exception as e:
            print(f"Error querying service events: {e}")

        return parsed_events

    def _query_application_crashes(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for application crash events from Application log."""
        parsed_events = []

        # Application error event IDs
        app_event_ids = [1000, 1001, 1002]
        event_id_filter = ",".join(str(eid) for eid in app_event_ids)

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='Application'
            ID={event_id_filter}
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
                        event = self._parse_application_crash(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for application crashes")
        except Exception as e:
            print(f"Error querying application crashes: {e}")

        return parsed_events

    def _query_system_errors(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for general error-level events from System log."""
        parsed_events = []

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='System'
            Level=2
            StartTime=$StartTime
        }} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
        Where-Object {{ $_.ProviderName -notlike 'Service Control Manager' -and $_.Id -notin @(1001,41,6008) }} |
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
                        event = self._parse_system_error(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for system errors")
        except Exception as e:
            print(f"Error querying system errors: {e}")

        return parsed_events

    def _parse_service_event(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a service-related event."""
        try:
            event_id = win_event.get('Id', 0)
            event_type = SERVICE_EVENT_IDS.get(event_id, "service_error")
            message_text = win_event.get('Message', '')

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Extract service name from message
            # Common pattern: "The <ServiceName> service..."
            service_match = re.search(r'The\s+(.+?)\s+service', message_text, re.IGNORECASE)
            if not service_match:
                service_match = re.search(r'service\s+([^\s]+)', message_text, re.IGNORECASE)

            service_name = service_match.group(1) if service_match else "unknown"

            # Extract error code if present
            error_match = re.search(r'error\s+(?:code\s+)?([0-9]+|0x[0-9a-fA-F]+)', message_text, re.IGNORECASE)
            error_code = error_match.group(1) if error_match else None

            # Determine severity
            severity_map = {
                7000: "error",
                7001: "error",
                7009: "error",
                7022: "warning",
                7023: "error",
                7024: "error",
                7026: "error",
                7031: "error",
                7032: "warning",
                7034: "error",
            }
            severity = severity_map.get(event_id, "warning")

            # Build message
            first_line = message_text.split('\n')[0]
            message = f"Service '{service_name}' {event_type.replace('_', ' ')}"
            if error_code:
                message += f" (Error: {error_code})"

            return create_event(
                category="service",
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
                    "service_name": service_name,
                    "error_code": error_code,
                    "full_message": message_text[:300],
                    "provider": "Service Control Manager",
                }
            )

        except Exception as e:
            print(f"Error parsing service event: {e}")
            return None

    def _parse_application_crash(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse an application crash event."""
        try:
            event_id = win_event.get('Id', 0)
            provider = win_event.get('ProviderName', 'unknown')
            message_text = win_event.get('Message', '')

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Extract application name
            # Pattern: "Faulting application name: <app.exe>"
            app_match = re.search(r'(?:Faulting application|Application)(?:\s+name)?:\s+([^\s,]+)', message_text, re.IGNORECASE)
            if not app_match:
                # Try another pattern
                app_match = re.search(r'application\s+([^\s]+\.exe)', message_text, re.IGNORECASE)

            app_name = app_match.group(1) if app_match else "unknown"

            # Extract exception code if present
            exception_match = re.search(r'exception code\s+(0x[0-9a-fA-F]+)', message_text, re.IGNORECASE)
            exception_code = exception_match.group(1) if exception_match else None

            # Extract fault module if present
            module_match = re.search(r'(?:Faulting module|module)\s+(?:name)?:\s+([^\s,]+)', message_text, re.IGNORECASE)
            fault_module = module_match.group(1) if module_match else None

            # Determine event type
            event_type_map = {
                1000: "application_crash",
                1001: "application_fault",
                1002: "application_hang",
            }
            event_type = event_type_map.get(event_id, "application_error")

            # Build message
            message = f"Application '{app_name}' {event_type.replace('_', ' ')}"
            if exception_code:
                message += f" (Exception: {exception_code})"

            return create_event(
                category="service",
                event_type=event_type,
                severity="error",
                message=message,
                source="Application",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "application_name": app_name,
                    "exception_code": exception_code,
                    "fault_module": fault_module,
                    "provider": provider,
                    "full_message": message_text[:300],
                }
            )

        except Exception as e:
            print(f"Error parsing application crash: {e}")
            return None

    def _parse_system_error(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a general system error event."""
        try:
            event_id = win_event.get('Id', 0)
            provider = win_event.get('ProviderName', 'unknown')
            message_text = win_event.get('Message', '')

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            timestamp = self._parse_timestamp(time_created)

            # Skip very common/noisy events
            skip_providers = ['volsnap', 'disk', 'ntfs']
            if any(p in provider.lower() for p in skip_providers):
                return None

            # Build message
            first_line = message_text.split('\n')[0][:100]
            message = f"System error from {provider} (Event {event_id}): {first_line}"

            return create_event(
                category="service",
                event_type="system_service_error",
                severity="warning",
                message=message,
                source="System",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "provider": provider,
                    "full_message": message_text[:300],
                }
            )

        except Exception as e:
            print(f"Error parsing system error: {e}")
            return None

    def _parse_timestamp(self, time_created: str) -> datetime:
        """Parse timestamp from PowerShell datetime string."""
        if time_created:
            try:
                return datetime.fromisoformat(time_created.replace('Z', '+00:00'))
            except:
                pass
        return datetime.utcnow()


def collect_service_events(hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect Windows service failure events.

    Args:
        hours: Hours to look back
        max_events: Maximum number of events to collect

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_service_events(hours=24)
        print(f"Collected {len(events)} service events")
    """
    collector = WindowsServiceCollector()
    return collector.collect_events(hours, max_events)


if __name__ == "__main__":
    """Test the Windows service collector."""
    import json

    print("=" * 70)
    print("Windows Service Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting service events from last 24 hours...")

    events = collect_service_events(hours=24, max_events=100)

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

        # Top services/apps with issues
        print("\nTop services/apps with issues:")
        services = {}
        for event in events:
            svc = event.get('data', {}).get('service_name') or event.get('data', {}).get('application_name', 'unknown')
            services[svc] = services.get(svc, 0) + 1

        for svc, count in sorted(services.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {svc}: {count} events")

    else:
        print("No service failure events found (this is good!).")

    print("\n" + "=" * 70)
