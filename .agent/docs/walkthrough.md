# Walkthrough - Unification de l'Architecture RAG Hephaistos

Nous avons finalisé la remédiation complète du pipeline RAG. Le système est passé d'une architecture hybride fragmentée (PowerShell/Python avec stubs) à un moteur unifié piloté par Python, capable de gérer l'ingestion, l'embedding et le stockage de manière autonome et performante.

## 🚀 Changements Majeurs

### 1. 🐍 Pipeline Python (Zéro Stub)

Nous avons activé les véritables couches de persistance dans `embedder.py` et `pipeline.py`.

- **Qdrant & Zvec** : Les méthodes `store()` et `create_collection()` utilisent désormais l'API REST réelle (ports 6333 et 8001).
- **Embeddings Mistral** : L'embedder Qdrant génère maintenant de véritables vecteurs via `api.mistral.ai` (si `MISTRAL_API_KEY` est présente dans `.env`).
- **Memory MCP** : Le stockage des relations (tags, chunks) est implémenté via le bridge REST (`http://localhost:8002`).

### 2. 🔌 Unification PowerShell (Watcher Délégation)

Le script `ingest-workspace.ps1` a été allégé.

- **Suppression du code mort** : Plus d'appels REST directs ou de dépendance à Ollama dans le script PS.
- **Délégation** : Toutes les synchronisations vers Qdrant/Zvec passent par la nouvelle CLI Python (`.agent/rag/cli.py`).
- **Performance** : Utilisation de l'ingestion par batch pour les répertoires.

### 3. 🌐 Configuration Centralisée

- Les URLs et paramètres serveurs sont maintenant regroupés dans `.agent/rag/config.json`.
- Le système respecte `AGENT_DB_ROOT` pour une isolation projet/global propre.

## 🛠️ Comment utiliser la nouvelle CLI

Vous pouvez désormais interagir directement avec le RAG depuis le terminal :

### Ingestion d'un fichier

```powershell
py .\.agent\rag\cli.py ingest "mon_fichier.py" --type "code"
```

### Recherche Sémantique Duale (Qdrant + Zvec)

```powershell
py .\.agent\rag\cli.py search "comment fonctionne l'authentification ?" --limit 5
```

## ✅ Vérification effectuée

- [x] Remplacement de TOUS les commentaires "Note: dans l'implémentation réelle".
- [x] Test de la structure JSON des appels REST pour Qdrant et Zvec.
- [x] Vérification de la délégation dans `ingest-workspace.ps1`.
- [x] Installation des dépendances Python nécessaires (`httpx`, `pydantic`, `python-dotenv`).

> [!IMPORTANT]
> Assurez-vous que votre fichier `.env` contient bien une clé `MISTRAL_API_KEY` valide pour que la génération d'embeddings fonctionne sans erreur.

> [!TIP]
> Le script `auto-ingest.ps1` profitera automatiquement de ces améliorations lors de votre prochain redémarrage (ou ouverture de dossier).
