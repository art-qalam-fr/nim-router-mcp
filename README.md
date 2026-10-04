# nim-router-mcp

MCP serveur de routage vers **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`).
Expose les modèles Nemotron aux agents via MCP. Clé via `NVIDIA_API_KEY` (jamais dans le code).

## Install

```bash
uv tool install .   # ou pip install mcp + configurer le serveur
```

Config MCP : `command: python`, `args: ["<path>/nim_mcp_server.py"]`, `env: NVIDIA_API_KEY`.
