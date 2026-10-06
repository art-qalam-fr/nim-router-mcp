# AGENTS.md — Projet {{PROJECT_NAME}}

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
| **sequentialthinking** | 1 | Raisonnement structuré |
| **colab-mcp** | 1 | Session Colab (si pertinent) |
| **devin/context7** | 2 | Docs libraries (si pertinent) |

> **Total : 104 outils MCP disponibles**, tous connectés.

---

## 🧠 MÉMOIRE UNIFIÉE — MODE D'EMPLOI

### Stockage dual
- **Local** : `memory-database/` dans le projet (toujours présent)
- **Global** : `{{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}/` (junction vers local)

### Databases utilisées
| Base | Chemin | Usage |
|------|--------|-------|
| `memory_mcp.db` | `{{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}/graph/memory_mcp.db` | Knowledge Graph principal |
| `graph-memory.db` | `{{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}/graph/graph-memory.db` | Edges rapides |
| `runtime-cache.db` | `{{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}/cache/runtime-cache.db` | Cache runtime |
| `zvec.db` | `{{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}/vector/zvec/zvec.db` | Index vectoriel 2048D |
| `qdrant.db` | `{{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}/vector/qdrant/qdrant.db` | Index vectoriel 2048D |

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

\$PROJECT_ROOT/
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
