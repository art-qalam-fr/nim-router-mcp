# AGENTS.md — Hermès Global (Hephaistos-Kit Integration Layer)

> Ce fichier s'applique à TOUS les workspaces Hermès.
> Il définit les règles globales pour l'utilisation du système de mémoire unifiée de Hephaistos-Kit.

---

## 🔗 MCP UNIFIÉS — CONFIGURATION GLOBALE

Les serveurs MCP suivants sont configurés dans `$HOME/.hermes/config.yaml` et disponibles pour tous les workspaces :

| Serveur | Transport | Outils | Utilisation principale |
|---------|-----------|--------|------------------------|
| **Memory** | stdio (node) | 9 | Knowledge Graph : entités, observations, relations, search |
| **Qdrant** | stdio (node) | 10 | Vector store 2048D : collections, documents, search catégorique |
| **Zvec** | stdio (node) | 10 | Vector store 2048D : stores, collections, semantic_search |
| **sqlite-node** | stdio (node) | 9 | SQLite multi-DB : connect, query, execute, describe, list_tables |
| **filesystem** | stdio (node) | 11 | Fichiers : read, write, edit, search, directory, tree |
| **kaggle** | stdio (exe) | 51 | Kaggle : compétitions, datasets, kernels, modèles |
| **sequentialthinking** | stdio (node) | 1 | Raisonnement structuré étape par étape |
| **colab-mcp** | stdio (uvx) | 1 | Session Colab : ouverture de connexion navigateur |
| **devin/context7** | stdio (node) | 2 | Documentation libraries : resolve + get-library-docs |

> **Total : 104 outils MCP disponibles**, tous connectés et fonctionnels.

---

## 🧠 PROCÉDURES MÉMOIRE UNIFIÉE — OBLIGATOIRES

### A. Sourcing systématique (AVANT toute tâche)

1. **Utiliser `mcp_Memory_search_nodes`** pour vérifier si le contexte existe déjà
2. **Si le contexte existe** : réutiliser sans re-explorer (économie de tokens)
3. **Si le contexte n'existe pas** : créer le contexte nécessaire avant de commencer

### B. Traçage des décisions (APRÈS toute décision importante)

1. **Utiliser `mcp_Memory_add_observations`** pour documenter la décision
2. **Inclure systématiquement les tags** :
   - `architecture` — décisions structurelles
   - `security` — aspects de sécurité
   - `mcp-tool` — interactions avec les MCP
3. ** Ajouter les métadonnées** pour la recherche future

### C. Recherche vectorielle (QUAND nécessaire)

| Type de recherche | Tags | Store | Outil |
|-------------------|------|-------|-------|
| Catégorique | type, domain, scope, priority | Qdrant 2048D | `mcp_qdrant_search` |
| Sémantique | concept, action, entity, relation | Zvec 2048D | `mcp_zvec_semantic_search` |
| Mixte | combinaison | Dual | Les deux |

### D. Gestion du stockage

1. **Toutes les données DOIVENT être dans** :
   `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/`

2. **Ne pas créer de bases SQLite hors de ce chemin** sans justification

3. **Maintenir la junction** : locale `memory-database/` → globale `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/`

---

## 📋 RÈGLES GLOBALES HERMÈS

### Langue
- **TOUS les agents communiquent en français** (déjà imposé par SOUL.md global)

### Évaluation des skills (obligatoire)
- Avant tout code : inventorier les skills/tools, évaluer leur pertinence, annoncer le plan
- Processus en 4 étapes (détaillé dans SOUL.md global + extension)

### Clean Garden Policy
- **Modifier avant de créer** : vérifier si un fichier similaire existe
- **Pas de duplication** : centraliser les fichiers similaires
- **Demander avant de placer** : si l'emplacement n'est pas évident
- **Sécurité Git** : vérifier .gitignore, scanner les secrets

### Économie de tokens
- **Recherche avant lecture** : `search_files` avant `read_file`
- **Lecture partielle** : `offset` + `limit` pour fichiers > 200 lignes
- **Regroupement parallèle** : appels indépendants en parallèle
- **Contexte minimal** : ne pas afficher de contenu superflu

---

## 🏗️ STRUCTURE DE LA COUCHE HERMÈS

La couche d'intégration Hermès est installée dans `$HOME/.hermes/` :

```
$HOME/.hermes/
├── SOUL.hermes-extension.md    ← Extension du SOUL.md global
├── AGENTS.md                   ← Ce fichier (règles globales)
├── skills-adapters/            ← Adaptateurs de compétences
│   └── ... (futur)
└── agents-ref/                 ← Références aux agents Hephaistos
    └── ... (futur)
```

### Composants de la couche

| Composant | Fichier source | Destination | Description |
|-----------|----------------|-------------|-------------|
| Extension SOUL | `layer/SOUL.hermes-extension.md` | `~/.hermes/SOUL.hermes-extension.md` | Connaissance des MCP unifiés |
| Règles globales | `layer/AGENTS.md` | `~/.hermes/AGENTS.md` | Règles pour tous les workspaces |
| Adaptateurs | `layer/skills-adapters/` | `~/.hermes/skills-adapters/` | Wrappers MCP (futur) |
| Références agents | `layer/agents-ref/` | `~/.hermes/agents-ref/` | Description des agents (futur) |

---

## 🔄 INTÉGRATION AVEC HERMÈS

### Chargement automatique

1. **Au démarrage de Hermès** :
   - `SOUL.md` global est chargé en premier
   - `SOUL.hermes-extension.md` est chargé ensuite (si présent)
   - `AGENTS.md` global est chargé (si présent)
   - `AGENTS.md` du projet est chargé ensuite (si présent)

2. **Ordre de priorité** :
   - SOUL.md global > SOUL.hermes-extension.md > AGENTS.md global > AGENTS.md projet
   - En cas de conflit : le fichier le plus spécifique a priorité sur le plus général

### Utilisation des MCP dans les sessions

Les MCP configurés dans `config.yaml` sont automatiquement disponibles. Pour les utiliser :

1. **Memory** : `mcp_Memory_search_nodes(query="...")`
2. **Qdrant** : `mcp_qdrant_search(collection="doc_index", vector=[...])`
3. **Zvec** : `mcp_zvec_semantic_search(collection="entities_index", query_vector=[...])`
4. **sqlite-node** : d'abord `mcp_sqlite_node_connect_database`, puis `query_data` ou `execute_query`

### Avec delegate_task

Pour utiliser les agents Hephaistos-Kit via `delegate_task` :

```python
# Exemple : déléguer une tâche de planification
result = delegate_task(
    goal="Planifier l'architecture du module X",
    context="Le système utilise Memory, Qdrant, Zvec, et sqlite-node pour la mémoire unifiée.",
    skills=["project-planner", "architecture"]
)
```

---

## ⚠️ RÈGLES SPÉCIFIQUES À LA COUCHE D'INTÉGRATION

### Non-modification de Hephaistos-Kit

- La couche d'intégration NE DOIT PAS modifier Hephaistos-Kit
- Les fichiers de la couche sont dans `.agent/hermes/` (ou `~/.hermes/` après injection)
- Hephaistos-Kit reste intact et utilisable avec ses propres IDE

### Réutilisation de la couche

- La couche est conçue pour être injectée une fois dans Hermès
- Elle est réutilisable pour tous les projets Hermès
- Elle peut être mise à jour indépendamment de Hephaistos-Kit

### Conflits de configuration

- En cas de conflit entre la couche et la configuration existante :
  - La configuration existante a priorité (ne pas écraser sans consentement)
  - La couche peut être retirée sans affecter la configuration existante

---

## 📚 RÉFÉRENCES EXTERNES

- **Hephaistos-Kit** : `<KIT_ROOT>\`
- **Documentation mémoire** : `<KIT_ROOT>\.agent\memory\ARCHITECTURE-ANALYSIS.md`
- **Config MCP exemple** : `<KIT_ROOT>\.agent\mcp-config.json.exemple`
- **Manifeste** : `<KIT_ROOT>\wiki-doc\manifeste.md`
- **Rapport RAG** : `<KIT_ROOT>\.agent\back-end\RAG-AUDIT-REPORT.md`
- **Global rules** : `<KIT_ROOT>\.agent\rules\global_rules.md`
