param(
    [string]$TaskName = "LoglumenAgent"
)

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "Please run this script from an elevated PowerShell session."
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Split-Path -Parent $scriptDir
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

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "Python interpreter not found in PATH. Install Python 3 and rerun."
    exit 1
}
$pythonPath = $python.Source

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$agentDir\main.py`" --config `"$configPath`"" -WorkingDirectory $agentDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

Write-Host "[+] Registering scheduled task '$TaskName'"
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null

Write-Host "[+] Starting scheduled task"
Start-ScheduledTask -TaskName $TaskName

Write-Host "[✓] Loglumen agent installed as startup task using $pythonPath"
Write-Host "    Config file: $configPath"
