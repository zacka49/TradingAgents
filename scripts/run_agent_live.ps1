param(
  [Parameter(Mandatory = $true)][string]$Symbol,
  [Parameter(Mandatory = $true)][string]$TradeDate,
  [switch]$SubmitOrder,
  [double]$OrderQty = 1.0,
  [string]$Model = "qwen3:0.6b"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = Join-Path $root "results\\run_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("run_" + $Symbol + "_" + $TradeDate + "_" + $stamp + ".log")

$args = @(
  "-u",
  "scripts/run_agent_with_live_console.py",
  "--symbol", $Symbol,
  "--trade-date", $TradeDate,
  "--order-qty", $OrderQty,
  "--model", $Model
)

if ($SubmitOrder) {
  $args += "--submit-order"
}

Write-Host "Starting live run..."
Write-Host "Log file: $logFile"

& ".\\.venv\\Scripts\\python.exe" @args 2>&1 | Tee-Object -FilePath $logFile

Write-Host "Run finished. Log saved to: $logFile"
