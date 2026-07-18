<#
.SYNOPSIS
    Registers the four TradingAgents operations tasks (T1-T4) in Windows
    Task Scheduler, per docs/business_recovery_plan.md Phase 1.

.DESCRIPTION
    This is the one step of the recovery plan that touches persistent system
    configuration outside the repo, and it enables unattended paper-order
    submission (T2). Review the task list this script prints before
    confirming, and review it again with Get-ScheduledTask any time after.

    All four tasks run in the *current user's* session context (no stored
    password, no SYSTEM account), so they only fire while this Windows
    account is logged on. They will NOT run if the PC is locked out at the
    OS login screen with nobody signed in, but WILL run while merely screen-
    locked under an active session on most default settings -- verify this
    matches what you expect.

    Idempotent: existing tasks with the same names are replaced.

.PARAMETER Confirm
    Pass -Confirm:$true (or answer 'y' at the prompt) to actually register
    the tasks. Without it, this script only prints what it would do.

.EXAMPLE
    # Preview only
    .\scripts\ops\register_scheduled_tasks.ps1

.EXAMPLE
    # Actually register
    .\scripts\ops\register_scheduled_tasks.ps1 -Apply
#>

param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found at $PythonExe. Run this from a repo with .venv already set up."
}

$TaskDefinitions = @(
    @{
        Name        = "TradingAgents-T1-PremarketPrep"
        Description = "TradingAgents: pre-market readiness check (Alpaca, Ollama, strategy library)."
        ScriptArgs  = "scripts\ops\premarket_prep.py"
        DaysOfWeek  = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
        Time        = "13:45"
        TimeLimit   = (New-TimeSpan -Minutes 15)
    },
    @{
        Name        = "TradingAgents-T2-TradingSession"
        Description = "TradingAgents: safe-profile day trader, flattens stale positions at start, single order-submitting task."
        ScriptArgs  = "scripts\ops\trading_session.py"
        DaysOfWeek  = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
        Time        = "14:20"
        TimeLimit   = (New-TimeSpan -Hours 9)
    },
    @{
        Name        = "TradingAgents-T3-PostmarketReview"
        Description = "TradingAgents: post-market scorecards, research-only CEO briefing, and daily digest."
        ScriptArgs  = "scripts\ops\postmarket_review.py"
        DaysOfWeek  = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
        Time        = "21:15"
        TimeLimit   = (New-TimeSpan -Minutes 30)
    },
    @{
        Name        = "TradingAgents-T4-WeeklyResearch"
        Description = "TradingAgents: weekly strategy library refresh, technology scout, and weekly review doc."
        ScriptArgs  = "scripts\ops\weekly_research.py"
        DaysOfWeek  = @("Saturday")
        Time        = "10:00"
        TimeLimit   = (New-TimeSpan -Minutes 30)
    }
)

Write-Host "Repo root:   $RepoRoot"
Write-Host "Python exe:  $PythonExe"
Write-Host ""
Write-Host "Tasks to register (times are this PC's local timezone):"
foreach ($def in $TaskDefinitions) {
    $days = $def.DaysOfWeek -join ","
    Write-Host ("  - {0,-32} {1,-16} {2}" -f $def.Name, "$days $($def.Time)", $def.ScriptArgs)
}
Write-Host ""

if (-not $Apply) {
    Write-Host "Preview only. Re-run with -Apply to actually register these tasks." -ForegroundColor Yellow
    exit 0
}

foreach ($def in $TaskDefinitions) {
    $existing = Get-ScheduledTask -TaskName $def.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Removing existing task: $($def.Name)"
        Unregister-ScheduledTask -TaskName $def.Name -Confirm:$false
    }

    $action = New-ScheduledTaskAction `
        -Execute $PythonExe `
        -Argument $def.ScriptArgs `
        -WorkingDirectory $RepoRoot

    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $def.DaysOfWeek -At $def.Time

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit $def.TimeLimit `
        -StartWhenAvailable `
        -DontStopOnIdleEnd `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries

    Register-ScheduledTask `
        -TaskName $def.Name `
        -Description $def.Description `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Limited | Out-Null

    Write-Host "Registered: $($def.Name)"
}

Write-Host ""
Write-Host "Done. Verify with: Get-ScheduledTask -TaskName 'TradingAgents-*' | Format-Table TaskName,State"
Write-Host "Remove all with:   Get-ScheduledTask -TaskName 'TradingAgents-*' | Unregister-ScheduledTask -Confirm:`$false"
