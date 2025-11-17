param(
    [string]$TaskName = "LoglumenAgent"
)

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "Please run this script from an elevated PowerShell session."
    exit 1
}

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Write-Host "[+] Stopping scheduled task '$TaskName'"
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host "[+] Removing scheduled task '$TaskName'"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[✓] Task removed"
}
catch {
    Write-Warning "Scheduled task '$TaskName' not found."
}
