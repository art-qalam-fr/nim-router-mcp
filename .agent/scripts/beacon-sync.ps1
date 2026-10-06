Param(
    [string]$ConfigPath = "",
    [switch]$DryRun = $false
)

# Beacon Sync - synchronise les traces Beacon vers la mémoire unifiée.
# Non-bloquant et non-fatal : toute erreur est loguée mais n'interrompt pas le workspace.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$ScriptRoot = $PSScriptRoot
$LogDir = Join-Path $ScriptRoot "..\logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "workspace.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $entry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    try { Add-Content -Path $LogFile -Value $entry -ErrorAction SilentlyContinue } catch { }
    Write-Host $entry
}

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $ScriptRoot "ingestion.config.json"
}

# --- Config ---
$beaconEnabled = $true
$beaconLogPath = Join-Path $env:USERPROFILE ".beacon\endpoint\logs\runtime.jsonl"
$maxSessions = 20

if (Test-Path $ConfigPath) {
    try {
        $cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        if ($null -ne $cfg.beacon) {
            if ($null -ne $cfg.beacon.enabled) { $beaconEnabled = [bool]$cfg.beacon.enabled }
            if ($cfg.beacon.log_path) { $beaconLogPath = [Environment]::ExpandEnvironmentVariables($cfg.beacon.log_path) }
            if ($cfg.beacon.max_sessions) { $maxSessions = [int]$cfg.beacon.max_sessions }
        }
    } catch {
        Write-Log "beacon-sync: config illisible, valeurs par défaut utilisées" "WARN"
    }
}

if (-not $beaconEnabled) {
    Write-Log "beacon-sync: désactivé dans ingestion.config.json"
    exit 0
}

if (-not (Test-Path $beaconLogPath)) {
    Write-Log "beacon-sync: pas de journal Beacon ($beaconLogPath) — skip"
    exit 0
}

# --- .env : AGENT_DB_ROOT pour le mode dual ---
$ProjectRootDir = Split-Path -Parent (Split-Path -Parent $ScriptRoot)
$EnvFile = Join-Path $ProjectRootDir ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if (-not $_.StartsWith('#') -and $_ -match '^\s*AGENT_DB_ROOT\s*=\s*(.+)$') {
            $env:AGENT_DB_ROOT = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

$IngestScript = Join-Path (Join-Path (Split-Path -Parent $ScriptRoot) "rag") "beacon_ingest.py"
if (-not (Test-Path $IngestScript)) {
    Write-Log "beacon-sync: beacon_ingest.py introuvable ($IngestScript)" "WARN"
    exit 0
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$cliArgs = @($IngestScript, "--once", "--limit", "$maxSessions")
if ($DryRun) { $cliArgs += "--dry-run" }

Write-Log "beacon-sync: distillation des traces Beacon vers la mémoire unifiée..."
Push-Location $ProjectRootDir
try {
    & python @cliArgs 2>&1 | ForEach-Object { Write-Log "  $_" }
    if ($LASTEXITCODE -eq 0) {
        Write-Log "beacon-sync: synchronisation terminée."
    } else {
        Write-Log "beacon-sync: terminé avec erreurs (exit $LASTEXITCODE)" "WARN"
    }
} catch {
    Write-Log "beacon-sync: exception $_" "WARN"
} finally {
    Pop-Location
}
exit 0
