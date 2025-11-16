# Loglumen

A lightweight SIEM (Security Information and Event Management) system that helps you monitor security events across all your Windows and Linux machines from one central dashboard.

## What Problem Does This Solve?

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

## How It Works

### Step 1: Agent Collects Logs (Python)
On each monitored machine, a Python agent runs that:
1. Reads system log files (Windows Event Logs or Linux syslogs)
2. Filters for important security events (logins, crashes, privilege changes, etc.)
3. Converts events to a standardized JSON format
4. Sends the JSON to the central server

### Step 2: Server Aggregates & Displays (Rust)
The central server:
1. Receives JSON events from all agents
2. Stores the events in a database
3. Analyzes which machines have issues
4. Displays everything in a web dashboard

## Quick Start

### Prerequisites
- **For Agent (on monitored machines):**
  - Python 3.7 or higher
  - Administrator/root access (to read system logs)

- **For Server (on central monitoring machine):**
  - Rust and Cargo
  - Network access from all monitored machines

### 1. Set Up the Server

```bash
# Navigate to server directory
cd server

# Build the server
cargo build --release

# Copy and configure the server settings
cp ../config/server.example.toml ../config/server.toml
# Edit server.toml with your preferences

# Run the server
cargo run --release
```

The server will start and listen for incoming events from agents.

### 2. Set Up Agents on Each Machine

```bash
# Navigate to agent directory
cd agent

# Install Python dependencies (if any are added later)
pip install -r requirements.txt  # (currently no dependencies)

# Copy and configure the agent settings
cp ../config/agent.example.toml ../config/agent.toml
# Edit agent.toml to set:
#   - server_ip: IP address of your central server
#   - client_name: A unique name for this machine
#   - client_ip: IP address of this machine

# Run the agent
python main.py  # (once implemented)
```

The agent will start monitoring logs and sending events to the server.

## What Events Are Monitored?

Loglumen tracks six categories of security-important events:

1. **Authentication** - Login attempts, failures, account lockouts
2. **Privilege Escalation** - User permission changes, account modifications
3. **System Crashes** - Kernel panics, blue screens, critical failures
4. **Service Issues** - Service crashes, daemon restarts, application failures
5. **Software Changes** - Installations, updates, removals
6. **Remote Access** - RDP connections, VPN logins, SSH access

See `agent/collectors/README.md` for detailed information on each event type.

## Project Structure

```
loglumen/
├── agent/              # Python code that runs on each monitored machine
│   ├── collectors/     # Log parsing scripts for different event types
│   │   ├── windows/    # Windows-specific collectors
│   │   └── linux/      # Linux-specific collectors
│   └── main.py         # Main agent entry point (to be implemented)
│
├── server/             # Rust server that receives and displays events
│   ├── src/
│   │   └── main.rs     # Server entry point
│   └── Cargo.toml      # Rust dependencies
│
├── config/             # Configuration files
│   ├── agent.example.toml   # Template for agent configuration
│   └── server.example.toml  # Template for server configuration
│
├── deploy/             # Deployment scripts and Docker files
├── scripts/            # Utility scripts
└── docs/               # Additional documentation
```

## For Collaborators New to Python

### Running Python Files
```bash
# Run a Python script
python script_name.py

# Or on some systems
python3 script_name.py
```

### Installing Python Packages
```bash
# Install from requirements file
pip install -r requirements.txt

# Install a specific package
pip install package_name
```

### Common Python Concepts You'll See
- **Imports**: `import os` - brings in functionality from other files/libraries
- **Functions**: `def function_name():` - reusable blocks of code
- **Dictionaries**: `{"key": "value"}` - Python's version of JSON objects
- **Lists**: `[1, 2, 3]` - ordered collections of items

## Next Steps

1. **Implement Agent Collectors**: Write Python scripts in `agent/collectors/windows/` and `agent/collectors/linux/` to parse specific log files
2. **Implement Server API**: Build the Rust server to receive JSON events
3. **Add Database**: Store events in a database (SQLite, PostgreSQL, etc.)
4. **Build Web Dashboard**: Create a web interface to view events
5. **Add Deployment Scripts**: Create Docker containers for easy deployment

## Getting Help

- See `agent/collectors/README.md` for detailed collector implementation guide
- See `config/README.md` for configuration options
- See `CLAUDE.md` for development guidance
