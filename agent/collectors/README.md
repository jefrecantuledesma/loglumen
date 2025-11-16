# Collectors

This folder contains the Python scripts that actually read and parse log files. Each collector is responsible for one category of security events.

## Folder Structure

```
collectors/
├── windows/          # Windows event log parsers
│   ├── auth.py       # Authentication events (Event ID 4624, 4625, etc.)
│   ├── privilege.py  # Privilege escalation events
│   ├── system.py     # System crashes and kernel panics
│   ├── service.py    # Service/app crashes
│   ├── software.py   # Software installs/updates
│   └── remote.py     # RDP and remote access
│
└── linux/            # Linux syslog/journald parsers
    ├── auth.py       # Authentication events from auth.log
    ├── privilege.py  # Sudo/su usage, user modifications
    ├── system.py     # Kernel panics, system failures
    ├── service.py    # Systemd service failures
    ├── software.py   # Package manager logs
    └── remote.py     # SSH and remote access
```

## How Collectors Work

Each collector is a Python file with one main function that:
1. Opens and reads a specific log file
2. Parses the log entries
3. Filters for important events
4. Returns a list of events in JSON format

```python
# Simplified collector example
def collect_events():
    events = []

    # Step 1: Open log file
    with open(LOG_FILE_PATH, 'r') as f:
        # Step 2: Parse each line
        for line in f:
            # Step 3: Filter for important events
            if is_important(line):
                # Step 4: Convert to JSON format
                event = parse_to_json(line)
                events.append(event)

    return events
```

## What We Are Collecting
We collect six categories of security-relevant events:

### 1. Authentication (auth.py)
**What**: Login attempts, failures, account lockouts, password changes

**Why it matters**: Failed logins could indicate brute-force attacks. Successful logins at unusual times could indicate compromised accounts.

**Windows locations**:
- `C:\Windows\System32\winevt\Logs\Security.evtx`
- Event IDs: 4624 (success), 4625 (failure), 4634 (logoff), 4648 (explicit credentials)

**Linux locations**:
- `/var/log/auth.log` (Ubuntu/Debian)
- `/var/log/secure` (RHEL/CentOS)
- `journalctl -u sshd` for SSH logins

### 2. Privilege Escalation (privilege.py)
**What**: Users gaining admin/root privileges, account modifications, group membership changes

**Why it matters**: Unauthorized privilege escalation is a key indicator of a compromise. Attackers often try to gain admin rights.

**Windows locations**:
- `C:\Windows\System32\winevt\Logs\Security.evtx`
- Event IDs: 4672 (special privileges), 4720 (user created), 4732 (user added to group), 4728 (user added to global group)

**Linux locations**:
- `/var/log/auth.log` - Look for `sudo` and `su` commands
- `/var/log/secure` - Same for RHEL/CentOS
- `journalctl | grep -E 'sudo|su\['`

### 3. System Crashes (system.py)
**What**: Kernel panics, blue screens (BSOD), system failures, unexpected reboots

**Why it matters**: Crashes can indicate hardware failure, driver issues, or attacks (like kernel exploits).

**Windows locations**:
- `C:\Windows\System32\winevt\Logs\System.evtx`
- Event IDs: 41 (unexpected shutdown), 1001 (bugcheck/BSOD), 6008 (unexpected shutdown)
- `C:\Windows\Minidump\` - Crash dump files
- `C:\Windows\MEMORY.DMP` - Full memory dump

**Linux locations**:
- `/var/log/kern.log` - Kernel messages
- `/var/log/syslog` - System messages
- `journalctl -k` - Kernel logs
- Look for: "kernel panic", "Oops:", "BUG:", "segfault"

### 4. Service Failures (service.py)
**What**: Services/daemons crashing, applications failing, service restarts

**Why it matters**: Unusual service crashes could indicate attacks, resource exhaustion, or stability issues.

**Windows locations**:
- `C:\Windows\System32\winevt\Logs\Application.evtx`
- `C:\Windows\System32\winevt\Logs\System.evtx`
- Look for: Event Type = Error or Critical

**Linux locations**:
- `journalctl -p err` - All error-level messages
- `journalctl -u service_name` - Specific service logs
- `/var/log/syslog` - Look for "failed", "error", "crash"

### 5. Software Changes (software.py)
**What**: Software installations, updates, removals, patch installations

**Why it matters**: Unauthorized software installation could indicate malware. Tracking patches helps ensure systems are up to date.

**Windows locations**:
- `C:\Windows\Logs\WindowsUpdate\`
- Event Viewer paths:
  - `Applications and Services Logs → Microsoft → Windows → WindowsUpdateClient`
  - `Windows Logs → Setup`
- Registry: `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`

**Linux locations**:
- **Ubuntu/Debian**: `/var/log/dpkg.log`, `/var/log/apt/history.log`
- **RHEL/CentOS**: `/var/log/yum.log`, `/var/log/dnf.log`
- **Arch**: `/var/log/pacman.log`

### 6. Remote Access (remote.py)
**What**: RDP connections, SSH logins, VPN access, remote desktop sessions

**Why it matters**: Remote access is a common attack vector. Tracking who connects remotely is critical for security.

**Windows locations**:
- `C:\Windows\System32\winevt\Logs\Security.evtx`
  - Event IDs: 4624 with Logon Type 10 (RemoteInteractive/RDP) or Logon Type 7 (Unlock/screensaver)
  - Event IDs: 4778 (RDP session reconnect), 4779 (RDP session disconnect)
- `Applications and Services Logs → Microsoft → Windows → TerminalServices-RemoteConnectionManager → Operational`
- `Applications and Services Logs → Microsoft → Windows → TerminalServices-LocalSessionManager → Operational`

**Linux locations**:
- `/var/log/auth.log` - SSH connections
- `journalctl -u sshd` - SSH service logs
- Look for: "Accepted publickey", "Accepted password", "Failed password"
- `/var/log/openvpn/` - VPN logs (if OpenVPN is used)

## Standard JSON Event Format

All collectors must output events in this exact format:

```json
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
```

### Field Descriptions

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `schema_version` | integer | Yes | Always `1` for now | `1` |
| `category` | string | Yes | Event category: `auth`, `privilege`, `system`, `service`, `software`, `remote` | `"auth"` |
| `event_type` | string | Yes | Specific event type | `"login_failed"`, `"service_crash"`, `"sudo_used"` |
| `time` | string | Yes | UTC timestamp in ISO 8601 format | `"2025-11-16T18:42:51Z"` |
| `host` | string | Yes | Hostname of the machine | `"DESKTOP-1234"` |
| `host_ipv4` | string | Yes | IPv4 address of the machine | `"192.168.1.100"` |
| `os` | string | Yes | Operating system: `windows` or `linux` | `"windows"` |
| `source` | string | Yes | Log source/file name | `"Security"`, `"auth.log"` |
| `severity` | string | Yes | Severity level: `info`, `warning`, `error`, `critical` | `"warning"` |
| `message` | string | Yes | Human-readable summary | `"Failed logon for user admin"` |
| `data` | object | Yes | Event-specific details (varies by event type) | See examples below |

### Example Events by Category

#### 1. Authentication Event (Windows)
```json
{
  "schema_version": 1,
  "category": "auth",
  "event_type": "login_failed",
  "time": "2025-11-16T18:42:51Z",
  "host": "DESKTOP-1234",
  "host_ipv4": "192.168.1.100",
  "os": "windows",
  "source": "Security",
  "severity": "warning",
  "message": "Failed logon for user admin from 192.168.1.50",
  "data": {
    "username": "admin",
    "remote_ip": "192.168.1.50",
    "logon_type": 3,
    "event_id": 4625,
    "reason": "Bad password",
    "failure_count": 5
  }
}
```

#### 2. Privilege Escalation (Linux)
```json
{
  "schema_version": 1,
  "category": "privilege",
  "event_type": "sudo_used",
  "time": "2025-11-16T19:15:22Z",
  "host": "webserver-01",
  "host_ipv4": "192.168.1.200",
  "os": "linux",
  "source": "auth.log",
  "severity": "info",
  "message": "User bob used sudo to run /usr/bin/systemctl restart nginx",
  "data": {
    "username": "bob",
    "command": "/usr/bin/systemctl restart nginx",
    "success": true,
    "tty": "pts/0"
  }
}
```

#### 3. System Crash (Windows)
```json
{
  "schema_version": 1,
  "category": "system",
  "event_type": "blue_screen",
  "time": "2025-11-16T03:22:15Z",
  "host": "WORKSTATION-05",
  "host_ipv4": "192.168.1.105",
  "os": "windows",
  "source": "System",
  "severity": "critical",
  "message": "System experienced BSOD with bugcheck code 0x0000007E",
  "data": {
    "event_id": 1001,
    "bugcheck_code": "0x0000007E",
    "bugcheck_string": "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED",
    "dump_file": "C:\\Windows\\Minidump\\111625-12345-01.dmp"
  }
}
```

#### 4. Service Failure (Linux)
```json
{
  "schema_version": 1,
  "category": "service",
  "event_type": "service_failed",
  "time": "2025-11-16T12:45:33Z",
  "host": "db-server",
  "host_ipv4": "192.168.1.150",
  "os": "linux",
  "source": "systemd",
  "severity": "error",
  "message": "Service postgresql failed to start",
  "data": {
    "service_name": "postgresql",
    "exit_code": 1,
    "signal": null,
    "restart_count": 3
  }
}
```

#### 5. Software Installation (Windows)
```json
{
  "schema_version": 1,
  "category": "software",
  "event_type": "software_installed",
  "time": "2025-11-16T14:30:12Z",
  "host": "LAPTOP-07",
  "host_ipv4": "192.168.1.107",
  "os": "windows",
  "source": "WindowsUpdateClient",
  "severity": "info",
  "message": "Security update KB5012345 installed successfully",
  "data": {
    "software_name": "Security Update for Windows (KB5012345)",
    "version": "10.0.19044.1234",
    "publisher": "Microsoft Corporation",
    "install_type": "update"
  }
}
```

#### 6. Remote Access (Linux SSH)
```json
{
  "schema_version": 1,
  "category": "remote",
  "event_type": "ssh_login_success",
  "time": "2025-11-16T16:20:45Z",
  "host": "ssh-gateway",
  "host_ipv4": "192.168.1.250",
  "os": "linux",
  "source": "auth.log",
  "severity": "info",
  "message": "User alice logged in via SSH from 203.0.113.45",
  "data": {
    "username": "alice",
    "remote_ip": "203.0.113.45",
    "auth_method": "publickey",
    "port": 22,
    "session_id": "12345"
  }
}
```

## How to Implement a Collector

### Step 1: Choose Your Event Category
Decide which collector you're implementing (auth, privilege, system, service, software, or remote).

### Step 2: Find the Log Files
Use the locations listed above to find where the logs are stored on Windows or Linux.

### Step 3: Understand the Log Format
- **Windows .evtx files**: Binary format, need special library like `python-evtx` or `pywin32`
- **Linux text logs**: Plain text, can read with standard Python `open()`

### Step 4: Create the Collector File

```python
# collectors/windows/auth.py
import socket
from datetime import datetime

def collect_events():
    """
    Collects authentication events from Windows Security log.
    Returns: List of event dictionaries
    """
    events = []

    # Get machine info once
    hostname = socket.gethostname()
    host_ip = socket.gethostbyname(hostname)

    # TODO: Open and parse Security.evtx
    # For Windows, you'll need a library like python-evtx or win32evtlog

    # Example: When you find a failed login event (Event ID 4625)
    event = create_event(
        category="auth",
        event_type="login_failed",
        severity="warning",
        message="Failed logon for user admin",
        hostname=hostname,
        host_ip=host_ip,
        data={
            "username": "admin",
            "event_id": 4625,
            "reason": "Bad password"
        }
    )
    events.append(event)

    return events

def create_event(category, event_type, severity, message, hostname, host_ip, data):
    """Helper function to create a standardized event dictionary"""
    return {
        "schema_version": 1,
        "category": category,
        "event_type": event_type,
        "time": datetime.utcnow().isoformat() + "Z",
        "host": hostname,
        "host_ipv4": host_ip,
        "os": "windows",  # or "linux"
        "source": "Security",  # or whatever log source
        "severity": severity,
        "message": message,
        "data": data
    }
```

### Step 5: Test Your Collector

```python
# test_auth_collector.py
import json
from collectors.windows.auth import collect_events

# Run the collector
events = collect_events()

# Print results
print(f"Collected {len(events)} events:")
for event in events:
    print(json.dumps(event, indent=2))
```

Run the test:
```bash
python test_auth_collector.py
```

## Recommended Python Libraries

### For Windows Event Logs
- **python-evtx**: Parse .evtx files
  ```bash
  pip install python-evtx
  ```
- **pywin32**: Windows API access (includes win32evtlog)
  ```bash
  pip install pywin32
  ```

### For Linux Logs
- **Built-in**: Use standard `open()` for text files
- **systemd**: For journald logs
  ```bash
  pip install systemd-python
  ```

### For Networking
- **requests**: Send events to server
  ```bash
  pip install requests
  ```

## Tips for Beginners

1. **Start simple**: Begin with a basic collector that just reads a few lines from a log file
2. **Test with sample data**: Create small test log files before working with real system logs
3. **Print everything**: Use `print()` statements to see what your code is doing
4. **Check JSON format**: Always validate your JSON output matches the schema exactly
5. **Handle errors**: Wrap file operations in try/except blocks
6. **Run with privileges**: Many log files require admin/root access

## Common Mistakes to Avoid

- ❌ Forgetting to use UTC time (`datetime.utcnow()`)
- ❌ Not ending timestamps with "Z" to indicate UTC
- ❌ Missing required fields in the JSON
- ❌ Using wrong category names (must be exactly: auth, privilege, system, service, software, remote)
- ❌ Trying to read binary .evtx files as text
- ❌ Running without administrator/root privileges

## Next Steps

1. Pick one collector to implement (start with auth - it's usually the easiest)
2. Research how to read the specific log format (Windows .evtx or Linux text)
3. Write a basic version that returns hardcoded test data
4. Test the JSON output format
5. Implement actual log parsing
6. Add error handling
7. Test on a real system (with appropriate permissions)
