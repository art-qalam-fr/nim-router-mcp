# SOUL.hermes-extension.md — Hephaistos-Kit Unified Memory System

> Ce fichier s'applique APRÈS le SOUL.md global de Hermès (`$HOME/.hermes/SOUL.md`).
> Il ajoute la connaissance du système de mémoire unifiée de Hephaistos-Kit.

---

## 🧠 MCP UNIFIÉS DISPONIBLES (Hephaistos-Kit)

Les serveurs MCP suivants sont configurés globalement dans Hermès et disponibles pour tous les workspaces :

### Memory MCP (Knowledge Graph)

| Outil | Description |
|-------|-------------|
| `mcp_Memory_search_nodes` | Recherche dans le graphe par requête, type, ou tags |
| `mcp_Memory_add_observations` | Ajouter des observations à des entités existantes |
| `mcp_Memory_create_entities` | Créer de nouvelles entités dans le graphe |
| `mcp_Memory_create_relations` | Créer des relations entre entités |
| `mcp_Memory_read_graph` | Lire le graphe complet (entités + relations) |
| `mcp_Memory_delete_entities` | Supprimer des entités |
| `mcp_Memory_delete_observations` | Supprimer des observations |
| `mcp_Memory_delete_relations` | Supprimer des relations |
| `mcp_Memory_open_nodes` | Ouvrir des nœuds spécifiques par nom |

**Usage prioritaire** :
- Avant toute tâche : `mcp_Memory_search_nodes` pour vérifier le contexte existant
- Après toute décision : `mcp_Memory_add_observations` avec tags (`architecture`, `security`, `mcp-tool`)
- Pour structurer le KG : `mcp_Memory_create_entities` + `mcp_Memory_create_relations`

### Qdrant MCP (Vector Store 2048D)

| Outil | Description |
|-------|-------------|
| `mcp_qdrant_create_collection` | Créer une nouvelle collection vectorielle |
| `mcp_qdrant_list_collections` | Lister toutes les collections |
| `mcp_qdrant_get_collection_info` | Obtenir les informations d'une collection |
| `mcp_qdrant_search` | Recherche vectorielle dans une collection |
| `mcp_qdrant_add_documents` | Ajouter des documents avec embeddings |
| `mcp_qdrant_delete_documents` | Supprimer des documents d'une collection |
| `mcp_qdrant_delete_collection` | Supprimer une collection |
| `mcp_qdrant_create_instance` | Créer une instance Qdrant |
| `mcp_qdrant_list_instances` | Lister les instances disponibles |
| `mcp_qdrant_switch_instance` | Basculer vers une instance |

**Usage prioritaire** :
- Recherche catégorique : tags type, domain, scope, priority → Qdrant
- Collections utilisées : `doc_index` (131k docs), `code_index`, `config_index`, `<projet>_*` (768D)

### Zvec MCP (Vector Store 2048D)

| Outil | Description |
|-------|-------------|
| `mcp_zvec_create_collection` | Créer une nouvelle collection vectorielle |
| `mcp_zvec_list_collections` | Lister toutes les collections |
| `mcp_zvec_get_collection_info` | Obtenir les informations d'une collection |
| `mcp_zvec_semantic_search` | Recherche sémantique dans une collection |
| `mcp_zvec_add_documents` | Ajouter des documents avec embeddings |
| `mcp_zvec_delete_documents` | Supprimer des documents d'une collection |
| `mcp_zvec_delete_collection` | Supprimer une collection |
| `mcp_zvec_create_store` | Créer un store vectoriel |
| `mcp_zvec_list_stores` | Lister les stores disponibles |
| `mcp_zvec_switch_store` | Basculer vers un store |

**Usage prioritaire** :
- Recherche sémantique : tags concept, action, entity, relation → Zvec
- Collections utilisées : `entities_index` (26k), `concepts_index` (502), `actions_index` (14.5k)

### sqlite-node MCP (SQLite multi-DB)

| Outil | Description |
|-------|-------------|
| `mcp_sqlite_node_connect_database` | Se connecter à une base SQLite |
| `mcp_sqlite_node_query_data` | Exécuter un SELECT sur une DB connectée |
| `mcp_sqlite_node_execute_query` | Exécuter INSERT/UPDATE/DELETE |
| `mcp_sqlite_node_list_tables` | Lister les tables d'une DB |
| `mcp_sqlite_node_describe_table` | Obtenir la structure d'une table |
| `mcp_sqlite_node_get_table_info` | Informations complètes d'une table |
| `mcp_sqlite_node_list_databases` | Lister les bases connectées |
| `mcp_sqlite_node_switch_database` | Changer de base connectée |
| `mcp_sqlite_node_attach_database` | Attacher une autre base |

**Usage prioritaire** :
- Lecture de `graph-memory.db` (edges rapides) : connect + query_data (lecture seule)
- Lecture de `runtime-cache.db` (cache runtime) : connect + query_data
- Gestion de bases projet : connect + execute_query

---

## 📋 PROCÉDURES D'USAGE DU SYSTÈME DE MÉMOIRE UNIFIÉE

### Flux de travail complet

1. **Début de session** (dans n'importe quel workspace) :
   - Utiliser `mcp_Memory_search_nodes` pour identifier le contexte existant
   - Vérifier les préférences utilisateur et les décisions précédentes
   - Identifier les workspaces et requêtes fréquentes

2. **Avant une tâche spécifique** :
   - Vérifier si le contexte existe déjà dans la mémoire
   - Si oui : réutiliser sans re-explorer (économie de tokens)
   - Si non : créer le contexte nécessaire

3. **Pendant la tâche** :
   - Utiliser les MCP pour stocker/retrouver des informations
   - Maintenir la cohérence du KG avec les étapes intermédiaires
   - Mettre à jour le cache si nécessaire

4. **Après une décision importante** :
   - Utiliser `mcp_Memory_add_observations` pour tracer la décision
   - Inclure systématiquement les tags : `architecture`, `security`, `mcp-tool`
   - Ajouter les métadonnées appropriées pour la recherche future

5. **Fin de session** :
   - Consolider les données vers le stockage global
   - Vérifier l'intégrité des données locale/global
   - Documenter les leçons apprises

### Routage vectoriel automatique

| Type de recherche | Tags concernés | Store à utiliser | Outil MCP |
|-------------------|----------------|------------------|-----------|
| **Catégorique** | type, domain, scope, priority | Qdrant 2048D | `mcp_qdrant_search` |
| **Sémantique** | concept, action, entity, relation | Zvec 2048D | `mcp_zvec_semantic_search` |
| **Mixte** | combinaison des deux | Dual (Qdrant + Zvec) | Les deux outils |

### Stockage dual (local + global)

```
LOCAL:  memory-database/
          └─ agentmemory/    (toujours présent)
          └─ graph/          (edges locaux)
          └─ vector/         (index locaux)
          └─ cache/          (runtime-cache.db)

GLOBAL: ${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/
          └─ graph/          (memory_mcp.db + graph-memory.db)
          └─ vector/         (zvec-data + qdrant-data)
          └─ cache/          (runtime-cache.db)
```

**Règle** : La junction locale → globale assure que le projet voit le stockage global comme local.

---

## ⚠️ RÈGLES SPÉCIFIQUES AU SYSTÈME MÉMOIRE UNIFIÉ

### Architecture et storage

1. **Toutes les données de mémoire DOIVENT être stockées dans** :
   `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/`

2. **Ne pas créer de bases SQLite hors de ce chemin** sans justification explicite

3. **Utiliser les tags systématiquement** :
   - `architecture` — pour les décisions structurelles
   - `security` — pour les aspects de sécurité
   - `mcp-tool` — pour les interactions avec les MCP

4. **Maintenir l'intégrité de la junction** :
   - La junction entre `memory-database/` (local) et le workspace global doit être fonctionnelle
   - Si la junction est cassée, utiliser le mode local temporairement

5. **Ne pas modifier directement les fichiers .db** :
   - Utiliser les MCP pour toutes les opérations sur les bases
   - Les accès directs peuvent corrompre la cohérence local/global

### Intégrité des données

1. **Cohérence local/global** :
   - Les données écrites localement doivent être répliquées vers le global
   - Les données globales doivent être accessibles localement via la junction
   - En cas de conflit, le global a priorité

2. **Gestion des caches** :
   - `runtime-cache.db` est le cache unifié pour MCP + Système + Agents
   - TTL : 1 heure (configurable dans sqlite-node env)
   - Nettoyage automatique : purge des entrées > 1000 avec TTL expiré

3. **Indexation vectorielle** :
   - Les documents ajoutés via MCP sont automatiquement indexés
   - L'embedding se fait via les modèles configurés (NVIDIA NIM pour Qdrant et Zvec)
   - En cas d'échec d'embedding, utiliser les alternatives (Ollama pour 768D)

### Sécurité

1. **Secrets** :
   - Ne jamais stocker de secrets dans la mémoire
   - Utiliser les variables d'environnement pour les informations sensibles
   - Les fichiers `.env` ne doivent pas être commités

2. **Permissions** :
   - Les bases SQLite sont accessibles en lecture/écriture par les MCP
   - Les processus concurrents doivent utiliser les mêmes instances MCP
   - Éviter les accès directs concurrents aux mêmes fichiers .db

---

## 🔄 INTÉGRATION AVEC LES AUTRES COMPOSANTS HERMÈS

### Avec SOUL.md global

Ce fichier s'applique APRÈS le `SOUL.md` global. En cas de conflit :
- Le `SOUL.md` global a priorité sur les règles d'identité (langue, éthique, etc.)
- Cette extension a priorité sur les procédures spécifiques au système mémoire

### Avec AGENTS.md (projet)

Les règles de ce fichier s'appliquent à TOUS les workspaces Hermès. Les `AGENTS.md` de projet peuvent :
- Surcharger les procédures spécifiques au projet
- Ajouter des règles spécifiques au domaine
- Ne PAS modifier les règles du système mémoire unifié

### Avec les compétences (skills)

Les compétences de Hephaistos-Kit peuvent être utilisées via :
- `delegate_task` pour du traitement parallèle
- Appels directs aux MCP pour les opérations de mémoire
- Adaptateurs dans `skills-adapters/` pour les wrappers spécifiques

### Avec les agents délégués

Les agents Hephaistos-Kit (orchestrator, project-planner, etc.) peuvent être délégués via `delegate_task`. Ils doivent :
- Utiliser les mêmes MCP que le workspace principal
- Respecter les mêmes règles de mémoire unifiée
- Partager le contexte via la mémoire (KG + vector stores)

---

## 📚 RÉFÉRENCES COMPLÈTES

- **Documentation Hephaistos-Kit** : `<KIT_ROOT>\.agent\hermes\README.md`
- **Config MCP exemple** : `<KIT_ROOT>\.agent\mcp-config.json.exemple`
- **Architecture mémoire** : `<KIT_ROOT>\.agent\memory\ARCHITECTURE-ANALYSIS.md`
- **Manifeste** : `<KIT_ROOT>\wiki-doc\manifeste.md`
- **Rapport RAG** : `<KIT_ROOT>\.agent\back-end\RAG-AUDIT-REPORT.md`
