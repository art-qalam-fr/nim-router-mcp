# install-devin-integration.ps1 — installe la couche Devin globale Hephaistos-Kit
# Usage : pwsh -File .agent\devin\install-devin-integration.ps1 [-HermesSkillsDir <path>]
[CmdletBinding()]
param(
    [string]$HermesSkillsDir = "$env:LOCALAPPDATA\hermes\skills",
    [string]$DevinConfigDir  = "$env:USERPROFILE\.config\devin",
    [string]$DevinSkillsDir  = "$env:APPDATA\devin\skills"
)

$ErrorActionPreference = 'Stop'
$LayerDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Installation couche Devin (Hephaistos-Kit) ===" -ForegroundColor Cyan

# 1. Scripts
$scriptsTarget = Join-Path $DevinConfigDir 'scripts'
New-Item -ItemType Directory -Force -Path $scriptsTarget | Out-Null
Copy-Item (Join-Path $LayerDir 'scripts\*.mjs') $scriptsTarget -Force
Write-Host "[1/4] Scripts copiés -> $scriptsTarget" -ForegroundColor Green

# 2. Hooks : fusion dans config.json (backup d'abord)
$configFile = Join-Path $DevinConfigDir 'config.json'
if (-not (Test-Path $configFile)) { '{}' | Set-Content $configFile -Encoding UTF8 }
Copy-Item $configFile "$configFile.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')" -Force

$cfg = Get-Content $configFile -Raw | ConvertFrom-Json
if (-not $cfg.hooks) { $cfg | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) }

$events = @{
    SessionStart      = 'session-start'
    UserPromptSubmit  = 'prompt-submit'
    Stop              = 'stop'
}
foreach ($evt in $events.Keys) {
    $cmd = "node '$($scriptsTarget -replace '\\','\\')\awareness.mjs' $($events[$evt])"
    if (-not $cfg.hooks.$evt) {
        $cfg.hooks | Add-Member -NotePropertyName $evt -NotePropertyValue @()
    }
    $already = $cfg.hooks.$evt | Where-Object { $_.hooks | Where-Object { $_.command -like '*awareness.mjs*' } }
    if (-not $already) {
        $cfg.hooks.$evt += [pscustomobject]@{
            hooks = @([pscustomobject]@{ type = 'command'; command = $cmd; timeout = 30 })
        }
        Write-Host "[2/4] Hook '$evt' ajouté" -ForegroundColor Green
    } else {
        Write-Host "[2/4] Hook '$evt' déjà présent (skip)" -ForegroundColor Yellow
    }
}
$cfg | ConvertTo-Json -Depth 20 | Set-Content $configFile -Encoding UTF8

# 3. Skills Hermès -> Devin global
if (Test-Path $HermesSkillsDir) {
    New-Item -ItemType Directory -Force -Path $DevinSkillsDir | Out-Null
    Copy-Item "$HermesSkillsDir\*" $DevinSkillsDir -Recurse -Force
    $count = (Get-ChildItem $DevinSkillsDir -Directory).Count
    Write-Host "[3/4] $count skills copiés -> $DevinSkillsDir" -ForegroundColor Green
} else {
    Write-Host "[3/4] Skills Hermès introuvables : $HermesSkillsDir (skip)" -ForegroundColor Yellow
}

# 4. Rappel enregistrement orchestrateur
Write-Host "[4/4] Pour enregistrer Devin dans l'orchestrateur MCP :" -ForegroundColor Cyan
Write-Host '  register_agent("devin", "cli", {"skills":["*"],"command":"devin -p \"{message}\" --respect-workspace-trust false"})'
Write-Host "=== Terminé. Vérifiez avec /hooks et /mcp dans une session Devin. ===" -ForegroundColor Cyan
