"""
Windows Authentication Event Collector

Collects authentication events from Windows Security log:
- Successful logins (Event ID 4624)
- Failed logins (Event ID 4625)
- Account lockouts (Event ID 4740)
- Logoffs (Event ID 4634)
- Explicit credential usage (Event ID 4648)

Uses PowerShell Get-WinEvent to query the Security event log.

Author: Loglumen Team
"""

import os
import re
import subprocess
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import create_event, get_hostname, get_local_ip


# Event IDs for authentication events
AUTH_EVENT_IDS = {
    4624: "login_success",
    4625: "login_failed",
    4634: "logoff",
    4647: "user_initiated_logoff",
    4648: "explicit_credentials",
    4740: "account_locked",
    4767: "account_unlocked",
}

# Logon types (for Event ID 4624)
LOGON_TYPES = {
    0: "System",
    2: "Interactive",
    3: "Network",
    4: "Batch",
    5: "Service",
    7: "Unlock",
    8: "NetworkCleartext",
    9: "NewCredentials",
    10: "RemoteInteractive",  # RDP
    11: "CachedInteractive",
}


class WindowsAuthCollector:
    """
    Collects authentication events from Windows Security log.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect authentication events from Windows Security log.

        Args:
            hours: How many hours back to search
            max_events: Maximum number of events to collect

        Returns:
            list: List of event dictionaries
        """
        events = []

        # Query Security log for authentication events
        event_ids = list(AUTH_EVENT_IDS.keys())

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
            print(f"Error collecting auth events: {e}")

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
            log_name: Name of the event log (e.g., "Security", "System")
            event_ids: List of event IDs to query
            hours: Hours to look back
            max_events: Maximum number of events to return

        Returns:
            list: List of event dictionaries from PowerShell
        """
        events = []

        # Build filter for event IDs
        event_id_filter = ",".join(str(eid) for eid in event_ids)

        # PowerShell command to get events
        # Using Get-WinEvent with FilterHashtable for better performance
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
            # Run PowerShell command
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                # Parse JSON output
                try:
                    # PowerShell returns single object or array depending on count
                    output = result.stdout.strip()
                    if output.startswith('['):
                        events = json.loads(output)
                    else:
                        events = [json.loads(output)]
                except json.JSONDecodeError as e:
                    print(f"Error parsing PowerShell JSON output: {e}")
                    # Fallback: try to parse as individual JSON objects per line
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            try:
                                events.append(json.loads(line))
                            except:
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
            event_type = AUTH_EVENT_IDS.get(event_id, "unknown")

            # Parse timestamp
            time_created = win_event.get('TimeCreated', '')
            if time_created:
                try:
                    # Parse PowerShell datetime format
                    timestamp = datetime.fromisoformat(time_created.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()

            # Parse event data (JSON string from PowerShell)
            event_data = {}
            if 'EventData' in win_event and win_event['EventData']:
                try:
                    event_data = json.loads(win_event['EventData'])
                except:
                    pass

            # Parse based on event ID
            if event_id == 4624:  # Successful login
                return self._parse_login_success(win_event, event_data, timestamp)
            elif event_id == 4625:  # Failed login
                return self._parse_login_failure(win_event, event_data, timestamp)
            elif event_id == 4634 or event_id == 4647:  # Logoff
                return self._parse_logoff(win_event, event_data, timestamp)
            elif event_id == 4648:  # Explicit credentials
                return self._parse_explicit_credentials(win_event, event_data, timestamp)
            elif event_id == 4740:  # Account lockout
                return self._parse_account_lockout(win_event, event_data, timestamp)
            elif event_id == 4767:  # Account unlocked
                return self._parse_account_unlock(win_event, event_data, timestamp)

        except Exception as e:
            print(f"Error parsing event: {e}")

        return None

    def _parse_login_success(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse successful login event (4624)."""
        try:
            username = event_data.get('TargetUserName', 'unknown')
            domain = event_data.get('TargetDomainName', '')
            logon_type = int(event_data.get('LogonType', 0))
            logon_type_name = LOGON_TYPES.get(logon_type, f"Type{logon_type}")
            workstation = event_data.get('WorkstationName', '')
            source_ip = event_data.get('IpAddress', '')

            # Skip system and service account logins for noise reduction
            if username.endswith('$') or username in ['SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE']:
                return None

            # Determine severity based on logon type
            severity = "info"
            if logon_type == 10:  # RDP
                severity = "warning"
            elif logon_type in [3, 8]:  # Network/ClearText
                severity = "info"

            # Build message
            if source_ip and source_ip != '-' and source_ip != '127.0.0.1':
                message = f"User {domain}\\{username} logged in via {logon_type_name} from {source_ip}"
            else:
                message = f"User {domain}\\{username} logged in via {logon_type_name}"

            return create_event(
                category="auth",
                event_type="login_success",
                severity=severity,
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 4624,
                    "username": username,
                    "domain": domain,
                    "full_username": f"{domain}\\{username}" if domain else username,
                    "logon_type": logon_type,
                    "logon_type_name": logon_type_name,
                    "workstation": workstation,
                    "source_ip": source_ip,
                    "logon_id": event_data.get('TargetLogonId', ''),
                    "process_name": event_data.get('ProcessName', ''),
                }
            )

        except Exception as e:
            print(f"Error parsing login success: {e}")
            return None

    def _parse_login_failure(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse failed login event (4625)."""
        try:
            username = event_data.get('TargetUserName', 'unknown')
            domain = event_data.get('TargetDomainName', '')
            logon_type = int(event_data.get('LogonType', 0))
            logon_type_name = LOGON_TYPES.get(logon_type, f"Type{logon_type}")
            workstation = event_data.get('WorkstationName', '')
            source_ip = event_data.get('IpAddress', '')
            failure_reason = event_data.get('FailureReason', '')
            status = event_data.get('Status', '')
            sub_status = event_data.get('SubStatus', '')

            # Build message
            if source_ip and source_ip != '-':
                message = f"Failed login for {domain}\\{username} from {source_ip} ({logon_type_name})"
            else:
                message = f"Failed login for {domain}\\{username} ({logon_type_name})"

            return create_event(
                category="auth",
                event_type="login_failed",
                severity="warning",
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 4625,
                    "username": username,
                    "domain": domain,
                    "full_username": f"{domain}\\{username}" if domain else username,
                    "logon_type": logon_type,
                    "logon_type_name": logon_type_name,
                    "workstation": workstation,
                    "source_ip": source_ip,
                    "failure_reason": failure_reason,
                    "status": status,
                    "sub_status": sub_status,
                }
            )

        except Exception as e:
            print(f"Error parsing login failure: {e}")
            return None

    def _parse_logoff(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse logoff event (4634, 4647)."""
        try:
            username = event_data.get('TargetUserName', 'unknown')
            domain = event_data.get('TargetDomainName', '')
            logon_type = int(event_data.get('LogonType', 0))
            logon_type_name = LOGON_TYPES.get(logon_type, f"Type{logon_type}")

            # Skip system accounts
            if username.endswith('$') or username in ['SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE']:
                return None

            message = f"User {domain}\\{username} logged off ({logon_type_name})"

            return create_event(
                category="auth",
                event_type="logoff",
                severity="info",
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": win_event.get('Id', 0),
                    "username": username,
                    "domain": domain,
                    "full_username": f"{domain}\\{username}" if domain else username,
                    "logon_type": logon_type,
                    "logon_type_name": logon_type_name,
                    "logon_id": event_data.get('TargetLogonId', ''),
                }
            )

        except Exception as e:
            print(f"Error parsing logoff: {e}")
            return None

    def _parse_explicit_credentials(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse explicit credential usage event (4648)."""
        try:
            subject_username = event_data.get('SubjectUserName', 'unknown')
            subject_domain = event_data.get('SubjectDomainName', '')
            target_username = event_data.get('TargetUserName', 'unknown')
            target_server = event_data.get('TargetServerName', '')
            process = event_data.get('ProcessName', '')

            message = f"User {subject_domain}\\{subject_username} used explicit credentials for {target_username}"

            return create_event(
                category="auth",
                event_type="explicit_credentials",
                severity="info",
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 4648,
                    "subject_username": subject_username,
                    "subject_domain": subject_domain,
                    "target_username": target_username,
                    "target_server": target_server,
                    "process": process,
                }
            )

        except Exception as e:
            print(f"Error parsing explicit credentials: {e}")
            return None

    def _parse_account_lockout(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse account lockout event (4740)."""
        try:
            username = event_data.get('TargetUserName', 'unknown')
            domain = event_data.get('TargetDomainName', '')
            caller_computer = event_data.get('SubjectUserName', '')

            message = f"Account {domain}\\{username} was locked out"

            return create_event(
                category="auth",
                event_type="account_locked",
                severity="warning",
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 4740,
                    "username": username,
                    "domain": domain,
                    "full_username": f"{domain}\\{username}" if domain else username,
                    "caller_computer": caller_computer,
                }
            )

        except Exception as e:
            print(f"Error parsing account lockout: {e}")
            return None

    def _parse_account_unlock(
        self,
        win_event: Dict[str, Any],
        event_data: Dict[str, Any],
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse account unlock event (4767)."""
        try:
            username = event_data.get('TargetUserName', 'unknown')
            domain = event_data.get('TargetDomainName', '')
            subject_username = event_data.get('SubjectUserName', 'unknown')

            message = f"Account {domain}\\{username} was unlocked by {subject_username}"

            return create_event(
                category="auth",
                event_type="account_unlocked",
                severity="info",
                message=message,
                source="Security",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": 4767,
                    "username": username,
                    "domain": domain,
                    "full_username": f"{domain}\\{username}" if domain else username,
                    "unlocked_by": subject_username,
                }
            )

        except Exception as e:
            print(f"Error parsing account unlock: {e}")
            return None


def collect_auth_events(hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect Windows authentication events.

    Args:
        hours: Hours to look back
        max_events: Maximum number of events to collect

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_auth_events(hours=24)
        print(f"Collected {len(events)} auth events")
    """
    collector = WindowsAuthCollector()
    return collector.collect_events(hours, max_events)


if __name__ == "__main__":
    """Test the Windows auth collector."""
    import json

    print("=" * 70)
    print("Windows Authentication Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting authentication events from last 24 hours...")
    print("(This requires administrator privileges)")

    events = collect_auth_events(hours=24, max_events=100)

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

        # Summary by user
        print("\nTop users:")
        users = {}
        for event in events:
            user = event.get('data', {}).get('full_username', 'unknown')
            users[user] = users.get(user, 0) + 1

        for user, count in sorted(users.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {user}: {count} events")

    else:
        print("No authentication events found.")
        print("Note: This collector requires administrator privileges.")
        print("Try running as administrator: py agent\\collectors\\windows\\auth.py")

    print("\n" + "=" * 70)
