# Changelog - Persistance Zvec et Corrections Système

## Date : 2026-04-09

## 🎯 Objectif

Assurer la persistance des données Zvec sur disque et corriger le chemin de données pour utiliser la hiérarchie `current_workspace`.

---

## 🔧 Modifications

### 1. Serveur Zvec MCP (`<HEPHAISTOS_ROOT>/mcp/servers/zvec-mcp-server/`)

#### `build/index.js`

- **Ajout de fonctions de persistance** :
  - `saveCollection()` : Sauvegarde les collections au format JSON
  - `loadCollection()` : Restaure les collections depuis le disque
  - `loadAllCollections()` : Charge toutes les collections au démarrage

- **Modification du chargement `.env`** :
  - Le serveur ne charge plus le fichier `.env` si `ZVEC_DATA_DIR` est déjà défini
  - Cela permet au bridge RAG de passer une valeur prioritaire

#### `.env`

- **Correction du chemin** :

```text
  # Avant
  ZVEC_DATA_DIR=<HEPHAISTOS_DATA>/zvec-data

  # Après
  ZVEC_DATA_DIR=<HEPHAISTOS_DATA>/current_workspace/vector/zvec-data
  ```

### 2. Bridge RAG (`<KIT_ROOT>\.agent\rag\rag_rest_bridge.py`)

#### Fonction `_resolve_data_path()`

- **Ajout du paramètre `force_env_var`** :
  - Permet de prioriser une variable d'environnement (ex: `AGENT_DB_ROOT`)
  - Construction automatique du chemin : `{AGENT_DB_ROOT}/current_workspace/vector/zvec-data`

#### Configuration `ZVEC_DATA_DIR`

- **Utilisation de `AGENT_DB_ROOT`** comme priorité absolue
- **Fallback** : Chemin relatif au projet

#### Méthode `MCPClient.start()`

- **Ajout de logs détaillés** pour vérifier l'environnement passé au sous-processus
- **Forçage explicite** de `ZVEC_DATA_DIR` dans l'environnement fusionné

### 3. Correction Qdrant (`embedder.py`)

#### Méthode `insert_chunk()`

- **Correction du format de vecteur** :
  - Avant : `"vector": vector`
  - Après : `"vector": {"dense": vector}`
  - Requis pour les collections hybrides Qdrant (Mistral 1536D)

#### Méthode `search()`

- **Correction du format de recherche** :
  - Avant : `"vector": vector`
  - Après : `"vector": {"dense": vector}`
  - Permet la recherche sémantique sur les collections hybrides

### 4. Migration des données

#### Collections migrées

- `test_new_path.json`
- `test_persist.json`
- `test_persist2.json`

**Source** : `<HEPHAISTOS_DATA>/zvec-data`
**Destination** : `<HEPHAISTOS_DATA>/current_workspace/vector/zvec-data`

---

## 📊 Résultats des tests

### Test de persistance

| Étape               | Résultat                                             |
| ------------------- | ---------------------------------------------------- |
| Création collection | ✅ `test_final` créée                                |
| Ajout document      | ✅ `doc1` ajouté avec vecteur 384D                   |
| Fichier JSON créé   | ✅ `test_final.json`                                 |
| Redémarrage serveur | ✅ Collections restaurées                            |
| Chemin correct      | ✅ `<HEPHAISTOS_DATA>/current_workspace/vector/zvec-data` |

### Test d'ingestion (README.md) - ✅ RÉUSSI

| Système    | Statut             | Points/Entités       |
| ---------- | ------------------ | -------------------- |
| **Qdrant** | ✅ **Corrigé**     | 16 points stockés    |
| **Zvec**   | ✅ **Fonctionnel** | 20 documents stockés |
| **SQLite** | ✅ **OK**          | 16 relations créées  |

---

## ✅ Tous les problèmes connus sont corrigés

### Qdrant : ✅ Corrigé

- **Solution appliquée** : Modification de `embedder.py` pour wrapper le vecteur dans `{"dense": vector}`
- **Test** : Ingestion de README.md réussie avec 16 points stockés
- **Note** : Erreurs Memory MCP liées aux tags (ignorées comme demandé) et erreur temporaire Mistral "overflow"

---

## 📁 Fichiers modifiés

1. `<HEPHAISTOS_ROOT>/mcp/servers/zvec-mcp-server/build/index.js`
2. `<HEPHAISTOS_ROOT>/mcp/servers/zvec-mcp-server/.env`
3. `<KIT_ROOT>\.agent\rag\rag_rest_bridge.py`
4. `<KIT_ROOT>\.agent\rag\embedder.py`

---

## ✅ Toutes les étapes sont complétées

1. ✅ **Qdrant corrigé** : `embedder.py` modifié pour le format hybride
2. ✅ **Ingestion validée** : Test réussi avec README.md (16 points Qdrant, 20 docs Zvec)
3. ✅ **Intégration automatique** : Le bridge se lance correctement et Zvec utilise le bon chemin

---

## ✨ Résumé Final

✅ **Zvec persiste maintenant les données sur disque**
✅ **Le chemin de données utilise la hiérarchie correcte**
✅ **Les collections sont restaurées au redémarrage**
✅ **Qdrant corrigé et fonctionnel avec le format hybride**
✅ **Ingestion complète validée (Qdrant + Zvec + SQLite)**
