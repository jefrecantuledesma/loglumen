# Loglumen Agent Testing Guide

## Quick Start: Check if Agent is Communicating with Server

### Option 1: Run the Test Script (Recommended)

This script will run the agent for 30 seconds and show you all output:

```powershell
cd "scripts\windows"
.\test_agent_communication.ps1
```

### Option 2: Manual Testing

1. **Check if server is running** - The server should be running on `192.168.0.254:8080`
   ```powershell
   Test-NetConnection -ComputerName 192.168.0.254 -Port 8080
   ```

2. **Run the agent manually** to see real-time output:
   ```powershell
   cd agent
   py main.py --config "..\config\agent.toml"
   ```

   You should see output like:
   ```
   [INFO] Collecting events from 4 categories...
   [INFO] Operating System: Windows
     [OK] Auth: 15 events
     [OK] Privilege: 3 events
     [OK] System: 0 events
     [OK] Service: 5 events
     [OK] Software: 12 events
     [OK] Remote: 0 events
   [INFO] Collected 35 events total
   [INFO] Sending 35 events to server...
   [OK] Successfully sent 35 events to http://192.168.0.254:8080/api/events
   ```

3. **Check server logs** - On the server machine, you should see incoming events being logged

### Option 3: Check the Scheduled Task

If you installed the agent as a Windows service:

1. **Check task status:**
   ```powershell
   Get-ScheduledTask -TaskName "LoglumenAgent"
   Start-ScheduledTask -TaskName "LoglumenAgent"  # Start it if needed
   ```

2. **View task history:**
   ```powershell
   Get-ScheduledTaskInfo -TaskName "LoglumenAgent"
   ```

3. **Check if Python process is running:**
   ```powershell
   Get-Process python* | Where-Object { $_.CommandLine -like "*main.py*" }
   ```

## Understanding the Output

### Agent Collection Logs

The agent prints status for each collector:
- `[OK] Auth: X events` - Successful collection
- `[ERROR] Auth collector failed:` - Error occurred
- `[INFO] Sending X events to server...` - Attempting to send
- `[OK] Successfully sent X events` - Server received the events
- `[ERROR] Failed to send events:` - Connection or server error

### Server Communication Errors

If you see errors like:
```
[ERROR] Failed to send events: Connection refused
```

**Troubleshooting:**
1. Make sure the server is running
2. Check the server IP/port in `config\agent.toml`
3. Verify firewall settings allow connection to port 8080
4. Test connectivity: `Test-NetConnection -ComputerName 192.168.0.254 -Port 8080`

If you see:
```
[ERROR] Failed to send events: HTTP 500 Internal Server Error
```

The server is reachable but encountered an error processing your events. Check the server logs.

## Configuration

Edit `config\agent.toml` to change:
- **Server IP/Port**: Where to send events
- **Collection interval**: How often to collect (in seconds)
- **Enabled categories**: Which types of events to collect
- **Log level**: Amount of debugging output

## Next Steps

Once you confirm the agent is collecting and sending events:

1. **View events on the server** - Use the Rust server's web interface or API
2. **Monitor in production** - The scheduled task runs the agent continuously
3. **Tune collectors** - Adjust which events are collected in the config file
4. **Set up multiple agents** - Install on other Windows/Linux machines

## Troubleshooting

### No Events Collected

If collectors return 0 events:
- **Auth events**: May need administrator privileges
- **System events**: Good news if 0 - means no crashes!
- **Service events**: Check Event Viewer to confirm there are service failures
- **Software events**: Only collects installs from last 7 days

### Permission Errors

Some collectors require administrator privileges:
- Auth events (Security log)
- Privilege escalation events
- Remote access events

Run PowerShell as Administrator when testing.

### Can't Connect to Server

1. Verify server IP in config matches your server
2. Make sure server is running: `cd server && cargo run`
3. Check Windows Firewall isn't blocking the connection
4. Try `curl http://192.168.0.254:8080/api/events` to test manually

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `install_loglumen_agent.ps1` | Install agent as Windows scheduled task |
| `test_agent_communication.ps1` | Run agent manually and check server communication |
| `check_agent_status.ps1` | Check if installed agent is running correctly |
| `verify_syntax.ps1` | Verify PowerShell script syntax |
