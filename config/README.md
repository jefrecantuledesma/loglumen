# Configuration

This folder contains configuration files for both the server and agent components. Configuration files use TOML format, which is easy to read and edit.

## Quick Start

### For the Server
```bash
# Copy the example configuration
cp config/server.example.toml config/server.toml

# Edit with your settings
nano config/server.toml  # or use any text editor
```

### For the Agent
```bash
# Copy the example configuration
cp config/agent.example.toml config/agent.toml

# Edit with your settings
nano config/agent.toml  # or use any text editor
```

## Agent Configuration (agent.toml)

The agent configuration controls how the log collection agent behaves on each monitored machine.

### Example Configuration

```toml
[agent]
# Unique name for this machine (use hostname or descriptive name)
client_name = "OFFICE-PC-01"

# IP address of this machine
client_ipv4 = "192.168.1.100"

# Operating system (auto-detected, but can override)
# Valid values: "windows", "linux"
os = "windows"

[server]
# IP address or hostname of the central Loglumen server
server_ip = "192.168.1.10"

# Port the server listens on
server_port = 8080

# Use HTTPS for secure communication (recommended for production)
use_https = false

# API endpoint path
api_path = "/api/events"

[collection]
# How often to collect events (in seconds)
collection_interval = 60

# Which event categories to collect
# Valid categories: auth, privilege, system, service, software, remote
enabled_categories = ["auth", "privilege", "system", "service", "software", "remote"]

# Maximum events to send per batch
max_events_per_batch = 100

[logging]
# Log level for the agent itself
# Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = "INFO"

# Where to write agent logs
log_file = "/var/log/loglumen-agent.log"  # Linux
# log_file = "C:\\ProgramData\\Loglumen\\agent.log"  # Windows

# Rotate logs when they reach this size (in MB)
max_log_size_mb = 10

# Keep this many old log files
max_log_files = 5
```

### Configuration Fields Explained

#### [agent] Section
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `client_name` | string | Yes | Unique identifier for this machine | `"OFFICE-PC-01"` |
| `client_ipv4` | string | Yes | IPv4 address of this machine | `"192.168.1.100"` |
| `os` | string | No | Operating system (auto-detected if omitted) | `"windows"` or `"linux"` |

#### [server] Section
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `server_ip` | string | Yes | IP or hostname of central server | `"192.168.1.10"` or `"loglumen.company.com"` |
| `server_port` | integer | Yes | Port server listens on | `8080` |
| `use_https` | boolean | No | Use HTTPS instead of HTTP | `true` or `false` |
| `api_path` | string | No | API endpoint path | `"/api/events"` |

#### [collection] Section
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `collection_interval` | integer | No | Seconds between collections (default: 60) | `60` |
| `enabled_categories` | array | No | Which event types to collect | `["auth", "system"]` |
| `max_events_per_batch` | integer | No | Max events per transmission | `100` |

#### [logging] Section
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `log_level` | string | No | Logging verbosity (default: INFO) | `"DEBUG"` |
| `log_file` | string | No | Where to write agent logs | `"/var/log/loglumen.log"` |
| `max_log_size_mb` | integer | No | Log rotation size in MB | `10` |
| `max_log_files` | integer | No | Number of old logs to keep | `5` |

### Finding Your Machine's IP Address

**Windows:**
```cmd
ipconfig
```
Look for "IPv4 Address" under your active network adapter.

**Linux:**
```bash
ip addr show
# or
hostname -I
```

### Testing Your Configuration

```bash
# Validate the TOML syntax
python -c "import toml; print(toml.load('config/agent.toml'))"
```

## Server Configuration (server.toml)

The server configuration controls how the central Loglumen server operates.

### Example Configuration

```toml
[server]
# IP address to bind to (0.0.0.0 = all interfaces)
bind_ip = "0.0.0.0"

# Port to listen on
port = 8080

# Maximum concurrent connections
max_connections = 100

[database]
# Database type: sqlite, postgres, mysql
db_type = "sqlite"

# For SQLite: path to database file
db_path = "/var/lib/loglumen/events.db"

# For PostgreSQL/MySQL: connection string
# db_connection = "postgresql://user:password@localhost/loglumen"

[storage]
# How long to keep events (in days)
retention_days = 90

# Automatically delete old events
auto_cleanup = true

# Run cleanup at this hour (24-hour format)
cleanup_hour = 2

[ui]
# Enable web dashboard
enable_dashboard = true

# Dashboard port (can be same as server port)
dashboard_port = 8080

# Dashboard theme: light, dark, auto
theme = "auto"

# Refresh interval for dashboard (seconds)
refresh_interval = 30

[alerts]
# Enable email alerts
enable_email = false

# SMTP server settings
smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_username = "alerts@company.com"
smtp_password = "your-password"

# Alert recipients
alert_recipients = ["admin@company.com", "security@company.com"]

# Alert on these severity levels
alert_on_severity = ["error", "critical"]

[logging]
# Server log level
log_level = "INFO"

# Server log file
log_file = "/var/log/loglumen-server.log"

# Log rotation settings
max_log_size_mb = 50
max_log_files = 10
```

### Server Configuration Fields Explained

#### [server] Section
| Field | Type | Required | Description | Default |
|-------|------|----------|-------------|---------|
| `bind_ip` | string | Yes | IP to bind to (`0.0.0.0` for all) | `"0.0.0.0"` |
| `port` | integer | Yes | Port to listen on | `8080` |
| `max_connections` | integer | No | Maximum concurrent connections | `100` |

#### [database] Section
| Field | Type | Required | Description | Default |
|-------|------|----------|-------------|---------|
| `db_type` | string | Yes | Database type | `"sqlite"` |
| `db_path` | string | For SQLite | Path to SQLite database | `"/var/lib/loglumen/events.db"` |
| `db_connection` | string | For Postgres/MySQL | Database connection string | N/A |

#### [storage] Section
| Field | Type | Required | Description | Default |
|-------|------|----------|-------------|---------|
| `retention_days` | integer | No | Days to keep events | `90` |
| `auto_cleanup` | boolean | No | Automatically delete old events | `true` |
| `cleanup_hour` | integer | No | Hour to run cleanup (0-23) | `2` |

#### [ui] Section
| Field | Type | Required | Description | Default |
|-------|------|----------|-------------|---------|
| `enable_dashboard` | boolean | No | Enable web dashboard | `true` |
| `dashboard_port` | integer | No | Dashboard port | `8080` |
| `theme` | string | No | UI theme (light/dark/auto) | `"auto"` |
| `refresh_interval` | integer | No | Dashboard refresh (seconds) | `30` |

## TOML Format Basics (For Beginners)

TOML (Tom's Obvious, Minimal Language) is a simple configuration file format.

### Basic Syntax

```toml
# Comments start with #

# String values use quotes
name = "value"

# Numbers don't use quotes
port = 8080

# Booleans are lowercase
enabled = true
disabled = false

# Arrays use square brackets
categories = ["auth", "system", "service"]

# Sections use [headers]
[section_name]
setting1 = "value1"
setting2 = "value2"

[another_section]
setting3 = "value3"
```

### Common Mistakes

- ❌ Forgetting quotes around strings: `name = value` (wrong)
- ✅ Correct: `name = "value"`

- ❌ Using quotes around numbers: `port = "8080"` (wrong)
- ✅ Correct: `port = 8080`

- ❌ Capitalizing booleans: `enabled = True` (wrong)
- ✅ Correct: `enabled = true`

## Security Best Practices

1. **Protect Config Files**: These files may contain sensitive information
   ```bash
   # Linux: Make config readable only by root
   sudo chmod 600 /etc/loglumen/agent.toml
   ```

2. **Use HTTPS in Production**: Set `use_https = true` when deploying
   ```toml
   [server]
   use_https = true
   ```

3. **Don't Commit Passwords**: Never commit actual config files to Git
   - Use `.example.toml` files as templates
   - Add `*.toml` to `.gitignore` (except `*.example.toml`)

4. **Rotate Credentials**: Change passwords and tokens regularly

## Troubleshooting

### Agent Can't Connect to Server
1. Check `server_ip` and `server_port` are correct
2. Verify server is running: `telnet 192.168.1.10 8080`
3. Check firewall rules allow the connection
4. Ensure `use_https` matches server configuration

### Invalid Configuration
1. Validate TOML syntax:
   ```bash
   python -c "import toml; toml.load('config/agent.toml')"
   ```
2. Check for typos in field names
3. Ensure values have correct types (string vs integer vs boolean)

### Permission Denied
1. Agent needs admin/root access to read system logs
2. Run agent with elevated privileges:
   ```bash
   # Linux
   sudo python main.py

   # Windows (Run as Administrator)
   python main.py
   ```

## Example Deployment Scenarios

### Small Office (1 server, 10 clients)
**Server config:**
```toml
[server]
bind_ip = "0.0.0.0"
port = 8080

[database]
db_type = "sqlite"
db_path = "/var/lib/loglumen/events.db"

[storage]
retention_days = 30
```

**Agent config:**
```toml
[server]
server_ip = "192.168.1.10"
server_port = 8080
use_https = false

[collection]
collection_interval = 300  # Every 5 minutes
```

### Enterprise (1 server, 1000+ clients)
**Server config:**
```toml
[server]
bind_ip = "0.0.0.0"
port = 443

[database]
db_type = "postgres"
db_connection = "postgresql://loglumen:password@db-server:5432/loglumen"

[storage]
retention_days = 365  # 1 year

[alerts]
enable_email = true
alert_on_severity = ["critical"]
```

**Agent config:**
```toml
[server]
server_ip = "loglumen.company.com"
server_port = 443
use_https = true

[collection]
collection_interval = 60  # Every minute
max_events_per_batch = 500
```

