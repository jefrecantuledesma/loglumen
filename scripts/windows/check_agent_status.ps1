# Check Loglumen Agent Status
# This script checks if the agent is running and shows recent logs

param(
    [string]$TaskName = "LoglumenAgent"
)

Write-Host "=" * 70
Write-Host "Loglumen Agent Status Check"
Write-Host "=" * 70

# Check scheduled task status
Write-Host "`n[1] Checking scheduled task status..."
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($task) {
    Write-Host "    Task Name: $($task.TaskName)"
    Write-Host "    State: $($task.State)"
    Write-Host "    Last Run: $($task.LastRunTime)"
    Write-Host "    Last Result: $($task.LastTaskResult)"

    if ($task.State -eq "Running") {
        Write-Host "    [OK] Task is currently running"
    } elseif ($task.State -eq "Ready") {
        Write-Host "    [WARNING] Task is ready but not running"
    } else {
        Write-Host "    [WARNING] Task state: $($task.State)"
    }
} else {
    Write-Host "    [ERROR] Scheduled task '$TaskName' not found"
    exit 1
}

# Check if Python process is running
Write-Host "`n[2] Checking for running Python agent process..."
$agentProcesses = Get-Process | Where-Object {
    $_.ProcessName -eq "python" -or $_.ProcessName -eq "py"
} | Where-Object {
    $_.CommandLine -like "*main.py*" -or $_.Path -like "*agent*"
}

if ($agentProcesses) {
    Write-Host "    [OK] Found $($agentProcesses.Count) agent process(es)"
    foreach ($proc in $agentProcesses) {
        Write-Host "        PID: $($proc.Id)"
        Write-Host "        Started: $($proc.StartTime)"
        Write-Host "        CPU Time: $($proc.CPU)s"
        Write-Host "        Memory: $([math]::Round($proc.WorkingSet64/1MB, 2)) MB"
    }
} else {
    Write-Host "    [WARNING] No Python agent process found"
    Write-Host "    The task may have failed to start or exited with an error"
}

# Check task history for errors
Write-Host "`n[3] Checking recent task history..."
$taskHistory = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue

if ($taskHistory) {
    Write-Host "    Number of Missed Runs: $($taskHistory.NumberOfMissedRuns)"
    Write-Host "    Next Run Time: $($taskHistory.NextRunTime)"
}

# Try to read agent log file if it exists
Write-Host "`n[4] Checking for agent log files..."
$possibleLogPaths = @(
    "C:\ProgramData\Loglumen\agent.log",
    "C:\ProgramData\Loglumen\logs\agent.log",
    "$env:TEMP\loglumen_agent.log"
)

$foundLog = $false
foreach ($logPath in $possibleLogPaths) {
    if (Test-Path $logPath) {
        Write-Host "    [OK] Found log file: $logPath"
        Write-Host "`n    Last 20 lines:"
        Write-Host "    " + ("-" * 66)
        Get-Content $logPath -Tail 20 | ForEach-Object {
            Write-Host "    $_"
        }
        $foundLog = $true
        break
    }
}

if (-not $foundLog) {
    Write-Host "    [INFO] No log files found at standard locations"
    Write-Host "    The agent may be logging to console or a different location"
}

# Check Event Viewer for task execution
Write-Host "`n[5] Checking Windows Event Log for task execution..."
$taskEvents = Get-WinEvent -FilterHashtable @{
    LogName='Microsoft-Windows-TaskScheduler/Operational'
    ID=100,102,107,110,111,200,201
} -MaxEvents 10 -ErrorAction SilentlyContinue | Where-Object {
    $_.Message -like "*$TaskName*"
}

if ($taskEvents) {
    Write-Host "    [OK] Found $($taskEvents.Count) recent task events"
    Write-Host "`n    Most recent events:"
    foreach ($evt in $taskEvents | Select-Object -First 5) {
        Write-Host "        [$($evt.TimeCreated)] Event $($evt.Id): $($evt.Message.Split("`n")[0])"
    }
} else {
    Write-Host "    [INFO] No recent task scheduler events found"
}

# Summary and recommendations
Write-Host "`n" + ("=" * 70)
Write-Host "SUMMARY"
Write-Host "=" * 70

if ($task.State -eq "Running" -and $agentProcesses) {
    Write-Host "[OK] Agent appears to be running correctly"
    Write-Host "`nTo check server communication:"
    Write-Host "  1. Check the server logs to see if it's receiving events"
    Write-Host "  2. Verify network connectivity to the server"
    Write-Host "  3. Check config file: C:\ProgramData\Loglumen\agent.toml"
} elseif ($task.State -eq "Ready" -and -not $agentProcesses) {
    Write-Host "[WARNING] Task is ready but no process is running"
    Write-Host "`nTroubleshooting steps:"
    Write-Host "  1. Check Event Viewer for errors"
    Write-Host "  2. Try running manually: Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "  3. Check if Python is accessible by SYSTEM account"
} else {
    Write-Host "[ERROR] Agent may not be running correctly"
    Write-Host "`nTroubleshooting steps:"
    Write-Host "  1. Review Event Viewer logs above"
    Write-Host "  2. Try running the agent manually to see errors"
    Write-Host "  3. Check the scheduled task configuration"
}

Write-Host "`n" + ("=" * 70)
