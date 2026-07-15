#!/usr/bin/env pwsh
#Requires -Version 7.0
<#
.SYNOPSIS
  Run local validation checks for market-research (mirrors CI + AGENTS.md gate).

.PARAMETER All
  Run lint, typecheck, tests, and frontend build (default when no switch is set).

.PARAMETER Lint
  ruff check .

.PARAMETER Typecheck
  basedpyright

.PARAMETER Test
  pytest (backend; LLM/search mocked)

.PARAMETER Frontend
  pnpm install --frozen-lockfile && pnpm build in frontend/

.PARAMETER Scan
  scan-uncommitted-secrets on changed files (uses ~/.agents skill if present)

.EXAMPLE
  pwsh -NoProfile -File ./scripts/validate.ps1 -All

.EXAMPLE
  pwsh -NoProfile -File ./scripts/validate.ps1 -Lint -Test
#>
[CmdletBinding()]
param(
    [switch]$All,
    [switch]$Lint,
    [switch]$Typecheck,
    [switch]$Test,
    [switch]$Frontend,
    [switch]$Scan
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not ($All -or $Lint -or $Typecheck -or $Test -or $Frontend -or $Scan)) {
    $All = $true
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Invoke-ValidateStep {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [scriptblock]$Action
    )
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Step failed ($LASTEXITCODE): $Name"
    }
}

function Test-CommandAvailable {
    param([Parameter(Mandatory)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

Push-Location $RepoRoot
try {
    if ($All -or $Lint) {
        if (-not (Test-CommandAvailable 'uv')) {
            throw "uv not found on PATH. Install uv, then re-run."
        }
        Invoke-ValidateStep -Name 'ruff' -Action {
            uv run ruff check .
        }
    }

    if ($All -or $Typecheck) {
        if (-not (Test-CommandAvailable 'uv')) {
            throw "uv not found on PATH. Install uv, then re-run."
        }
        Invoke-ValidateStep -Name 'basedpyright' -Action {
            uv run basedpyright
        }
    }

    if ($All -or $Test) {
        if (-not (Test-CommandAvailable 'uv')) {
            throw "uv not found on PATH. Install uv, then re-run."
        }
        Invoke-ValidateStep -Name 'pytest' -Action {
            uv run pytest -q
        }
    }

    if ($All -or $Frontend) {
        if (-not (Test-CommandAvailable 'pnpm')) {
            throw "pnpm not found on PATH. Install pnpm (Node 24+), then re-run."
        }
        Invoke-ValidateStep -Name 'frontend build' -Action {
            Push-Location (Join-Path $RepoRoot 'frontend')
            try {
                pnpm install --frozen-lockfile
                if ($LASTEXITCODE -ne 0) { throw "pnpm install failed ($LASTEXITCODE)" }
                pnpm build
                if ($LASTEXITCODE -ne 0) { throw "pnpm build failed ($LASTEXITCODE)" }
            }
            finally {
                Pop-Location
            }
        }
    }

    if ($All -or $Scan) {
        $scanCandidates = @(
            (Join-Path $HOME '.agents/skills/scan-uncommitted-secrets/scripts/scan.sh'),
            (Join-Path $RepoRoot '.cursor/skills/scan-uncommitted-secrets/scripts/scan.sh')
        )
        $scanScript = $scanCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($scanScript) {
            Invoke-ValidateStep -Name 'secret scan' -Action {
                bash $scanScript
            }
        }
        else {
            Write-Warning "Skipping secret scan: scan-uncommitted-secrets script not found."
        }
    }

    Write-Host ""
    Write-Host "Validation passed." -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "Validation FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
