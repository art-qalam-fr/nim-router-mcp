# Adaptateur Mémoire — Hephaistos-Kit Unified Memory System

> Wrapper pour les opérations fréquentes sur le système mémoire unifié.

---

## Mémoire — Opérations courantes

### 1. Rechercher le contexte existant (AVANT toute tâche)

```
Équivalent MCP: mcp_Memory_search_nodes

Usage: Vérifier si le contexte existe déjà avant de commencer une tâche.
```

**Procédure :**
1. Identifier les mots-clés de la tâche
2. Appeler `mcp_Memory_search_nodes(query="mot-clé1 mot-clé2", tags=["architecture", "security", ...])`
3. Analyser les résultats (entités, observations, relations)
4. Si le contexte existe → réutiliser sans re-explorer
5. Si le contexte n'existe pas → créer le contexte nécessaire

**Exemple :**
```
mcp_Memory_search_nodes(query="authentification JWT", tags=["security", "architecture"])
→ Retourne: liste d'entités + observations + relations sur l'authentification JWT
```

---

### 2. Enregistrer une décision (APRÈS toute décision importante)

```
Équivalent MCP: mcp_Memory_add_observations

Usage: Tracer une décision dans le KG avec tags.
```

**Procédure :**
1. Synthétiser la décision en une phrase claire
2. Identifier les tags pertinents (`architecture`, `security`, `mcp-tool`, `pattern`, `decision`)
3. Appeler `mcp_Memory_add_observations(entity=entity_name, content=decision_text, tags=[...])`
4. Si la décision est structurelle → créer une entité "decision-{slug}" avec relations

**Exemple :**
```
mcp_Memory_add_observations(
    entity="decision-auth-v2",
    content="JWT avec refresh tokens, expiration 15min/7jours, stockage localStorage + httpOnly cookie",
    tags=["architecture", "security", "decision"]
)
```

---

### 3. Créer une entité structurée

```
Équivalents MCP: mcp_Memory_create_entities + mcp_Memory_create_relations

Usage: Structurer une nouvelle entité dans le KG avec ses relations.
```

**Procédure :**
1. Définir le nom unique de l'entité
2. Identifier le type (project, decision, pattern, preference, user, workspace, etc.)
3. Définir les attributs (description, date, priority, stack, etc.)
4. Définir les relations avec d'autres entités existantes
5. Appeler `mcp_Memory_create_entities(entities=[{...}]`) 
6. Appeler `mcp_Memory_create_relations(relations=[...])`

**Exemple :**
```
mcp_Memory_create_entities(entities=[{
    "name": "project-marotte",
    "type": "project",
    "description": "Plateforme de prédiction Loto/EuroMillions",
    "date": "2026-09-17",
    "priority": "high",
    "stack": "python, fastapi, react"
}])

mcp_Memory_create_relations(relations=[{
    "from": "project-marotte",
    "to": "user-local",
    "type": "owned_by",
    "weight": 1.0
}, {
    "from": "project-marotte",
    "to": "stack-python-fastapi",
    "type": "uses",
    "weight": 0.9
}])
```

---

### 4. Lire le graphe complet (pour analyse)

```
Équivalent MCP: mcp_Memory_read_graph

Usage: Analyse globale de la mémoire, consolidation, audit.
```

**Procédure :**
1. Appeler `mcp_Memory_read_graph()`
2. Analyser les entités, observations, et relations
3. Identifier les patterns, les doublons, les lacunes
4. Préparer les actions de consolidation ou de correction

**Note :** Cette opération peut être lourde en tokens. Préférer des recherches ciblées pour les sessions normales.

---

### 5. Ouvrir un nœud spécifique

```
Équivalent MCP: mcp_Memory_open_nodes

Usage: Récupérer les détails d'une entité connue par son nom.
```

**Procédure :**
1. Identifier le nom exact de l'entité (ex: "project-marotte", "decision-auth-v2")
2. Appeler `mcp_Memory_open_nodes(names=["nom_de_l_entité"])`
3. Lire les attributs, observations, et relations de l'entité

**Exemple :**
```
mcp_Memory_open_nodes(names=["project-marotte"])
→ Retourne: entité complète avec description, date, priority, stack, et relations
```

---

### 6. Supprimer une entité/observation/relation

```
Équivalents MCP: mcp_Memory_delete_entities / _delete_observations / _delete_relations

Usage: Nettoyage de la mémoire (entités obsolètes, observations incorrectes, relations inutiles).
```

**Procédure :**
1. Identifier l'entité/observation/relation à supprimer
2. Vérifier qu'elle n'est pas référencée par d'autres entités (sinon, supprimer les relations d'abord)
3. Appeler la fonction de suppression appropriée

**Exemple :**
```
mcp_Memory_delete_entities(names=["old-project-unused"])
→ Supprime l'entité et ses relations (si pas de dépendances)

mcp_Memory_delete_observations(entity="project-marotte", ids=[123, 456])
→ Supprime les observations spécifiques

mcp_Memory_delete_relations(ids=[789])
→ Supprime les relations spécifiques
```

---

## Procédures par contexte

### Contexte: Début de session

```
1. mcp_Memory_search_nodes(query="preferences", tags=["preference"])
   → Vérifier les préférences utilisateur connues

2. mcp_Memory_search_nodes(query="workspace", tags=["project"])
   → Identifier les workspaces connus

3. mcp_Memory_search_nodes(query="frequent queries")
   → Identifier les requêtes récurrentes
```

### Contexte: Avant de commencer une tâche

```
1. Identifier les mots-clés de la tâche (ex: "authentification", "API", "base de données")
2. mcp_Memory_search_nodes(query="mot-clé1 mot-clé2", tags=["architecture", "pattern"])
3. Si résultats suffisants → réutiliser le contexte existant
4. Si pas de résultats → créer le contexte nécessaire avant de commencer
```

### Contexte: Pendant une tâche (intermédiaires)

```
1. Pour chaque étape importante:
   → mcp_Memory_add_observations(entity=task_entity, content=etape_summary, tags=["architecture"])
2. Pour les décisions intermédiaires:
   → Créer une entité "decision-étape-slug" avec relations vers la tâche parente
```

### Contexte: Après une décision importante

```
1. Synthétiser la décision en une phrase claire
2. Identifier les tags (architecture, security, decision, etc.)
3. mcp_Memory_add_observations(entity=task_entity, content=decision_text, tags=[...])
4. Si décision structurelle:
   → Créer une entité "decision-{slug}" avec relations vers:
     - La tâche parente
     - Les entités impactées
     - Les alternatives envisagées (si documentées)
```

### Contexte: Fin de session

```
1. Vérifier la cohérence local/global (si junction utilisée)
2. Documenter les leçons apprises:
   → mcp_Memory_add_observations(entity="lessons", content=lesson_text, tags=["lesson", "project"])
3. Mettre à jour les requêtes fréquentes si nécessaire:
   → mcp_Memory_add_observations(entity="frequent-queries", content=update_text, tags=["preference"])
4. Consolider les données vers le stockage global (si nécessaire)
```

---

## Tags recommandés

| Tag | Quand l'utiliser | Exemple |
|-----|------------------|---------|
| `architecture` | Décisions structurelles, choix d'implémentation | "Choix de FastAPI pour le backend" |
| `security` | Questions de sécurité, auth, secrets | "JWT avec refresh tokens" |
| `mcp-tool` | Utilisation des MCP (Memory, Qdrant, Zvec, etc.) | "Utilisation de Qdrant pour la recherche catégorique" |
| `pattern` | Patterns d'implémentation récurrents | "Pattern Repository pour l'accès aux données" |
| `preference` | Préférences utilisateur découvertes | "Préfère des fonctions pures plutôt que des méthodes" |
| `lesson` | Leçons apprises, corrections de bugs | "Éviter les requêtes N+1 sur les gros jeux de données" |
| `decision` | Décisions importantes (ADR) | "ADR-001: Utiliser SQLite pour le stockage local" |
| `project` | Métadonnées de projet | "Projet Marotte — prédiction Loto/EuroMillions" |
| `workspace` | Métadonnées de workspace | "Workspace <PROJECTS_ROOT>/marotte" |

**Règle :** Tout tag personnalisé doit être documenté dans l'observation correspondante.

---

## Bonnes pratiques

1. **Toujours utiliser les tags** — Sans tags, les données ne sont pas recherchables efficacement.
2. **Être précis dans les descriptions** — Une description vague ("modifié") ne sera pas utile pour la recherche future.
3. **Lier les entités entre elles** — Une entité isolée est difficile à retrouver. Créer des relations vers les entités connexes.
4. **Mettre à jour les entités existantes** — Préférer `mcp_Memory_add_observations` sur une entité existante plutôt que de créer une nouvelle entité.
5. **Nettoyer les données obsolètes** — Supprimer régulièrement les entités/observations/relations obsolètes pour maintenir la qualité du KG.
6. **Utiliser des noms cohérents** — Adopter une convention de nommage (ex: "project-{slug}", "decision-{slug}", "pattern-{slug}") pour faciliter les recherches.
