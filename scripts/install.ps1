<#
.SYNOPSIS
    Agent Skill Forge — Windows 1-Liner Universal Installer

.DESCRIPTION
    Mirrors scripts/install.sh step for step:
      1. resolve the reference-only upstream skills at their pinned commits
      2. link skills into each harness, minus what that harness already ships
      3. fetch the user's voice profile when AGENT_PERSONA_REPO is set
      4. optionally make the design gate mechanical (Claude Code only)
      5. report media tool readiness or install media CLIs (--with-media-tools)

.EXAMPLE
    powershell -File scripts\install.ps1 --spine --hard-gate
.EXAMPLE
    powershell -File scripts\install.ps1 --offline --clusters c3,d1
.EXAMPLE
    powershell -File scripts\install.ps1 --content --with-media-tools
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$WithMediaTools,
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
$WithMediaToolsFlag = [bool]$WithMediaTools
$ProjectDir = ''
$HasSelectionFlag = $false
$HasListOnly = $false
$HasSpine = $false
$HasMediaSelection = $false
$PassArgs = @()

function Resolve-ClustersForMedia([string]$RawList) {
    foreach ($tok in ($RawList.ToLowerInvariant() -split ',')) {
        switch ($tok.Trim()) {
            { $_ -in @('c3', 'content', 'core', 'all') } { $script:HasMediaSelection = $true }
            { $_ -in @('c5', 'spine') } { $script:HasSpine = $true }
        }
    }
}

function Resolve-SkillsForMedia([string]$RawList) {
    foreach ($tok in ($RawList.ToLowerInvariant() -split ',')) {
        if ($tok.Trim() -in @('image-gen', 'image-gen-expert')) {
            $script:HasMediaSelection = $true
        }
    }
}

# @($null) is a one-element array containing $null, so an unguarded foreach
# over an absent $ForwardArgs would push $null into $PassArgs, make its Count 1,
# and silently skip the interactive wizard.
if ($ForwardArgs) {
    for ($idx = 0; $idx -lt $ForwardArgs.Count; $idx++) {
        $arg = $ForwardArgs[$idx]
        if ([string]::IsNullOrWhiteSpace($arg)) { continue }
        switch -Wildcard ($arg) {
            '--hard-gate'        { $HardGate = $true }
            '--no-hard-gate'     { $HardGate = $false }
            '--no-fetch'         { $NoFetch = $true }
            '--offline'          { $Offline = $true }
            '--with-media-tools' { $WithMediaToolsFlag = $true }
            '--uninstall'        { $Uninstall = $true }
            '--all'              { $HasSelectionFlag = $true; $HasMediaSelection = $true; $PassArgs += $arg }
            '--core'             { $HasSelectionFlag = $true; $HasMediaSelection = $true; $PassArgs += $arg }
            '--content'          { $HasSelectionFlag = $true; $HasMediaSelection = $true; $PassArgs += $arg }
            '--spine'            { $HasSelectionFlag = $true; $HasSpine = $true; $PassArgs += $arg }
            '--domain'           { $HasSelectionFlag = $true; $PassArgs += $arg }
            '--list-available'   { $HasListOnly = $true; $PassArgs += $arg }
            '--list-clusters'    { $HasListOnly = $true; $PassArgs += $arg }
            '--list-harnesses'   { $HasListOnly = $true; $PassArgs += $arg }
            '--project' {
                $PassArgs += $arg
                if ($idx + 1 -lt $ForwardArgs.Count) {
                    $idx++
                    $ProjectDir = $ForwardArgs[$idx]
                    $PassArgs += $ProjectDir
                }
            }
            '--project=*' {
                $ProjectDir = $arg.Substring('--project='.Length)
                $PassArgs += $arg
            }
            '--clusters' {
                $PassArgs += $arg
                $HasSelectionFlag = $true
                if ($idx + 1 -lt $ForwardArgs.Count) {
                    $idx++
                    Resolve-ClustersForMedia $ForwardArgs[$idx]
                    $PassArgs += $ForwardArgs[$idx]
                }
            }
            '--clusters=*' {
                $HasSelectionFlag = $true
                Resolve-ClustersForMedia ($arg.Substring('--clusters='.Length))
                $PassArgs += $arg
            }
            '--skills' {
                $PassArgs += $arg
                $HasSelectionFlag = $true
                if ($idx + 1 -lt $ForwardArgs.Count) {
                    $idx++
                    Resolve-SkillsForMedia $ForwardArgs[$idx]
                    $PassArgs += $ForwardArgs[$idx]
                }
            }
            '--skills=*' {
                $HasSelectionFlag = $true
                Resolve-SkillsForMedia ($arg.Substring('--skills='.Length))
                $PassArgs += $arg
            }
            default { $PassArgs += $arg }
        }
    }
}

function Assert-SafeMediaToolUrl([string]$EnvName, [string]$UrlValue) {
    if ([string]::IsNullOrWhiteSpace($UrlValue)) { return }
    if ($UrlValue -notmatch '^(https|file)://') {
        [Console]::Error.WriteLine("❌ Error: $EnvName must use https:// or file:// (got: $UrlValue).")
        exit 2
    }
}

if ($WithMediaToolsFlag -and $Offline) {
    [Console]::Error.WriteLine("❌ Error: --with-media-tools cannot be combined with --offline (media tool installation requires network access).")
    exit 2
}

if ($WithMediaToolsFlag) {
    # Offline test / mirror seams (unprivileged):
    #   FORGE_GEMINI_API_INSTALL_CMD - custom PowerShell command replacing release download in offline tests.
    #   FORGE_GEMINI_API_INSTALL_URL - POSIX installer URL seam parity (must use https:// or file:// if set).
    #   FORGE_GEMINI_API_RELEASE_URL - custom GitHub releases JSON endpoint (must use https:// or file://).
    Assert-SafeMediaToolUrl 'FORGE_GEMINI_API_INSTALL_URL' $env:FORGE_GEMINI_API_INSTALL_URL
    Assert-SafeMediaToolUrl 'FORGE_GEMINI_API_RELEASE_URL' $env:FORGE_GEMINI_API_RELEASE_URL
}

function Resolve-LocalMediaBin {
    $localBin = Join-Path (Join-Path $HOME '.local') 'bin'
    if (-not (Get-Command 'gemini-api' -ErrorAction SilentlyContinue)) {
        foreach ($candidateName in @('gemini-api.exe', 'gemini-api')) {
            $candidate = Join-Path $localBin $candidateName
            if (Test-Path -LiteralPath $candidate) {
                $env:PATH = "$localBin$([System.IO.Path]::PathSeparator)$env:PATH"
                break
            }
        }
    }
    return $localBin
}

function Save-MediaAssetFromUrl([string]$Url, [string]$DestPath, [hashtable]$Headers) {
    if ($Url -match '^file://') {
        Copy-Item -LiteralPath ([Uri]$Url).LocalPath -Destination $DestPath -Force
        return
    }
    Invoke-WebRequest -Uri $Url -OutFile $DestPath -Headers $Headers -UseBasicParsing
}

function Install-ForgeMediaTools {
    Write-Host "`n🎬 Checking & installing user-space media CLI tools (--with-media-tools, zero elevation)..." -ForegroundColor Cyan
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    } catch { }
    Assert-SafeMediaToolUrl 'FORGE_GEMINI_API_INSTALL_URL' $env:FORGE_GEMINI_API_INSTALL_URL
    Assert-SafeMediaToolUrl 'FORGE_GEMINI_API_RELEASE_URL' $env:FORGE_GEMINI_API_RELEASE_URL
    $localBin = Resolve-LocalMediaBin

    if (-not (Get-Command 'gemini-api' -ErrorAction SilentlyContinue)) {
        Write-Host "⬇️  gemini-api not found on PATH; installing user-space CLI into $localBin..." -ForegroundColor Yellow
        if (-not (Test-Path $localBin)) {
            New-Item -ItemType Directory -Force -Path $localBin | Out-Null
        }
        $installFailed = $false
        try {
            if ($env:FORGE_GEMINI_API_INSTALL_CMD) {
                $global:LASTEXITCODE = 0
                & ([scriptblock]::Create($env:FORGE_GEMINI_API_INSTALL_CMD))
                if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
                    throw "Custom install command exited $LASTEXITCODE"
                }
            } else {
                $releaseUrl = if ($env:FORGE_GEMINI_API_RELEASE_URL) {
                    $env:FORGE_GEMINI_API_RELEASE_URL
                } else {
                    'https://api.github.com/repos/google-gemini/gemini-api-cli/releases/latest'
                }
                Assert-SafeMediaToolUrl 'FORGE_GEMINI_API_RELEASE_URL' $releaseUrl
                $arch = 'amd64'
                try {
                    if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq [System.Runtime.InteropServices.Architecture]::Arm64) {
                        $arch = 'arm64'
                    }
                } catch { }
                $headers = @{ 'User-Agent' = 'agent-skill-forge-installer' }
                $release = $null
                if ($releaseUrl -match '^file://') {
                    $release = Get-Content -LiteralPath ([Uri]$releaseUrl).LocalPath -Raw | ConvertFrom-Json
                }
                if ($releaseUrl -notmatch '^file://') {
                    $release = Invoke-RestMethod -Uri $releaseUrl -Headers $headers -UseBasicParsing
                }
                $assets = @($release.assets)
                $winAssets = $assets | Where-Object {
                    $_.name -match '(^|[_.-])(windows|win32|win64)([_.-]|$)' -and $_.name -match '\.(zip|exe)$'
                }
                $asset = $winAssets | Where-Object {
                    if ($arch -eq 'arm64') { $_.name -match 'arm64|aarch64' } else { $_.name -match 'amd64|x86_64|x64' }
                } | Select-Object -First 1
                if (-not $asset) {
                    $asset = $winAssets | Select-Object -First 1
                }
                if (-not $asset -or -not $asset.browser_download_url) {
                    throw "No Windows .zip or .exe release asset found at $releaseUrl"
                }
                $assetFileName = [System.IO.Path]::GetFileName([string]$asset.name)
                if ([string]::IsNullOrWhiteSpace($assetFileName) -or $assetFileName -in @('.', '..')) {
                    throw "Invalid Windows release asset filename: $($asset.name)"
                }
                Assert-SafeMediaToolUrl 'release asset URL' $asset.browser_download_url
                $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("forge-gemini-api-" + [guid]::NewGuid().ToString('N'))
                New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
                try {
                    $dlFile = Join-Path $tmpDir $assetFileName
                    Save-MediaAssetFromUrl $asset.browser_download_url $dlFile $headers

                    # Verify SHA-256 checksum when upstream release provides checksums.txt or a .sha256 asset.
                    $checksumAsset = $assets | Where-Object {
                        $_.name -eq "$($asset.name).sha256" -or $_.name -eq "$($asset.name).sha256sum"
                    } | Select-Object -First 1
                    if (-not $checksumAsset) {
                        $checksumAsset = $assets | Where-Object {
                            $_.name -match '^(checksums?.*|sha256sums?)(\.txt)?$' -or $_.name -match '\.sha256(sums?)?$'
                        } | Select-Object -First 1
                    }
                    if ($checksumAsset -and $checksumAsset.browser_download_url) {
                        Assert-SafeMediaToolUrl 'checksum asset URL' $checksumAsset.browser_download_url
                        $checksumFileName = [System.IO.Path]::GetFileName([string]$checksumAsset.name)
                        if ([string]::IsNullOrWhiteSpace($checksumFileName) -or $checksumFileName -in @('.', '..')) {
                            throw "Invalid checksum asset filename: $($checksumAsset.name)"
                        }
                        $checksumFile = Join-Path $tmpDir $checksumFileName
                        Save-MediaAssetFromUrl $checksumAsset.browser_download_url $checksumFile $headers
                        $expectedHash = $null
                        $hasNamedEntries = $false
                        $bareHashes = @()
                        $checksumLines = Get-Content -LiteralPath $checksumFile -ErrorAction Stop
                        foreach ($line in $checksumLines) {
                            if ($line -match '^\s*([0-9a-fA-F]{64})\s+[*]?(.+?)\s*$') {
                                $hasNamedEntries = $true
                                $candidateName = [System.IO.Path]::GetFileName($Matches[2].Trim())
                                if ($candidateName -eq $assetFileName) {
                                    $expectedHash = $Matches[1].ToLowerInvariant()
                                    break
                                }
                            } elseif ($line -match '^\s*([0-9a-fA-F]{64})\s*$') {
                                $bareHashes += $Matches[1].ToLowerInvariant()
                            }
                        }
                        if (-not $expectedHash -and -not $hasNamedEntries -and $checksumFileName -match '\.sha256(sum)?$' -and $bareHashes.Count -eq 1) {
                            $expectedHash = $bareHashes[0]
                        }
                        if (-not $expectedHash) {
                            throw "Checksum asset '$checksumFileName' did not contain a SHA-256 digest for '$assetFileName'"
                        }
                        $actualHash = (Get-FileHash -LiteralPath $dlFile -Algorithm SHA256).Hash.ToLowerInvariant()
                        if ($actualHash -ne $expectedHash) {
                            throw "SHA-256 checksum mismatch for $($assetFileName): expected $expectedHash, got $actualHash"
                        }
                        Write-Host "  🔒 Verified SHA-256 checksum for $assetFileName" -ForegroundColor Green
                    }
                    if (-not $checksumAsset -or -not $checksumAsset.browser_download_url) {
                        [Console]::Error.WriteLine("⚠️  WARNING: Release at $releaseUrl includes no checksums.txt or .sha256 asset; proceeding without SHA-256 verification for $assetFileName.")
                    }

                    if ($assetFileName -match '\.zip$') {
                        $extractDir = Join-Path $tmpDir 'extracted'
                        Expand-Archive -LiteralPath $dlFile -DestinationPath $extractDir -Force
                        $exe = Get-ChildItem -Path $extractDir -Filter 'gemini-api.exe' -Recurse | Select-Object -First 1
                        if (-not $exe) { throw "gemini-api.exe not found inside $assetFileName" }
                        Copy-Item -LiteralPath $exe.FullName -Destination (Join-Path $localBin 'gemini-api.exe') -Force
                    } elseif ($assetFileName -match '\.exe$') {
                        Copy-Item -LiteralPath $dlFile -Destination (Join-Path $localBin 'gemini-api.exe') -Force
                    } else {
                        throw "Unsupported Windows asset format '$assetFileName' (expected .zip or .exe)"
                    }
                } finally {
                    Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {
            $installFailed = $true
            [Console]::Error.WriteLine("⚠️  gemini-api install error: $($_.Exception.Message)")
        }
        $null = Resolve-LocalMediaBin
        $installedExe = Join-Path $localBin 'gemini-api.exe'
        $geminiCmd = Get-Command 'gemini-api' -ErrorAction SilentlyContinue
        if (-not $geminiCmd) { $geminiCmd = Get-Command 'gemini-api.exe' -ErrorAction SilentlyContinue }
        if (-not $geminiCmd -and (Test-Path -LiteralPath $installedExe)) {
            $geminiCmd = $installedExe
        }
        if ($installFailed -or -not $geminiCmd) {
            [Console]::Error.WriteLine("❌ Error: failed to install gemini-api CLI into $localBin.")
            [Console]::Error.WriteLine("   Manual install: download from https://github.com/google-gemini/gemini-api-cli/releases into $localBin")
            [Console]::Error.WriteLine("   Docs: https://aistudio.google.com/docs/cli")
            exit 1
        }
    }

    $installedExe = Join-Path $localBin 'gemini-api.exe'
    $geminiBin = Get-Command 'gemini-api' -ErrorAction SilentlyContinue
    if (-not $geminiBin) { $geminiBin = Get-Command 'gemini-api.exe' -ErrorAction SilentlyContinue }
    if (-not $geminiBin -and (Test-Path -LiteralPath $installedExe)) {
        $geminiBin = $installedExe
    }
    $global:LASTEXITCODE = 0
    $geminiVer = ''
    try { $geminiVer = (& $geminiBin --version 2>&1) -join ' ' } catch { $global:LASTEXITCODE = 0 }
    Write-Host "  ✅ gemini-api: $(if ($geminiVer) { $geminiVer } else { 'available' })" -ForegroundColor Green

    $global:LASTEXITCODE = 0
    try { $null = (& $geminiBin whoami -o json 2>&1) } catch { $global:LASTEXITCODE = 1 }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  🔐 gemini-api auth (whoami): authenticated"
    } else {
        Write-Host "  ℹ️  gemini-api auth: not authenticated yet (non-fatal). Run: gemini-api auth login" -ForegroundColor Yellow
    }
    $global:LASTEXITCODE = 0

    if (-not [string]::IsNullOrEmpty($env:GEMINI_API_KEY)) {
        Write-Host "  ⚠️  Warning: GEMINI_API_KEY is set in your environment and could shadow OS keyring credentials (https://aistudio.google.com/docs/cli)." -ForegroundColor Yellow
    }

    $haveFfmpeg = [bool](Get-Command 'ffmpeg' -ErrorAction SilentlyContinue)
    $haveFfprobe = [bool](Get-Command 'ffprobe' -ErrorAction SilentlyContinue)
    if (-not $haveFfmpeg -or -not $haveFfprobe) {
        if (Get-Command 'winget' -ErrorAction SilentlyContinue) {
            Write-Host "⬇️  ffmpeg/ffprobe missing; installing via winget (Gyan.FFmpeg)..." -ForegroundColor Yellow
            $global:LASTEXITCODE = 0
            try {
                & winget install --id Gyan.FFmpeg -e --scope user --accept-source-agreements --accept-package-agreements
            } catch { }
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  ⚠️  winget install did not complete (exit $LASTEXITCODE); install manually from https://ffmpeg.org/download.html" -ForegroundColor Yellow
            }
            $global:LASTEXITCODE = 0
        } elseif (Get-Command 'scoop' -ErrorAction SilentlyContinue) {
            Write-Host "⬇️  ffmpeg/ffprobe missing; installing via scoop (scoop install ffmpeg)..." -ForegroundColor Yellow
            $global:LASTEXITCODE = 0
            try {
                & scoop install ffmpeg
            } catch { }
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  ⚠️  scoop install ffmpeg failed (exit $LASTEXITCODE); install manually from https://ffmpeg.org/download.html" -ForegroundColor Yellow
            }
            $global:LASTEXITCODE = 0
        } else {
            Write-Host "  ⚠️  ffmpeg/ffprobe not found on PATH (optional for media workflows)." -ForegroundColor Yellow
            Write-Host "     Install with: winget install --id Gyan.FFmpeg -e --scope user --accept-source-agreements --accept-package-agreements   or   scoop install ffmpeg"
        }
    }
    if ((Get-Command 'ffmpeg' -ErrorAction SilentlyContinue) -and (Get-Command 'ffprobe' -ErrorAction SilentlyContinue)) {
        Write-Host "  ✅ ffmpeg & ffprobe: available" -ForegroundColor Green
    }
}

function Show-MediaReadinessNote {
    $mediaSynced = $false
    if ($script:HasListOnly) {
        $mediaSynced = $false
    } elseif ($script:HasMediaSelection -or -not $script:HasSelectionFlag) {
        $mediaSynced = $true
    } elseif (-not $script:HasSpine) {
        $projBase = if ($script:ProjectDir) { $script:ProjectDir } else { '.' }
        $checkPaths = @(
            (Join-Path (Join-Path (Join-Path $HOME '.agents') 'skills') 'image-gen'),
            (Join-Path (Join-Path (Join-Path $HOME '.gemini') 'skills') 'image-gen'),
            (Join-Path (Join-Path (Join-Path $projBase '.gemini') 'skills') 'image-gen')
        )
        foreach ($p in $checkPaths) {
            if (Test-Path -LiteralPath $p) {
                $mediaSynced = $true
                break
            }
        }
    }
    if ($mediaSynced) {
        $null = Resolve-LocalMediaBin
        $geminiState = if ((Get-Command 'gemini-api' -ErrorAction SilentlyContinue) -or (Get-Command 'gemini-api.exe' -ErrorAction SilentlyContinue)) { 'found' } else { 'missing' }
        $ffmpegState = if (Get-Command 'ffmpeg' -ErrorAction SilentlyContinue) { 'found' } else { 'missing' }
        $ffprobeState = if (Get-Command 'ffprobe' -ErrorAction SilentlyContinue) { 'found' } else { 'missing' }
        Write-Host "`n 🎬 Media tools readiness: gemini-api=$geminiState, ffmpeg=$ffmpegState, ffprobe=$ffprobeState"
        Write-Host "    To install user-space media CLIs (zero elevation), re-run with: --with-media-tools"
    }
}

$SyncScript = Join-Path $ScriptDir 'sync_skills.py'
$FetchScript = Join-Path $ScriptDir 'fetch_upstream.py'
$DesignGateScript = Join-Path (Join-Path $RepoRoot 'hooks') 'design_gate.py'
$PersonaScript = Join-Path (Join-Path (Join-Path (Join-Path $RepoRoot 'skills') 'voice-register') 'scripts') 'persona.py'

if ($Uninstall) {
    & $PythonExe $SyncScript --uninstall
    try { & $PythonExe $DesignGateScript --uninstall } catch { }
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
    & $PythonExe $FetchScript @FetchArgs
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
    & $PythonExe (Join-Path $ScriptDir 'sync_skills.py') --fix @PassArgs
} elseif ($Interactive) {
    & $PythonExe (Join-Path $ScriptDir 'sync_skills.py') --interactive --fix
} else {
    # Additive, matching install.sh. The non-interactive path is CI and
    # piped-script installs, where a default that removes things nobody
    # agreed to remove is not a default worth having.
    Write-Host "🔄 Synchronizing skills across AI developer tools using $PythonExe..." -ForegroundColor Yellow
    & $PythonExe (Join-Path $ScriptDir 'sync_skills.py') --fix
}

# $ErrorActionPreference does not apply to a native process's exit code, so
# without this check a failed sync fell straight through to the green banner.
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Skill synchronization failed (exit $LASTEXITCODE). Nothing further was done." -ForegroundColor Red
    exit $LASTEXITCODE
}

# ------------------------------------------------------------------------------
# Step 3: fetch the user's private voice profile, if they configured one.
# Unset means a neutral install: nothing is fetched. A failure here never fails
# the install; voice-register falls back to neutral prose and says why.
# ------------------------------------------------------------------------------
if ($env:AGENT_PERSONA_REPO -and $Offline) {
    Write-Host ""
    Write-Host "🎙️  Offline install: skipping the voice profile fetch. Run persona.py pull later." -ForegroundColor Yellow
} elseif ($env:AGENT_PERSONA_REPO -and (Test-Path -LiteralPath $PersonaScript)) {
    Write-Host ""
    Write-Host "🎙️  Fetching your voice profile from $($env:AGENT_PERSONA_REPO)..." -ForegroundColor Yellow
    & $PythonExe $PersonaScript pull --force
    # Exit 1 only means no profile resolved yet; 2 means the fetch failed.
    if ($LASTEXITCODE -eq 2) {
        Write-Host "⚠️  Could not fetch it. voice-register will stay neutral until it can." -ForegroundColor Yellow
    }
    $global:LASTEXITCODE = 0
}

# ------------------------------------------------------------------------------
# Step 4: optionally make the design gate mechanical.
# Only Claude Code has a hook API; elsewhere the gate stays advisory.
# ------------------------------------------------------------------------------
if ($HardGate) {
    Write-Host ""
    Write-Host "🚧 Enabling the design gate (blocks product-code edits without an approved design)..." -ForegroundColor Yellow
    & $PythonExe $DesignGateScript --install
    if ($LASTEXITCODE -ne 0) {
        # Claiming an enforced gate that was never installed is worse than
        # failing here: the user would rely on it.
        Write-Host "`n❌ The design gate could not be installed (exit $LASTEXITCODE)." -ForegroundColor Red
        Write-Host "    Skills are installed, but the gate is NOT enforced." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "    Antigravity, Gemini CLI, and Codex have no hook API. There the gate is"
    Write-Host "    the instruction text in the brainstorm skill and nothing more."
}

# ------------------------------------------------------------------------------
# Step 5: media tools readiness & opt-in installation (--with-media-tools).
# Uses separate conditionals so Step 2 remains the final non-interactive else branch.
# ------------------------------------------------------------------------------
if ($WithMediaToolsFlag) {
    Install-ForgeMediaTools
}
if (-not $WithMediaToolsFlag) {
    Show-MediaReadinessNote
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
$InstallSelf = Join-Path $ScriptDir 'install.ps1'
Write-Host " Each harness only gets what it lacks. See what was skipped where:"
Write-Host "    $PythonExe $SyncScript --list-harnesses"
Write-Host ""
Write-Host " 🛠️  Installer Usage Examples:"
Write-Host "    Interactive Wizard:             powershell -File $InstallSelf"
Write-Host "    Install the spine only:         powershell -File $InstallSelf --spine"
Write-Host "    Spine + enforced design gate:   powershell -File $InstallSelf --spine --hard-gate"
Write-Host "    Install Content & Creative:     powershell -File $InstallSelf --content"
Write-Host "    Install C3 + media CLIs:        powershell -File $InstallSelf --content --with-media-tools"
Write-Host "    Install Specific Clusters:      powershell -File $InstallSelf --clusters c3,d1"
Write-Host "    Install Complete Forge (All):   powershell -File $InstallSelf --all"
Write-Host "    Air-gapped install from cache:  powershell -File $InstallSelf --offline"
Write-Host "    Skip the upstream fetch:        powershell -File $InstallSelf --no-fetch"
Write-Host "    Physical copies, no symlinks:   powershell -File $InstallSelf --copy"
Write-Host "    Uninstall All Forge Skills:     powershell -File $InstallSelf --uninstall"
Write-Host "========================================================================" -ForegroundColor Green
