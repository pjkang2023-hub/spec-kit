#!/usr/bin/env pwsh
# Deterministic systems quality verification gate (Windows PowerShell 5.1+ entrypoint).
# ASCII-only for Windows PowerShell 5.1 compatibility.

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SoftExit,
    [switch]$Strict,
    [string]$ProjectRoot = "",
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

if ($Help) {
    Write-Output @"
Usage: verify-quality.ps1 [-Json] [-SoftExit | -Strict] [-ProjectRoot <dir>] [-Help]

Run deterministic compiler, linter, test/sanitizer, and zero-stub verification
gates for C, C++, Rust, and Go projects.
"@
    exit 0
}

if ($SoftExit -and $Strict) {
    [Console]::Error.WriteLine("Error: -SoftExit and -Strict are mutually exclusive.")
    exit 2
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyScript = Join-Path (Split-Path -Parent $ScriptDir) (Join-Path "python" "verify_quality.py")

$ForwardArgs = New-Object System.Collections.Generic.List[string]
if ($Json) {
    $ForwardArgs.Add("--json")
}
if ($SoftExit) {
    $ForwardArgs.Add("--soft-exit")
}
if ($Strict) {
    $ForwardArgs.Add("--strict")
}
if ($ProjectRoot -ne "") {
    $ForwardArgs.Add("--project-root")
    $ForwardArgs.Add($ProjectRoot)
}

$PythonCmd = $null
foreach ($Candidate in @("python3", "python", "py")) {
    $Found = Get-Command $Candidate -ErrorAction SilentlyContinue
    if ($null -ne $Found) {
        $PythonCmd = $Found.Source
        $PythonName = $Candidate
        break
    }
}

if ($null -eq $PythonCmd) {
    [Console]::Error.WriteLine("Error: Python 3.11+ is required to run verify-quality.")
    exit 2
}

if ($PythonName -eq "py") {
    & $PythonCmd -3 $PyScript @ForwardArgs
} else {
    & $PythonCmd $PyScript @ForwardArgs
}
exit $LASTEXITCODE
