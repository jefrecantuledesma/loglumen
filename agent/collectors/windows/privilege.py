"""
Windows Privilege Escalation Event Collector

Collects privilege escalation and account modification events:
- User account creation, modification, deletion (4720, 4722, 4726, 4738)
- Group membership changes (4728, 4729, 4732, 4733, 4756, 4757)
- Special privileges assigned (4672)
- Password changes (4723, 4724)
- Account enable/disable (4722, 4725)

Uses PowerShell Get-WinEvent to query the Security event log.

Author: Loglumen Team
"""

import os
import subprocess
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import create_event, get_hostname, get_local_ip


# Event IDs for privilege/account events
PRIVILEGE_EVENT_IDS = {
    4720: "user_created",
    4722: "user_enabled",
    4723: "password_change_attempt",
    4724: "password_reset_attempt",
    4725: "user_disabled",
    4726: "user_deleted",
    4738: "user_modified",
    4740: "user_locked_out",
    4767: "user_unlocked",
    # Group membership changes
    4728: "user_added_to_global_group",
    4729: "user_removed_from_global_group",
    4732: "user_added_to_local_group",
    4733: "user_removed_from_local_group",
    4756: "user_added_to_universal_group",
    4757: "user_removed_from_universal_group",
    # Privilege assignment
    4672: "special_privileges_assigned",
}


class WindowsPrivilegeCollector:
    """
    Collects privilege escalation and account modification events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect privilege escalation events from Windows Security log.

        Args:
            hours: How many hours back to search
            max_events: Maximum number of events to collect

        Returns:
            list: List of event dictionaries
        """
        events = []

        # Query Security log for privilege events
        event_ids = list(PRIVILEGE_EVENT_IDS.keys())

        try:
            # Get events from Security log
            win_events = self._query_event_log(
                log_name="Security",
                event_ids=event_ids,
                hours=hours,
                max_events=max_events
            )

            # Parse each event
            for win_event in win_events:
                event = self._parse_event(win_event)
                if event:
                    events.append(event)

        except Exception as e:
            print(f"Error collecting privilege events: {e}")

        return events

    def _query_event_log(
        self,
        log_name: str,
        event_ids: List[int],
        hours: int,
        max_events: int
    ) -> List[Dict[str, Any]]:
        """
        Query Windows Event Log using PowerShell.

        Args:
            log_name: Name of the event log
            event_ids: List of event IDs to query
            hours: Hours to look back
            max_events: Maximum number of events

        Returns:
            list: List of event dictionaries from PowerShell
        """
        events = []

        # Build filter for event IDs
        event_id_filter = ",".join(str(eid) for eid in event_ids)

        # PowerShell command to get events
        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='{log_name}'
            ID={event_id_filter}
            StartTime=$StartTime
        }} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
        Select-Object -Property TimeCreated, Id, LevelDisplayName, Message, @{{Name='EventData';Expression={{
            $xml = [xml]$_.ToXml()
            $data = @{{}}
            foreach ($item in $xml.Event.EventData.Data) {{
                $data[$item.Name] = $item.'#text'
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
                        events = json.loads(output)
                    else:
                        events = [json.loads(output)]
                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print(f"PowerShell query timed out for {log_name}")
        except Exception as e:
            print(f"Error querying event log: {e}")

        return events

    def _parse_event(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a Windows event into our standardized format.

        Args:
            win_event: Event dictionary from PowerShell

        Returns:
            dict: Standardized event dictionary or None
        """
        try:
            event_id = win_event.get('Id', 0)
            event_type = PRIVILEGE_EVENT_IDS.get(event_id, "unknown")

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            if time_created:
                try:
                    timestamp = datetime.fromisoformat(time_created.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()

            # Parse event data
            event_data = {}
            if 'EventData' in win_event and win_event['EventData']:
                try:
                    event_data = json.loads(win_event['EventData'])
                except:
                    pass

            # Parse based on event ID category
            if event_id in [4720, 4722, 4725, 4726, 4738]:  # User account changes
                return self._parse_user_account_change(event_id, win_event, event_data, timestamp)
            elif event_id in [4723, 4724]:  # Password changes
                return self._parse_password_change(event_id, win_event, event_data, timestamp)
            elif event_id in [4728, 4729, 4732, 4733, 4756, 4757]:  # Group changes
                return self._parse_group_change(event_id, win_event, event_data, timestamp)
            elif event_id == 4672:  # Special privileges
                return self._parse_special_privileges(win_event, event_data, timestamp)

        except Exception as e:
            print(f"Error parsing event: {e}")

        return None

    def _parse_user_account_change(
        self,
        event_id: int,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse user account creation/modification/deletion events."""
        try:
            target_username = event_data.get('TargetUserName', 'unknown')
            target_domain = event_data.get('TargetDomainName', '')
            subject_username = event_data.get('SubjectUserName', 'unknown')
            subject_domain = event_data.get('SubjectDomainName', '')

            # Determine event type and message
            event_type_name = PRIVILEGE_EVENT_IDS.get(event_id, "unknown")

            messages = {
                4720: f"User account {target_domain}\\{target_username} was created by {subject_domain}\\{subject_username}",
                4722: f"User account {target_domain}\\{target_username} was enabled by {subject_domain}\\{subject_username}",
                4725: f"User account {target_domain}\\{target_username} was disabled by {subject_domain}\\{subject_username}",
                4726: f"User account {target_domain}\\{target_username} was deleted by {subject_domain}\\{subject_username}",
                4738: f"User account {target_domain}\\{target_username} was modified by {subject_domain}\\{subject_username}",
            }

            message = messages.get(event_id, f"User account {target_domain}\\{target_username} was changed")

            # Determine severity
            severity = "warning" if event_id in [4720, 4726] else "info"

            return create_event(
                category="privilege",
                event_type=event_type_name,
                severity=severity,
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "target_username": target_username,
                    "target_domain": target_domain,
                    "target_full_username": f"{target_domain}\\{target_username}" if target_domain else target_username,
                    "subject_username": subject_username,
                    "subject_domain": subject_domain,
                    "subject_full_username": f"{subject_domain}\\{subject_username}" if subject_domain else subject_username,
                    "sam_account_name": event_data.get('SamAccountName', ''),
                    "display_name": event_data.get('DisplayName', ''),
                }
            )

        except Exception as e:
            print(f"Error parsing user account change: {e}")
            return None

    def _parse_password_change(
        self,
        event_id: int,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse password change/reset events."""
        try:
            target_username = event_data.get('TargetUserName', 'unknown')
            target_domain = event_data.get('TargetDomainName', '')
            subject_username = event_data.get('SubjectUserName', 'unknown')
            subject_domain = event_data.get('SubjectDomainName', '')

            if event_id == 4723:
                message = f"User {target_domain}\\{target_username} changed their password"
                event_type = "password_changed"
            else:  # 4724
                message = f"Password for {target_domain}\\{target_username} was reset by {subject_domain}\\{subject_username}"
                event_type = "password_reset"

            return create_event(
                category="privilege",
                event_type=event_type,
                severity="info",
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "target_username": target_username,
                    "target_domain": target_domain,
                    "target_full_username": f"{target_domain}\\{target_username}" if target_domain else target_username,
                    "subject_username": subject_username,
                    "subject_domain": subject_domain,
                    "subject_full_username": f"{subject_domain}\\{subject_username}" if subject_domain else subject_username,
                }
            )

        except Exception as e:
            print(f"Error parsing password change: {e}")
            return None

    def _parse_group_change(
        self,
        event_id: int,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse group membership change events."""
        try:
            member_username = event_data.get('MemberName', event_data.get('TargetUserName', 'unknown'))
            member_sid = event_data.get('MemberSid', '')
            group_name = event_data.get('TargetUserName', 'unknown')
            group_domain = event_data.get('TargetDomainName', '')
            subject_username = event_data.get('SubjectUserName', 'unknown')
            subject_domain = event_data.get('SubjectDomainName', '')

            # Determine action
            action = "added to" if event_id in [4728, 4732, 4756] else "removed from"

            # Determine group type
            group_types = {
                4728: "global security group",
                4729: "global security group",
                4732: "local security group",
                4733: "local security group",
                4756: "universal security group",
                4757: "universal security group",
            }
            group_type = group_types.get(event_id, "security group")

            message = f"User {member_username} was {action} {group_type} {group_domain}\\{group_name} by {subject_domain}\\{subject_username}"

            # Higher severity for additions to admin groups
            severity = "warning" if "admin" in group_name.lower() and action == "added to" else "info"

            event_type_name = PRIVILEGE_EVENT_IDS.get(event_id, "unknown")

            return create_event(
                category="privilege",
                event_type=event_type_name,
                severity=severity,
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "member_name": member_username,
                    "member_sid": member_sid,
                    "group_name": group_name,
                    "group_domain": group_domain,
                    "group_full_name": f"{group_domain}\\{group_name}" if group_domain else group_name,
                    "action": action,
                    "group_type": group_type,
                    "subject_username": subject_username,
                    "subject_domain": subject_domain,
                    "subject_full_username": f"{subject_domain}\\{subject_username}" if subject_domain else subject_username,
                }
            )

        except Exception as e:
            print(f"Error parsing group change: {e}")
            return None

    def _parse_special_privileges(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse special privileges assigned event."""
        try:
            subject_username = event_data.get('SubjectUserName', 'unknown')
            subject_domain = event_data.get('SubjectDomainName', '')
            privileges = event_data.get('PrivilegeList', '')

            # Skip system accounts and common service accounts
            if subject_username.endswith('$') or subject_username in ['SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE']:
                return None

            # Skip if no special privileges (some events have empty privilege list)
            if not privileges or privileges.strip() == '-':
                return None

            message = f"Special privileges assigned to {subject_domain}\\{subject_username}: {privileges}"

            return create_event(
                category="privilege",
                event_type="special_privileges_assigned",
                severity="info",
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 4672,
                    "username": subject_username,
                    "domain": subject_domain,
                    "full_username": f"{subject_domain}\\{subject_username}" if subject_domain else subject_username,
                    "privileges": privileges,
                }
            )

        except Exception as e:
            print(f"Error parsing special privileges: {e}")
            return None


def collect_privilege_events(hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect Windows privilege escalation events.

    Args:
        hours: Hours to look back
        max_events: Maximum number of events to collect

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_privilege_events(hours=24)
        print(f"Collected {len(events)} privilege events")
    """
    collector = WindowsPrivilegeCollector()
    return collector.collect_events(hours, max_events)


if __name__ == "__main__":
    """Test the Windows privilege collector."""
    import json

    print("=" * 70)
    print("Windows Privilege Escalation Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting privilege escalation events from last 24 hours...")
    print("(This requires administrator privileges)")

    events = collect_privilege_events(hours=24, max_events=100)

    print(f"\n[OK] Collected {len(events)} events\n")

    if events:
        print("Sample events (first 3):")
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
        print("No privilege escalation events found.")
        print("Note: This collector requires administrator privileges.")
        print("Try running as administrator.")

    print("\n" + "=" * 70)
