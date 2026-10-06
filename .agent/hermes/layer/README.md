# Hermès Integration Layer — Hephaistos-Kit Unified Memory System

Ce dossier contient la **couche d'intégration Hermès** — un module autonome conçu pour être injecté directement dans la configuration de Hermes (`~/.hermes/`).

Une fois injectée, cette couche donne à Hermes :
- La connaissance du système de mémoire unifiée de Hephaistos-Kit (Memory, Qdrant, Zvec, sqlite-node)
- Les patterns d'usage des MCP unifiés
- Les règles spécifiques à ce système
- La capacité de travailler avec le stockage dual (local + global)

## Structure de la couche

```
.agent/hermes/layer/
├── SOUL.hermes-extension.md    # Extension du SOUL.md global de Hermes
├── AGENTS.md                   # Règles projet pour le workspace Hermès
├── skills-adapters/            # Adaptateurs de compétences pour Hermès
├── agents-ref/                 # Références aux agents Hephaistos
└── README.md                   # Documentation de la couche
```

## Injection dans Hermes

Pour installer cette couche dans Hermes :

```powershell
# Depuis le répertoire de Hephaistos-Kit
pwsh -File .agent/hermes/inject-into-hermès.ps1

# Ou explicitement
pwsh -File .agent/hermes/inject-into-hermès.ps1 `
    -LayerPath .agent/hermes/layer `
    -HermèsHome $HOME/.hermes
```

Le script :
1. Copie `SOUL.hermes-extension.md` dans `~/.hermes/SOUL.hermes-extension.md`
2. Crée `~/.hermes/AGENTS.md` avec les règles du système de mémoire unifiée
3. Crée les répertoires `skills-adapters/` et `agents-ref/` dans `~/.hermes/`
4. Documente l'installation dans `~/.hermes/README.md`

## Ce que fait la couche injectée

### 1. Extension du SOUL.md global

Le fichier `SOUL.hermes-extension.md` est automatiquement chargé par Hermès après le `SOUL.md` principal. Il ajoute :

- La connaissance des MCP unifiés disponibles (Memory, Qdrant, Zvec, sqlite-node, filesystem, etc.)
- Les patterns d'usage prioritaires pour chaque MCP
- Les règles spécifiques au système de mémoire unifiée de Hephaistos-Kit
- La procédure de stockage dual (local + global via AGENT_DB_ROOT)

### 2. Règles projet (AGENTS.md)

Le fichier `AGENTS.md` dans `~/.hermes/` définit les règles applicables à TOUS les workspaces Hermès :

- Comment utiliser les MCP unifiés pour la mémoire, la recherche vectorielle, et le stockage
- Les procédures d'usage de la mémoire unifiée (sourcing systématique, traçage des décisions, etc.)
- Les règles de Clean Garden adaptées au système de mémoire

### 3. Adaptateurs de compétences

Le répertoire `skills-adapters/` contient des adaptateurs qui permettent à Hermès d'utiliser les compétences de Hephaistos-Kit via les MCP. Ces adaptateurs fournissent :

- Des wrappers pour les appels MCP fréquents
- Des procédures d'interaction avec le système de mémoire
- Des fonctions utilitaires pour les opérations courantes

### 4. Références aux agents

Le répertoire `agents-ref/` contient des descriptions des agents Hephaistos-Kit (orchestrator, project-planner, security-auditor, etc.) pour utilisation via `delegate_task` dans Hermès.

## Concept de couche

Cette approche permet de :

1. **Séparer la couche d'intégration du projet** : La couche Hermès peut être mise à jour indépendamment des projets qui l'utilisent
2. **Réutiliser la même couche pour tous les projets** : Une fois injectée dans Hermes, elle est disponible pour tous les workspaces
3. **Maintenir Hephaistos-Kit intact** : Le projet original n'est pas modifié; la couche est un module adjacent
4. **Permettre une injection sélective** : L'utilisateur peut choisir d'injecter uniquement certaines parties de la couche

## Components détaillés

### SOUL.hermes-extension.md

Ce fichier s'applique au SOUL.md global de Hermès. Il ajoute :

```markdown
# Extension — Hephaistos-Kit Unified Memory System

## 🧠 MCP UNIFIÉS DISPONIBLES

### Memory MCP (Knowledge Graph)
- `mcp_Memory_search_nodes` — Recherche dans le graphe
- `mcp_Memory_add_observations` — Ajouter des observations
- `mcp_Memory_create_entities` — Créer des entités
- `mcp_Memory_create_relations` — Créer des relations
- `mcp_Memory_read_graph` — Lire le graphe complet
- `mcp_Memory_delete_entities` / `_delete_observations` / `_delete_relations`
- `mcp_Memory_open_nodes` — Ouvrir des nœuds spécifiques

### Qdrant MCP (Vector 2048D)
- `mcp_qdrant_create_collection` — Créer une collection
- `mcp_qdrant_list_collections` — Lister les collections
- `mcp_qdrant_get_collection_info` — Info d'une collection
- `mcp_qdrant_search` — Recherche vectorielle
- `mcp_qdrant_add_documents` — Ajouter des documents
- `mcp_qdrant_delete_documents` — Supprimer des documents
- `mcp_qdrant_delete_collection` — Supprimer une collection
- `mcp_qdrant_create_instance` / `list_instances` / `switch_instance`

### Zvec MCP (Vector 2048D)
- `mcp_zvec_create_collection` — Créer une collection
- `mcp_zvec_list_collections` — Lister les collections
- `mcp_zvec_get_collection_info` — Info d'une collection
- `mcp_zvec_semantic_search` — Recherche sémantique
- `mcp_zvec_add_documents` — Ajouter des documents
- `mcp_zvec_delete_documents` — Supprimer des documents
- `mcp_zvec_delete_collection` — Supprimer une collection
- `mcp_zvec_create_store` / `list_stores` / `switch_store`

### sqlite-node MCP (SQLite multi-DB)
- `mcp_sqlite_node_connect_database` — Se connecter à une DB
- `mcp_sqlite_node_query_data` — SELECT
- `mcp_sqlite_node_execute_query` — INSERT/UPDATE/DELETE
- `mcp_sqlite_node_list_tables` — Lister les tables
- `mcp_sqlite_node_describe_table` — Description d'une table
- `mcp_sqlite_node_get_table_info` — Info complète d'une table
- `mcp_sqlite_node_list_databases` — Lister les DB
- `mcp_sqlite_node_switch_database` — Changer de DB
- `mcp_sqlite_node_attach_database` — Attacher une DB

## 📋 PROCÉDURES D'USAGE

### Mémoire unifiée — Flux de travail

1. **Début de session** : Consulter la mémoire existante via `mcp_Memory_search_nodes`
2. **Avant une tâche** : Vérifier si le contexte existe déjà
3. **Pendant la tâche** : Utiliser les MCP pour stocker/retrouver des informations
4. **Après une décision** : Tracer dans le KG via `mcp_Memory_add_observations`
5. **Fin de session** : Consolider les données vers le stockage global

### Recherche vectorielle — Routage

- **Tags catégoriques** (type, domain, scope, priority) → Qdrant
- **Tags sémantiques** (concept, action, entity, relation) → Zvec
- **Tags mixtes** → Routage dual (Qdrant + Zvec)

### Stockage dual

- **Local** : `memory-database/` dans le projet (toujours présent)
- **Global** : `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/` (junction vers local)

## ⚠️ RÈGLES SPÉCIFIQUES

### Architecture mémoire
- Toutes les données de mémoire DOIVENT être stockées dans `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/`
- Ne pas créer de bases SQLite hors de ce chemin sans justification
- Utiliser les tags `architecture`, `security`, `mcp-tool` systématiquement

### Intégrité des données
- La junction entre local et global doit être maintenue
- Ne pas modifier directement les fichiers .db sans passer par les MCP
- Utiliser les procédures d'usage définies dans ce fichier
```

### AGENTS.md (dans ~/.hermes/)

Ce fichier définit les règles pour tous les workspaces Hermès :

```markdown
# AGENTS.md — Hermès Global (Hephaistos-Kit Integration)

> Ce fichier s'applique à TOUS les workspaces Hermès.
> Il complète les règles spécifiques à chaque projet.

---

## 🔗 MCP UNIFIÉS — USAGE GLOBAL

### Mémoire unifiée (Hephaistos-Kit)

Les serveurs MCP suivants sont configurés globalement :

| Serveur | Type | Usage principal |
|---------|------|-----------------|
| **Memory** | Knowledge Graph | Entités, observations, relations |
| **Qdrant** | Vector 2048D | Recherche catégorique |
| **Zvec** | Vector 2048D | Recherche sémantique |
| **sqlite-node** | SQLite | Bases multiples, cache, graph |

### Procédures obligatoires

1. **Avant toute tâche** : `mcp_Memory_search_nodes` pour vérifier le contexte
2. **Après toute décision** : `mcp_Memory_add_observations` avec tags
3. **Recherche catégorique** : `mcp_qdrant_search` (tags: type, domain)
4. **Recherche sémantique** : `mcp_zvec_semantic_search` (tags: concept, action)

### Stockage

- **Local** : `memory-database/` dans le projet
- **Global** : `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/`
- **Junction** : locale → global (gérée par `start-workspace.ps1`)

---

## 📋 RÈGLES GLOBALES

### Langue
- TOUS les agents communiquent en **français**

### Évaluation des skills (obligatoire)
- Avant tout code : inventorier les skills, évaluer, annoncer le plan

### Clean Garden
- Modifier avant de créer
- Pas de duplication
- Demander avant de placer

---

## 🏗️ RÉFÉRENCES

- **Documentation Hephaistos-Kit** : `<KIT_ROOT>\.agent\hermes\README.md`
- **Config MCP** : `<KIT_ROOT>\.agent\mcp-config.json.exemple`
- **Architecture mémoire** : `<KIT_ROOT>\.agent\memory\ARCHITECTURE-ANALYSIS.md`
```

## Utilisation avec le script hermes-init.ps1

Le script `hermes-init.ps1` (déjà créé) peut être étendu pour utiliser cette couche :

```powershell
# Dans hermes-init.ps1, après les étapes 1-6 :

# 7. Injecter la couche Hermès si demandé
if ($InjectHermèsLayer) {
    Write-Host "[7/7] Injection de la couche Hermès..."
    & .agent/hermes/inject-into-hermès.ps1 -HermèsHome $HOME/.hermes
}
```

## Mise à jour de la couche

Pour mettre à jour la couche Injectée dans Hermès :

```powershell
# Réinjecter la couche (écrase les fichiers existants)
pwsh -File .agent/hermes/inject-into-hermès.ps1 -Force
```

## Retirer la couche

```powershell
# Retirer la couche de Hermès
Remove-Item "$HOME/.hermes/SOUL.hermes-extension.md" -Force
Remove-Item "$HOME/.hermes/AGENTS.md" -Force  # Si créé par l'injection
Remove-Item "$HOME/.hermes/hermes-integration/" -Recurse -Force
```

## Notes

- La couche ne remplace PAS le SOUL.md global de Hermès, elle s'y ajoute
- La couche ne modifie PAS les configurations de projet existantes
- La couche est réutilisable pour tous les projets Hermès
- La couche peut être mise à jour indépendamment de Hephaistos-Kit
