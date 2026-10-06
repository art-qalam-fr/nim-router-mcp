# Adaptateur Gestion des tâches — Hephaistos-Kit (suite)

### Planifier une tâche complexe

```
Équivalent MCP: orchestrator MCP (si disponible) ou sqlite-node fallback

Usage: Planifier une tâche complexe avec décomposition, dépendances, et assignation.
```

**Procédure :**
1. Analyser la tâche et identifier les sous-tâches
2. Déterminer les dépendances entre sous-tâches
3. Assigner les agents appropriés à chaque sous-tâche
4. Créer les entités "task-{slug}" dans le KG avec les détails
5. Créer les relations entre les tâches (dépendances, séquences)

**Exemple :**
```
# Créer une tâche de planification
mcp_Memory_create_entities(entities=[{
    "name": "task-auth-refactor",
    "type": "task",
    "description": "Refactoriser le système d'authentification",
    "priority": "high",
    "status": "pending",
    "assignee": "security-auditor + backend-specialist",
    "estimated_duration": "4h"
}])

# Créer les sous-tâches avec dépendances
mcp_Memory_create_entities(entities=[
    {"name": "task-audit-auth", "type": "subtask", "status": "pending"},
    {"name": "task-implement-jwt", "type": "subtask", "status": "pending"},
    {"name": "task-write-tests", "type": "subtask", "status": "pending"}
])

# Créer les relations de dépendance
mcp_Memory_create_relations(relations=[
    {"from": "task-auth-refactor", "to": "task-audit-auth", "type": "has_subtask", "weight": 1.0},
    {"from": "task-auth-refactor", "to": "task-implement-jwt", "type": "has_subtask", "weight": 1.0},
    {"from": "task-auth-refactor", "to": "task-write-tests", "type": "has_subtask", "weight": 1.0},
    {"from": "task-implement-jwt", "to": "task-audit-auth", "type": "depends_on", "weight": 1.0},
    {"from": "task-write-tests", "to": "task-implement-jwt", "type": "depends_on", "weight": 1.0}
])
```

### Suivre l'avancement d'une tâche

```
Équivalent MCP: mcp_Memory_add_observations

Usage: Mettre à jour le statut d'une tâche au fur et à mesure.
```

**Procédure :**
1. Identifier l'entité tâche
2. Ajouter une observation avec le nouveau statut et les détails
3. Si la tâche est complétée, ajouter les leçons apprises

**Exemple :**
```
mcp_Memory_add_observations(entity="task-audit-auth", content="""
Statut: completed
Résultat: Audit terminé, 3 vulnérabilités trouvées (2 moyennes, 1 haute)
Leçons: Utiliser bcrypt au lieu de md5, ajouter rate limiting
""", tags=["task", "security", "lesson"])
```

### Récupérer les tâches en attente

```
Équivalent MCP: mcp_Memory_search_nodes

Usage: Lister les tâches en attente pour planification.
```

**Exemple :**
```
mcp_Memory_search_nodes(query="pending tasks", tags=["task"])
→ Retourne: liste des tâches avec statut, priorité, et assignee
```

---

## Bonnes pratiques

1. **Créer les tâches avant de commencer** — Une tâche sans entité dans le KG est une tâche perdue.
2. **Documenter les dépendances** — Les relations entre tâches permettent de comprendre l'ordre d'exécution.
3. **Mettre à jour le statut régulièrement** — Un statut obsolète est pire que pas de statut.
4. **Tracer les leçons apprises** — À la fin de chaque tâche, ajouter une observation avec les leçons.
5. **Archiver les tâches terminées** — Après une period de temps, archiver les tâches complétées pour nettoyer le KG.

---

## Templates de tâche

### Template: Tâche de développement

```json
{
  "name": "task-{slug}",
  "type": "task",
  "description": "{description claire de la tâche}",
  "priority": "high|medium|low",
  "status": "pending|in_progress|completed|failed",
  "assignee": "{agent-name}",
  "estimated_duration": "{estimation}",
  "tags": ["development", "{domaine}", "{technologie}"],
  "acceptance_criteria": [
    "{critère 1}",
    "{critère 2}",
    "{critère 3}"
  ]
}
```

### Template: Tâche de sécurité

```json
{
  "name": "task-{slug}",
  "type": "task",
  "description": "{description de l'audit ou de la correction}",
  "priority": "high|medium|low",
  "status": "pending|in_progress|completed|failed",
  "assignee": "security-auditor",
  "estimated_duration": "{estimation}",
  "tags": ["security", "{vulnérabilité}", "{domaine}"],
  "findings": [
    {"severity": "critical|high|medium|low", "description": "{description}", "remediation": "{action}"}
  ]
}
```

### Template: Tâche de test

```json
{
  "name": "task-{slug}",
  "type": "task",
  "description": "{description des tests à écrire ou améliorer}",
  "priority": "high|medium|low",
  "status": "pending|in_progress|completed|failed",
  "assignee": "test-engineer",
  "estimated_duration": "{estimation}",
  "tags": ["testing", "{type}", "{domaine}"],
  "coverage_target": "{cible de couverture}",
  "test_types": ["unit", "integration", "e2e"]
}
```
