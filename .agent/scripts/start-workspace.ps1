Param(
    [ValidateSet('auto', 'force', 'skip')]
    [string]$IngestMode = 'auto',
    [switch]$Watch = $true,
    [switch]$Quiet = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Configuration du logging
$ScriptRoot = $PSScriptRoot
if (-not $ScriptRoot) { $ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
$LogDir = Join-Path $ScriptRoot "..\logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$LogFile = Join-Path $LogDir "workspace.log"
$ErrorLogFile = Join-Path $LogDir "error.log"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    
    try {
        Add-Content -Path $LogFile -Value $logEntry -ErrorAction SilentlyContinue
    }
    catch {
        # Si le fichier log est inaccessible, on continue quand même
    }
    
    Write-Host $logEntry
}

function Set-Junction {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Target,
        [switch]$Optional
    )

    $resolvedTarget = [System.IO.Path]::GetFullPath($Target)
    if (-not (Test-Path $resolvedTarget)) {
        New-Item -ItemType Directory -Path $resolvedTarget -Force | Out-Null
    }

    if (Test-Path $Path) {
        $item = Get-Item $Path -Force -ErrorAction SilentlyContinue
        if ($item -and $item.LinkType -eq "Junction") {
            $currentTarget = @($item.Target)[0]
            if ($currentTarget) {
                $currentTarget = [System.IO.Path]::GetFullPath($currentTarget)
            }
            if ($currentTarget -eq $resolvedTarget) {
                Write-Log "Junction déjà OK: $Path -> $resolvedTarget"
                return
            }
            cmd /c "rmdir `"$Path`"" 2>$null | Out-Null
        }
        else {
            Write-Log "Remplacement du dossier existant par une junction: $Path" "WARN"
            Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue | ForEach-Object {
                $dest = Join-Path $resolvedTarget $_.Name
                if (-not (Test-Path -LiteralPath $dest)) {
                    Move-Item -LiteralPath $_.FullName -Destination $dest -Force -ErrorAction SilentlyContinue
                }
            }
            cmd /c "rmdir /s /q `"$Path`"" 2>$null | Out-Null
            if (Test-Path $Path) {
                Remove-Item -LiteralPath $Path -Force -Recurse -ErrorAction SilentlyContinue
            }
        }
    }

    if (Test-Path $Path) {
        $message = "Impossible de remplacer '$Path' par une junction vers '$resolvedTarget' (dossier verrouillé)."
        if ($Optional) {
            Write-Log "$message Le workspace continue avec le dossier local." "WARN"
            return
        }
        throw $message
    }

    New-Item -ItemType Junction -Path $Path -Target $resolvedTarget -Force | Out-Null
    Write-Log "Junction créée: $Path -> $resolvedTarget"
}

function Write-ErrorLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [ERROR] $Message"
    
    try {
        Add-Content -Path $ErrorLogFile -Value $logEntry -ErrorAction SilentlyContinue
    }
    catch {
        # Si le fichier error log est inaccessible, on continue quand même
    }
    
    Write-Host $logEntry -ForegroundColor Red
}

# $ScriptRoot is already defined at the top
$ProjectRoot = Split-Path -Parent $ScriptRoot  # = .agent folder
$ProjectRootDir = Split-Path -Parent $ProjectRoot  # = actual project root
$autoIngest = Join-Path $ScriptRoot 'auto-ingest.ps1'
$ingestScript = Join-Path $ScriptRoot 'ingest-workspace.ps1'
$ingestConfig = Join-Path $ScriptRoot 'ingestion.config.json'
$monitorScript = Join-Path $ScriptRoot 'monitor.js'

# --- INITIALISATION STRUCTURELLE CRITIQUE (SYNCHRONE) ---
$MemoryDbRoot = Join-Path $ScriptRoot "../memory-database"
$GraphDir = Join-Path $MemoryDbRoot "graph"
$VectorDir = Join-Path $MemoryDbRoot "vector"
$CacheDir = Join-Path $MemoryDbRoot "cache"
$KnowledgeDir = Join-Path $ScriptRoot "../knowledge"

# Création immédiate des dossiers parents UNIQUEMENT.
# Les fichiers .db seront créés proprement par les serveurs MCP lors de l'accès.
$criticalDirs = @($GraphDir, $VectorDir, $CacheDir, $KnowledgeDir)
foreach ($dir in $criticalDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

Write-Log "Structure de répertoires locale synchronisée."

# --- LECTURE DU FICHIER .ENV ---
$EnvFile = Join-Path $ProjectRootDir ".env"
if (Test-Path $EnvFile) {
    Write-Log "Lecture de .env..."
    Get-Content $EnvFile | ForEach-Object {
        if (-not $_.StartsWith('#')) {
            $parts = $_.Split('=', 2)
            if ($parts.Count -eq 2) {
                $key = $parts[0].Trim()
                $value = $parts[1].Trim()
                # Supprimer les guillemets si présents
                if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") {
                    $value = $matches[1]
                }
                if ($key -eq "AGENT_DB_ROOT" -and -not [string]::IsNullOrWhiteSpace($value)) {
                    $env:AGENT_DB_ROOT = $value
                    Write-Log "AGENT_DB_ROOT défini depuis .env: $value"
                }
            }
        }
    }
}

# --- STOCKAGE DUAL-MODE (LOCAL + GLOBAL) ---
# Mode LOCAL: ./memory-database/agentmemory/ (toujours)
# Mode GLOBAL: junction vers stockage externe (optionnel)

$UseGlobalStorage = $false
$GlobalDbRoot = $null

if ($env:AGENT_DB_ROOT) {
    # Mode GLOBAL activé via .env
    $UseGlobalStorage = $true
    $GlobalDbRoot = $env:AGENT_DB_ROOT
}

$LocalMemoryDb = Join-Path $ProjectRootDir "memory-database"

Write-Log "Configuration DUAL-MODE..."

# 1. Structure LOCAL (toujours créée) — uniquement agentmemory, pas de doublons racine
$localAgentDir = Join-Path $LocalMemoryDb "agentmemory"

foreach ($dir in @($localAgentDir)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

# 2. Structure GLOBAL (si activé)
if ($UseGlobalStorage) {
    $GlobalWorkspaceDir = Join-Path $GlobalDbRoot "current_workspace"

    Write-Log "Mode GLOBAL activé - DbRoot: $GlobalDbRoot"
    
    # Créer le dossier global s'il n'existe pas
    if (-not (Test-Path $GlobalWorkspaceDir)) { 
        New-Item -ItemType Directory -Path $GlobalWorkspaceDir -Force | Out-Null 
    }
    
    # Créer les sous-dossiers dans le stockage global
    $globalCacheDir = Join-Path $GlobalWorkspaceDir "cache"
    $globalGraphDir = Join-Path $GlobalWorkspaceDir "graph"
    $globalVectorDir = Join-Path $GlobalWorkspaceDir "vector"
    foreach ($dir in @($globalCacheDir, $globalGraphDir, $globalVectorDir)) {
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    }
    
    Set-Junction -Path $LocalMemoryDb -Target $GlobalWorkspaceDir
}
else {
    Write-Log "Mode LOCAL uniquement - Pas de junction"
}

# Nettoyage de la junction obsolète semantic-cache-data (le cache est désormais
# accessible via memory-database/cache — une seule junction racine suffit)
$StaleCacheJunction = Join-Path $ProjectRootDir "semantic-cache-data"
if (Test-Path $StaleCacheJunction) {
    $staleItem = Get-Item $StaleCacheJunction -Force -ErrorAction SilentlyContinue
    if ($staleItem -and $staleItem.LinkType -eq "Junction") {
        $staleItem.Delete()
        Write-Log "Junction obsolète supprimée: $StaleCacheJunction"
    }
}

Write-Log "Stockage LOCAL: $localAgentDir"

# Créer les sous-répertoires pour MCP (graph, vector) dans le stockage GLOBAL
$globalGraphDir = Join-Path $LocalMemoryDb "graph"
$globalVectorDir = Join-Path $LocalMemoryDb "vector"
foreach ($dir in @($globalGraphDir, $globalVectorDir)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

# --- LES SERVEURS MCP SONT GÉRÉS PAR L'IDE (DEVIN) ---
# Suppression du démarrage manuel pour éviter les conflits de ports et les erreurs système.

# --- PONT REST RAG (AUTONOME) ---
# Lance le pont HTTP Python qui traduit les appels REST du pipeline
# en appels MCP stdio vers Zvec et Memory (instances dédiées, non gérées par l'IDE).
$BridgeScript = Join-Path (Join-Path $ProjectRoot "rag") "rag_rest_bridge.py"
$BridgePidFile = Join-Path $ScriptRoot "rag_bridge.pid"

# Arrêter le bridge précédent s'il tourne encore
if (Test-Path $BridgePidFile) {
    $oldPid = Get-Content $BridgePidFile -ErrorAction SilentlyContinue
    if ($oldPid) {
        try {
            $oldProc = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
            if ($oldProc) { 
                Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
                Start-Sleep -Milliseconds 500
            }
        }
        catch { }  # Process déjà mort, on continue
    }
    Remove-Item $BridgePidFile -Force -ErrorAction SilentlyContinue
}

# FERMETURE DES ORPHELINS (Zvec, Memory)
# Le bridge peut laisser des processus node en vie s'il est tué avec -Force
$orphans = @(Get-Process node -ErrorAction SilentlyContinue | Where-Object { 
    try { $_.CommandLine -like "*Zvec*" -or $_.CommandLine -like "*memory*" } catch { $false }
})

if ($orphans.Count -gt 0) {
    Write-Log "Nettoyage de $($orphans.Count) processus MCP orphelins..."
    $orphans | Stop-Process -Force -ErrorAction SilentlyContinue
}


# Vérifier les ports 8001 / 8002 libres (LISTENING uniquement — pas les connexions sortantes)
$port8001Busy = (netstat -ano 2>$null | Select-String "LISTENING" | Select-String ":8001\s") -ne $null
$port8002Busy = (netstat -ano 2>$null | Select-String "LISTENING" | Select-String ":8002\s") -ne $null

if ($port8001Busy -or $port8002Busy) {
    Write-Log "⚠️  Ports 8001/8002 déjà occupés - ponte REST peut-être déjà actif."
}
else {
    if (Test-Path $BridgeScript) {
        Write-Log "Démarrage du pont REST RAG (ports 8001/8002)..."
        $zvecDataDir = Join-Path (Join-Path (Join-Path $ProjectRoot "memory-database") "vector") "zvec"
        $ProjectName = Split-Path -Leaf $ProjectRootDir
        
        # Définir les variables d'environnement pour le processus bridge
        $env:ZVEC_BRIDGE_PORT = "8001"
        $env:MEMORY_BRIDGE_PORT = "8002"
        $env:ZVEC_DATA_DIR = $zvecDataDir
        # UTF-8 obligatoire : le bridge log des emojis, cp1252 le tue sinon
        $env:PYTHONUTF8 = "1"
        $env:PYTHONIOENCODING = "utf-8"
        # Chemins explicites des serveurs MCP (installations globales partagées)
        # Priorité : variables d'env, sinon racine des serveurs installés
        $serversRoot = if ($env:MCP_SERVERS_ROOT) { $env:MCP_SERVERS_ROOT } else { "C:\Program Files\servers" }
        $zvecMcpJs = if ($env:ZVEC_MCP_PATH) { $env:ZVEC_MCP_PATH } else { "$serversRoot\zvec-mcp-server\build\index.js" }
        $memoryMcpJs = if ($env:MEMORY_MCP_PATH) { $env:MEMORY_MCP_PATH } else { "$serversRoot\memory\dist\index.js" }
        if (Test-Path $zvecMcpJs) { $env:ZVEC_MCP_PATH = $zvecMcpJs }
        if (Test-Path $memoryMcpJs) { $env:MEMORY_MCP_PATH = $memoryMcpJs }
        if ($env:AGENT_DB_ROOT) {
            # On aligne sur current_workspace qui est la cible de la junction locale
            $env:ZVEC_DATA_DIR = Join-Path (Join-Path (Join-Path $env:AGENT_DB_ROOT "current_workspace") "vector") "zvec"
            $env:MEMORY_DB_PATH = Join-Path (Join-Path (Join-Path (Join-Path $env:AGENT_DB_ROOT "current_workspace") "agentmemory") "graph") "memory_mcp.db"
        }

        
        $bridgeLogFile = Join-Path $ScriptRoot "rag_bridge_stdout.log"
        $bridgeErrorFile = Join-Path $ScriptRoot "rag_bridge_stderr.log"
        $bridgeFolder = Split-Path $BridgeScript -Parent
        # Utiliser WorkingDirectory permet d'éviter les problèmes d'espaces dans le chemin du script
        $bridgeProcess = Start-Process python -ArgumentList @("-u", "rag_rest_bridge.py") -WorkingDirectory $bridgeFolder -WindowStyle Hidden -PassThru -RedirectStandardOutput $bridgeLogFile -RedirectStandardError $bridgeErrorFile

        
        $bridgeProcess.Id | Out-File $BridgePidFile -Encoding ascii
        Write-Log "✅ Pont REST RAG lancé (PID=$($bridgeProcess.Id))"
        
        # Attendre que le bridge soit prêt (max 60 secondes)
        $maxWait = 60

        $ready = $false
        for ($i = 0; $i -lt $maxWait; $i++) {
            Start-Sleep -Seconds 1
            try {
                $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -TimeoutSec 1 -ErrorAction Stop
                if ($resp.StatusCode -eq 200) { $ready = $true; break }
            }
            catch { }
        }
        if ($ready) {
            Write-Log "✅ Pont REST RAG opérationnel et répondant."
        }
        else {
            Write-Log "⚠️  Pont REST RAG timeout (vérifie rag_bridge.log)"
        }
    }
    else {
        Write-Log "⚠️  Script pont REST non trouvé : $BridgeScript"
    }
}

# Lancer le moniteur en arrière-plan
Write-Log "Lancement du Moniteur (Port 3055)"
Start-Process node -ArgumentList $monitorScript -WindowStyle Hidden

Write-Log "Vérification/ingestion initiale ($IngestMode)"

& powershell -ExecutionPolicy Bypass -File $autoIngest -Mode $IngestMode -ConfigPath $ingestConfig

# --- SYNC BEACON -> MÉMOIRE UNIFIÉE (non-bloquant, non-fatal) ---
# Distille les traces d'agents capturées par Beacon (runtime.jsonl) et les
# injecte dans le pipeline RAG (zvec/qdrant + memory_mcp.db) en mode dual.
$beaconSync = Join-Path $ScriptRoot 'beacon-sync.ps1'
if (Test-Path $beaconSync) {
    Write-Log "Synchronisation Beacon -> mémoire unifiée..."
    & powershell -ExecutionPolicy Bypass -File $beaconSync -ConfigPath $ingestConfig
}

# --- MAINTENANCE MEMOIRE UNIFIEE (non-bloquant, non-fatal) ---
# Purge caches expires, relations orphelines KG, checkpoint WAL, rapport
# auto-observe dans kv (maintenance:last_report) -> consomme par /reflect.
$memMaint = Join-Path $ScriptRoot 'memory-maintenance.ps1'
if (Test-Path $memMaint) {
    Write-Log "Maintenance memoire unifiee..."
    & powershell -ExecutionPolicy Bypass -File $memMaint
}

if ($Watch) {
    Write-Log "Lancement de la surveillance continue (Ctrl+C pour arrêter)"
    $cmdArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ingestScript, "-Mode", "watch", "-ConfigPath", $ingestConfig)
    & powershell @cmdArgs
}
else {
    Write-Log "Surveillance désactivée (paramètre -Watch:$false)"
}
