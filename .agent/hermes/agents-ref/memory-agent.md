# Référence Agent — memory-agent

## Identification
- **Nom** : memory-agent
- **Source** : `<KIT_ROOT>\.agent\agents\memory-agent.md`
- **Description** : Gestionnaire de connaissances (Memory Specialist). Gère la hiérarchie mémoire hybride (Workspace + Global), le routage vectoriel dual (Qdrant + Zvec), et la cohérence de la mémoire à long terme.

## Rôle
 gérer le système mémoire unifiée de Hephaistos-Kit :
- Curation : analyser les interactions locales pour identifier les patterns transversaux
- Promotion : faire remonter les connaissances validées vers la mémoire globale
- Optimisation de la retrieval across local et global
- Maintenance de la cohérence de la mémoire à long terme
- Orchestration du dual vector store (Qdrant + Zvec)

## Compétences (skills)
- memory-systems
- context-management

## Architecture mémoire gérée
- **memory_mcp.db** — Knowledge Graph (entités, observations, relations)
- **graph-memory.db** — Traversals rapides (edges)
- **Qdrant** — Vector 2048D (recherche catégorique : code_index, doc_index, config_index, etc.)
- **Zvec** — Vector 2048D (recherche sémantique : entities, concepts, actions, etc.)
- **Cache Runtime** — KV Store (cache unifié MCP + Système)

## Routage vectoriel
- Tags catégoriques (type, domain, scope, priority) → Qdrant
- Tags sémantiques (concept, action, entity, relation) → Zvec
- Tags mixtes → Routage dual (les deux stores)

## Quand l'utiliser
- Archivage d'informations importantes
- Recherche de contexte existant avant une tâche
- Consolidation de mémoire entre projets
- Audit de l'état de la mémoire
- Optimisation des performances de retrieval

## Protocole (adapté pour Hermès / delegate_task)

### Procédures clés
1. **Début de session** : Consulter les préférences utilisateur et les workspaces connus
2. **Avant tâche** : Chercher le contexte existant dans Memory MCP
3. **Pendant tâche** : Stocker les informations importantes dans le KG
4. **Après décision** : Tracer dans le KG avec tags (architecture, security, mcp-tool)
5. **Fin de session** : Consolider les données vers le stockage global

### Tags de routage
- Catégorique : type, domain, scope, priority → Qdrant
- Sémantique : concept, action, entity, relation → Zvec

## Limites
- N'implémente pas de fonctionnalités — uniquement gestion mémoire
- N'accède pas directement aux fichiers .db — utilise les MCP

## Référence complète
Voir : `<KIT_ROOT>\.agent\agents\memory-agent.md` (209 lignes)
