# nim-router-mcp

MCP serveur de routage vers **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`).
Expose les modèles Nemotron aux agents via MCP. Clé via `NVIDIA_API_KEY` (jamais dans le code).
**Stdlib Python pure** — aucune dépendance à installer (`urllib`, `json`, `os`).

## Outils MCP

| Outil | Rôle |
|-------|------|
| `nim_domains` | Domaines routés + modèle primaire de chaque domaine |
| `nim_models` | `model_id`s servis live (`GET /models`) |
| `nim_chat(domain, prompt)` | Chat routé par domaine (+ fallbacks auto) |
| `nim_chat_model(model, ...)` | Appel direct par `model_id` |
| `nim_embed(texts)` | Embeddings (domaine `rag_embedding`, nemotron-3-embed-1b) |

## Install

Python ≥ 3.10, rien d'autre. Lancer en stdio :

```bash
python nim_mcp_server.py
```

## Config MCP

```json
"nim-router": {
  "command": "python",
  "args": ["<chemin-vers>/nim-router-mcp/nim_mcp_server.py"],
  "env": { "NVIDIA_API_KEY": "${env:NVIDIA_API_KEY}" }
}
```

## Variables d'environnement

| Variable | Rôle | Défaut |
|----------|------|--------|
| `NVIDIA_API_KEY` | Clé NIM (requis) | — |
| `NVIDIA_BASE_URL` | Endpoint NIM | `https://integrate.api.nvidia.com/v1` |

Licence MIT.
