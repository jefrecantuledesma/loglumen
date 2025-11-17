# Test Loglumen Agent Communication
# This script runs the agent manually and monitors its output

param(
    [int]$TimeoutSeconds = 30
)

Write-Host "=" * 70
Write-Host "Loglumen Agent Communication Test"
Write-Host "=" * 70

# Check if server is reachable
Write-Host "`n[1] Checking server connectivity..."
$serverIP = "192.168.0.254"
$serverPort = 8080

try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connect = $tcpClient.BeginConnect($serverIP, $serverPort, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(3000, $false)

    if ($wait) {
        $tcpClient.EndConnect($connect)
        $tcpClient.Close()
        Write-Host "    [OK] Server is reachable at ${serverIP}:${serverPort}"
    } else {
        $tcpClient.Close()
        Write-Host "    [WARNING] Server did not respond within 3 seconds"
    }
} catch {
    Write-Host "    [ERROR] Cannot connect to server: $_"
    Write-Host "    Make sure the server is running at ${serverIP}:${serverPort}"
}

# Check Python is available
Write-Host "`n[2] Checking Python..."
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}

if ($python) {
    $version = & $python.Source --version 2>&1
    Write-Host "    [OK] Python found: $version"
    Write-Host "    Path: $($python.Source)"
} else {
    Write-Host "    [ERROR] Python not found"
    exit 1
}

# Find agent directory
Write-Host "`n[3] Locating agent..."
$scriptDir = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptDir
$agentDir = Join-Path $repoRoot "agent"
$mainPy = Join-Path $agentDir "main.py"

if (Test-Path $mainPy) {
    Write-Host "    [OK] Agent found at: $agentDir"
} else {
    Write-Host "    [ERROR] Agent main.py not found at: $mainPy"
    exit 1
}

# Check config
Write-Host "`n[4] Checking configuration..."
$configPath = Join-Path $repoRoot "config\agent.toml"

if (Test-Path $configPath) {
    Write-Host "    [OK] Config found at: $configPath"
    Write-Host "`n    Configuration:"
    Get-Content $configPath | Select-String -Pattern "server_ip|server_port|collection_interval|log_level" | ForEach-Object {
        Write-Host "        $_"
    }
} else {
    Write-Host "    [WARNING] Config not found at: $configPath"
}

# Run agent
Write-Host "`n" + ("=" * 70)
Write-Host "RUNNING AGENT (${TimeoutSeconds}s timeout)"
Write-Host "=" * 70
Write-Host ""

$proc = Start-Process -FilePath $python.Source `
    -ArgumentList "`"$mainPy`" --config `"$configPath`"" `
    -WorkingDirectory $agentDir `
    -NoNewWindow `
    -PassThru `
    -RedirectStandardOutput "C:\Windows\Temp\loglumen_test_stdout.txt" `
    -RedirectStandardError "C:\Windows\Temp\loglumen_test_stderr.txt"

Write-Host "[+] Agent started with PID: $($proc.Id)"
Write-Host "[+] Monitoring for ${TimeoutSeconds} seconds..."
Write-Host "[+] Press Ctrl+C to stop early"
Write-Host ""

# Monitor for the specified time
$elapsed = 0
while ($elapsed -lt $TimeoutSeconds -and -not $proc.HasExited) {
    Start-Sleep -Seconds 2
    $elapsed += 2

    # Read stdout
    if (Test-Path "C:\Windows\Temp\loglumen_test_stdout.txt") {
        $stdout = Get-Content "C:\Windows\Temp\loglumen_test_stdout.txt" -Tail 5 -ErrorAction SilentlyContinue
        if ($stdout) {
            Write-Host "[STDOUT] $($stdout -join "`n         ")"
        }
    }

    # Read stderr
    if (Test-Path "C:\Windows\Temp\loglumen_test_stderr.txt") {
        $stderr = Get-Content "C:\Windows\Temp\loglumen_test_stderr.txt" -Tail 5 -ErrorAction SilentlyContinue
        if ($stderr) {
            Write-Host "[STDERR] $($stderr -join "`n         ")"
        }
    }

    Write-Host "    ... running ($elapsed/$TimeoutSeconds seconds)"
}

# Stop the process
if (-not $proc.HasExited) {
    Write-Host "`n[+] Stopping agent..."
    Stop-Process -Id $proc.Id -Force
}

# Show full output
Write-Host "`n" + ("=" * 70)
Write-Host "FULL OUTPUT"
Write-Host "=" * 70

Write-Host "`nSTDOUT:"
Write-Host "-" * 70
if (Test-Path "C:\Windows\Temp\loglumen_test_stdout.txt") {
    Get-Content "C:\Windows\Temp\loglumen_test_stdout.txt"
} else {
    Write-Host "(No stdout output)"
}

Write-Host "`nSTDERR:"
Write-Host "-" * 70
if (Test-Path "C:\Windows\Temp\loglumen_test_stderr.txt") {
    Get-Content "C:\Windows\Temp\loglumen_test_stderr.txt"
} else {
    Write-Host "(No stderr output)"
}

Write-Host "`n" + ("=" * 70)
Write-Host "TEST COMPLETE"
Write-Host "=" * 70

# Cleanup temp files
Remove-Item "C:\Windows\Temp\loglumen_test_stdout.txt" -ErrorAction SilentlyContinue
Remove-Item "C:\Windows\Temp\loglumen_test_stderr.txt" -ErrorAction SilentlyContinue

Write-Host "`nTo view server logs, check your Rust server console or log files."
