# Test script for install_loglumen_agent.ps1
# This validates the script logic without actually installing

Write-Host "=" * 70
Write-Host "Testing Install Script Logic"
Write-Host "=" * 70

# Test 1: Check if we're admin
Write-Host "`n[TEST 1] Checking administrator privileges..."
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if ($isAdmin) {
    Write-Host "[PASS] Running as Administrator"
} else {
    Write-Host "[FAIL] Not running as Administrator"
    Write-Host "       The install script requires admin privileges"
}

# Test 2: Check paths
Write-Host "`n[TEST 2] Checking paths..."
$scriptDir = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptDir
$agentDir = Join-Path $repoRoot "agent"
$configDir = Join-Path $env:ProgramData "Loglumen"

Write-Host "  Script dir: $scriptDir"
Write-Host "  Repo root: $repoRoot"
Write-Host "  Agent dir: $agentDir"
Write-Host "  Config dir: $configDir"

if (Test-Path $agentDir) {
    Write-Host "[PASS] Agent directory exists"
} else {
    Write-Host "[FAIL] Agent directory not found at $agentDir"
}

# Test 3: Check for Python
Write-Host "`n[TEST 3] Checking for Python..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}

if ($python) {
    Write-Host "[PASS] Python found at: $($python.Source)"

    # Check Python version
    $version = & $python.Source --version 2>&1
    Write-Host "       Version: $version"
} else {
    Write-Host "[FAIL] Python not found in PATH"
}

# Test 4: Check for config files
Write-Host "`n[TEST 4] Checking for config files..."
$defaultConfig = Join-Path $repoRoot "config\agent.toml"
$exampleConfig = Join-Path $repoRoot "config\agent.example.toml"

if (Test-Path $defaultConfig) {
    Write-Host "[PASS] Default config found: $defaultConfig"
} elseif (Test-Path $exampleConfig) {
    Write-Host "[PASS] Example config found: $exampleConfig"
} else {
    Write-Host "[FAIL] No config template found"
}

# Test 5: Check if main.py exists
Write-Host "`n[TEST 5] Checking for main.py..."
$mainPy = Join-Path $agentDir "main.py"
if (Test-Path $mainPy) {
    Write-Host "[PASS] main.py found at: $mainPy"
} else {
    Write-Host "[FAIL] main.py not found at: $mainPy"
}

# Test 6: Simulate scheduled task command
Write-Host "`n[TEST 6] Simulating scheduled task command..."
if ($python) {
    $pythonPath = $python.Source
    $configPath = Join-Path $configDir "agent.toml"
    $taskCommand = "`"$agentDir\main.py`" --config `"$configPath`""

    Write-Host "  Command: $pythonPath $taskCommand"
    Write-Host "  Working Directory: $agentDir"
    Write-Host "[PASS] Scheduled task command generated"
}

# Summary
Write-Host "`n" + "=" * 70
Write-Host "TEST SUMMARY"
Write-Host "=" * 70

$allGood = $true
if (-not $isAdmin) {
    Write-Host "[!] Script must be run as Administrator"
    $allGood = $false
}
if (-not (Test-Path $agentDir)) {
    Write-Host "[!] Agent directory missing"
    $allGood = $false
}
if (-not $python) {
    Write-Host "[!] Python not installed or not in PATH"
    $allGood = $false
}
if (-not (Test-Path $mainPy)) {
    Write-Host "[!] main.py missing"
    $allGood = $false
}

if ($allGood) {
    Write-Host "`n[SUCCESS] All tests passed! Install script should work."
    Write-Host "`nTo install, run from an admin PowerShell:"
    Write-Host "  .\install_loglumen_agent.ps1"
} else {
    Write-Host "`n[WARNING] Some tests failed. Fix issues before installing."
}

Write-Host "`n" + "=" * 70
