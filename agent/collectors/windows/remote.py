"""
Windows Remote Access Event Collector

Collects remote access and RDP connection events:
- RDP logons (Event ID 4624 with LogonType 10)
- RDP session connections (Event ID 4778)
- RDP session disconnections (Event ID 4779)
- RDP session reconnections (Event ID 4778)
- Remote Desktop Services events (Event ID 1149)
- TerminalServices-LocalSessionManager events (21, 22, 23, 24, 25)

Uses PowerShell Get-WinEvent to query Security and TerminalServices logs.

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


# Logon types
LOGON_TYPE_RDP = 10  # RemoteInteractive (RDP)
LOGON_TYPE_NETWORK = 3  # Network
LOGON_TYPE_UNLOCK = 7  # Unlock

# Terminal Services event IDs
TERMINAL_SERVICES_EVENT_IDS = {
    21: "rdp_session_logon",  # Session logon succeeded
    22: "rdp_shell_start",  # Shell start notification
    23: "rdp_session_logoff",  # Session logoff succeeded
    24: "rdp_session_disconnected",  # Session has been disconnected
    25: "rdp_session_reconnected",  # Session reconnection succeeded
    39: "rdp_session_disconnect_user",  # Session disconnected by user
    40: "rdp_session_disconnect_network",  # Session disconnected from network
}


class WindowsRemoteAccessCollector:
    """
    Collects remote access and RDP connection events.
    """

    def __init__(self):
        """Initialize the collector."""
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()

    def collect_events(self, hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
        """
        Collect remote access events from Windows logs.

        Args:
            hours: How many hours back to search
            max_events: Maximum number of events to collect

        Returns:
            list: List of event dictionaries
        """
        events = []

        try:
            # Get RDP logons from Security log
            rdp_logons = self._query_rdp_logons(hours, max_events // 3)
            events.extend(rdp_logons)

            # Get RDP session events from Security log
            rdp_sessions = self._query_rdp_sessions(hours, max_events // 3)
            events.extend(rdp_sessions)

            # Get Terminal Services events
            ts_events = self._query_terminal_services(hours, max_events // 3)
            events.extend(ts_events)

        except Exception as e:
            print(f"Error collecting remote access events: {e}")

        return events

    def _query_rdp_logons(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for RDP logon events (Event ID 4624 with LogonType 10)."""
        parsed_events = []

        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='Security'
            ID=4624
            StartTime=$StartTime
        }} -MaxEvents {max_events * 2} -ErrorAction SilentlyContinue |
        ForEach-Object {{
            $xml = [xml]$_.ToXml()
            $logonType = $xml.Event.EventData.Data | Where-Object {{ $_.Name -eq 'LogonType' }} | Select-Object -ExpandProperty '#text'
            if ($logonType -eq '10') {{
                $_ | Select-Object -Property TimeCreated, Id, LevelDisplayName, Message, @{{Name='EventData';Expression={{
                    $data = @{{}}
                    foreach ($item in $xml.Event.EventData.Data) {{
                        $data[$item.Name] = $item.'#text'
                    }}
                    $data | ConvertTo-Json -Compress
                }}}}
            }}
        }} |
        Select-Object -First {max_events} |
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
                        event = self._parse_rdp_logon(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for RDP logons")
        except Exception as e:
            print(f"Error querying RDP logons: {e}")

        return parsed_events

    def _query_rdp_sessions(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for RDP session connection/disconnection events."""
        parsed_events = []

        # Event IDs: 4778 (session reconnect), 4779 (session disconnect)
        ps_command = f"""
        $StartTime = (Get-Date).AddHours(-{hours})
        Get-WinEvent -FilterHashtable @{{
            LogName='Security'
            ID=4778,4779
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
                        win_events = json.loads(output)
                    else:
                        win_events = [json.loads(output)]

                    for win_event in win_events:
                        event = self._parse_rdp_session(win_event)
                        if event:
                            parsed_events.append(event)

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("PowerShell query timed out for RDP sessions")
        except Exception as e:
            print(f"Error querying RDP sessions: {e}")

        return parsed_events

    def _query_terminal_services(self, hours: int, max_events: int) -> List[Dict[str, Any]]:
        """Query for Terminal Services events."""
        parsed_events = []

        ts_event_ids = list(TERMINAL_SERVICES_EVENT_IDS.keys())
        event_id_filter = ",".join(str(eid) for eid in ts_event_ids)

        # Try both possible log locations for Terminal Services events
        log_names = [
            'Microsoft-Windows-TerminalServices-LocalSessionManager/Operational',
            'Microsoft-Windows-TerminalServices-RemoteConnectionManager/Operational'
        ]

        for log_name in log_names:
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
                            win_events = json.loads(output)
                        else:
                            win_events = [json.loads(output)]

                        for win_event in win_events:
                            event = self._parse_terminal_services(win_event, log_name)
                            if event:
                                parsed_events.append(event)

                    except json.JSONDecodeError:
                        pass

            except subprocess.TimeoutExpired:
                print(f"PowerShell query timed out for {log_name}")
            except Exception as e:
                # Log name might not exist, continue silently
                pass

        return parsed_events

    def _parse_rdp_logon(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse RDP logon event (Event ID 4624 with LogonType 10)."""
        try:
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

            username = event_data.get('TargetUserName', 'unknown')
            domain = event_data.get('TargetDomainName', '')
            source_ip = event_data.get('IpAddress', '')
            source_workstation = event_data.get('WorkstationName', '')
            logon_id = event_data.get('TargetLogonId', '')

            # Skip system accounts
            if username.endswith('$') or username in ['SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE']:
                return None

            # Build message
            message = f"RDP login by {domain}\\{username}"
            if source_ip and source_ip not in ['-', '127.0.0.1', '::1']:
                message += f" from {source_ip}"
            if source_workstation:
                message += f" (workstation: {source_workstation})"

            return create_event(
                category="remote",
                event_type="rdp_login",
                severity="info",
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
                    "source_ip": source_ip,
                    "source_workstation": source_workstation,
                    "logon_type": 10,
                    "logon_type_name": "RemoteInteractive",
                    "logon_id": logon_id,
                    "connection_type": "rdp",
                }
            )

        except Exception as e:
            print(f"Error parsing RDP logon: {e}")
            return None

    def _parse_rdp_session(self, win_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse RDP session connection/disconnection event."""
        try:
            event_id = win_event.get('Id', 0)

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

            account_name = event_data.get('AccountName', 'unknown')
            account_domain = event_data.get('AccountDomain', '')
            session_name = event_data.get('SessionName', '')
            client_name = event_data.get('ClientName', '')
            client_address = event_data.get('ClientAddress', '')

            # Determine event type and message
            if event_id == 4778:
                event_type = "rdp_session_reconnect"
                action = "reconnected to"
            else:  # 4779
                event_type = "rdp_session_disconnect"
                action = "disconnected from"

            message = f"User {account_domain}\\{account_name} {action} RDP session"
            if client_address:
                message += f" from {client_address}"
            if client_name:
                message += f" (client: {client_name})"

            return create_event(
                category="remote",
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
                    "username": account_name,
                    "domain": account_domain,
                    "full_username": f"{account_domain}\\{account_name}" if account_domain else account_name,
                    "client_name": client_name,
                    "client_address": client_address,
                    "session_name": session_name,
                    "connection_type": "rdp",
                }
            )

        except Exception as e:
            print(f"Error parsing RDP session: {e}")
            return None

    def _parse_terminal_services(
        self,
        win_event: Dict[str, Any],
        log_name: str
    ) -> Optional[Dict[str, Any]]:
        """Parse Terminal Services event."""
        try:
            event_id = win_event.get('Id', 0)
            event_type = TERMINAL_SERVICES_EVENT_IDS.get(event_id, "rdp_event")
            message_text = win_event.get('Message', '')

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

            # Extract user and session info from event data or message
            user = event_data.get('User', '')
            if not user:
                # Try to extract from message
                user_match = re.search(r'User:\s*([^\s]+)', message_text, re.IGNORECASE)
                user = user_match.group(1) if user_match else "unknown"

            session_id = event_data.get('SessionID', event_data.get('Session', ''))
            source_ip = event_data.get('Address', '')
            if not source_ip:
                ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', message_text)
                source_ip = ip_match.group(1) if ip_match else ""

            # Build message
            event_messages = {
                21: f"User {user} successfully logged on to RDP session {session_id}",
                22: f"RDP shell started for user {user} in session {session_id}",
                23: f"User {user} logged off from RDP session {session_id}",
                24: f"User {user} disconnected from RDP session {session_id}",
                25: f"User {user} reconnected to RDP session {session_id}",
                39: f"User {user} disconnected from RDP session (user-initiated)",
                40: f"RDP session {session_id} disconnected (network)",
            }

            message = event_messages.get(event_id, f"RDP session event for user {user}")
            if source_ip:
                message += f" from {source_ip}"

            return create_event(
                category="remote",
                event_type=event_type,
                severity="info",
                message=message,
                source="TerminalServices",
                os="windows",
                hostname=self.hostname,
                host_ip=self.host_ip,
                timestamp=timestamp,
                data={
                    "event_id": event_id,
                    "user": user,
                    "session_id": session_id,
                    "source_ip": source_ip,
                    "connection_type": "rdp",
                    "log_name": log_name,
                }
            )

        except Exception as e:
            print(f"Error parsing Terminal Services event: {e}")
            return None

    def _parse_timestamp(self, time_created: str) -> datetime:
        """Parse timestamp from PowerShell datetime string."""
        if time_created:
            try:
                return datetime.fromisoformat(time_created.replace('Z', '+00:00'))
            except:
                pass
        return datetime.utcnow()


def collect_remote_events(hours: int = 24, max_events: int = 1000) -> List[Dict[str, Any]]:
    """
    Convenience function to collect Windows remote access events.

    Args:
        hours: Hours to look back
        max_events: Maximum number of events to collect

    Returns:
        list: List of event dictionaries

    Example:
        events = collect_remote_events(hours=24)
        print(f"Collected {len(events)} remote access events")
    """
    collector = WindowsRemoteAccessCollector()
    return collector.collect_events(hours, max_events)


if __name__ == "__main__":
    """Test the Windows remote access collector."""
    import json

    print("=" * 70)
    print("Windows Remote Access Event Collector - Test Mode")
    print("=" * 70)

    print("\nCollecting remote access events from last 24 hours...")
    print("(This requires administrator privileges for Security log)")

    events = collect_remote_events(hours=24, max_events=100)

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

        # Remote connections by user
        print("\nRemote access by user:")
        users = {}
        for event in events:
            user = event.get('data', {}).get('full_username', event.get('data', {}).get('user', 'unknown'))
            users[user] = users.get(user, 0) + 1

        for user, count in sorted(users.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {user}: {count} events")

    else:
        print("No remote access events found.")
        print("Note: Security log access requires administrator privileges.")

    print("\n" + "=" * 70)
