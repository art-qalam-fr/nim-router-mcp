# Protocole de Coordination MCP Multi-IDE

## Vue d'ensemble

Système de coordination **round-robin** permettant à plusieurs IDE de partager les MCP sans conflit.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                 MCP_COORDINATOR                              │
│                                                               │
│  Paramètres:                                                  │
│  - quota_per_ide: 5 requêtes                                  │
│  - timeout_seconds: 30                                        │
│  - max_wait_seconds: 60                                       │
│  - backoff_strategy: exponential                              │
│                                                               │
│  Queues:                                                      │
│  - MCP_Cache_Queue                                            │
│  - MCP_Memory_Queue                                           │
│  - MCP_Zvec_Queue                                             │
│  - MCP_Qdrant_Queue                                           │
│  - MCP_SQLite_Queue                                           │
└─────────────────────────────────────────────────────────────┘
```

## Workflow Round-Robin

### Scénario: Devin et Cursor en parallèle

```text
T0: Devin demande MCP_Memory
    → MCP_Memory_Queue.current_holder = Devin
    → Devin.requests_count = 1

T1: Cursor demande MCP_Memory
    → MCP_Memory_Queue.queue = [Cursor]
    → Cursor attend (max 60s)

T2-T6: Devin fait 5 requêtes
    → Devin.requests_count = 5 (quota atteint)
    → Devin libère MCP_Memory

T7: Cursor prend la main
    → MCP_Memory_Queue.current_holder = Cursor
    → Cursor.requests_count = 0
    → Cursor fait ses requêtes

T12: Cursor libère MCP_Memory
    → MCP_Memory_Queue.current_holder = none
    → Prochain dans la queue prend la main
```

## États de la Queue

| État                        | Description          |
| --------------------------- | -------------------- |
| `current_holder: none`      | MCP libre            |
| `current_holder: Devin`     | Devin utilise le MCP |
| `queue: [Cursor, KiloCode]` | IDEs en attente      |

## Requêtes de Coordination

### 1. Demander l'accès

```sql
-- Vérifier si le MCP est libre
SELECT content FROM observations
WHERE entity_id = (SELECT id FROM entities WHERE name = 'MCP_Memory_Queue')
AND content LIKE 'current_holder:%';

-- Si libre, prendre la main
UPDATE observations SET content = 'current_holder: Devin'
WHERE entity_id = (SELECT id FROM entities WHERE name = 'MCP_Memory_Queue')
AND content = 'current_holder: none';

-- Incrémenter le compteur
INSERT INTO observations (entity_id, content) VALUES
((SELECT id FROM entities WHERE name = 'Devin'), 'mcp_memory_requests: 1');
```

### 2. Libérer l'accès

```sql
-- Libérer le MCP
UPDATE observations SET content = 'current_holder: none'
WHERE entity_id = (SELECT id FROM entities WHERE name = 'MCP_Memory_Queue')
AND content LIKE 'current_holder:%';

-- Notifier le prochain dans la queue
SELECT content FROM observations
WHERE entity_id = (SELECT id FROM entities WHERE name = 'MCP_Memory_Queue')
AND content LIKE 'queue:%';
```

### 3. Mettre en queue

```sql
-- Ajouter à la queue
UPDATE observations SET content = 'queue: [Cursor, KiloCode]'
WHERE entity_id = (SELECT id FROM entities WHERE name = 'MCP_Memory_Queue');
```

## Timeouts et Backoff

| Situation              | Action                             |
| ---------------------- | ---------------------------------- |
| Requête > 30s          | Timeout, libérer le MCP            |
| Attente > 60s          | Backoff, réessayer plus tard       |
| 3 timeouts consécutifs | Augmenter le backoff (exponentiel) |

## Exemple de Session

```sql
-- Devin commence
INSERT INTO observations (entity_id, content) VALUES
(mcp_memory_queue_id, 'current_holder: Devin'),
(mcp_memory_queue_id, 'requests_count: 0');

-- Devin fait 3 requêtes
UPDATE observations SET content = 'requests_count: 3'
WHERE entity_id = mcp_memory_queue_id AND content LIKE 'requests_count:%';

-- Cursor demande l'accès
UPDATE observations SET content = 'queue: [Cursor]'
WHERE entity_id = mcp_memory_queue_id AND content LIKE 'queue:%';

-- Devin atteint le quota (5)
UPDATE observations SET content = 'requests_count: 5'
WHERE entity_id = mcp_memory_queue_id AND content LIKE 'requests_count:%';

-- Devin libère
UPDATE observations SET content = 'current_holder: none'
WHERE entity_id = mcp_memory_queue_id AND content LIKE 'current_holder:%';

-- Cursor prend la main
UPDATE observations SET content = 'current_holder: Cursor'
WHERE entity_id = mcp_memory_queue_id AND content = 'current_holder: none';

UPDATE observations SET content = 'queue: []'
WHERE entity_id = mcp_memory_queue_id AND content LIKE 'queue:%';
```

## Avantages

1. **Équité**: Chaque IDE a le même quota
2. **Prévisibilité**: Timeouts connus à l'avance
3. **Stabilité**: Pas de famine (chaque IDE finit par avoir accès)
4. **Simplicité**: Implémenté via SQLite, pas de nouveau MCP

## Limitations

1. **Latence**: Attente possible si un IDE utilise longtemps
2. **Manuel**: L'IDE doit respecter le protocole
3. **Pas temps réel**: Coordination via polling SQLite

## Intégration Future

Pour une coordination automatique, un **MCP Coordinator** dédié pourrait:

- Gérer les queues automatiquement
- Notifier les IDE via WebSocket
- Implémenter des priorités

Mais pour l'instant, le système SQLite simple fonctionne.
