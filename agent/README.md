# Agent

The agent is the Python program that runs on each machine you want to monitor (Windows or Linux). It reads system logs, extracts important security events, and sends them to the central server.

## What Does the Agent Do?

Think of the agent as a security guard that:
1. **Watches** system log files continuously
2. **Recognizes** important security events (like failed logins or crashes)
3. **Reports** these events to headquarters (the central server)

```
┌─────────────────────────────────────┐
│      Monitored Machine              │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  System Logs                 │  │
│  │  • Security.evtx (Windows)   │  │
│  │  • /var/log/auth.log (Linux) │  │
│  │  • Application logs          │  │
│  │  • System logs               │  │
│  └──────────┬───────────────────┘  │
│             │ reads                │
│             ▼                       │
│  ┌──────────────────────────────┐  │
│  │  Agent (Python)              │  │
│  │                              │  │
│  │  1. Parse log files          │  │
│  │  2. Filter for important     │  │
│  │     events                   │  │
│  │  3. Convert to JSON          │  │
│  │  4. Send to server           │  │
│  └──────────┬───────────────────┘  │
│             │ sends JSON           │
└─────────────┼──────────────────────┘
              │
              ▼
   ┌──────────────────┐
   │  Central Server  │
   └──────────────────┘
```

## Agent Responsibilities

### 1. Parsing Log Files
The agent knows how to read different log file formats:
- **Windows**: Binary `.evtx` files (Event Viewer logs)
- **Linux**: Text-based syslog/journald files

### 2. Collecting Important Information
Not all log entries are important. The agent filters for security-relevant events:
- Authentication failures (someone trying wrong passwords)
- Privilege changes (user becoming admin)
- System crashes (blue screens, kernel panics)
- Service failures (critical apps crashing)
- Software changes (new programs installed)
- Remote access attempts (RDP, SSH connections)

### 3. Creating JSON-Formatted Data
The agent converts log entries into a standardized JSON format that the server understands:

```json
{
  "schema_version": 1,
  "category": "auth",
  "event_type": "login_failed",
  "time": "2025-11-16T18:42:51Z",
  "host": "LAPTOP-XYZ",
  "host_ipv4": "192.168.1.100",
  "os": "windows",
  "source": "Security",
  "severity": "warning",
  "message": "Failed logon for user admin from 192.168.1.50",
  "data": {
    "username": "admin",
    "remote_ip": "192.168.1.50",
    "event_id": 4625
  }
}
```

### 4. Sending Data to the Server
The agent sends these JSON events to the server via HTTP/HTTPS.

## Project Structure

```
agent/
├── main.py              # Main entry point - starts the agent (to be created)
├── config_loader.py     # Reads agent.toml configuration (to be created)
├── collectors/          # Contains all log collection modules
│   ├── windows/         # Windows-specific collectors
│   │   ├── auth.py           # Collects authentication events
│   │   ├── privilege.py      # Collects privilege escalation events
│   │   ├── system.py         # Collects system crash events
│   │   ├── service.py        # Collects service failure events
│   │   ├── software.py       # Collects software install/update events
│   │   └── remote.py         # Collects remote access events
│   │
│   └── linux/           # Linux-specific collectors
│       ├── auth.py           # Collects authentication events
│       ├── privilege.py      # Collects privilege escalation events
│       ├── system.py         # Collects system crash events
│       ├── service.py        # Collects service failure events
│       ├── software.py       # Collects software install/update events
│       └── remote.py         # Collects remote access events
│
└── sender.py            # Sends JSON events to server (to be created)
```

## How to Set Up the Agent

### Step 1: Install Python
Make sure Python 3.7+ is installed:
```bash
python --version
# or
python3 --version
```

If not installed:
- **Windows**: Download from [python.org](https://python.org)
- **Linux**: `sudo apt install python3` (Ubuntu/Debian) or `sudo yum install python3` (RHEL/CentOS)

### Step 2: Install Dependencies
```bash
cd agent
pip install -r requirements.txt
```
(Currently there are no external dependencies, but this may change)

### Step 3: Configure the Agent
Copy the example configuration:
```bash
cp ../config/agent.example.toml ../config/agent.toml
```

Edit `config/agent.toml` to set:
```toml
server_ip = "192.168.1.10"      # IP of your central server
server_port = 8080              # Port the server listens on
client_name = "OFFICE-PC-01"    # Unique name for this machine
client_ip = "192.168.1.100"     # IP of this machine
```

### Step 4: Run the Agent
```bash
# On Windows (may need administrator privileges)
python main.py

# On Linux (may need sudo for log access)
sudo python3 main.py
```

## How to Create a Collector (For Developers)

Each collector is a Python module that:
1. Reads a specific log file
2. Parses it for relevant events
3. Returns events in the standard JSON format

### Example: Simple Windows Authentication Collector

```python
# collectors/windows/auth.py
import json
from datetime import datetime

def collect_auth_events():
    """
    Collects authentication events from Windows Security log.
    Returns a list of event dictionaries.
    """
    events = []

    # TODO: Read from C:\Windows\System32\winevt\Logs\Security.evtx
    # For now, here's the structure you'd create:

    event = {
        "schema_version": 1,
        "category": "auth",
        "event_type": "login_failed",
        "time": datetime.utcnow().isoformat() + "Z",
        "host": get_hostname(),
        "host_ipv4": get_local_ip(),
        "os": "windows",
        "source": "Security",
        "severity": "warning",
        "message": "Failed logon for user admin",
        "data": {
            "username": "admin",
            "event_id": 4625,
            "reason": "Bad password"
        }
    }

    events.append(event)
    return events

def get_hostname():
    import socket
    return socket.gethostname()

def get_local_ip():
    import socket
    return socket.gethostbyname(socket.gethostname())
```

### Testing Your Collector

Create a test file to verify your collector works:

```python
# test_collector.py
from collectors.windows import auth
import json

# Run the collector
events = auth.collect_auth_events()

# Print the results nicely
for event in events:
    print(json.dumps(event, indent=2))
```

Run it:
```bash
python test_collector.py
```

## Python Concepts Used in This Project

### Imports
```python
import os           # Work with files and directories
import json         # Convert Python dictionaries to JSON
from datetime import datetime  # Work with dates and times
```

### Functions
```python
def my_function(parameter):
    """This is a docstring explaining what the function does"""
    result = parameter + 1
    return result
```

### Dictionaries (JSON in Python)
```python
# Create a dictionary
event = {
    "key": "value",
    "number": 42,
    "list": [1, 2, 3]
}

# Access values
print(event["key"])  # Prints: value

# Convert to JSON string
json_string = json.dumps(event)
```

### Lists
```python
# Create a list
events = []

# Add items
events.append(event1)
events.append(event2)

# Loop through items
for event in events:
    print(event)
```

### Reading Files
```python
# Read a text file
with open("file.txt", "r") as f:
    content = f.read()

# Read line by line
with open("file.txt", "r") as f:
    for line in f:
        print(line)
```

## Common Tasks

### Run a Specific Collector
```bash
python -c "from collectors.windows.auth import collect_auth_events; print(collect_auth_events())"
```

### Test JSON Output
```bash
python -c "import json; from collectors.windows.auth import collect_auth_events; print(json.dumps(collect_auth_events(), indent=2))"
```

### Check for Python Errors
```bash
python -m py_compile collectors/windows/auth.py
```

## Next Steps for Development

1. Create `main.py` - the main agent program that:
   - Loads configuration from `config/agent.toml`
   - Runs all collectors periodically (e.g., every 60 seconds)
   - Sends collected events to the server

2. Implement collectors in `collectors/windows/` and `collectors/linux/`

3. Create `sender.py` - handles sending JSON to the server via HTTP POST

4. Add error handling and logging

5. Create a Windows service / Linux systemd unit for automatic startup

See `collectors/README.md` for detailed information on what events to collect and where to find them.
