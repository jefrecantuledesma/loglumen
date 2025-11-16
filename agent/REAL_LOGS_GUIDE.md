# Using the Auth Collector with Real System Logs

This guide shows how to use the authentication collector with **real Linux system logs** instead of sample data.

## Quick Start - Real Logs

### Option 1: Auto-Detect Method (Easiest)

```bash
cd /home/fribbit/Projects/hackathon/loglumen/agent

# Try without sudo first
python test_real_logs.py

# If that shows limited events, use sudo for full access
sudo python test_real_logs.py
```

The collector will automatically:
1. Try to find `/var/log/auth.log` or `/var/log/secure`
2. Fall back to `journalctl` (systemd journal) if no log files
3. Collect and display real authentication events

### Option 2: Force Specific Method

```bash
# Force use of journald (modern systems)
python test_real_logs.py --method journald --hours 24

# Force use of log files (traditional systems)
sudo python test_real_logs.py --method logfile
```

### Option 3: Save to JSON File

```bash
# Collect and save to file
sudo python test_real_logs.py --output real_events.json

# View the JSON file
cat real_events.json | jq .  # If you have jq installed
# or
python -m json.tool real_events.json
```

## Three Collection Methods

### Method 1: Traditional Log Files (`auth.py`)

**Best for:** Ubuntu, Debian, older systems

**Log files used:**
- `/var/log/auth.log` (Ubuntu/Debian)
- `/var/log/secure` (RHEL/CentOS)

**Requirements:**
- Root access to read log files
- Log files must exist

**Usage:**
```python
from collectors.linux.auth import collect_auth_events

# Auto-detect log file location
events = collect_auth_events()

# Or specify exact file
events = collect_auth_events(log_file="/var/log/auth.log")

# Limit to recent lines
events = collect_auth_events(max_lines=500)
```

**Command line:**
```bash
# Using the original collector
sudo python collectors/linux/auth.py
```

### Method 2: Journald (`auth_journald.py`)

**Best for:** Modern systems (Ubuntu 16.04+, Fedora, Arch, systemd-based)

**Data source:** systemd journal via `journalctl`

**Requirements:**
- `journalctl` command available
- May need root for full journal access

**Usage:**
```python
from collectors.linux.auth_journald import collect_auth_events

# Get events from last 24 hours
events = collect_auth_events(hours=24)

# Last hour only
events = collect_auth_events(hours=1)

# Last week
events = collect_auth_events(hours=24*7)
```

**Command line:**
```bash
# Using journald collector
python collectors/linux/auth_journald.py

# With sudo
sudo python collectors/linux/auth_journald.py
```

### Method 3: Unified Auto-Detect (`auth_unified.py`)

**Best for:** Production use, maximum compatibility

**How it works:**
1. Tries log files first (faster)
2. Falls back to journald if no log files
3. Works on any Linux distribution

**Usage:**
```python
from collectors.linux.auth_unified import collect_auth_events

# Auto-detect best method
events = collect_auth_events()

# Force journald
events = collect_auth_events(prefer_method="journald", hours=24)

# Force log file
events = collect_auth_events(prefer_method="logfile")

# Specific file
events = collect_auth_events(log_file="/var/log/auth.log")
```

**Command line:**
```bash
# Use the unified test script
python test_real_logs.py

# With options
sudo python test_real_logs.py --method auto --hours 48
```

## Real-World Examples

### Example 1: Monitor Last Hour of Activity

```bash
# Get events from last hour
sudo python test_real_logs.py --hours 1 --output last_hour.json
```

### Example 2: Detect Brute Force Attacks

```python
from collectors.linux.auth_unified import collect_auth_events

# Collect recent events
events = collect_auth_events(hours=24)

# Count failed attempts by IP
failed_by_ip = {}
for event in events:
    if 'failed' in event['event_type'].lower():
        ip = event.get('data', {}).get('remote_ip', 'unknown')
        failed_by_ip[ip] = failed_by_ip.get(ip, 0) + 1

# Show IPs with 5+ failures
print("Potential attacks:")
for ip, count in failed_by_ip.items():
    if count >= 5:
        print(f"  {ip}: {count} failed attempts")
```

### Example 3: Track Sudo Usage

```python
from collectors.linux.auth_unified import collect_auth_events

events = collect_auth_events(hours=24)

# Filter for sudo events
sudo_events = [e for e in events if e['event_type'] == 'sudo_used']

# Show commands run with sudo
for event in sudo_events:
    user = event['data']['username']
    cmd = event['data']['command']
    when = event['time']
    print(f"{when}: {user} ran: {cmd}")
```

### Example 4: Monitor Specific Users

```python
from collectors.linux.auth_unified import collect_auth_events

events = collect_auth_events(hours=168)  # Last week

# Track activity for user 'alice'
alice_events = [e for e in events
                if e.get('data', {}).get('username') == 'alice']

print(f"Alice had {len(alice_events)} authentication events")
for event in alice_events:
    print(f"  {event['time']}: {event['message']}")
```

### Example 5: Continuous Monitoring (Production)

```python
import time
from collectors.linux.auth_unified import collect_auth_events

# Track last processed timestamp
last_check = None

while True:
    # Collect events from last 5 minutes
    events = collect_auth_events(hours=0.083)  # 5 minutes

    # Filter to only new events
    new_events = [e for e in events if e['time'] > last_check] if last_check else events

    if new_events:
        print(f"Found {len(new_events)} new events")
        # Send to server here
        # send_to_server(new_events)

        # Update last check time
        last_check = max(e['time'] for e in new_events)

    # Wait 1 minute before checking again
    time.sleep(60)
```

## Production Integration

### Integrating with Agent Main Loop

When you build `agent/main.py`, use the unified collector:

```python
# agent/main.py
import time
from collectors.linux.auth_unified import collect_auth_events
from sender import send_events_to_server  # You'll create this

def main():
    print("Loglumen Agent starting...")

    while True:
        # Collect events (will auto-detect method)
        events = collect_auth_events(hours=1, max_lines=1000)

        if events:
            print(f"Collected {len(events)} events")

            # Send to server
            success = send_events_to_server(events)

            if success:
                print("Events sent successfully")
            else:
                print("Failed to send events, will retry next cycle")

        # Wait before next collection (e.g., 5 minutes)
        time.sleep(300)

if __name__ == "__main__":
    main()
```

### Running as a Service

Once integrated into `main.py`, run as a systemd service:

```ini
# /etc/systemd/system/loglumen-agent.service
[Unit]
Description=Loglumen Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/loglumen/agent
ExecStart=/usr/bin/python3 /opt/loglumen/agent/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable loglumen-agent
sudo systemctl start loglumen-agent
sudo systemctl status loglumen-agent
```

## Troubleshooting

### "No events collected"

**Possible causes:**

1. **No authentication activity**
   - Solution: Generate some activity (SSH in, use sudo)
   - Test: `ssh localhost` or `sudo ls`

2. **Permission denied**
   - Solution: Run with sudo
   - Test: `sudo python test_real_logs.py`

3. **No log files or journald**
   - Check: `ls -la /var/log/auth.log /var/log/secure`
   - Check: `journalctl --version`

### "Permission denied reading /var/log/auth.log"

**Solution:** Auth logs require root access

```bash
# Run with sudo
sudo python test_real_logs.py

# Or add user to adm group (Ubuntu/Debian)
sudo usermod -a -G adm $USER
# Log out and back in for group to take effect
```

### "journalctl not found"

**Cause:** System doesn't use systemd

**Solution:** Use log file method explicitly

```bash
python test_real_logs.py --method logfile
```

### Events are old/stale

**For log files:** Log files contain all historical data. Limit with `max_lines`:
```python
events = collect_auth_events(max_lines=100)  # Only recent 100 lines
```

**For journald:** Specify time range:
```python
events = collect_auth_events(hours=1)  # Only last hour
```

## Performance Considerations

### Log File Method
- **Speed:** Very fast (reads plain text)
- **Memory:** Low (streams file)
- **Best for:** Real-time monitoring

### Journald Method
- **Speed:** Slower (queries journal database)
- **Memory:** Higher (loads entries into memory)
- **Best for:** Historical analysis

### Recommendations

- **Production agents:** Use auto-detect (tries fast method first)
- **Historical analysis:** Use journald with specific time range
- **Real-time monitoring:** Use log files if available
- **Limit lines:** Always set `max_lines` to avoid processing huge logs

## Security Best Practices

1. **Run with minimum required privileges**
   - Log files need root
   - Journald may work with user in `systemd-journal` group

2. **Protect the collector**
   - Store in `/opt/loglumen` with restricted permissions
   - Only root should be able to modify collector code

3. **Secure communication**
   - Send events over HTTPS to server
   - Validate server certificate

4. **Rate limiting**
   - Don't overwhelm server with too many events
   - Batch events and send periodically

5. **Handle sensitive data**
   - Events may contain usernames, IPs
   - Ensure server storage is secure
   - Consider data retention policies

## Testing Checklist

Before deploying to production:

- [ ] Test collector runs without errors
- [ ] Test with sudo (full log access)
- [ ] Test without sudo (limited access)
- [ ] Verify JSON output matches schema
- [ ] Test on your specific Linux distribution
- [ ] Test time range filtering
- [ ] Test max_lines limiting
- [ ] Generate test events (SSH, sudo) and verify collection
- [ ] Test auto-detect method selection
- [ ] Verify events have correct timestamps
- [ ] Check performance with large log files

## Next Steps

1. **Test on your systems**
   ```bash
   sudo python test_real_logs.py --output test.json
   ```

2. **Integrate into agent main.py**
   - Add continuous collection loop
   - Add sender module
   - Handle errors and retries

3. **Deploy to test machine**
   - Set up as systemd service
   - Monitor for errors
   - Verify events reach server

4. **Scale to production**
   - Deploy to all machines
   - Set up centralized monitoring
   - Configure alerting

---

**You now have three production-ready collectors** that work with any Linux system! Choose the method that best fits your environment, or use the unified auto-detect for maximum compatibility.
