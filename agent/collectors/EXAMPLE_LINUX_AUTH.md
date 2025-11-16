# Linux Authentication Collector - Complete Example

This is a **complete, working example** of a log collector for Loglumen. Your teammates can study this code to understand how to build other collectors.

## What This Example Does

The `linux/auth.py` collector:
- ✅ Reads Linux authentication logs (`/var/log/auth.log` or `/var/log/secure`)
- ✅ Parses SSH login attempts (successful and failed)
- ✅ Parses sudo command usage
- ✅ Parses su (switch user) commands
- ✅ Parses local console logins
- ✅ Converts everything to standard Loglumen JSON format
- ✅ Includes comprehensive error handling
- ✅ Works with sample data (no root required for testing)

## Files in This Example

```
agent/
├── collectors/
│   ├── utils.py                    # Helper functions (shared by all collectors)
│   ├── linux/
│   │   ├── __init__.py            # Makes this a Python package
│   │   └── auth.py                # THE MAIN COLLECTOR (study this!)
│   └── test_data/
│       └── sample_auth.log        # Sample log data for testing
│
└── test_auth_collector.py         # Test script to run the collector
```

## Quick Start - Test Without Root Access

The easiest way to test this collector is with the provided sample data:

```bash
# Navigate to the agent directory
cd /home/fribbit/Projects/hackathon/loglumen/agent

# Run the test script
python test_auth_collector.py
```

This will:
1. Use the sample log data (no permissions needed)
2. Collect all authentication events
3. Show a summary
4. Analyze for security concerns
5. Display sample events

## Testing With Real System Logs

To test with actual system logs (requires root):

```bash
# Navigate to the agent directory
cd /home/fribbit/Projects/hackathon/loglumen/agent

# Run with sudo to access real logs
sudo python test_auth_collector.py --real
```

## Using the Collector in Your Code

### Example 1: Basic Usage

```python
from collectors.linux.auth import collect_auth_events

# Collect events (auto-detects log file)
events = collect_auth_events()

# Print how many we found
print(f"Collected {len(events)} authentication events")

# Print each event
for event in events:
    print(event['message'])
```

### Example 2: Save to JSON File

```python
from collectors.linux.auth import collect_auth_events
import json

# Collect events
events = collect_auth_events(max_lines=500)

# Save to file
with open('auth_events.json', 'w') as f:
    json.dump(events, f, indent=2)

print(f"Saved {len(events)} events to auth_events.json")
```

### Example 3: Filter Specific Event Types

```python
from collectors.linux.auth import collect_auth_events

# Collect all events
events = collect_auth_events()

# Filter for only failed SSH logins
failed_ssh = [e for e in events if e['event_type'] == 'ssh_login_failed']

print(f"Found {len(failed_ssh)} failed SSH login attempts")
for event in failed_ssh:
    username = event['data']['username']
    ip = event['data']['remote_ip']
    print(f"  {username} from {ip}")
```

### Example 4: Detect Brute Force Attacks

```python
from collectors.linux.auth import collect_auth_events

# Collect events
events = collect_auth_events()

# Count failed attempts by IP
failed_by_ip = {}
for event in events:
    if 'failed' in event['event_type'].lower():
        ip = event.get('data', {}).get('remote_ip', 'unknown')
        failed_by_ip[ip] = failed_by_ip.get(ip, 0) + 1

# Show IPs with 5+ failures (potential brute force)
print("Potential brute force attacks:")
for ip, count in failed_by_ip.items():
    if count >= 5:
        print(f"  {ip}: {count} failed attempts")
```

## Understanding the Code Structure

### 1. The Main Collector Class (`LinuxAuthCollector`)

```python
class LinuxAuthCollector:
    def __init__(self, log_file=None):
        # Initialize: find log file, get hostname/IP
        pass

    def collect_events(self, max_lines=1000):
        # Main entry point: reads log and returns events
        pass

    def _parse_log_line(self, line):
        # Decides what type of event each line is
        pass

    def _parse_ssh_success(self, line):
        # Parses successful SSH logins
        pass

    def _parse_ssh_failure(self, line):
        # Parses failed SSH logins
        pass

    # ... more parsing methods
```

### 2. Helper Functions (`utils.py`)

```python
create_event(...)    # Creates standardized event dictionary
get_hostname()       # Gets machine's hostname
get_local_ip()       # Gets machine's IP address
parse_syslog_timestamp(line)  # Parses syslog date format
```

### 3. Regular Expressions for Parsing

The collector uses regex patterns to extract information:

```python
# Example: Extract username from SSH success
username_match = re.search(r'Accepted \w+ for (\S+) from', line)
username = username_match.group(1)
```

**Common Regex Patterns:**
- `\S+` - Match non-whitespace characters (username, hostname)
- `[\d\.]+` - Match digits and dots (IP address)
- `\d+` - Match digits (port number, PID)
- `\w+` - Match word characters (method, command)

## How to Create Your Own Collector

Use this auth collector as a template! Here's the process:

### Step 1: Choose What to Collect

Pick an event category from the main README:
- `privilege` - Privilege escalation events
- `system` - System crashes
- `service` - Service failures
- `software` - Software installations
- `remote` - Remote access (we did auth already)

### Step 2: Find the Log Files

Research where those logs are stored:
- Look in `/var/log/`
- Check system documentation
- Use `journalctl` for systemd services

### Step 3: Understand the Log Format

Read sample log lines and identify patterns:

```bash
# Example: Look at service logs
journalctl -u nginx -n 20
```

### Step 4: Copy and Modify This Collector

1. Copy `auth.py` to a new file (e.g., `system.py`)
2. Change the class name (`LinuxSystemCollector`)
3. Update the log file paths
4. Modify the parsing methods for your log format
5. Update the event types and categories

### Step 5: Test Your Collector

1. Create sample log data in `test_data/`
2. Write parsing tests
3. Test with real logs (using sudo)

## Code Walkthrough for Beginners

### How SSH Success Parsing Works

Let's trace through one example in detail:

**Input (log line):**
```
Nov 16 14:30:25 hostname sshd[12345]: Accepted publickey for alice from 192.168.1.50 port 54321 ssh2
```

**Step 1: Extract timestamp**
```python
timestamp = parse_syslog_timestamp(line)
# Result: datetime(2025, 11, 16, 14, 30, 25)
```

**Step 2: Extract username**
```python
username_match = re.search(r'Accepted \w+ for (\S+) from', line)
username = username_match.group(1)
# Result: "alice"
```

**Step 3: Extract IP address**
```python
ip_match = re.search(r'from ([\d\.]+) port', line)
remote_ip = ip_match.group(1)
# Result: "192.168.1.50"
```

**Step 4: Create event**
```python
return create_event(
    category="auth",
    event_type="ssh_login_success",
    severity="info",
    message=f"User alice logged in via SSH from 192.168.1.50",
    # ... more fields
)
```

**Output (JSON):**
```json
{
  "schema_version": 1,
  "category": "auth",
  "event_type": "ssh_login_success",
  "time": "2025-11-16T14:30:25Z",
  "host": "webserver-01",
  "host_ipv4": "192.168.1.100",
  "os": "linux",
  "source": "auth.log",
  "severity": "info",
  "message": "User alice logged in via SSH from 192.168.1.50",
  "data": {
    "username": "alice",
    "remote_ip": "192.168.1.50",
    "auth_method": "publickey",
    "port": 54321,
    "protocol": "ssh"
  }
}
```

## Common Python Concepts Used

### 1. Regular Expressions (Regex)

```python
import re

# Search for pattern in text
match = re.search(r'pattern', text)
if match:
    # Extract the captured group
    result = match.group(1)
```

### 2. List Comprehensions

```python
# Long way
failed = []
for event in events:
    if event['severity'] == 'warning':
        failed.append(event)

# Short way (list comprehension)
failed = [e for e in events if e['severity'] == 'warning']
```

### 3. Dictionary .get() Method

```python
# Safe way to access dictionary keys
ip = event.get('remote_ip', 'unknown')  # Returns 'unknown' if key doesn't exist

# vs. risky way:
ip = event['remote_ip']  # Crashes if key doesn't exist!
```

### 4. Try/Except Error Handling

```python
try:
    # Try to do something that might fail
    with open('/var/log/auth.log', 'r') as f:
        data = f.read()
except PermissionError:
    print("Need root access!")
except Exception as e:
    print(f"Something else went wrong: {e}")
```

### 5. f-strings (Formatted Strings)

```python
username = "alice"
ip = "192.168.1.50"

# Old way
message = "User " + username + " from " + ip

# New way (f-string)
message = f"User {username} from {ip}"
```

## Test Script Features

The `test_auth_collector.py` script includes:

1. **Summary Statistics** - Counts by event type and severity
2. **Security Analysis** - Detects brute force, invalid users, root access
3. **Sample Output** - Shows detailed events
4. **JSON Export** - Saves events to file
5. **Flexible Options** - Real logs or sample data

### Command-Line Options

```bash
# Use sample data (default)
python test_auth_collector.py

# Use real system logs
sudo python test_auth_collector.py --real

# Save to JSON file
python test_auth_collector.py --output events.json

# Show all events (not just first 5)
python test_auth_collector.py --show-all

# Process only last 100 lines
python test_auth_collector.py --max-lines 100
```

## Tips for Learning from This Code

1. **Start at the bottom** - Look at the `if __name__ == "__main__"` section first to see how it's used
2. **Trace one example** - Pick one log line and follow it through the code
3. **Print everything** - Add `print()` statements to see what variables contain
4. **Break things** - Modify the code and see what happens
5. **Test frequently** - Run the test script after every change

## Common Issues and Solutions

### "Permission denied" Error

**Problem:** Can't read `/var/log/auth.log`

**Solution:** Run with sudo:
```bash
sudo python test_auth_collector.py --real
```

### "No module named 'utils'" Error

**Problem:** Python can't find the utils module

**Solution:** Make sure you're running from the `agent/` directory:
```bash
cd /home/fribbit/Projects/hackathon/loglumen/agent
python test_auth_collector.py
```

### "No events collected"

**Problem:** Collector ran but found nothing

**Solutions:**
1. Check if log file exists: `ls -la /var/log/auth.log`
2. Check if log has content: `tail /var/log/auth.log`
3. Try the sample data instead: `python test_auth_collector.py` (without --real)

## Next Steps for Your Team

1. **Study this collector** - Read through `auth.py` line by line
2. **Run the tests** - Use `test_auth_collector.py` to see it in action
3. **Modify it** - Try adding a new event type (e.g., account lockouts)
4. **Create a new collector** - Use this as a template for `system.py` or `service.py`
5. **Share knowledge** - Each team member creates one collector and teaches the others

## Questions?

If you have questions about this code:

1. Read the comments in `auth.py` - they explain each section
2. Check the main `agent/collectors/README.md` for background
3. Run the test script with sample data to see what it produces
4. Try modifying small parts and re-running to understand behavior

Good luck! This is a complete, production-ready example that demonstrates all the key concepts for building Loglumen collectors.
