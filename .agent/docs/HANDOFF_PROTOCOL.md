# Protocole de Handoff Inter-Agents

## Vue d'ensemble

Ce protocole permet la coordination entre différents agents (Devin, Cursor, KiloCode, Antigravity) via la mémoire unifiée.

## Structure de la Mémoire

### Agents (entityType: agent)

| Agent       | ID  | Description          |
| ----------- | --- | -------------------- |
| Devin       | 11  | IDE avec LLM intégré |
| Cursor      | 12  | IDE alternatif       |
| KiloCode    | 13  | CLI agent            |
| Antigravity | 14  | Orchestrateur        |

### Relations (can_handoff)

```text
Devin ←→ Cursor
Devin ←→ KiloCode
Devin ←→ Antigravity
```

### Tâches (entityType: task)

**Observations obligatoires** :

- `status`: pending | in_progress | completed | blocked
- `owner`: agent_id ou none
- `description`: description de la tâche
- `progress`: 0-100%
- `handoff_to`: (optionnel) agent cible
- `handoff_reason`: (optionnel) raison du transfert

## Workflow de Handoff

### 1. Cursor commence une tâche

```sql
-- Créer la tâche
INSERT INTO entities (name, entityType) VALUES ('Task_2026_04_03_001', 'task');

-- Ajouter les observations
INSERT INTO observations (entity_id, content) VALUES
(task_id, 'status: in_progress'),
(task_id, 'owner: Cursor'),
(task_id, 'description: Implémenter feature X'),
(task_id, 'progress: 60%');

-- Créer la relation
INSERT INTO relations (from_entity, to_entity, relationType) VALUES
('Cursor', 'Task_2026_04_03_001', 'owns');
```

### 2. Cursor transfère à Devin

```sql
-- Mettre à jour le statut
UPDATE observations SET content = 'status: handoff_pending'
WHERE entity_id = task_id AND content LIKE 'status:%';

-- Ajouter les informations de handoff
INSERT INTO observations (entity_id, content) VALUES
(task_id, 'handoff_to: Devin'),
(task_id, 'handoff_reason: Cursor ne supporte pas TypeScript'),
(task_id, 'handoff_timestamp: 2026-04-03T10:30:00Z');
```

### 3. Devin reprend la tâche

```sql
-- Vérifier les tâches en attente
SELECT e.name, o.content FROM entities e
JOIN observations o ON e.id = o.entity_id
WHERE e.entityType = 'task'
AND o.content LIKE 'handoff_to: Devin%';

-- Prendre ownership
UPDATE observations SET content = 'owner: Devin'
WHERE entity_id = task_id AND content LIKE 'owner:%';

UPDATE observations SET content = 'status: in_progress'
WHERE entity_id = task_id AND content LIKE 'status:%';
```

## Requêtes Utiles

### Voir toutes les tâches en attente de handoff

```sql
SELECT e.name as task,
       GROUP_CONCAT(o.content, ' | ') as info
FROM entities e
JOIN observations o ON e.id = o.entity_id
WHERE e.entityType = 'task'
GROUP BY e.id
HAVING info LIKE '%handoff_to:%';
```

### Voir les tâches par agent

```sql
SELECT e.name as task, o.content as owner
FROM entities e
JOIN observations o ON e.id = o.entity_id
WHERE e.entityType = 'task'
AND o.content LIKE 'owner:%';
```

### Voir l'historique d'une tâche

```sql
SELECT e.name, o.content, o.created_at
FROM entities e
JOIN observations o ON e.id = o.entity_id
WHERE e.name = 'Task_2026_04_03_001'
ORDER BY o.created_at;
```

## Intégration avec l'Ingestion

Le dossier `.agent/` est ingéré automatiquement par le RAG. Les fichiers suivants sont indexés :

- `HANDOFF_PROTOCOL.md` (ce fichier)
- `sessions/` - Sessions de travail
- `tasks/` - Définitions de tâches

## Convention de Nommage

- **Tâches** : `Task_YYYY_MM_DD_NNN`
- **Sessions** : `Session_Agent_YYYYMMDD_NNN`
- **Agents** : Noms prédéfinis (Devin, Cursor, KiloCode, Antigravity)
