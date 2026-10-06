# SOUL.hermes.md — Session identity override for {{PROJECT_NAME}}

> Ce fichier S'APPLIQUE sur le SOUL.md global (`$HOME/.hermes/SOUL.md`) quand
> Hermès démarre dans ce projet. Il ajoute des règles spécifiques au projet.

---

## 🎯 CONTEXTE DU PROJET

- **Nom** : {{PROJECT_NAME}}
- **Chemin** : {{PROJECT_ROOT}}
- **AGENT_DB_ROOT** : {{AGENT_DB_ROOT}}
- **Workspace mémoire** : {{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}

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
- Toutes les données de mémoire DOIVENT être stockées dans `${{AGENT_DB_ROOT}}/current_workspace/{{PROJECT_ID}}/`
- Ne pas créer de bases SQLite hors de ce chemin sans justification
- Utiliser les tags `architecture`, `security`, `mcp-tool` systématiquement

### Chemins
- Les chemins absolus dans ce projet utilisent la racine : {{PROJECT_ROOT}}
- Les chemins relatifs sont exprimés depuis {{PROJECT_ROOT}}

### Communiquer en français
- Obligatoire (déjà imposé par SOUL.md global, mais rappelé ici)

---

## 📚 RÉFÉRENCES

- **SOUL.md global** : $HOME/.hermes/SOUL.md
- **AGENTS.md** : {{PROJECT_ROOT}}/AGENTS.md
- **Config MCP Hephaistos-Kit** : .agent/mcp-config.json.exemple
- **Documentation mémoire** : .agent/memory/ARCHITECTURE-ANALYSIS.md
