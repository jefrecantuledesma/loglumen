# Quick syntax verification
Write-Host "Verifying install script syntax..."

try {
    $script = Get-Content ".\install_loglumen_agent.ps1" -Raw
    $null = [System.Management.Automation.PSParser]::Tokenize($script, [ref]$null)
    Write-Host "[OK] Syntax is valid!"
} catch {
    Write-Host "[ERROR] Syntax error found:"
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host "`nScript is ready to use."
Write-Host "`nTo install Loglumen agent as a startup task:"
Write-Host "  1. Open PowerShell as Administrator"
Write-Host "  2. Run: .\install_loglumen_agent.ps1"
