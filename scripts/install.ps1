<#
.SYNOPSIS
    Agent Skill Forge — Windows 1-Liner Universal Installer
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " 🔨 AGENT SKILL FORGE — Windows Universal Skill Installer" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " Repo Source: $RepoRoot`n"

# Locate available Python executable
$PythonExe = $null
foreach ($cmd in @('python3.12', 'python3.13', 'py', 'python3', 'python')) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $PythonExe = $cmd
        break
    }
}

if (-not $PythonExe) {
    Write-Error "❌ Error: Python 3 is required but not found in PATH."
    exit 1
}

Write-Host "🔄 Synchronizing Core Action Verbs across AI developer tools using $PythonExe..." -ForegroundColor Yellow
& $PythonExe "$ScriptDir\sync_skills.py" --prune --fix

Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host " ✅ AGENT SKILL FORGE IS FULLY INSTALLED & ACTIVE" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
