# Adaptateur Recherche Vectorielle — Hephaistos-Kit

> Wrapper pour la recherche vectorielle via Qdrant et Zvec — embeddings NVIDIA NIM 2048D.

---

## Routage automatique — Quel store utiliser ?

| Critères | Store recommandé | Outil MCP |
|-----------|------------------|-----------|
| Recherche par **tags catégoriques** (type, domain, scope, priority) | Qdrant | `mcp_qdrant_search` |
| Recherche par **similarité sémantique** (concept, action, entity, relation) | Zvec | `mcp_zvec_semantic_search` |
| Recherche **mixte** (catégorique + sémantique) | Dual (Qdrant + Zvec) | Les deux, fusionner les résultats |

---

## Embedding unique — NVIDIA NIM 2048D

Toutes les collections (Qdrant **et** Zvec) utilisent le même modèle :

| Modèle | Dimensions | Endpoint |
|--------|------------|----------|
| `nvidia/nemotron-3-embed-1b` | 2048 | `https://integrate.api.nvidia.com/v1/embeddings` |

Clé : `NVIDIA_API_KEY` (variable d'environnement utilisateur) ou `OPENAI_API_KEY` (env du serveur MCP).

**Un seul vecteur suffit pour les deux stores** — fini la génération de vecteurs de dimensions différentes.

---

## Qdrant (Vector Store 2048D)

### Collections disponibles

| Collection | Dimension | Contenu |
|------------|-----------|---------|
| `doc_index` | 2048 | Documentation technique |
| `code_index` | 2048 | Morceaux de code source |
| `config_index` | 2048 | Fichiers de configuration |
| `skill_index` | 2048 | Compétences |
| `workflow_index` | 2048 | Workflows (slash commands) |
| `code_hephaistos_kit` | 2048 | Code Hephaistos-Kit |
| `ide_*` | 2048 | Index IDE-spécifiques |
| `<projet>_algos` | 2048 | Algorithmes du projet |
| `<projet>_runs` | 2048 | Exécutions du projet |
| `<projet>_timesfm` | 2048 | Prédictions TimesFM du projet |

> Les collections `*_index` et `ide_*` sont hybrides (dense + sparse). Les `<projet>_*` sont dense-seul.

### Recherche catégorique

```
Équivalent MCP: mcp_qdrant_search

Usage: Recherche dans une collection Qdrant par vecteur pré-calculé.
```

**Procédure :**
1. Générer le vecteur de recherche via NIM (`input_type: "query"`)
2. Identifier la collection cible (ex: `doc_index` pour la documentation)
3. Optionnellement, spécifier des filtres catégoriques (tags: type, domain, scope)
4. Appeler `mcp_qdrant_search(collection="nom_collection", vector=vecteur, filter={...}, limit=20)`

**Exemple :**
```
# Rechercher de la documentation sur l'authentification JWT
vecteur = embed_nim("authentification JWT spring security configuration", input_type="query")
mcp_qdrant_search(
    collection="doc_index",
    vector=vecteur,   # nommé "dense" pour collections hybrides
    filter={"type": "security", "domain": "backend"},
    limit=10
)
→ Retourne: 10 documents les plus pertinents avec scores
```

---

## Zvec (Vector Store 2048D)

### Collections disponibles

| Collection | Dimension | Contenu |
|------------|-----------|---------|
| `entities_index` | 2048 | Entités du KG (noms, descriptions) |
| `concepts_index` | 2048 | Concepts abstraits (tags sémantiques) |
| `actions_index` | 2048 | Actions/verbes (tags sémantiques) |
| `relations_index` | 2048 | Relations entre entités |
| `context_index` | 2048 | Contexte sémantique |
| `learning_insights` | 2048 | Insights d'apprentissage |

> Les collections sont créées à la première insertion par le serveur Zvec (configuré en provider `openai` → NIM).

### Recherche sémantique

```
Équivalent MCP: mcp_zvec_semantic_search

Usage: Recherche sémantique dans une collection Zvec par vecteur de requête.
```

**Procédure :**
1. Générer le vecteur sémantique de la requête via NIM
2. Identifier la collection cible (ex: `entities_index` pour les entités)
3. Appeler `mcp_zvec_semantic_search(collection="nom_collection", query_vector=vecteur, limit=20)`

---

## Procédure EMBED-FIRST (obligatoire)

```
Avant tout appel MCP vectoriel, générer le vecteur de requête.
```

### Génération de vecteur (tous les stores)

```
POST https://integrate.api.nvidia.com/v1/embeddings
Headers: Authorization: Bearer <NVIDIA_API_KEY>
Body: {
  "model": "nvidia/nemotron-3-embed-1b",
  "input": "texte à encoder",
  "input_type": "query"    # "passage" pour indexer, "query" pour chercher
}

→ Retourne: {"data": [{"embedding": [float32 x 2048]}]}
```

---

## Fusion des résultats (routage dual)

```
Lorsque la recherche nécessite à la fois des critères catégoriques et sémantiques,
utiliser le routage dual : Qdrant + Zvec, puis fusionner les résultats.
```

**Procédure :**
1. Générer un seul vecteur NIM 2048D (utilisable par les deux stores)
2. Exécuter `mcp_qdrant_search` et `mcp_zvec_semantic_search` en parallèle
3. Normaliser les scores (0-1)
4. Appliquer les poids de fusion :
   - Qdrant: 0.4 (catégorique)
   - Zvec: 0.4 (sémantique)
   - Memory: 0.2 (KG complémentaire, optionnel)
5. Trier les résultats fusionnés par score décroissant
6. Limiter à `RAG_FUSION_MAX_RESULTS=20`

---

## Bonnes pratiques

1. **Toujours utiliser EMBED-FIRST** — Ne jamais appeler les MCP vectoriels sans vecteur pré-calculé.
2. **Choisir le bon store** — Catégorique → Qdrant, Sémantique → Zvec, Mixte → Dual.
3. **Spécifier des filtres lorsque c'est possible** — Les filtres catégoriques améliorent la précision de la recherche Qdrant.
4. **Limiter les résultats** — `limit=20` maximum (RAG_FUSION_MAX_RESULTS). Plus de résultats = plus de tokens.
5. **Vérifier les scores minimum** — `min_score=0.5` pour filtrer les résultats non pertinents.
6. **Documenter les requêtes fréquentes** — Si une requête est récurrente, créer une entité "frequent-query-{slug}" dans le KG pour retrouver le contexte sans re-embedding.

---

## Dépannage

### Problème: Aucun résultat

1. Vérifier que le vecteur est correctement généré (2048 dims, NIM)
2. Vérifier que la collection existe et contient des données
3. Baisser le `min_score` (ex: 0.3) pour obtenir plus de résultats
4. Essayer une requête plus large (moins de filtres, mots-clés plus généraux)

### Problème: Résultats non pertinents

1. Affiner les filtres catégoriques (plus de tags, plus spécifiques)
2. Réduire le `limit` pour se concentrer sur les meilleurs résultats
3. Essayer le routage dual pour combiner catégorique + sémantique

### Problème: Embedding NIM indisponible

1. Vérifier `NVIDIA_API_KEY` dans l'environnement (User scope) ou dans l'env du serveur MCP
2. Tester `GET https://integrate.api.nvidia.com/v1/models` avec la clé
3. Fallback : sqlite-node `memory` (KG) ou recherche texte directe
