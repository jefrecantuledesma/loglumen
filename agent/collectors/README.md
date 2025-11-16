# Collectors
- This folder holds the individual log-parsing Python scripts

## Windows
- This folder holds log-parsing code for Windows machines

## Linux
- This folder holds log-parsing code for Linux machines

## What We are Collecting
### Types of Data
- Logins and auth failures
- Privilege escalations and account changes
- System and kernel panics
- Service, daemon, and app crashes and restarts
- Software installs, updates, and removals
- Remote access and network-related logs 

### Where these Logs are
- Logins and auth logs
  - C:\Windows\System32\winevt\Logs\Security.evtx
  - You may also want to figure out how to use Windows event viewer

- Privilege escalations and account changes
  - C:\Windows\System32\winevt\Logs\Security.evtx
  - You may also want to figure out how to use Windows event viewer

- System and kernel panics
  - C:\Windows\System32\winevt\Logs\System.evtx
  - C:\Windows\Minidump\
  - C:\Windows\MEMORY.DMP

- Service, daemon, and app crashes / restarts
  - C:\Windows\System32\winevt\Logs\Application.evtx
  - C:\Windows\System32\winevt\Logs\System.evtx
  - Look for Error / Critical messages

- Software installs, updates, and removals
  - C:\Windows\Logs\WindowsUpdate\
  - In event viewer:
    - Applications and Services Logs → Microsoft → Windows → WindowsUpdateClient
    - Windows Logs → Setup

- Remote access and network-related logs
  - Windows Logs → Security
    - Logon Type 10 or 7 events, 4624/4625 with RDP-specific fields
  - Applications and Services Logs → Microsoft → Windows → TerminalServices-*
  - In event viewer: Applications and Services Logs → Microsoft → Windows → <VPN / RRAS / NPS>

## Example JSON Schemes
{
  "schema_version": 1,
  "category": "auth",
  "event_type": "login_failed",
  "time": "2025-11-16T18:42:51Z",
  "host": "DESKTOP-1234",
  "host_ipv4": "192.0.2.10",
  "os": "windows",
  "source": "Security",
  "severity": "warning",
  "message": "Failed logon for user sam from 203.0.113.10",
  "data": {
    "username": "sam",
    "remote_ip": "203.0.113.10",
    "logon_method": "rdp",
    "event_id": 4625,
    "reason": "Bad password"
  }
}

