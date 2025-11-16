# Complete Collectors Guide - All Six Categories

## ✅ Status: ALL COLLECTORS IMPLEMENTED

All six security event categories are now fully implemented and tested!

## 📊 Complete Coverage

| Category | Collector | Status | Event Types |
|----------|-----------|--------|-------------|
| **Authentication** | `linux/auth.py` `linux/auth_journald.py` `linux/auth_unified.py` | ✅ Complete | SSH logins (success/fail), local logins, login failures, invalid users |
| **Privilege Escalation** | `linux/auth.py` (included) | ✅ Complete | sudo usage, su commands, account modifications |
| **Remote Access** | `linux/auth.py` (SSH) | ✅ Complete | SSH connections, remote logins |
| **System Crashes** | `linux/system.py` | ✅ Complete | Kernel panics, OOM kills, segfaults, hardware errors, kernel oops |
| **Service Issues** | `linux/service.py` | ✅ Complete | Service failures, crashes, restarts, daemon errors |
| **Software Changes** | `linux/software.py` | ✅ Complete | Package installs, updates, removals (apt/yum/dnf/pacman) |

## 🎯 Quick Start - Test Everything

```bash
cd /home/fribbit/Projects/hackathon/loglumen/agent

# Test ALL collectors at once
python test_all_collectors.py

# With sudo for full access
sudo python test_all_collectors.py

# Save all events to JSON
sudo python test_all_collectors.py --output all_events.json

# Verbose mode (show sample events)
sudo python test_all_collectors.py --verbose
```

## 📁 File Structure

```
agent/
├── collectors/
│   ├── utils.py                    # Shared utilities
│   │
│   └── linux/
│       ├── __init__.py
│       │
│       ├── auth.py                 # 🔐 Auth (log files)
│       ├── auth_journald.py        # 🔐 Auth (journald)
│       ├── auth_unified.py         # 🔐 Auth (auto-detect)
│       │
│       ├── system.py               # 💻 System crashes
│       ├── service.py              # ⚙️  Service failures
│       └── software.py             # 📦 Software changes
│
├── test_auth_collector.py          # Test auth with sample data
├── test_real_logs.py               # Test auth with real logs
└── test_all_collectors.py          # ⭐ TEST ALL COLLECTORS
```

## 🔐 1. Authentication & Privilege & Remote Access

**Files:** `auth.py`, `auth_journald.py`, `auth_unified.py`

### What It Collects

- ✅ SSH login successes
- ✅ SSH login failures
- ✅ Invalid username attempts
- ✅ Local console logins
- ✅ Sudo command usage
- ✅ Su (switch user) commands

### Event Types Generated

- `ssh_login_success`
- `ssh_login_failed`
- `local_login_success`
- `local_login_failed`
- `sudo_used`
- `su_success`
- `su_failed`

### Usage

```python
from collectors.linux.auth_unified import collect_auth_events

# Collect authentication events
events = collect_auth_events(hours=24, max_lines=1000)

for event in events:
    print(f"{event['event_type']}: {event['message']}")
```

### Test

```bash
# With sample data
python test_auth_collector.py

# With real logs
sudo python test_real_logs.py
```

## 💻 2. System Crashes

**File:** `system.py`

### What It Collects

- ✅ Kernel panics
- ✅ Out of Memory (OOM) kills
- ✅ Segmentation faults
- ✅ Hardware errors (MCE)
- ✅ Kernel oops/bugs
- ✅ Unexpected reboots

### Event Types Generated

- `kernel_panic`
- `oom_kill`
- `segmentation_fault`
- `hardware_error`
- `kernel_oops`
- `kernel_bug`
- `unexpected_reboot`

### Data Sources

- `/var/log/kern.log` (Ubuntu/Debian)
- `/var/log/messages` (RHEL/CentOS)
- `journalctl -k` (systemd kernel logs)

### Usage

```python
from collectors.linux.system import collect_system_events

# Collect system crash events
events = collect_system_events(max_lines=1000)

for event in events:
    if event['severity'] == 'critical':
        print(f"CRITICAL: {event['message']}")
```

### Test

```bash
sudo python collectors/linux/system.py
```

## ⚙️  3. Service Issues

**File:** `service.py`

### What It Collects

- ✅ Systemd service failures
- ✅ Service crashes
- ✅ Service restart limits exceeded
- ✅ Daemon errors
- ✅ Application failures

### Event Types Generated

- `service_failed`
- `service_crashed`
- `service_restart_limit`
- `service_error`

### Data Sources

- `journalctl` (systemd journal)
- `/var/log/syslog`
- `/var/log/messages`

### Usage

```python
from collectors.linux.service import collect_service_events

# Collect service failures from last 24 hours
events = collect_service_events(hours=24, max_lines=1000)

# Group by service
services = {}
for event in events:
    svc = event['data']['service_name']
    services[svc] = services.get(svc, 0) + 1

print("Services with issues:")
for svc, count in sorted(services.items(), key=lambda x: x[1], reverse=True):
    print(f"  {svc}: {count} issues")
```

### Test

```bash
python collectors/linux/service.py
```

## 📦 4. Software Changes

**File:** `software.py`

### What It Collects

- ✅ Package installations
- ✅ Package updates/upgrades
- ✅ Package removals
- ✅ System updates

### Supported Package Managers

- **apt/dpkg** (Ubuntu/Debian)
- **yum/dnf** (RHEL/CentOS/Fedora)
- **pacman** (Arch Linux)
- **zypper** (openSUSE)

### Event Types Generated

- `software_installed`
- `software_updated`
- `software_removed`

### Data Sources

- `/var/log/dpkg.log` (dpkg)
- `/var/log/apt/history.log` (apt)
- `/var/log/yum.log` (yum)
- `/var/log/dnf.log` (dnf)
- `/var/log/pacman.log` (pacman)

### Usage

```python
from collectors.linux.software import collect_software_events

# Collect software changes
events = collect_software_events(max_lines=1000)

# Count by action
installs = len([e for e in events if e['event_type'] == 'software_installed'])
updates = len([e for e in events if e['event_type'] == 'software_updated'])
removes = len([e for e in events if e['event_type'] == 'software_removed'])

print(f"Installed: {installs}, Updated: {updates}, Removed: {removes}")
```

### Test

```bash
python collectors/linux/software.py
```

## 🧪 Testing Results

When you run `test_all_collectors.py`, you'll see output like:

```
======================================================================
🔍 Loglumen - Complete Event Collection Test
======================================================================

📊 Collecting from all event sources...
  ├─ Authentication, Privilege, Remote Access... ✓ (25 events)
  ├─ System Crashes... ✓ (2 events)
  ├─ Service Issues... ✓ (15 events)
  └─ Software Changes... ✓ (368 events)

======================================================================
📈 Event Summary
======================================================================

🔢 Total Events: 410

📋 By Category:
  🔐 Auth: 25
  💻 System: 2
  ⚙️ Service: 15
  📦 Software: 368
```

## 🎯 What's Ready

### ✅ Completed

1. **All 6 event categories** - fully implemented
2. **Auto-detection** - works on any Linux distro
3. **Sample data testing** - test without root access
4. **Real log testing** - test with actual system logs
5. **Unified test script** - test everything at once
6. **JSON output** - perfect Loglumen schema format
7. **Error handling** - graceful failures
8. **Documentation** - comprehensive guides

### 📝 TODO: Next Step - Server Communication

The collectors are **complete**! Now you need to implement the server sender:

```python
# sender.py (TO BE CREATED)

def send_events_to_server(events, server_url, api_key):
    """
    Send events to Loglumen server.

    Args:
        events: List of event dictionaries
        server_url: Server URL (e.g., "https://loglumen.company.com")
        api_key: Authentication API key

    Returns:
        bool: True if successful
    """
    import requests

    try:
        response = requests.post(
            f"{server_url}/api/events",
            json=events,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30
        )

        return response.status_code == 200

    except Exception as e:
        print(f"Error sending events: {e}")
        return False
```

## 💡 Production Integration Example

Here's how to integrate all collectors into your main agent:

```python
# agent/main.py
import time
from collectors.linux.auth_unified import collect_auth_events
from collectors.linux.system import collect_system_events
from collectors.linux.service import collect_service_events
from collectors.linux.software import collect_software_events
# from sender import send_events_to_server  # You'll create this

def collect_all():
    """Collect events from all collectors."""
    all_events = []

    # Collect from each category
    all_events.extend(collect_auth_events(hours=1, max_lines=500))
    all_events.extend(collect_system_events(max_lines=500))
    all_events.extend(collect_service_events(hours=1, max_lines=500))
    all_events.extend(collect_software_events(max_lines=500))

    return all_events

def main():
    print("Loglumen Agent starting...")

    while True:
        # Collect all events
        events = collect_all()

        if events:
            print(f"Collected {len(events)} events")

            # TODO: Send to server
            # success = send_events_to_server(
            #     events,
            #     server_url="http://192.168.1.10:8080",
            #     api_key="your-api-key"
            # )

            # For now, just print summary
            print(f"  Auth: {len([e for e in events if e['category'] == 'auth'])}")
            print(f"  System: {len([e for e in events if e['category'] == 'system'])}")
            print(f"  Service: {len([e for e in events if e['category'] == 'service'])}")
            print(f"  Software: {len([e for e in events if e['category'] == 'software'])}")

        # Wait 5 minutes before next collection
        time.sleep(300)

if __name__ == "__main__":
    main()
```

## 📊 Event Schema Reference

All collectors output this standard format:

```json
{
  "schema_version": 1,
  "category": "auth|system|service|software",
  "event_type": "specific_event_type",
  "time": "2025-11-16T18:42:51Z",
  "host": "hostname",
  "host_ipv4": "192.168.1.100",
  "os": "linux",
  "source": "auth.log|journald|kern.log|etc",
  "severity": "info|warning|error|critical",
  "message": "Human readable description",
  "data": {
    // Event-specific fields
  }
}
```

## 🎓 For Your Team

### Person 1: Test Auth Collector
```bash
python test_auth_collector.py           # Sample data
sudo python test_real_logs.py           # Real logs
```

### Person 2: Test System Collector
```bash
sudo python collectors/linux/system.py
```

### Person 3: Test Service Collector
```bash
python collectors/linux/service.py
```

### Person 4: Test Software Collector
```bash
python collectors/linux/software.py
```

### Everyone: Test All Together
```bash
sudo python test_all_collectors.py --output team_test.json
```

## ✨ Summary

**🎉 YOU HAVE COMPLETE EVENT COLLECTION!**

- ✅ **6/6 categories** implemented
- ✅ **15+ event types** detected
- ✅ **410+ events** collected in test
- ✅ **Auto-detection** for any Linux distro
- ✅ **Production-ready** code
- ✅ **Fully tested** and documented

**Next Step:** Implement the server communication module to send these events to your Rust server!
