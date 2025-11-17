param(
    [string]$TaskName = "LoglumenAgent"
)

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "Please run this script from an elevated PowerShell session."
    exit 1
}

# Script is in scripts/windows/, need to go up 2 levels to reach repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$scriptsDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $scriptsDir
$agentDir = Join-Path $repoRoot "agent"
$configDir = Join-Path $env:ProgramData "Loglumen"
$configPath = Join-Path $configDir "agent.toml"
$defaultConfig = Join-Path $repoRoot "config\agent.toml"
$exampleConfig = Join-Path $repoRoot "config\agent.example.toml"

if (-not (Test-Path $agentDir)) {
    Write-Error "Agent directory not found at $agentDir"
    exit 1
}

if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir | Out-Null
}

if (-not (Test-Path $configPath)) {
    $sourceConfig = if (Test-Path $defaultConfig) { $defaultConfig } else { $exampleConfig }
    if (-not (Test-Path $sourceConfig)) {
        Write-Error "Unable to find agent configuration template."
        exit 1
    }
    Copy-Item $sourceConfig $configPath -Force
}

# Prefer py launcher over python command (avoids Windows Store stub)
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "Python interpreter not found in PATH. Install Python 3 and rerun."
    exit 1
}
$pythonPath = $python.Source

# Verify it's a real Python installation
$version = & $pythonPath --version 2>&1
if ($version -notmatch "Python \d+\.\d+") {
    Write-Error "Python command found but appears invalid. Output: $version"
    Write-Error "Please install Python from python.org or ensure 'py' launcher is available."
    exit 1
}

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$agentDir\main.py`" --config `"$configPath`"" -WorkingDirectory $agentDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

# Settings for long-running daemon
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)  # No time limit (runs indefinitely)

Write-Host "[+] Registering scheduled task '$TaskName'"
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "[+] Starting scheduled task"
Start-ScheduledTask -TaskName $TaskName

Write-Host "[OK] Loglumen agent installed as startup task using $pythonPath"
Write-Host "    Config file: $configPath"
