<#
.SYNOPSIS
    Agent Skill Forge — Windows 1-Liner Universal Installer

.DESCRIPTION
    Mirrors scripts/install.sh step for step:
      1. resolve the reference-only upstream skills at their pinned commits
      2. link skills into each harness, minus what that harness already ships
      3. optionally make the design gate mechanical (Claude Code only)

.EXAMPLE
    powershell -File scripts\install.ps1 --spine --hard-gate
.EXAMPLE
    powershell -File scripts\install.ps1 --offline --clusters c3,d1
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

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

# ------------------------------------------------------------------------------
# Split our own flags out of the pass-through list, exactly as install.sh does.
# ------------------------------------------------------------------------------
$HardGate = $false
$NoFetch = $false
$Offline = $false
$PassArgs = @()

# @($null) is a one-element array containing $null, so an unguarded foreach
# over an absent $ForwardArgs would push $null into $PassArgs, make its Count 1,
# and silently skip the interactive wizard.
if ($ForwardArgs) {
    foreach ($arg in $ForwardArgs) {
        if ([string]::IsNullOrWhiteSpace($arg)) { continue }
        switch ($arg) {
            '--hard-gate'    { $HardGate = $true }
            '--no-hard-gate' { $HardGate = $false }
            '--no-fetch'     { $NoFetch = $true }
            '--offline'      { $Offline = $true }
            '--uninstall'    { $Uninstall = $true }
            default          { $PassArgs += $arg }
        }
    }
}

if ($Uninstall) {
    & $PythonExe "$ScriptDir\sync_skills.py" --uninstall
    try { & $PythonExe "$RepoRoot\hooks\design_gate.py" --uninstall } catch { }
    exit 0
}

# Windows symlinks need either Developer Mode or an elevated shell. Without one
# of those, os.symlink raises and the sync aborts halfway. Say so up front
# rather than after the first failure.
$DevMode = $false
try {
    $key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
    $DevMode = (Get-ItemProperty -Path $key -Name AllowDevelopmentWithoutDevLicense -ErrorAction Stop).AllowDevelopmentWithoutDevLicense -eq 1
} catch { }
$Elevated = $false
try {
    $Elevated = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch { }  # PowerShell Core on non-Windows: no Windows identity to ask.
if (-not $DevMode -and -not $Elevated -and ($PassArgs -notcontains '--copy')) {
    Write-Host "⚠️  Symlinks need Developer Mode or an elevated shell on Windows." -ForegroundColor Yellow
    Write-Host "    If linking fails, re-run with --copy to install physical copies instead.`n" -ForegroundColor Yellow
}

$Interactive = [Environment]::UserInteractive -and -not [Console]::IsInputRedirected

# ------------------------------------------------------------------------------
# Step 1: resolve reference-only upstream skills at their pinned commits.
# Nothing is vendored in this repo, so this must run before the symlink pass.
# ------------------------------------------------------------------------------
if (-not $NoFetch) {
    Write-Host "🔗 Resolving reference-only upstream skills (pinned commits)..." -ForegroundColor Yellow
    $FetchArgs = @()
    if ($Offline) { $FetchArgs += '--offline' }
    if (-not $Interactive) { $FetchArgs += '--non-interactive' }

    # A failed fetch must not abort the install: the forge's own skills are
    # local and should still land. $ErrorActionPreference='Stop' does not apply
    # to native exit codes, so check $LASTEXITCODE explicitly.
    & $PythonExe "$ScriptDir\fetch_upstream.py" @FetchArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "⚠️  Some upstream skills could not be resolved (see above)." -ForegroundColor Yellow
        Write-Host "    The forge's own skills will still install. Re-run this installer"
        Write-Host "    once you have network access to complete the spine."
        Write-Host ""
    }
    Write-Host ""
}

# ------------------------------------------------------------------------------
# Step 2: link skills into each harness, minus what that harness already ships.
# ------------------------------------------------------------------------------
if ($PassArgs.Count -gt 0) {
    & $PythonExe "$ScriptDir\sync_skills.py" --fix @PassArgs
} elseif ($Interactive) {
    & $PythonExe "$ScriptDir\sync_skills.py" --interactive --fix
} else {
    Write-Host "🔄 Synchronizing skills across AI developer tools using $PythonExe..." -ForegroundColor Yellow
    & $PythonExe "$ScriptDir\sync_skills.py" --prune --fix
}

# ------------------------------------------------------------------------------
# Step 3: optionally make the design gate mechanical.
# Only Claude Code has a hook API; elsewhere the gate stays advisory.
# ------------------------------------------------------------------------------
if ($HardGate) {
    Write-Host ""
    Write-Host "🚧 Enabling the design gate (blocks product-code edits without an approved design)..." -ForegroundColor Yellow
    & $PythonExe "$RepoRoot\hooks\design_gate.py" --install
    Write-Host "    Antigravity, Gemini CLI, and Codex have no hook API. There the gate is"
    Write-Host "    the instruction text in the brainstorm skill and nothing more."
}

Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host " ✅ AGENT SKILL FORGE IS FULLY CONFIGURED & ACTIVE" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host " 🧭 The four-gate spine:"
Write-Host "    understand   /echo  /grill  /done"
Write-Host "    think        /brainstorm  /research  /doubt"
Write-Host "    verify       /prove  /bar  /scope"
Write-Host "    human        /profile  /land  /nudge"
Write-Host ""
Write-Host " Each harness only gets what it lacks. See what was skipped where:"
Write-Host "    $PythonExe $ScriptDir\sync_skills.py --list-harnesses"
Write-Host ""
Write-Host " 🛠️  Installer Usage Examples:"
Write-Host "    Interactive Wizard:             powershell -File $ScriptDir\install.ps1"
Write-Host "    Install the spine only:         powershell -File $ScriptDir\install.ps1 --spine"
Write-Host "    Spine + enforced design gate:   powershell -File $ScriptDir\install.ps1 --spine --hard-gate"
Write-Host "    Install Specific Clusters:      powershell -File $ScriptDir\install.ps1 --clusters c3,d1"
Write-Host "    Install Complete Forge (All):   powershell -File $ScriptDir\install.ps1 --all"
Write-Host "    Air-gapped install from cache:  powershell -File $ScriptDir\install.ps1 --offline"
Write-Host "    Skip the upstream fetch:        powershell -File $ScriptDir\install.ps1 --no-fetch"
Write-Host "    Physical copies, no symlinks:   powershell -File $ScriptDir\install.ps1 --copy"
Write-Host "    Uninstall All Forge Skills:     powershell -File $ScriptDir\install.ps1 --uninstall"
Write-Host "========================================================================" -ForegroundColor Green
