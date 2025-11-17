# Diagnose Installation Issues

Write-Host "=" * 70
Write-Host "Loglumen Agent Installation Diagnostic"
Write-Host "=" * 70

# 1. Check if running as admin
Write-Host "`n[1] Checking administrator privileges..."
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if ($isAdmin) {
    Write-Host "    [OK] Running as Administrator"
} else {
    Write-Host "    [ERROR] NOT running as Administrator"
    Write-Host "    The install script requires admin privileges to create scheduled tasks"
}

# 2. Check for the scheduled task
Write-Host "`n[2] Checking for scheduled task..."
$task = Get-ScheduledTask -TaskName "LoglumenAgent" -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "    [OK] Task exists"
    Write-Host "        Name: $($task.TaskName)"
    Write-Host "        State: $($task.State)"
    Write-Host "        Last Run: $($task.LastRunTime)"
    Write-Host "        Last Result: $($task.LastTaskResult)"

    # Get task details
    $taskInfo = Get-ScheduledTaskInfo -TaskName "LoglumenAgent" -ErrorAction SilentlyContinue
    if ($taskInfo) {
        Write-Host "        Next Run: $($taskInfo.NextRunTime)"
        Write-Host "        Missed Runs: $($taskInfo.NumberOfMissedRuns)"
    }

    # Get task action
    $action = $task.Actions[0]
    Write-Host "`n    Task Command:"
    Write-Host "        Execute: $($action.Execute)"
    Write-Host "        Arguments: $($action.Arguments)"
    Write-Host "        WorkingDirectory: $($action.WorkingDirectory)"
} else {
    Write-Host "    [ERROR] Task 'LoglumenAgent' not found"
    Write-Host "    The install script may have failed or not been run"
}

# 3. Check for Python processes
Write-Host "`n[3] Checking for running Python agent processes..."
$processes = Get-Process -Name python*, py -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*main.py*" -or $_.CommandLine -like "*loglumen*"
}

if ($processes) {
    Write-Host "    [OK] Found $($processes.Count) agent process(es)"
    foreach ($proc in $processes) {
        Write-Host "        PID: $($proc.Id)"
        Write-Host "        Started: $($proc.StartTime)"
        Write-Host "        CPU: $($proc.CPU)s"
        Write-Host "        Memory: $([math]::Round($proc.WorkingSet64/1MB, 2)) MB"
    }
} else {
    Write-Host "    [WARNING] No Python agent processes found"
}

# 4. Check Task Scheduler event log for recent errors
Write-Host "`n[4] Checking Task Scheduler event log (last 50 events)..."
$events = Get-WinEvent -FilterHashtable @{
    LogName='Microsoft-Windows-TaskScheduler/Operational'
    StartTime=(Get-Date).AddHours(-24)
} -MaxEvents 50 -ErrorAction SilentlyContinue

if ($events) {
    $loglumenEvents = $events | Where-Object { $_.Message -like "*Loglumen*" }

    if ($loglumenEvents) {
        Write-Host "    [INFO] Found $($loglumenEvents.Count) Loglumen-related events"
        foreach ($evt in $loglumenEvents | Select-Object -First 5) {
            Write-Host "`n    Event ID $($evt.Id) at $($evt.TimeCreated):"
            Write-Host "        $($evt.Message.Split("`n")[0])"
        }
    } else {
        Write-Host "    [INFO] No Loglumen-related events in Task Scheduler log"
        Write-Host "    This suggests the task was never registered or hasn't run"
    }

    # Check for any recent task registration events
    $regEvents = $events | Where-Object { $_.Id -eq 106 } | Select-Object -First 3
    if ($regEvents) {
        Write-Host "`n    Recent task registrations (Event ID 106):"
        foreach ($evt in $regEvents) {
            $xml = [xml]$evt.ToXml()
            $taskName = $xml.Event.EventData.Data | Where-Object { $_.Name -eq 'TaskName' } | Select-Object -ExpandProperty '#text'
            Write-Host "        $($evt.TimeCreated): $taskName"
        }
    }
} else {
    Write-Host "    [INFO] No recent Task Scheduler events"
}

# 5. Check if config file exists
Write-Host "`n[5] Checking for agent configuration..."
$configPath = "C:\ProgramData\Loglumen\agent.toml"
if (Test-Path $configPath) {
    Write-Host "    [OK] Config file exists: $configPath"
    Write-Host "`n    Config contents:"
    Get-Content $configPath | Select-String -Pattern "server_|client_|collection_interval" | ForEach-Object {
        Write-Host "        $_"
    }
} else {
    Write-Host "    [WARNING] Config file not found at $configPath"
    Write-Host "    The install script creates this file"
}

# 6. Check Python availability
Write-Host "`n[6] Checking Python installation..."
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}

if ($python) {
    $version = & $python.Source --version 2>&1
    Write-Host "    [OK] Python found: $version"
    Write-Host "        Path: $($python.Source)"
} else {
    Write-Host "    [ERROR] Python not found"
}

# 7. Try to manually test the agent
Write-Host "`n[7] Testing agent manually..."
$scriptDir = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptDir
$agentDir = Join-Path $repoRoot "agent"
$mainPy = Join-Path $agentDir "main.py"

if (Test-Path $mainPy) {
    Write-Host "    [OK] Agent main.py found at: $mainPy"
    Write-Host "`n    Attempting to run agent in test mode..."

    $testOutput = & $python.Source $mainPy --config $configPath --once 2>&1 | Out-String

    if ($testOutput -like "*Successfully sent*") {
        Write-Host "    [OK] Agent test run successful!"
    } elseif ($testOutput -like "*Failed to send*" -or $testOutput -like "*Connection*error*") {
        Write-Host "    [WARNING] Agent runs but can't connect to server"
        Write-Host "    Check that the server is running at the configured address"
    } else {
        Write-Host "    [ERROR] Agent test encountered issues"
    }

    Write-Host "`n    Agent output (last 10 lines):"
    $testOutput.Split("`n") | Select-Object -Last 10 | ForEach-Object {
        Write-Host "        $_"
    }
} else {
    Write-Host "    [ERROR] Agent main.py not found at: $mainPy"
}

# Summary
Write-Host "`n" + ("=" * 70)
Write-Host "DIAGNOSTIC SUMMARY"
Write-Host "=" * 70

if (-not $task) {
    Write-Host "`n[ISSUE] Scheduled task not found"
    Write-Host "`nPossible causes:"
    Write-Host "  1. Install script was not run"
    Write-Host "  2. Install script was not run as Administrator"
    Write-Host "  3. Install script encountered an error"
    Write-Host "`nRecommendation:"
    Write-Host "  Run the install script again from an Administrator PowerShell:"
    Write-Host "  PS> cd 'scripts\windows'"
    Write-Host "  PS> .\install_loglumen_agent.ps1"
} elseif ($task.State -ne "Running") {
    Write-Host "`n[ISSUE] Task exists but is not running"
    Write-Host "`nRecommendation:"
    Write-Host "  Start the task manually:"
    Write-Host "  PS> Start-ScheduledTask -TaskName 'LoglumenAgent'"
} else {
    Write-Host "`n[OK] Task appears to be configured and running"
    Write-Host "`nCheck server logs to see if events are being received"
}

Write-Host "`n" + ("=" * 70)
