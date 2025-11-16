# Complete Linux Auth Collector Example - Quick Start for Your Team

## What We Built

A **fully functional** Linux authentication log collector that:

- ✅ Parses real Linux auth logs (`/var/log/auth.log`)
- ✅ Extracts SSH logins, sudo usage, su commands, local logins
- ✅ Outputs standardized JSON matching Loglumen schema
- ✅ Includes comprehensive error handling
- ✅ Comes with sample data for testing (no root needed!)
- ✅ Has a complete test suite with security analysis

## For Your Teammates: 3-Minute Quick Start

### 1. Test It Right Now (No Setup Required!)

```bash
cd /home/fribbit/Projects/hackathon/loglumen/agent
python test_auth_collector.py
```

This runs against sample data and shows you exactly what the collector does!

### 2. See the Output

The test will show:
- 📊 How many events were collected
- 👤 Which users had activity
- 🔒 Security analysis (brute force attempts, invalid users)
- 📝 Sample events in detail
- 📄 Complete JSON output

### 3. Save Events to JSON

```bash
python test_auth_collector.py --output my_events.json
```

Now you have a JSON file with all the events!

### 4. Look at the Code

Open these files to learn how it works:

1. **Start here:** `collectors/EXAMPLE_LINUX_AUTH.md` - Complete explanation
2. **The collector:** `collectors/linux/auth.py` - Main code (~450 lines, heavily commented)
3. **Helper utilities:** `collectors/utils.py` - Shared functions
4. **Test script:** `test_auth_collector.py` - How to use the collector

## What Your Team Will Learn

### Python Concepts Demonstrated

1. **Classes and Objects** - OOP design pattern
2. **Regular Expressions** - Parsing log lines
3. **Error Handling** - Try/except blocks
4. **File I/O** - Reading log files
5. **JSON** - Creating standardized output
6. **List Comprehensions** - Filtering data
7. **String Formatting** - f-strings
8. **Command-line Arguments** - Using argparse

### SIEM Concepts Demonstrated

1. **Log Parsing** - Converting text logs to structured data
2. **Event Normalization** - Standardizing different event types
3. **Security Analysis** - Detecting brute force, invalid users
4. **Categorization** - Auth vs privilege events
5. **Severity Levels** - Info vs warning classification

## File Structure Created

```
agent/
├── collectors/
│   ├── utils.py                         # Shared helper functions
│   │                                    # - create_event()
│   │                                    # - get_hostname()
│   │                                    # - get_local_ip()
│   │                                    # - parse_syslog_timestamp()
│   │
│   ├── linux/
│   │   ├── __init__.py                  # Makes it a Python package
│   │   └── auth.py                      # Main collector (450 lines)
│   │                                    # Class: LinuxAuthCollector
│   │                                    # Methods:
│   │                                    #   - collect_events()
│   │                                    #   - _parse_ssh_success()
│   │                                    #   - _parse_ssh_failure()
│   │                                    #   - _parse_sudo_command()
│   │                                    #   - _parse_su_command()
│   │                                    #   - _parse_local_login()
│   │
│   ├── test_data/
│   │   └── sample_auth.log              # 20 sample log lines
│   │                                    # Contains:
│   │                                    #   - SSH successes
│   │                                    #   - SSH failures
│   │                                    #   - Sudo commands
│   │                                    #   - Su commands
│   │                                    #   - Brute force attempts
│   │
│   └── EXAMPLE_LINUX_AUTH.md            # Complete documentation
│                                        # - How it works
│                                        # - Code examples
│                                        # - How to create new collectors
│
└── test_auth_collector.py               # Test script (300 lines)
                                         # Features:
                                         #   - Summary statistics
                                         #   - Security analysis
                                         #   - JSON export
                                         #   - Pretty output
```

## Example Output

When you run the test, you'll see output like:

```
======================================================================
✅ Collection Complete - Found 20 Events
======================================================================

📊 Total Events: 20
👤 Unique Users: 9

📋 Events by Type:
  • ssh_login_failed: 7
  • ssh_login_success: 6
  • sudo_used: 4
  • su_success: 1
  • local_login_success: 1
  • su_failed: 1

🔒 Security Analysis:
----------------------------------------------------------------------
⚠️  Found 8 failed authentication attempts
   🚨 Potential brute force attacks detected:
     - 45.76.123.45: 3 failed attempts

⚠️  Found 3 attempts with invalid usernames
   Attempted usernames: admin, hacker, oracle
```

## Sample JSON Event

```json
{
  "schema_version": 1,
  "category": "auth",
  "event_type": "ssh_login_failed",
  "time": "2025-11-16T08:20:45Z",
  "host": "webserver-01",
  "host_ipv4": "192.168.1.100",
  "os": "linux",
  "source": "auth.log",
  "severity": "warning",
  "message": "Failed SSH login for bob from 192.168.1.51 - Bad password",
  "data": {
    "username": "bob",
    "remote_ip": "192.168.1.51",
    "port": 54322,
    "reason": "Bad password",
    "invalid_user": false,
    "protocol": "ssh"
  }
}
```

## How to Use This as a Template

Your teammates can copy this pattern to create new collectors:

### Example: Creating a System Crash Collector

```python
# collectors/linux/system.py

from utils import create_event, get_hostname, get_local_ip

class LinuxSystemCollector:
    def __init__(self):
        self.hostname = get_hostname()
        self.host_ip = get_local_ip()
        self.log_file = "/var/log/kern.log"  # Kernel log

    def collect_events(self):
        events = []
        with open(self.log_file, 'r') as f:
            for line in f:
                if 'kernel panic' in line.lower():
                    event = self._parse_kernel_panic(line)
                    events.append(event)
        return events

    def _parse_kernel_panic(self, line):
        # Parse kernel panic and create event
        return create_event(
            category="system",
            event_type="kernel_panic",
            severity="critical",
            message="Kernel panic detected",
            source="kern.log",
            os="linux",
            data={"panic_message": line.strip()}
        )

def collect_system_events():
    collector = LinuxSystemCollector()
    return collector.collect_events()
```

## Testing on Real System Logs

When ready to test with actual system logs:

```bash
# Requires root access
sudo python test_auth_collector.py --real
```

This will parse `/var/log/auth.log` and show real authentication events from your system!

## Next Steps for Your Team

### Person 1: Study the Auth Collector
- Read through `auth.py` with the comments
- Understand how regex patterns work
- Run the test script multiple times
- Try modifying the sample data and re-running

### Person 2: Create System Collector
- Copy `auth.py` to `system.py`
- Change it to parse `/var/log/kern.log`
- Look for kernel panics, OOM kills, hardware errors
- Create sample data for testing

### Person 3: Create Service Collector
- Copy `auth.py` to `service.py`
- Use `journalctl` to get service failures
- Parse systemd service crash events
- Focus on "failed", "error", "crash" messages

### Person 4: Create Software Collector
- Copy `auth.py` to `software.py`
- Parse `/var/log/dpkg.log` (Ubuntu) or `/var/log/yum.log` (RHEL)
- Track package installations, updates, removals
- Include version numbers and timestamps

## Pro Tips

1. **Test with sample data first** - Don't need root, faster iteration
2. **Print everything** - Add `print()` statements to debug
3. **Start simple** - Get basic parsing working before adding features
4. **Use the helpers** - The `utils.py` functions save time
5. **Copy the pattern** - This structure works for all collectors

## Common Questions

**Q: Why is there a LinuxAuthCollector class?**
A: Using a class lets us organize related functions together and maintain state (like hostname, IP) without passing it everywhere.

**Q: What's with all the regex?**
A: Regular expressions let us extract specific parts of text. `re.search(r'pattern', line)` finds patterns in log lines.

**Q: Why UTC timestamps?**
A: The server might be in a different timezone. UTC is universal, so all events use the same time reference.

**Q: Can I test without root access?**
A: Yes! That's why we included sample data. Just run `python test_auth_collector.py` without `--real`.

**Q: How do I add a new event type?**
A: Add a new parsing method (like `_parse_account_lockout()`) and call it from `_parse_log_line()`.

## Success Criteria

You'll know your team understands this when they can:

1. ✅ Run the test script and explain the output
2. ✅ Find where SSH failures are parsed in the code
3. ✅ Explain what `create_event()` does
4. ✅ Modify the sample data and see it reflected in output
5. ✅ Create a new collector using this as a template

## Resources

- **Main README**: `/README.md` - Project overview
- **Agent README**: `/agent/README.md` - How agents work
- **Collectors README**: `/agent/collectors/README.md` - All event types
- **Example Guide**: `/agent/collectors/EXAMPLE_LINUX_AUTH.md` - Detailed walkthrough
- **Config README**: `/config/README.md` - Configuration options

---

**This is production-ready code!** It handles errors, follows best practices, and matches the Loglumen JSON schema exactly. Your team can use this as-is or as a template for building more collectors.

Happy coding! 🚀
