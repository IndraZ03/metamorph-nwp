param([string]$Python, [switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$Name = 'Metamorph-NWP-Hourly'
$Root = $PSScriptRoot
$Existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
$Marker = 'Metamorph NWP managed hourly updater v1'
if ($Existing -and $Existing.Description -ne $Marker) { throw 'Unknown task already uses this name; refusing replacement.' }
if ($Uninstall) {
    if ($Existing) {
        Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }
    return
}
if ($Root -match '[\\/]\.claude[\\/]worktrees[\\/]') { throw 'Install only from permanent checkout, not agent worktree.' }
if (-not $Python) { throw 'Specify -Python with absolute verified python.exe path.' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Python executable missing.' }
$Python = (Resolve-Path -LiteralPath $Python).Path
$Pythonw = Join-Path (Split-Path $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $Pythonw)) { throw 'Matching pythonw.exe missing.' }
Push-Location $Root
try {
    & $Python -m engine.hourly --preflight
    if ($LASTEXITCODE -ne 0) { throw 'Runtime preflight failed; inspect data/updater/hourly.log. No task installed.' }
} finally { Pop-Location }
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument '-m engine.hourly' -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Write-Host "Task: $Name; interpreter: $Pythonw; directory: $Root; user: $User"
if ($Existing) { throw 'Managed task exists. Uninstall explicitly before reinstalling.' }
Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description $Marker
# Registration only. No automatic start; user starts after reviewing retention dry-run.
