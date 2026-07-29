<#
.SYNOPSIS
  Build the ta-* Ollama persona models from ollama/modelfiles/*.Modelfile.

.DESCRIPTION
  Each Modelfile layers a role-specific SYSTEM prompt + parameters onto an
  existing local base model. Re-running is idempotent (ollama create overwrites).
  These custom model names MUST exist in `ollama list`, or the local-first
  compute policy (tradingagents/llm_clients/compute_policy.py) will silently
  swap the role back to a generic fallback.

  See docs/model_specialization_plan.md (Phase B).
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$modelfileDir = Join-Path $repoRoot "ollama/modelfiles"

Get-ChildItem (Join-Path $modelfileDir "*.Modelfile") | ForEach-Object {
    $name = $_.BaseName            # e.g. "ta-bear" from "ta-bear.Modelfile"
    Write-Host "==> Creating $name`:latest from $($_.Name)"
    ollama create "$name`:latest" -f $_.FullName
}

Write-Host ""
Write-Host "Persona models now installed:"
ollama list | Select-String "ta-"
