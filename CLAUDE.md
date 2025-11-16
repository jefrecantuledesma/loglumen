# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Loglumen is a SIEM (Security Information and Event Management) system that aggregates important log notifications from Windows and Linux systems, sending them to a centralized server for easy viewing.

**Architecture:**
- **Agent (Python)**: Client-side log collection code that parses Windows/Linux log files, extracts relevant information, aggregates it into JSON event structures, and sends to the server
- **Server (Rust)**: Log-parsing front-end that receives events, tracks which devices are having specific issues, and displays information to users

## Directory Structure

```
/agent              - Python log collecting code
  /collectors       - Individual log-parsing scripts
    /windows        - Windows log collectors
    /linux          - Linux log collectors
/server             - Rust server (Cargo project)
/config             - Configuration files
/deploy             - Deployment scripts (Docker files, etc.)
/scripts            - Utility scripts
/docs               - Documentation
```

## Development Commands

### Server (Rust)
```bash
# Build the server
cd server && cargo build

# Run the server
cd server && cargo run

# Run tests
cd server && cargo test
```

### Agent (Python)
The agent is written in Python but currently has no package configuration files set up.

## Event Collection

The agent collects six categories of security-relevant events:

1. **Logins and auth failures** - Authentication attempts and failures
2. **Privilege escalations and account changes** - User account modifications
3. **System and kernel panics** - Critical system failures
4. **Service, daemon, and app crashes/restarts** - Service stability issues
5. **Software installs, updates, and removals** - Software lifecycle events
6. **Remote access and network-related logs** - RDP, VPN, and remote access events

### Event JSON Schema

All events follow this standardized structure:

```json
{
  "schema_version": 1,
  "category": "auth|privilege|system|service|software|remote",
  "event_type": "login_failed|login_success|crash|etc",
  "time": "2025-11-16T18:42:51Z",
  "host": "DESKTOP-1234",
  "host_ipv4": "192.0.2.10",
  "os": "windows|linux",
  "source": "Security|System|Application",
  "severity": "info|warning|error|critical",
  "message": "Human-readable description",
  "data": {
    // Event-specific fields
  }
}
```

## Configuration

- **Agent config**: `config/agent.example.toml` - Configure server IP, client name, client IP
- **Server config**: `config/server.example.toml` - Configure data retention, UI settings

Copy example configs and modify as needed for deployment.

## Windows Event Log Locations

Key Windows event log paths the agent monitors:
- Security events: `C:\Windows\System32\winevt\Logs\Security.evtx`
- System events: `C:\Windows\System32\winevt\Logs\System.evtx`
- Application events: `C:\Windows\System32\winevt\Logs\Application.evtx`
- Windows Update: `C:\Windows\Logs\WindowsUpdate\`
- Crash dumps: `C:\Windows\Minidump\`, `C:\Windows\MEMORY.DMP`
- Terminal Services: `Applications and Services Logs → Microsoft → Windows → TerminalServices-*`

## Key Event IDs

When working with Windows event collectors:
- 4624/4625: Logon success/failure
- Logon Type 10 or 7: Remote/RDP logons
- Event Viewer paths documented in `agent/collectors/README.md`
