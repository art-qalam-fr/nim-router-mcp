# Adaptateurs de compétences — Hermès Integration Layer

Ce répertoire contient des adaptateurs (wrappers) qui permettent à Hermès d'utiliser
les compétences et les MCP de Hephaistos-Kit de manière native.

## Structure

```
skills-adapters/
├── memory-utils.md           # Utilitaires mémoire (KG + vector)
├── vector-search.md          # Abstraction recherche vectorielle (Qdrant + Zvec)
├── sqlite-utils.md           # Utilitaires SQLite (multi-DB)
├── task-management.md        # Gestion des tâches (équivalent orchestrator)
└── project-utils.md          # Utilitaires projet (manifest, roadmap, etc.)
```

## Usage

Ces adaptateurs sont documentés pour être utilisés directement par Hermès.
Ils ne nécessitent pas d'exécution — ce sont des références de procédures.

---

## memory-utils.md

# Adaptateur Mémoire — Hephaistos-Kit Unified Memory System

> Wrapper pour les opérations fréquentes sur le système mémoire unifié.

---

### Mémoire — Opérations courantes

#### 1. Rechercher le contexte existant (AVANT toute tâche)

```python
# Equivalent MCP: mcp_Memory_search_nodes
# Usage: Vérifier si le contexte existe déjà avant de commencer

def search_memory_context(query: str, tags: list[str] = None):
    """
    Recherche dans le Knowledge Graph.
    
    Args:
        query: Terme de recherche (texte libre)
        tags: Tags optionnels pour filtrer (architecture, security, mcp-tool, etc.)
    
    Returns: Liste d'entités, observations, et relations correspondantes
    """
    # Appel MCP: mcp_Memory_search_nodes(query=query, tags=tags)
    pass
```

#### 2. Enregistrer une décision (APRÈS toute décision importante)

```python
# Equivalent MCP: mcp_Memory_add_observations
# Usage: Tracer une décision dans le KG avec tags

def record_decision(entity_name: str, content: str, tags: list[str]):
    """
    Enregistre une décision dans le Knowledge Graph.
    
    Args:
        entity_name: Nom de l'entité (ex: "decision-auth-v2")
        content: Contenu de la décision (texte)
        tags: Tags obligatoires — architecture, security, mcp-tool
    
    Example:
        record_decision(
            entity_name="decision-auth-v2",
            content="JWT avec refresh tokens, expiration 15min/7jours",
            tags=["architecture", "security", "mcp-tool"]
        )
    """
    # Appel MCP: mcp_Memory_add_observations(entity=entity_name, content=content, tags=tags)
    pass
```

#### 3. Créer une entité structurée

```python
# Equivalent MCP: mcp_Memory_create_entities + mcp_Memory_create_relations

def create_memory_entity(name: str, entity_type: str, attributes: dict, relations: list[dict]):
    """
    Crée une entité et ses relations dans le KG.
    
    Args:
        name: Nom unique de l'entité
        entity_type: Type (project, decision, pattern, preference, etc.)
        attributes: Attributs clé-valeur (description, date, priority, etc.)
        relations: Liste de relations [{target, type, weight}]
    
    Example:
        create_memory_entity(
            name="project-marotte",
            entity_type="project",
            attributes={
                "description": "Plateforme de prédiction Loto/EuroMillions",
                "date": "2026-09-17",
                "priority": "high"
            },
            relations=[
                {"target": "user-local", "type": "owned_by", "weight": 1.0},
                {"target": "stack-python-fastapi", "type": "uses", "weight": 0.9}
            ]
        )
    """
    # Appel MCP: mcp_Memory_create_entities(entities=[...])
    # Appel MCP: mcp_Memory_create_relations(relations=[...])
    pass
```

#### 4. Lire le graphe complet (pour analyse)

```python
# Equivalent MCP: mcp_Memory_read_graph

def read_full_graph():
    """
    Lit le graphe complet (entités + relations).
    Usage: Analyse globale de la mémoire, consolidation, audit.
    """
    # Appel MCP: mcp_Memory_read_graph()
    pass
```

#### 5. Ouvrir un nœud spécifique

```python
# Equivalent MCP: mcp_Memory_open_nodes

def open_node(node_name: str):
    """
    Ouvre un nœud spécifique par son nom.
    Usage: Récupérer les détails d'une entité connue.
    """
    # Appel MCP: mcp_Memory_open_nodes(names=[node_name])
    pass
```

---

### Mémoire — Procédures par contexte

#### Contexte: Nouvelle session

```
1. mcp_Memory_search_nodes(query="preferences") → vérifier les préférences utilisateur
2. mcp_Memory_search_nodes(query="workspace") → identifier les workspaces connus
3. mcp_Memory_search_nodes(query="frequent queries") → identifier les requêtes récurrentes
```

#### Contexte: Nouvelle tâche

```
1. mcp_Memory_search_nodes(query=task_keywords) → vérifier si le contexte existe
2. Si existe → réutiliser sans re-explorer
3. Si non existe → créer le contexte (créer entité + observations)
```

#### Contexte: Après décision

```
1. mcp_Memory_add_observations(
       entity=task_entity,
       content=f"Decided: {decision_summary}",
       tags=["architecture" | "security" | "mcp-tool"]
   )
2. Si décision structurelle → créer une entité "decision-{slug}" avec relations
```

#### Contexte: Session terminée

```
1. Vérifier la cohérence local/global
2. Documenter les leçons apprises
3. Mettre à jour les requêtes fréquentes si nécessaire
```

---

### Tags recommandés

| Tag | Quand l'utiliser |
|-----|------------------|
| `architecture` | Décisions structurelles, choix d'implémentation |
| `security` | Questions de sécurité, choix d'authentification, etc. |
| `mcp-tool` | Interactions avec les MCP (utilisation de Memory, Qdrant, etc.) |
| `pattern` | Patterns d'implémentation récurrents |
| `preference` | Préférences utilisateur découvertes |
| `lesson` | Leçons apprises, corrections de bugs |
| `decision` | Décisions importantes (ADR) |
| `project` | Métadonnées de projet |

---

## vector-search.md

# Adaptateur Recherche Vectorielle — Hephaistos-Kit

> Wrapper pour la recherche vectorielle via Qdrant et Zvec — NVIDIA NIM 2048D.

---

### Routage automatique — Quel store utiliser ?

| Critères | Store recommandé | Outil MCP |
|-----------|------------------|-----------|
| Recherche par **tags catégoriques** (type, domain, scope, priority) | Qdrant | `mcp_qdrant_search` |
| Recherche par **similarité sémantique** (concept, action, entity, relation) | Zvec | `mcp_zvec_semantic_search` |
| Recherche **mixte** (catégorique + sémantique) | Dual (Qdrant + Zvec) | Les deux, fusionner les résultats |

---

### Recherche catégorique (Qdrant)

```python
# Equivalent MCP: mcp_qdrant_search
# Usage: Recherche par tags catégoriques dans une collection

def qdrant_search_collection(
    collection: str,
    vector: list[float],  # ou query_vector si décision dual
    filter_tags: dict = None,
    limit: int = 20,
    min_score: float = 0.5
):
    """
    Recherche dans une collection Qdrant.
    
    Args:
        collection: Nom de la collection (doc_index, code_index, config_index, etc.)
        vector: Vecteur de recherche (pré-calculé via embedding)
        filter_tags: Filtres catégoriques optionnels {key: value}
        limit: Nombre de résultats max
        min_score: Score minimum pour filtrer les résultats
    
    Collections disponibles:
        - doc_index — documentation technique
        - code_index — code source
        - config_index — fichiers de configuration
        - <projet>_algos, <projet>_runs, <projet>_timesfm — collections projet 2048D
    
    Example:
        qdrant_search_collection(
            collection="doc_index",
            vector=embed_query("authentification JWT"),
            filter_tags={"type": "security", "domain": "backend"},
            limit=10
        )
    """
    # Appel MCP: mcp_qdrant_search(
    #     collection=collection,
    #     vector=vector,
    #     filter=filter_tags,
    #     limit=limit,
    #     min_score=min_score
    # )
    pass
```

### Recherche sémantique (Zvec)

```python
# Equivalent MCP: mcp_zvec_semantic_search
# Usage: Recherche par similarité sémantique

def zvec_search_collection(
    collection: str,
    query_vector: list[float],  # vecteur 2048D (nvidia/nemotron-3-embed-1b)
    limit: int = 20,
    min_score: float = 0.5
):
    """
    Recherche sémantique dans une collection Zvec.
    
    Args:
        collection: Nom de la collection (entities_index, concepts_index, actions_index)
        query_vector: Vecteur 2048D de la requête
        limit: Nombre de résultats max
        min_score: Score minimum

    Collections disponibles:
        - entities_index — entités du KG
        - concepts_index — concepts abstraits
        - actions_index — actions/verbes
    
    Example:
        zvec_search_collection(
            collection="entities_index",
            query_vector=embed_semantic("authentification utilisateur"),
            limit=10
        )
    """
    # Appel MCP: mcp_zvec_semantic_search(
    #     collection=collection,
    #     query_vector=query_vector,
    #     limit=limit,
    #     min_score=min_score
    # )
    pass
```

### Procédure EMBED-FIRST (obligatoire)

```python
# Avant tout appel MCP vectoriel, générer le vecteur de requête.

def embed_query(text: str, input_type: str = "query") -> list[float]:
    """
    Génère un vecteur 2048D via NVIDIA NIM — même modèle pour Qdrant et Zvec.

    Args:
        text: Texte à encoder
        input_type: "query" pour recherche, "passage" pour indexation

    Retourns:
        Vecteur de float32 de 2048 dimensions
    """
    # NVIDIA NIM — POST https://integrate.api.nvidia.com/v1/embeddings
    # Headers: Authorization: Bearer <NVIDIA_API_KEY>
    # Body: {"model": "nvidia/nemotron-3-embed-1b", "input": text, "input_type": input_type}
    pass
```

### Fusion des résultats (routage dual)

```python
def dual_search(query: str, query_vector_qdrant: list[float], query_vector_zvec: list[float]):
    """
    Recherche duale Qdrant + Zvec avec fusion des résultats.
    
    Fusion weights (configurables):
        - Qdrant: 0.4 (catégorique)
        - Zvec: 0.4 (sémantique)
        - Memory: 0.2 (KG complémentaire)
    """
    qdrant_results = qdrant_search_collection("doc_index", query_vector_qdrant)
    zvec_results = zvec_search_collection("entities_index", query_vector_zvec)
    
    # Fusionner les résultats par score pondéré
    # Triés par score décroissant, limités à RAG_FUSION_MAX_RESULTS=20
    pass
```

---

## sqlite-utils.md

# Adaptateur SQLite — Hephaistos-Kit

> Wrapper pour les opérations courantes sur les bases SQLite gérées par sqlite-node MCP.

---

### Bases disponibles (global)

| Alias | Chemin | Usage |
|-------|--------|-------|
| `memory` | `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/graph/memory_mcp.db` | KG principal (entités, observations, relations) |
| `graph` | `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/graph/graph-memory.db` | Edges rapides (relations simples) |
| `cache` | `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/cache/runtime-cache.db` | Cache runtime (TTL 1h) |
| `qdrant` | `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/vector/qdrant/qdrant.db` | Données Qdrant (si persistées) |
| `zvec` | `${AGENT_DB_ROOT}/current_workspace/<PROJECT_ID>/vector/zvec/zvec.db` | Données Zvec (si persistées) |

### Bases locales (dans le projet)

| Alias | Chemin | Usage |
|-------|--------|-------|
| `local` | `memory-database/agentmemory/graph/memory_mcp.db` | KG local (si pas de junction) |
| `local-graph` | `memory-database/graph/graph-memory.db` | Edges locaux |

---

### Opérations courantes

#### 1. Lire les tables d'une base

```python
# Equivalent MCP: mcp_sqlite_node_list_tables

def list_tables(alias: str = "memory") -> list[str]:
    """
    Liste les tables d'une base.
    Usage: Explorer la structure d'une base avant de requêter.
    """
    # 1. mcp_sqlite_node_connect_database(alias=alias, path=path)
    # 2. mcp_sqlite_node_list_tables()
    pass
```

#### 2. Décrire une table

```python
# Equivalent MCP: mcp_sqlite_node_describe_table

def describe_table(table_name: str, alias: str = "memory") -> dict:
    """
    Obtient la structure d'une table (colonnes, types, clés).
    """
    # 1. mcp_sqlite_node_connect_database(alias=alias)
    # 2. mcp_sqlite_node_describe_table(table=table_name)
    pass
```

#### 3. Exécuter une requête SELECT

```python
# Equivalent MCP: mcp_sqlite_node_query_data

def query(sql: str, alias: str = "memory") -> list[dict]:
    """
    Exécute un SELECT et retourne les résultats.
    Usage: Lire des données spécifiques.
    """
    # 1. mcp_sqlite_node_connect_database(alias=alias)
    # 2. mcp_sqlite_node_query_data(query=sql)
    pass
```

#### 4. Exécuter INSERT/UPDATE/DELETE

```python
# Equivalent MCP: mcp_sqlite_node_execute_query

def execute(sql: str, alias: str = "memory") -> dict:
    """
    Exécute une requête de modification.
    Usage: Insérer, mettre à jour, ou supprimer des données.
    """
    # 1. mcp_sqlite_node_connect_database(alias=alias)
    # 2. mcp_sqlite_node_execute_query(query=sql)
    pass
```

#### 5. Information complète d'une table

```python
# Equivalent MCP: mcp_sqlite_node_get_table_info

def get_table_info(table_name: str, alias: str = "memory") -> dict:
    """
    Informations complètes sur une table (structure, indexes, stats).
    """
    # 1. mcp_sqlite_node_connect_database(alias=alias)
    # 2. mcp_sqlite_node_get_table_info(table=table_name)
    pass
```

### Exemples concrets

#### Exemple 1: Lire les entités d'un projet

```python
query("""
    SELECT e.name, e.type, e.created_at
    FROM entities e
    WHERE e.tags LIKE '%project%'
    ORDER BY e.created_at DESC
""", alias="memory")
```

#### Exemple 2: Vérifier le cache runtime

```python
query("""
    SELECT key, value, expires_at
    FROM cache_table
    WHERE expires_at > datetime('now')
    ORDER BY expires_at DESC
""", alias="cache")
```

#### Exemple 3: Analyser les relations d'une entité

```python
query("""
    SELECT r.from_id, r.to_id, r.type, r.weight
    FROM relations r
    WHERE r.from_id = (SELECT id FROM entities WHERE name = 'project-marotte')
    OR r.to_id = (SELECT id FROM entities WHERE name = 'project-marotte')
""", alias="graph")
```

---

## task-management.md

# Adaptateur Gestion des tâches — Hephaistos-Kit

> Wrapper pour la gestion des tâches via l'orchestrateur MCP (si disponible) ou fallback SQLite.

---

### Équivalent orchestrator MCP (si disponible)

Si l'orchestrateur MCP est configuré et disponible, utiliser ses outils :

| Outil | Description |
|-------|-------------|
| `orchestrator.list_agents` | Lister les agents disponibles |
| `orchestrator.get_next_task` | Récupérer la prochaine tâche en attente |
| `orchestrator.create_task` | Créer une nouvelle tâche |
| `orchestrator.update_task` | Mettre à jour le statut/résultat d'une tâche |
| `orchestrator.register_agent` | Enregistrer un agent |
| `orchestrator.delete_task` | Supprimer une tâche |

### Fallback SQLite (si orchestrator MCP indisponible)

Si l'orchestrateur MCP n'est pas disponible, utiliser sqlite-node pour gérer les tâches.

#### Créer une tâche

```python
def create_task(
    title: str,
    description: str,
    project_id: str,
    priority: str = "medium",
    status: str = "pending",
    tags: list[str] = None
):
    """
    Crée une tâche dans la base de tâches locale.
    """
    execute(f"""
        INSERT INTO tasks (title, description, project_id, priority, status, created_at, tags)
        VALUES (
            '{title}',
            '{description}',
            '{project_id}',
            '{priority}',
            '{status}',
            datetime('now'),
            '{','.join(tags) if tags else ""}'
        )
    """, alias="local")
```

#### Récupérer les tâches en attente

```python
def get_pending_tasks(project_id: str = None) -> list[dict]:
    """
    Récupère les tâches en attente, triées par priorité.
    """
    sql = """
        SELECT * FROM tasks
        WHERE status = 'pending'
        ORDER BY
            CASE priority
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
            END,
            created_at ASC
    """
    if project_id:
        sql += f" AND project_id = '{project_id}'"
    return query(sql, alias="local")
```

#### Mettre à jour une tâche

```python
def update_task_status(task_id: int, status: str, result: str = None):
    """
    Met à jour le statut (et optionnellement le résultat) d'une tâche.
    """
    if result:
        execute(f"""
            UPDATE tasks
            SET status = '{status}', result = '{result}', completed_at = datetime('now')
            WHERE id = {task_id}
        """, alias="local")
    else:
        execute(f"""
            UPDATE tasks
            SET status = '{status}', completed_at = datetime('now')
            WHERE id = {task_id}
        """, alias="local")
```

### Procédure de gestion des tâches

```
1. Au début d'une session complexe:
   → get_pending_tasks(project_id) pour voir les tâches en attente
   → Si 악순환 orchestrator MCP: utiliser orchestrator.get_next_task()

2. Avant de commencer une tâche:
   → update_task_status(task_id, "in_progress")

3. Après avoir complété une tâche:
   → update_task_status(task_id, "completed", result="...")
   → mcp_Memory_add_observations(entity=task_entity, content=result, tags=["lesson", "project"])

4. Si une tâche échoue:
   → update_task_status(task_id, "failed", result="erreur: ...")
   → documenter l'erreur dans la mémoire
```

---

## project-utils.md

# Adaptateur Projet — Hephaistos-Kit

> Wrapper pour les opérations courantes sur les projets.

---

### Créer un MANIFEST.md

```python
def create_manifest(
    project_name: str,
    project_type: str,
    description: str,
    objectives: str,
    constraints: str,
    target_users: str,
    tech_stack: str,
    timeline: str,
    priority: str = "medium"
):
    """
    Crée un MANIFEST.md pour un nouveau projet.
    Basé sur le template Hephaistos-Kit (init-project.ps1).
    """
    # Génère le fichier MANIFEST.md avec la structure standard
    # Voir: .agent/hermes/templates/AGENTS.md pour le template
    pass
```

### Lire un MANIFEST.md existant

```python
def read_manifest(project_root: str) -> dict:
    """
    Lit et parse un MANIFEST.md existant.
    Retourns: dictionnaire avec les sections du manifeste.
    """
    # Lire le fichier project_root/MANIFEST.md
    # Parser les sections (Définition, Architecture, Roadmap, Métriques, etc.)
    pass
```

### Vérifier la structure du projet

```python
def verify_project_structure(project_root: str) -> dict:
    """
    Vérifie que la structure du projet est conforme aux attentes.
    Retourns: dictionnaire avec les vérifications (OK/FAIL).
    """
    checks = {
        "memory-database/ exists": (Path(project_root) / "memory-database").exists(),
        "AGENTS.md exists": (Path(project_root) / "AGENTS.md").exists(),
        ".env exists": (Path(project_root) / ".env").exists(),
        ".agent/hermes/ exists": (Path(project_root) / ".agent" / "hermes").exists(),
        "SOCURE.md exists (global)": Path.home() / ".hermes" / "SOUL.md").exists(),
    }
    return checks
```

### Lister les MCP disponibles

```python
def list_available_mcps() -> list[dict]:
    """
    Liste tous les MCP configurés dans Hermès.
    Retourns: liste de {name, type, tools_count, status}
    """
    # Cette fonction est un wrapper conceptuel.
    # En pratique, utiliser `hermes mcp list` ou lire config.yaml.
    # Ici: documenter les MCP attendus.
    pass
```

### Résumé des adaptateurs

| Adaptateur | Fichier | MCP utilisé | Usage principal |
|------------|---------|-------------|-----------------|
| Mémoire | `memory-utils.md` | Memory MCP | KG: créer/lier/observer/supprimer entités, search |
| Vector search | `vector-search.md` | Qdrant + Zvec | Recherche catégorique + sémantique |
| SQLite | `sqlite-utils.md` | sqlite-node | Multi-DB: connect, query, execute |
| Tâches | `task-management.md` | orchestrator MCP ou sqlite-node | Créer/suivre/tâches |
| Projet | `project-utils.md` | filesystem MCP | MANIFEST, structure, vérification |
