#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Hermes-compatible injection du système de mémoire unifiée Hephaistos-Kit dans un workspace Hermès.
.DESCRIPTION
    Crée la structure .agent/hermes/ dans un projet Hermès pour utiliser les MCP unifiés
    (Memory, Qdrant, Zvec, sqlite-node), le stockage dual (local+global), et les conventions
    du projet, sans modifier le projet Hephaistos-Kit source ni supprimer l'injection existante.
.PARAMETER ProjectPath
    Chemin du workspace Hermès cible (par défaut: pwd)
.PARAMETER DbRoot
    Racine globale de stockage (AGENT_DB_ROOT). Par défaut: <HEPHAISTOS_DATA> (comme dans .env.example)
.PARAMETER ProjectId
    Identifiant du projet pour l'isolation mémoire. Par défaut: nom du répertoire.
.EXAMPLE
    ./hermes-init.ps1 -ProjectPath <PROJECTS_ROOT>/mon-projet-hermès
.EXAMPLE
    ./hermes-init.ps1 -ProjectPath <PROJECTS_ROOT>/marotte -ProjectId marotte
#>
[CmdletBinding()]
param(
    [string]$ProjectPath = (Get-Location).Path,
    [string]$DbRoot = "<HEPHAISTOS_DATA>",
    [string]$ProjectId = (Split-Path $ProjectPath -Leaf)
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Resolve-Path $ProjectPath
$AgentDir = Join-Path $ProjectRoot '.agent'
$HermesDir = Join-Path $AgentDir 'hermes'
$MemoryDbDir = Join-Path $ProjectRoot 'memory-database'
$CurrentWorkspace = Join-Path $DbRoot 'current_workspace'
$ProjectWorkspace = Join-Path $CurrentWorkspace $ProjectId

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  HERMÈS INJECTION — Hephaistos-Kit" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "Projet cible : $ProjectRoot"
Write-Host "ProjectId    : $ProjectId"
Write-Host "AGENT_DB_ROOT: $DbRoot"
Write-Host "Workspace    : $ProjectWorkspace`n"

# ============================================================
# 1. CRÉER LA STRUCTURE DE STOCKAGE LOCALE (si absente)
# ============================================================
Write-Host "[1/6] Structure de stockage locale..." -ForegroundColor Yellow

$localDirs = @(
    (Join-Path $MemoryDbDir 'agentmemory'),
    (Join-Path $MemoryDbDir 'graph'),
    (Join-Path $MemoryDbDir 'vector'),
    (Join-Path $MemoryDbDir 'cache')
)
foreach ($d in $localDirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Host "  + $d" -ForegroundColor Gray
    }
}

# ============================================================
# 2. JUNCTION VERS STOCKAGE GLOBAL (mode dual, comme start-workspace.ps1)
# ============================================================
Write-Host "[2/6] Junction stockage global..." -ForegroundColor Yellow

if (-not (Test-Path $ProjectWorkspace)) {
    New-Item -ItemType Directory -Path $ProjectWorkspace -Force | Out-Null
    Write-Host "  + $ProjectWorkspace (créé)" -ForegroundColor Green
}

# Créer les sous-dossiers globaux si absents
$globalSubdirs = @('cache', 'graph', 'vector', 'vector/zvec-data')
foreach ($sub in $globalSubdirs) {
    $gd = Join-Path $ProjectWorkspace $sub
    if (-not (Test-Path $gd)) {
        New-Item -ItemType Directory -Path $gd -Force | Out-Null
    }
}

# Établir la junction locale -> global (comme start-workspace.ps1 le fait)
$localMemoryDb = Join-Path $ProjectRoot 'memory-database'
if (-not (Test-Path $localMemoryDb)) {
    New-Item -ItemType Junction -Path $localMemoryDb -Target $ProjectWorkspace -Force | Out-Null
    Write-Host "  ~ memory-database -> $ProjectWorkspace (junction)" -ForegroundColor Cyan
} else {
    Write-Host "  ~ memory-database déjà existant (skip junction)" -ForegroundColor Gray
}

# ============================================================
# 3. CRÉER .agent/hermes/ (couche d'intégration Hermès)
# ============================================================
Write-Host "[3/6] Couche d'intégration Hermès..." -ForegroundColor Yellow

$hermesSubdirs = @('skills-adapters', 'agents-ref')
foreach ($sub in $hermesSubdirs) {
    $d = Join-Path $HermesDir $sub
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}

# ============================================================
# 4. FICHIER .env (si absent — pour AGENT_DB_ROOT)
# ============================================================
Write-Host "[4/6] Variable d'environnement..." -ForegroundColor Yellow

$envFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $envFile)) {
    $envContent = @"
# Hephaistos-Kit / Hermès — Configuration mémoire unifiée
# Autorisé: modification, ajout de clés.
# Ne pas committer les secrets.

AGENT_DB_ROOT=$DbRoot
PROJECT_ID=$ProjectId
"@
    $envContent | Set-Content -Path $envFile -Encoding UTF8
    Write-Host "  + .env créé" -ForegroundColor Green
} else {
    # Ajouter AGENT_DB_ROOT si absent
    $envContent = Get-Content $envFile -Raw
    if ($envContent -notmatch 'AGENT_DB_ROOT=') {
        Add-Content -Path $envFile -Value "`nAGENT_DB_ROOT=$DbRoot" -Encoding UTF8
        Write-Host "  ~ AGENT_DB_ROOT ajouté à .env existant" -ForegroundColor Cyan
    } else {
        Write-Host "  ~ .env déjà configuré (skip)" -ForegroundColor Gray
    }
}

# ============================================================
# 5. FICHIER AGENTS.md (règles projet compatibles Hermès)
# ============================================================
Write-Host "[5/6] Fichier AGENTS.md (règles projet)..." -ForegroundColor Yellow

$agentsMd = @"
# AGENTS.md — Projet $ProjectId

> Ce fichier est chargé automatiquement par Hermès à chaque session dans ce projet.
> Il complète le SOUL.md global (`$HOME/.hermes/SOUL.md`) avec les règles spécifiques au projet.

---

## 🔗 CONNEXION AUX MCP UNIFIÉS (Hephaistos-Kit)

Les serveurs MCP suivants sont configurés globalement et disponibles dans ce projet :

| Serveur | Outils | Usage dans ce projet |
|---------|--------|----------------------|
| **Memory** | 9 | Knowledge Graph : créér/lier/observer/supprimer entités, search, read_graph |
| **Qdrant** | 10 | Vector store 2048D (NVIDIA NIM) : collections, documents, search catégorique |
| **Zvec** | 10 | Vector store 2048D (NVIDIA NIM) : stores, collections, semantic_search |
| **sqlite-node** | 9 | SQLite multi-bases : connect, query, execute, describe, list_tables |
| **filesystem** | 11 | Lecture/écriture/recherche de fichiers (étendu via Hephaistos-Kit) |
| **kaggle** | 51 | Compétitions, datasets, kernels (si pertinent) |
| **colab-mcp** | 1 | Session Colab (si pertinent) |
| **devin/context7** | 2 | Docs libraries (si pertinent) |

> **Total : 103 outils MCP disponibles**, tous connectés.

---

## 🧠 MÉMOIRE UNIFIÉE — MODE D'EMPLOI

### Stockage dual
- **Local** : `memory-database/` dans le projet (toujours présent)
- **Global** : `<HEPHAISTOS_DATA>/current_workspace/$ProjectId/` (junction vers local)

### Databases utilisées
| Base | Chemin | Usage |
|------|--------|-------|
| `memory_mcp.db` | `<HEPHAISTOS_DATA>/current_workspace/$ProjectId/graph/memory_mcp.db` | Knowledge Graph principal |
| `graph-memory.db` | `<HEPHAISTOS_DATA>/current_workspace/$ProjectId/graph/graph-memory.db` | Edges rapides |
| `runtime-cache.db` | `<HEPHAISTOS_DATA>/current_workspace/$ProjectId/cache/runtime-cache.db` | Cache runtime |
| `zvec.db` | `<HEPHAISTOS_DATA>/current_workspace/$ProjectId/vector/zvec/zvec.db` | Index vectoriel 2048D |
| `qdrant.db` | `<HEPHAISTOS_DATA>/current_workspace/$ProjectId/vector/qdrant/qdrant.db` | Index vectoriel 2048D |

### Procédure d'usage
1. **Avant toute tâche** : `mcp_Memory_search_nodes` pour vérifier le contexte existant
2. **Après une décision** : `mcp_Memory_add_observations` avec tags (`architecture`, `security`, `mcp-tool`)
3. **Recherche catégorique** : `mcp_qdrant_search` (tags: type, domain, scope)
4. **Recherche sémantique** : `mcp_zvec_semantic_search` (tags: concept, action, entity)
5. **Lecture BP** : `mcp_sqlite_node_query_data` sur `graph-memory.db` (lectures seule)

---

## 📋 RÈGLES PROPRES AU PROJET

### Clean Garden (surcharge globale si nécessaire)
- Toujours vérifier si un fichier similaire existe avant de créer
- Privilégier la modification des fichiers existants
- Ne pas dupliquer — centraliser

### Langue
- Toutes les réponses en **français** (déjà imposé par SOUL.md global)

### Évaluation des skills (obligatoire)
- Avant tout code : inventorier les skills/tools, évaluer leur pertinence, annoncer le plan
- Processus en 4 étapes (détaillé dans SOUL.md global)

---

## 🏗️ STRUCTURE DU PROJET

\$ProjectRoot/
├── .agent/              ← Configuration projet (agents, skills, workflows)
│   ├── agents/          ← (futurs agents spécialisés du projet)
│   ├── skills/          ← (futurs skills du projet)
│   ├── workflows/       ← (futurs workflows slash-commands)
│   ├── hermes/          ← ◀ Couche d'intégration Hermès (cette couche)
│   │   ├── skills-adapters/  ← Adaptateurs de compétences
│   │   └── agents-ref/       ← Références aux agents Hephaistos
│   └── rules/
│       └── global_rules.md ← Règles globales du système (lecture seule)
├── memory-database/     ← Stockage local (junction vers global)
│   ├── agentmemory/
│   ├── graph/
│   ├── vector/
│   └── cache/
├── .env                 ← AGENT_DB_ROOT + PROJECT_ID
└── MANIFEST.md          ← (à créer) Définition du projet
"@

$agentsPath = Join-Path $ProjectRoot 'AGENTS.md'
$agentsMd | Set-Content -Path $agentsPath -Encoding UTF8
Write-Host "  + AGENTS.md créé" -ForegroundColor Green

# ============================================================
# 6. FICHIER SOUL.HERMES.MD (identité session sur mesure)
# ============================================================
Write-Host "[6/6] Fichier SOUL.hermes.md (identité session)..." -ForegroundColor Yellow

$soulHermes = @"
# SOUL.hermes.md — Session identity override for $ProjectId

> Ce fichier S'APPLIQUE sur le SOUL.md global (`$HOME/.hermes/SOUL.md`) quand
> Hermès démarre dans ce projet. Il ajoute des règles spécifiques au projet.

---

## 🎯 CONTEXTE DU PROJET

- **Nom** : $ProjectId
- **Chemin** : $ProjectRoot
- **AGENT_DB_ROOT** : $DbRoot
- **Workspace mémoire** : $ProjectWorkspace

---

## 🔗 MCP TOOLS — Usage prioritaire dans ce projet

### Mémoire (prioritaire absolu)
1. `mcp_Memory_search_nodes` — Avant toute tâche, chercher le contexte existant
2. `mcp_Memory_add_observations` — Après toute décision, tracer avec tags
3. `mcp_Memory_create_entities` / `memory.create_relations` — Structurer le KG

### Vector search
4. `mcp_qdrant_search` — Recherche catégorique (tags: type, domain, scope, priority)
5. `mcp_zvec_semantic_search` — Recherche sémantique (tags: concept, action, entity, relation)

### SQLite
6. `mcp_sqlite_node_connect_database` — Se connecter à une DB
7. `mcp_sqlite_node_query_data` — SELECT sur une DB connectée
8. `mcp_sqlite_node_execute_query` — INSERT/UPDATE/DELETE

### Fichiers
9. `mcp_filesystem_read_file` / `write_file` / `edit_file`
10. `mcp_filesystem_list_directory` / `search_files`
11. `mcp_filesystem_directory_tree`

---

## ⚠️ RÈGLES SPÉCIFIQUES À CE PROJET

### Architecture mémoire
- Toutes les données de mémoire DOIVENT être stockées dans `${AGENT_DB_ROOT}/current_workspace/$ProjectId/`
- Ne pas créer de bases SQLite hors de ce chemin sans justification
- Utiliser les tags `architecture`, `security`, `mcp-tool` systématiquement

### Chemins
- Les chemins absolus dans ce projet utilisent la racine : $ProjectRoot
- Les chemins relatifs sont exprimés depuis $ProjectRoot

### Communiquer en français
- Obligatoire (déjà imposé par SOUL.md global, mais rappelé ici)

---

## 📚 RÉFÉRENCES

- **SOUL.md global** : $HOME/.hermes/SOUL.md
- **AGENTS.md** : $ProjectRoot/AGENTS.md
- **Config MCP Hephaistos-Kit** : .agent/mcp-config.json.exemple
- **Documentation mémoire** : .agent/memory/ARCHITECTURE-ANALYSIS.md
"@

$soulHermesPath = Join-Path $HermesDir 'SOUL.hermes.md'
$soulHermes | Set-Content -Path $soulHermesPath -Encoding UTF8
Write-Host "  + SOUL.hermes.md créé" -ForegroundColor Green

# ============================================================
# RÉSUMÉ
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  INJECTION HERMÈS TERMINÉE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Ce qui a été créé dans $ProjectRoot :" -ForegroundColor White
Write-Host "  .env                       ← AGENT_DB_ROOT + PROJECT_ID" -ForegroundColor Green
Write-Host "  AGENTS.md                  ← Règles projet compatibles Hermès" -ForegroundColor Green
Write-Host ".agent/hermes/ ← Couche d'intégration" -ForegroundColor Green
Write-Host "    SOUL.hermes.md          ← Identité session sur mesure" -ForegroundColor Green
Write-Host "    skills-adapters/        ← (répertoire pour adaptateurs)" -ForegroundColor Green
Write-Host "    agents-ref/             ← (répertoire pour refs agents)" -ForegroundColor Green
Write-Host "  memory-database/           ← Structure de stockage locale" -ForegroundColor Green
Write-Host "`nStockage global : $ProjectWorkspace" -ForegroundColor Cyan
Write-Host "Junction locale : $localMemoryDb -> $ProjectWorkspace" -ForegroundColor Cyan
Write-Host "`nProchaines étapes :" -ForegroundColor Yellow
Write-Host "  1. Redémarrer Hermès (ou relancer la session) pour charger AGENTS.md + SOUL.hermes.md" -ForegroundColor White
Write-Host "  2. Tester la mémoire : mcp_Memory_search_nodes sur ce projet" -ForegroundColor White
Write-Host "  3. Créer un MANIFEST.md si nécessaire" -ForegroundColor White
