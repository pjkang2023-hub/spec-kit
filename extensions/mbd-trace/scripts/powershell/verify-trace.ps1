#!/usr/bin/env pwsh
# Two-way traceability gate (PowerShell entrypoint): delegates to the stdlib-only Python implementation.
param(
    [switch]$Json,
    [switch]$SoftExit,
    [switch]$Strict,
    [string]$ProjectRoot = ".",
    [string]$Query = ""
)
$ErrorActionPreference = "Stop"
$py = Join-Path $PSScriptRoot "..\python\verify_trace.py"
$exe = (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $exe) { $exe = (Get-Command python -ErrorAction SilentlyContinue) }
if (-not $exe) { Write-Error "python3 or python is required to run verify-trace."; exit 2 }
$cliArgs = @($py, "--project-root", $ProjectRoot)
if ($Json) { $cliArgs += "--json" }
if ($SoftExit) { $cliArgs += "--soft-exit" }
if ($Strict) { $cliArgs += "--strict" }
if ($Query) { $cliArgs += @("--query", $Query) }
& $exe.Source @cliArgs
exit $LASTEXITCODE
