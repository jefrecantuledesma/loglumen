# Loglumen

A lightweight SIEM (Security Information and Event Management) system that helps you monitor security events across all your Windows and Linux machines from one central dashboard.

## What Does This Tool Do?

This tool:

- Collects security events from Windows and Linux machines automatically,
- Monitors six critical event categories (authentication, privilege escalation, system crashes, service failures, software changes, and remote access),
- Aggregates all events in a central server with a web dashboard,
- Provides per-host and per-category statistics and filtering,
- Displays recent events with severity levels and detailed metadata,
- Supports flexible configuration for collection intervals and event filtering, and
- Has a 🦀Rust🦀 back-end with Actix-web and a Python agent system.

## The Problem It Solves

Imagine you manage 10, 50, or 100 computers. How do you know if:
- Someone tried to hack into one of them?
- A critical service crashed?
- Unauthorized software was installed?
- A system is experiencing kernel panics?

Instead of manually checking logs on each machine, Loglumen automatically collects important security events from all your systems and displays them in one place.

## Architecture Overview

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Windows PC #1  │         │  Linux Server   │         │  Windows PC #2  │
│                 │         │                 │         │                 │
│  ┌───────────┐  │         │  ┌───────────┐  │         │  ┌───────────┐  │
│  │  Agent    │──┼─────┐   │  │  Agent    │──┼─────┐   │  │  Agent    │──┼─────┐
│  │ (Python)  │  │     │   │  │ (Python)  │  │     │   │  │ (Python)  │  │     │
│  └───────────┘  │     │   │  └───────────┘  │     │   │  └───────────┘  │     │
│                 │     │   │                 │     │   │                 │     │
│  Reads local    │     │   │  Reads local    │     │   │  Reads local    │     │
│  event logs     │     │   │  syslog/journald│     │   │  event logs     │     │
└─────────────────┘     │   └─────────────────┘     │   └─────────────────┘     │
                        │                           │                           │
                        │   Sends JSON events       │                           │
                        └───────────────────────────┼───────────────────────────┘
                                    │               │
                                    ▼               ▼
                        ┌────────────────────────────────┐
                        │    Central Server (Rust)       │
                        │                                │
                        │  • Receives events from agents │
                        │  • Stores event data           │
                        │  • Provides web dashboard      │
                        │  • Tracks issues per device    │
                        └────────────────────────────────┘
```

## Dependencies

### For the Server (Central Monitoring Machine)
- Rust and Cargo
- Network access from all monitored machines

### For the Agent (On Each Monitored Machine)
- Python 3.7 or higher
- Administrator/root access (to read system logs)
- Network access to the central server

Optional Python libraries (the agent works without these, but they're recommended):
- `toml` - Better configuration parsing (falls back to built-in parser)
- `requests` - Better HTTP handling (falls back to urllib)

## Installation

### Server Setup

```bash
# Navigate to server directory
cd server

# Build the server
cargo build --release

# Copy and configure the server settings
cp ../config/server.example.toml ../config/server.toml
# Edit server.toml and set bind_address (e.g., 0.0.0.0:8080 for LAN access)
nano ../config/server.toml

# Run the server
cargo run --release
```

For systemd installation on Linux:
```bash
sudo ./scripts/install_loglumen_server.sh
```

### Agent Setup (On Each Monitored Machine)

```bash
# Navigate to agent directory
cd agent

# Install optional Python dependencies (recommended but not required)
pip install toml requests

# Copy and configure the agent settings
cp ../config/agent.example.toml ../config/agent.toml
# Edit agent.toml - see Configuration section below
nano ../config/agent.toml

# Run the agent
python main.py
```

For systemd installation on Linux:
```bash
sudo ./scripts/install_loglumen_agent.sh
```

For Windows installation:
```powershell
# Run PowerShell as Administrator
.\scripts\windows\install_loglumen_agent.ps1
```

## Usage

### Starting the Server

Once the server is running, connect to the web dashboard by opening a browser and going to `http://<server-ip>:8080/`. For example:
- Local development: `http://127.0.0.1:8080/`
- On your network: `http://192.168.1.10:8080/`

The dashboard displays:
- Total event count across all machines
- Events grouped by category (authentication, privilege escalation, etc.)
- Per-host statistics and event counts
- Recent events with timestamps and severity levels
- Filtering by host or category

### Running the Agent

The agent has several run modes:

```bash
# Run continuously (daemon mode) - for production
python main.py

# Run once and exit - for testing
python main.py --once

# Test mode - collect but don't send events
python main.py --test

# Dry run - show what would be collected without sending
python main.py --dry-run

# Specify custom config file
python main.py --config /path/to/config.toml
```

**Important**: The agent requires administrator/root privileges to read system logs:
- **Linux**: Run with `sudo python main.py`
- **Windows**: Run PowerShell or Command Prompt as Administrator

### Testing Individual Collectors

You can test individual event collectors before running the full agent:

```bash
cd agent/collectors

# Test Linux collectors
sudo python linux/auth_unified.py    # Authentication, privilege, and remote access events
sudo python linux/system.py          # System crashes and kernel panics
sudo python linux/service.py         # Service failures
sudo python linux/software.py        # Package installations and updates

# Test Windows collectors (run as Administrator)
python windows/auth.py               # Authentication events
python windows/privilege.py          # Privilege escalation
python windows/system.py             # System crashes
python windows/service.py            # Service failures
python windows/software.py           # Software installations
python windows/remote.py             # Remote access (RDP)
```

## Configuration

This application uses TOML configuration files. Two files are needed:
- `config/server.toml` - For the central server
- `config/agent.toml` - For each monitored machine's agent

### Server Configuration (config/server.toml)

The server configuration is minimal and has one main section:

#### [server]

The `[server]` section has one variable: `bind_address` (string).

The `bind_address` variable sets the IP address and port the server listens on. Use `0.0.0.0:8080` to accept connections from any machine on the network, or `127.0.0.1:8080` to only accept local connections (for testing).

You can also override this with the `LOGLUMEN_BIND_ADDRESS` environment variable if needed.

Example:
```toml
[server]
bind_address = "0.0.0.0:8080"
```

### Agent Configuration (config/agent.toml)

The agent configuration controls how the log collection agent behaves on each monitored machine. There are four sections:

- `[agent]`
- `[server]`
- `[collection]`
- `[logging]`

#### [agent]

The `[agent]` section has three variables:

- `client_name` (string) - A unique identifier for this machine
- `client_ipv4` (string, optional) - IPv4 address of this machine (auto-detected if not specified)
- `os` (string, optional) - Operating system: "linux" or "windows" (auto-detected if not specified)

The `client_name` is how this machine will appear in the dashboard. Use something descriptive like "office-pc-01" or "web-server-prod".

The `client_ipv4` is auto-detected from your network interface, but you can override it if the auto-detection picks the wrong interface.

The `os` is auto-detected from Python's platform detection, but you can override it for testing purposes.

Example:
```toml
[agent]
client_name = "dev-machine-01"
# client_ipv4 = "192.168.1.100"  # Optional: auto-detected
# os = "linux"                   # Optional: auto-detected
```

#### [server]

The `[server]` section tells the agent where to send events. It has seven variables:

- `server_ip` (string, required) - IP address or hostname of the Loglumen server
- `server_port` (integer, required) - Port the server listens on
- `use_https` (boolean) - Use HTTPS for secure communication (default: false)
- `api_path` (string) - API endpoint path (default: "/api/events")
- `api_key` (string, optional) - API key for authentication (not currently enforced)
- `timeout` (integer) - Connection timeout in seconds (default: 30)
- `max_retries` (integer) - Number of retry attempts on failure (default: 3)
- `retry_delay` (integer) - Seconds to wait between retries (default: 5)

The `server_ip` should be the IP address or hostname where your central Loglumen server is running.

The `use_https` variable determines whether to use HTTP or HTTPS. For production deployments across the internet, you should set this to `true` and configure SSL certificates.

Example:
```toml
[server]
server_ip = "192.168.0.254"
server_port = 8080
use_https = false
api_path = "/api/events"
timeout = 30
max_retries = 3
retry_delay = 5
```

#### [collection]

The `[collection]` section controls what events are collected and how often. It has five variables:

- `collection_interval` (integer) - How often to collect events in seconds (default: 60)
- `max_lines_per_log` (integer) - Maximum lines to process per log file (default: 1000)
- `hours_lookback` (integer) - For journald-based collectors, how many hours back to search (default: 1)
- `enabled_categories` (array) - Which event categories to collect
- `max_events_per_batch` (integer) - Maximum events to send in a single batch (default: 500)

The `collection_interval` sets how frequently the agent runs. If you set it to 60, the agent will collect and send events every 60 seconds. For high-security environments, you might want a shorter interval like 30 seconds. For less critical systems, you might use 300 (5 minutes).

The `enabled_categories` variable is an array of event types to monitor. Valid categories are:
- `"authentication"` - Login attempts, failures, account lockouts
- `"privilege_escalation"` - Users gaining admin/root privileges
- `"remote_access"` - SSH, RDP connections
- `"system"` - Kernel panics, blue screens, OOM kills
- `"service"` - Service crashes and failures
- `"software"` - Package installations, updates, removals

You can also use short aliases: `"auth"`, `"privilege"`, `"remote"`.

If you only care about authentication and system crashes, you could set this to `["authentication", "system"]`.

Example:
```toml
[collection]
collection_interval = 60
max_lines_per_log = 1000
hours_lookback = 1
enabled_categories = ["authentication", "privilege_escalation", "remote_access", "system", "service", "software"]
max_events_per_batch = 500
```

#### [logging]

The `[logging]` section controls logging for the agent itself (not the events it collects). It has five variables:

- `log_level` (string) - Logging verbosity: "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL" (default: "INFO")
- `log_file` (string) - Where to write agent logs
- `log_to_console` (boolean) - Whether to also print logs to console (default: true)
- `max_log_size_mb` (integer) - Rotate logs when they reach this size in MB (default: 10)
- `max_log_files` (integer) - Keep this many old log files (default: 5)

The `log_level` variable determines how much detail you get. Use "DEBUG" when troubleshooting, "INFO" for normal operation, and "WARNING" or "ERROR" for production systems where you only want to see problems.

Example:
```toml
[logging]
log_level = "INFO"
log_file = "/var/log/loglumen-agent.log"  # Linux
# log_file = "C:\\ProgramData\\Loglumen\\agent.log"  # Windows
log_to_console = true
max_log_size_mb = 10
max_log_files = 5
```

## Example Complete Configuration Files

### Server Configuration (config/server.toml)

```toml
[server]
# Bind to all interfaces on port 8080
bind_address = "0.0.0.0:8080"
```

### Agent Configuration (config/agent.toml)

```toml
[agent]
client_name = "office-server-01"
# client_ipv4 = "192.168.1.50"  # Auto-detected

[server]
server_ip = "192.168.1.10"
server_port = 8080
use_https = false
api_path = "/api/events"
timeout = 30
max_retries = 3
retry_delay = 5

[collection]
collection_interval = 60
max_lines_per_log = 1000
hours_lookback = 1
enabled_categories = ["authentication", "privilege_escalation", "remote_access", "system", "service", "software"]
max_events_per_batch = 500

[logging]
log_level = "INFO"
log_file = "/var/log/loglumen-agent.log"
log_to_console = true
max_log_size_mb = 10
max_log_files = 5
```

## What Events Are Monitored?

Loglumen tracks six categories of security-important events:

1. **Authentication** - Login attempts, failures, account lockouts
2. **Privilege Escalation** - User permission changes, sudo/su usage, account modifications
3. **System Crashes** - Kernel panics, blue screens, critical failures, OOM kills
4. **Service Issues** - Service crashes, daemon restarts, application failures
5. **Software Changes** - Installations, updates, removals (via apt, dpkg, yum, Windows installers)
6. **Remote Access** - RDP connections, SSH logins, VPN access

See `agent/collectors/README.md` for detailed information on each event type and what log sources are used.

## Project Structure

```
loglumen/
├── agent/              # Python code that runs on each monitored machine
│   ├── collectors/     # Log parsing scripts for different event types
│   │   ├── windows/    # Windows-specific collectors
│   │   └── linux/      # Linux-specific collectors
│   ├── main.py         # Main agent entry point
│   ├── config_loader.py # Configuration management
│   └── sender.py       # HTTP client for sending events
│
├── server/             # Rust server that receives and displays events
│   ├── src/
│   │   └── main.rs     # Server entry point
│   ├── static/         # Web dashboard files
│   └── Cargo.toml      # Rust dependencies
│
├── config/             # Configuration files
│   ├── agent.example.toml   # Template for agent configuration
│   └── server.example.toml  # Template for server configuration
│
├── deploy/             # Deployment scripts and systemd files
└── scripts/            # Installation scripts
```

## Troubleshooting

### Agent Can't Connect to Server
1. Check `server_ip` and `server_port` are correct in `config/agent.toml`
2. Verify the server is running: `curl http://192.168.1.10:8080/api/stats`
3. Check firewall rules allow connections on port 8080
4. Ensure `use_https` matches your server configuration

### Permission Denied Errors
The agent needs administrator/root access to read system logs:
- **Linux**: Run with `sudo python main.py`
- **Windows**: Run PowerShell/Command Prompt as Administrator

### No Events Being Collected
1. Run the agent in dry-run mode: `python main.py --dry-run`
2. Check that your user has permission to read log files
3. Verify events exist in the time window (default: last 1 hour)
4. Check `enabled_categories` in config matches the events you expect
5. Test individual collectors directly (see Testing Individual Collectors)

### Events Not Appearing in Dashboard
1. Check the agent successfully sent events (look for "SUCCESS" in agent output)
2. Verify the server received them: `curl http://192.168.1.10:8080/api/events`
3. Refresh the dashboard page
4. Check browser console for JavaScript errors

## To-Do / Future Enhancements

- [ ] Add persistent database storage (SQLite/PostgreSQL) instead of in-memory
- [ ] Implement API key authentication and validation
- [ ] Add email/Slack/webhook alerting for critical events
- [ ] Create event correlation and anomaly detection
- [ ] Add support for custom log sources and parsers
- [ ] Implement log retention policies and automatic cleanup
- [ ] Add TLS/HTTPS support for the server
- [ ] Create pre-built binaries and packages for easy installation
- [ ] Add support for macOS agents
- [ ] Implement role-based access control for the dashboard
- [ ] Add event export functionality (CSV, JSON, SIEM format)
- [ ] Create a dark theme for the dashboard

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Getting Help

- See `agent/collectors/README.md` for detailed collector implementation guide
- See `config/README.md` for configuration options
- See `CLAUDE.md` for development guidance and architecture details
